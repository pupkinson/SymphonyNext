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

GITHUB_ADAPTER = '''import mmap
import select
import threading


def github_diagnostic_emit(record):
    print(json.dumps(record, sort_keys=True), flush=True)


def github_transport_child(api, method, path, body, timeout, deadline, shared):
    # This child performs exactly one already-authorized HTTP attempt. It never
    # executes a launcher, writes evidence, logs provider data, or retries.
    # The kernel also ends this child at the deadline if its parent dies or is
    # paused. This changes only the child, never the owner's signal handlers.
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGALRM})
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return
    signal.setitimer(signal.ITIMER_REAL, remaining)
    conn = None
    try:
        conn = http.client.HTTPSConnection('api.github.com', timeout=timeout,
                                          context=ssl.create_default_context())
        data = None if body is None else json.dumps(body).encode()
        conn.request(method, path, body=data, headers={
            'Authorization': 'Bearer ' + api.token,
            'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
            'User-Agent': 'SymphonyNext-BOOT-P01-owner-run'})
        response = conn.getresponse()
        result = ['response', response.status,
                  github_safe_headers(dict(response.getheaders())),
                  response.read(2_000_001).hex()]
    except BaseException as exc:
        result = ['timeout' if isinstance(exc, TimeoutError) else 'network']
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    payload = json.dumps(result).encode()
    if len(payload) > len(shared) - 4:
        payload = b'["network"]'
    shared[4:4 + len(payload)] = payload
    shared[:4] = len(payload).to_bytes(4, 'big')


def github_reap_transport(pid, deadline, interrupt_signals=frozenset()):
    while True:
        if signal.sigpending() & interrupt_signals:
            raise Stop('operator_interrupted')
        waited, status = os.waitpid(pid, os.WNOHANG)
        if waited:
            return status
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(0.005, remaining))


def github_http_transport(api, method, path, body, timeout, *, deadline):
    # A socket timeout cannot bound DNS, TLS, headers and a trickling body as a
    # whole. Supervise one disposable Unix child from the single-threaded owner.
    # Anonymous bounded memory avoids unbounded pipe recv and temporary files.
    if getattr(api, 'github_transport_cleanup_failed', False):
        raise GithubDiagnosticError('transport_cleanup_unverified')
    if (threading.active_count() != 1 or not hasattr(os, 'fork') or
            not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal') or
            signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL):
        raise GithubDiagnosticError('transport_context_unsupported')
    if time.monotonic() >= deadline:
        raise TimeoutError()
    # Read the old mask without changing it, before acquiring any resource.
    # Enter the restoration try before blocking: even an interruption during
    # mask installation cannot strand the caller with a modified mask.
    old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    blocked = signal.valid_signals() - {signal.SIGKILL, signal.SIGSTOP}
    interrupt_signals = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP} - old_mask
    try:
        signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
        # Refuse an unsupported kernel before a child could perform HTTP.
        try:
            probe_fd = os.pidfd_open(os.getpid())
        except OSError:
            raise GithubDiagnosticError('transport_context_unsupported') from None
        os.close(probe_fd)
        with mmap.mmap(-1, 4_100_004) as shared:
            read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
            pid = None
            pidfd = None
            reaped = False
            try:
                if signal.sigpending() & interrupt_signals:
                    raise Stop('operator_interrupted')
                pid = os.fork()
                if pid == 0:
                    try:
                        os.close(read_fd)
                        github_transport_child(api, method, path, body, timeout, deadline, shared)
                    finally:
                        # No inherited stream flush, atexit handlers, or parent flow.
                        os._exit(0)
                os.close(write_fd)
                write_fd = None
                pidfd = os.pidfd_open(pid)
                # Keep asynchronous handlers deferred throughout ownership,
                # including the transition into finally. Poll pending owner
                # stops so blocking the handler does not delay operator stop
                # until the HTTP deadline. Do not consume queued signals.
                while True:
                    if signal.sigpending() & interrupt_signals:
                        raise Stop('operator_interrupted')
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError()
                    ready = select.select([read_fd], [], [], min(0.05, remaining))
                    if ready and ready[0]:
                        break
                status = github_reap_transport(pid, deadline, interrupt_signals)
                if status is None:
                    raise TimeoutError()
                reaped = True
                if time.monotonic() >= deadline:
                    raise TimeoutError()
                size = int.from_bytes(shared[:4], 'big')
                if status != 0 or not 0 < size <= len(shared) - 4:
                    raise OSError()
                result = json.loads(shared[4:4 + size])
                if result[0] == 'timeout':
                    raise TimeoutError()
                if result[0] != 'response':
                    raise OSError()
                return result[1], result[2], bytes.fromhex(result[3])
            finally:
                # Signals are already blocked; no unprotected cleanup entry.
                try:
                    if pid is not None and not reaped:
                        try:
                            if pidfd is not None:
                                # The handle still identifies our child after waitpid
                                # released its numeric PID. A recycled PID is unreachable.
                                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                            else:
                                # Acquisition failed before any waitpid: this child
                                # is still ours and its numeric PID cannot be recycled.
                                os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        except OSError:
                            api.github_transport_cleanup_failed = True
                            raise GithubDiagnosticError('transport_cleanup_unverified') from None
                        try:
                            status = github_reap_transport(pid, time.monotonic() + 1)
                        except ChildProcessError:
                            # An interruption may follow successful waitpid before
                            # reaped=True. With our stable handle, ECHILD means it was
                            # already reaped; preserve the original owner interruption.
                            if pidfd is None:
                                api.github_transport_cleanup_failed = True
                                raise GithubDiagnosticError('transport_cleanup_unverified') from None
                            status = 0
                        if status is None:
                            api.github_transport_cleanup_failed = True
                            raise GithubDiagnosticError('transport_cleanup_unverified')
                finally:
                    try:
                        if pidfd is not None:
                            os.close(pidfd)
                    finally:
                        try:
                            os.close(read_fd)
                        finally:
                            if write_fd is not None:
                                os.close(write_fd)
    finally:
        # Child termination/reaping and descriptor/mmap cleanup precede delivery
        # to the original handlers. Previously blocked signals remain blocked.
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)


def diagnostic_api_request(self, method, path, body=None):
    validate_api(method, path)
    # Only fixed routes / exact immutable SHAs are safe to include in evidence.
    endpoint = path.split('?', 1)[0]
    exact = {API, API+'/issues/2', API+'/git/ref/heads/main',
             API+'/git/ref/heads/'+BRANCH, API+'/labels/'+LABEL,
             API+'/labels', API+'/issues/2/labels', API+'/issues/2/labels/'+LABEL,
             API+'/issues', API+'/pulls'}
    if endpoint not in exact and not re.fullmatch(re.escape(API+'/compare/'+MAIN+'...') + '[0-9a-f]{40}', endpoint):
        raise Stop('api_scope_refused')
    # One deadline across this request's attempts. Later cleanup/reconciliation
    # reads need their own budget, even after the worker's long-running session.
    deadline = time.monotonic() + 120
    expected = method == 'GET' and endpoint in {API+'/git/ref/heads/'+BRANCH, API+'/labels/'+LABEL}
    delivery_state = self.__dict__.setdefault('github_diagnostics', {'delivery_failed': False})
    try:
        return github_request(method, endpoint,
            lambda timeout: github_http_transport(self, method, path, body, timeout, deadline=deadline),
            emit=github_diagnostic_emit, deadline=deadline, delivery_state=delivery_state,
            clock=time.monotonic, sleep=time.sleep, wall=time.time, expected_404=expected)
    except GithubDiagnosticError as exc:
        # A distinct terminal code prevents the legacy observer from retrying
        # an already exhausted three-attempt read. Unknown writes require readback.
        raise Stop('github_' + exc.reason) from None


# Explicit binding preserves the archival class definition and its get contract.
Api.request = diagnostic_api_request
'''

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
    diagnostics = Path(__file__).with_name('github_diagnostics.py').read_text(encoding='utf-8')
    module += '\n\n' + diagnostics + '\n\n' + GITHUB_ADAPTER
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
        "        current=reconcile_start_ownership(start_ticket,monitor)\n"+
        "        record_reconciled_start(current,monitor)\n"+
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
        "        except (ObserverError,OSError):\n"+
        "            monitor.state['persistence_error']=True\n"+
        "            cleanup.append('observer_checkpoint_failed')\n"+
        "        reason=monitor.state['termination_reason'] or 'observer_error'\n"+
        "        obs=monitor.snapshot()\n"+anchor)
    candidate = replace_once(candidate,
        "                run(['/usr/bin/systemctl','stop',UNIT],seconds=45)\n                st=unit_state()",
        "                current=reconcile_start_ownership(start_ticket,monitor)\n"+
        "                # Diagnostic storage cannot veto the independently verified stop.\n"+
        "                try: record_reconciled_start(current,monitor)\n"+
        "                except (ObserverError,OSError):\n"+
        "                    monitor.state['persistence_error']=True\n"+
        "                    if 'observer_checkpoint_failed' not in cleanup:\n"+
        "                        cleanup.append('observer_checkpoint_failed')\n"+
        "                if current.get('ActiveState') not in ('inactive','failed'):\n"+
        "                    expected=current.get('InvocationID')\n"+
        "                    if not expected or current.get('InvocationID')!=expected:\n"+
        "                        raise Stop('service_owner_changed_no_stop')\n"+
        "                    if unit_state().get('InvocationID')!=expected:\n"+
        "                        raise Stop('service_owner_changed_no_stop')\n"+
        "                    run(['/usr/bin/systemctl','stop',UNIT],seconds=50)\n"+
        "                st=unit_state()")
    candidate = replace_once(candidate, "reason=='worker_finished'", "reason=='worker_finished_awaiting_acceptance'")
    candidate = replace_once(candidate, "        atomic_json(RECORD/'result.json',summary)\n",
        "        try: atomic_json(RECORD/'result.json',summary)\n"+
        "        except OSError:\n"+
        "            cleanup.append('result_persistence_failed')\n"+
        "            summary['status']='STOP'\n"+
        "            monitor.state['persistence_error']=True\n"+
        "            summary['runtime_observations']=monitor.snapshot()\n"+
        "        finally: monitor.close()\n")
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
