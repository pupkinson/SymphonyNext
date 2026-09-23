#!/usr/bin/env python3
"""Build-only exact-source patch for issue #7. NEVER installs or runs the output.

Use an archival copy of the supplied v1 launcher as --source. Existing server
v1/v2 launchers, outcomes and one-shot guards remain untouched. The candidate
keeps their consumed operation paths, so it is NOT a BOOT-P01 retry command.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path

LEGACY_SHA256 = 'b5e58bb18b46330792b4922d6349bf25dd3f8b6c008efcb1e769b2484b12d518'

ADAPTER = '''def observer_worker_alive():
    # UID995 is dedicated to this one bootstrap, not to DF Assistant.
    p = subprocess.run(['/usr/bin/ps', '-u', '995', '-o', 'comm='],
                       env=ENV, capture_output=True, text=True, timeout=5)
    if p.returncode not in (0, 1): return None
    infrastructure = {'beam.smp', 'erl_child_setup', 'inet_gethost'}
    return any(name.strip() not in infrastructure for name in p.stdout.splitlines() if name.strip())


def observer_runtime_read():
    conn = http.client.HTTPConnection('127.0.0.1', 4327, timeout=3)
    try:
        conn.request('GET', '/api/v1/state')
        response = conn.getresponse()
        raw = response.read(524289)
        if response.status != 200 or len(raw) > 524288: return None
        return json.loads(raw)
    except (OSError, http.client.HTTPException, ValueError):
        return None
    finally:
        conn.close()


def observer(monitor, api):
    failures = 0
    while True:
        try:
            st = unit_state()
            if st.get('InvocationID') not in ('', monitor.state['invocation_id']):
                return monitor.finish('service_identity_changed'), monitor.snapshot()
            runtime = observer_runtime_read()
            alive = observer_worker_alive()
        except (Stop, OSError, ValueError, subprocess.TimeoutExpired) as exc:
            if isinstance(exc, Stop) and str(exc) == 'operator_interrupted': raise
            outcome = monitor._unavailable()
        else:
            # Persistence failures are NOT retried as transient network failures.
            outcome = monitor.sample(st, runtime,
                agent_started=(RUN/'agent-started').is_file(),
                hook_finished=(RUN/'worker-finished').is_file(), worker_alive=alive)
        if outcome == 'observation_unavailable':
            failures += 1
            if failures >= 3:
                return monitor.finish('observation_lost_after_three_reads'), monitor.snapshot()
            delay = (10, 60)[failures-1]
        else:
            failures = 0
            delay = 3
        if outcome == 'idle_requires_reconciliation':
            # A bounded readback; never repeat a mutation or start another worker.
            for attempt, delay in enumerate((0, 10, 60)):
                if delay: time.sleep(min(delay, max(0, monitor.wall_limit-(time.monotonic()-monitor.begun))))
                if time.monotonic()-monitor.begun >= monitor.wall_limit:
                    return monitor.finish('wall_deadline_reached'), monitor.snapshot()
                try:
                    monitor.reconcile(result_readback(api))
                    return monitor.state['termination_reason'], monitor.snapshot()
                except Stop as exc:
                    if str(exc) == 'operator_interrupted': raise
                    if str(exc) != 'github_transport_or_json':
                        return monitor.finish('artifact_readback_rejected'), monitor.snapshot()
                except (OSError, ValueError):
                    return monitor.finish('artifact_readback_unavailable'), monitor.snapshot()
                if attempt == 2:
                    return monitor.finish('artifact_readback_unavailable'), monitor.snapshot()
        elif outcome and outcome != 'observation_unavailable':
            return outcome, monitor.snapshot()
        # Persisted BEFORE sleeping. Lost stdout or SIGINT cannot erase history.
        remaining = max(0, monitor.wall_limit-(time.monotonic()-monitor.begun))
        time.sleep(min(delay, remaining))
'''

READBACK_ADDITION = '''    # Exact immutable commit metadata, not just PR text or a filename count.
    commits = comp.get('commits', [])
    if (base == MAIN and isinstance(commits, list) and len(commits) == 1
            and isinstance(commits[0], dict) and commits[0].get('sha') == head):
        obj = commits[0]
        parents = obj.get('parents', [])
        tree = obj.get('commit', {}).get('tree', {}).get('sha')
        if (isinstance(parents, list) and len(parents) == 1
                and parents[0].get('sha') == MAIN
                and isinstance(tree, str) and re.fullmatch('[0-9a-f]{40}', tree)
                and len(files) == 1 and files[0].get('status') == 'added'):
            result.update(parent=MAIN, tree=tree, source_verified=True)
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('patch_anchor_count_mismatch')
    return text.replace(old, new, 1)


def build_candidate(source):
    if hashlib.sha256(source).hexdigest() != LEGACY_SHA256:
        raise ValueError('legacy_sha256_mismatch')
    original = source.decode('utf-8')
    module = Path(__file__).with_name('pilot_observer.py').read_text(encoding='utf-8')
    # The observer is inlined: -I host entry points do not depend on sys.path/imports.
    ownership = Path(__file__).with_name('start_ownership.py').read_text(encoding='utf-8')
    ast.parse(ownership, feature_version=(3, 10))
    module += '\n\n' + ownership
    ast.parse(module, feature_version=(3, 10))
    tree = ast.parse(original)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'observer')
    lines = original.splitlines(keepends=True)
    candidate = ''.join(lines[:node.lineno-1]) + module + '\n\n' + ADAPTER + '\n' + ''.join(lines[node.end_lineno:])
    candidate = replace_once(candidate, '    return result\n\n\ndef launch():',
                             READBACK_ADDITION + '    return result\n\n\ndef launch():')
    anchor = "    summary=dict(schema='symphony-next-boot-p01-execution/v1',repository=REPO,source_head=MAIN,model_profile=report['model_profile'],old_df_touched=False,merge='NOT_RUN',deploy='NOT_RUN')\n"
    candidate = replace_once(candidate, anchor, anchor +
        "    monitor=PilotObserver(RECORD/'observer-state.json',operation=RECORD.name,source=MAIN,\n"+
        "        emit=lambda value: print(json.dumps(value,ensure_ascii=False),flush=True))\n")
    candidate = replace_once(candidate, "        start_intent=True\n        run(['/usr/bin/systemctl','start',UNIT],seconds=40)\n        reason,obs=observer()",
        "        start_intent=True\n        monitor.start_requested()\n"+
        "        run(['/usr/bin/systemctl','start',UNIT],seconds=40)\n"+
        "        reconcile_start_ownership(start_ticket,monitor)\n"+
        "        reason,obs=observer(monitor,api)")
    candidate = replace_once(candidate,
        "    except (Stop,OSError,ValueError) as exc:\n        error=str(exc) if isinstance(exc,Stop) else type(exc).__name__\n    finally:",
        "    except (Stop,ObserverError,OSError,ValueError,KeyError,TypeError) as exc:\n"+
        "        error=str(exc) if isinstance(exc,(Stop,ObserverError)) else type(exc).__name__\n    finally:")
    anchor = '        # Stop only the service owned by this operation. Never restart it.\n'
    candidate = replace_once(candidate, anchor,
        "        # State belongs to the caller, not a callee that may never return.\n"+
        "        try:\n"+
        "            ended=error or monitor.state['termination_reason'] or ('start_outcome_unknown' if start_intent else 'not_started')\n"+
        "            monitor.finish(ended)\n"+
        "        except (ObserverError,OSError): cleanup.append('observer_checkpoint_failed')\n"+
        "        reason=monitor.state['termination_reason'] or 'observer_error'\n"+
        "        obs=monitor.snapshot()\n"+anchor)
    candidate = replace_once(candidate,
        "                run(['/usr/bin/systemctl','stop',UNIT],seconds=45)\n                st=unit_state()",
        "                current=reconcile_start_ownership(start_ticket,monitor)\n"+
        "                if current.get('ActiveState') not in ('inactive','failed'):\n"+
        "                    expected=monitor.state.get('invocation_id')\n"+
        "                    if not expected or current.get('InvocationID')!=expected:\n"+
        "                        raise Stop('service_owner_changed_no_stop')\n"+
        "                    if unit_state().get('InvocationID')!=expected:\n"+
        "                        raise Stop('service_owner_changed_no_stop')\n"+
        "                    run(['/usr/bin/systemctl','stop',UNIT],seconds=50)\n"+
        "                st=unit_state()")
    candidate = replace_once(candidate, "reason=='worker_finished'", "reason=='worker_finished_awaiting_acceptance'")
    candidate = replace_once(candidate, "        atomic_json(RECORD/'result.json',summary)\n",
        "        atomic_json(RECORD/'result.json',summary)\n        monitor.close()\n")
    candidate = replace_once(candidate,
        'except (Stop,OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:',
        'except (Stop,ObserverError,OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:')
    # Bind every possible start (including a lost acknowledgement) before ExecStart.
    candidate = replace_once(candidate, "'ExecCondition=/usr/bin/test -f '+str(CONF/'BOOT_P01_WINDOW')+'\\n')",
        "'ExecCondition=/usr/bin/test -f '+str(CONF/'BOOT_P01_WINDOW')+'\\n'\n"
        "        'RuntimeMaxSec=1800\\nTimeoutStartSec=45\\nTimeoutStopSec=45\\nRestart=no\\n'\n"
        "        'KillMode=control-group\\nSendSIGKILL=yes\\n'\n"
        "        'ExecStartPre=/usr/bin/python3 -I -B '+str(DRIVER)+' start-witness\\n')")
    candidate = replace_once(candidate, "window=b'BOOT-P01-v1\\n'",
        "window=(json.dumps(dict(unit=UNIT,operation=RECORD.name,nonce=os.urandom(16).hex()))+'\\n').encode()")
    candidate = replace_once(candidate, "        admission_intent=True;admit(api)",
        "        verify_manager_deadline(start_guard_state())\n"
        "        monitor.state['manager_deadline_verified']=True;monitor._save()\n"
        "        admission_intent=True;admit(api)")
    candidate = replace_once(candidate, "        atomic_json(RECORD/'start-intent.json',dict(time=utc(),unit=UNIT))",
        "        start_ticket=make_start_ticket(window)\n"
        "        atomic_json(RECORD/'start-intent.json',start_ticket)")
    candidate = replace_once(candidate, "        candidate=(not error and not cleanup",
        "        obs=monitor.snapshot()\n        candidate=(not error and not cleanup")
    candidate = replace_once(candidate, "        elif mode in ('before','agent','after'): guard(mode)",
        "        elif mode=='start-witness': record_start_witness()\n"
        "        elif mode in ('before','agent','after'): guard(mode)")
    ast.parse(candidate, feature_version=(3, 10))
    return candidate.encode('utf-8')


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='new candidate file, never an installation target')
    args = parser.parse_args(argv)
    target = args.out.absolute()
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError('output_symlink')
    target = target.resolve(strict=False)
    if any(str(target).startswith(p) for p in ('/opt/', '/etc/', '/var/lib/', '/run/', '/srv/')):
        raise ValueError('host_install_target_refused')
    if args.source.is_symlink() or args.source.stat().st_size > 100000:
        raise ValueError('source_invalid')
    source = args.source.read_bytes()
    candidate = build_candidate(source)
    write_new(target, candidate)
    print(json.dumps(dict(status='CANDIDATE_BUILT_NOT_INSTALLED',
        source_sha256=LEGACY_SHA256, candidate_sha256=hashlib.sha256(candidate).hexdigest(),
        launch='NOT_RUN', installation='NOT_RUN')))


if __name__ == '__main__':
    main()
