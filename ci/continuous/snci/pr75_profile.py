"""Closed owner profile preparation and paused installation; never starts CI.

prepare and install are distinct single-use native leaves. Incomplete or unknown
transitions retain their evidence and require investigation, never replay.
"""
import argparse
import copy
from contextlib import contextmanager, closing
import fcntl
import hashlib
import os
from pathlib import Path
import re
import signal
import sqlite3
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import API, RULESET, Hold, blob_hash, canonical, decode, require, sha256, trusted, write_new
from snci.source import PR75_REQUEST, Source, select_profile, validate_rules, validate_target
from snci.github import GitHub
from snci import daily_limit, refresh, recover_retention, runner
from snci.repair_review import native_probe, verify_stage
from snci.rebuild_missing import seed_identity

BASE = '2f40275cd7f2f6a2f2147c195acfab79e434cfa6'
BASE_TREE = '30b0f90ff0b78269d68b55429ac4f6d3959ea8dd'
POLICY_SHA = '8438cf3f0b6854b2659b9375757fb58483d8baeb085730dec6a3e89b75d278e4'
HISTORY_HEAD = '06f2bb716af887b4f1cc52b1f850b0608bf81076'
OLD_IMAGES = {'main': 'sha256:12e54646c896886029addbfc72f36848c633a7588abf4b72d6d21bf7fd1512fc',
              'sn004': 'sha256:e29492434b19b7015e518193feeb789eb7b889341a660793e1db880aa6ded46c'}
OLD_RECEIPTS = {'main': '1bd4d6bcaa9ad97611b983972ae903fdfeb7882ca8110a2a7a99b670627e6622',
                'sn004': '12ba9000be8c6dcd59cb795f2a7a0b6699002536e63984cb76404a5dd868b35a'}
ADVANCE = {'elixir/mix.exs', 'elixir/mix.lock', 'elixir/test/test_helper.exs',
           'elixir/test/symphony_elixir/core_test.exs'}
DELTA = {refresh.PREFIX + p for p in ('profiles-pr75.json', 'snci/pr75_profile.py',
    'snci/source.py', 'snci/controller.py', 'tests/test_pr75_profile.py',
    'tests/test_pr75_target.py', 'README.md')}
INSTALL = refresh.INSTALL
STATE = refresh.STATE
ETC = refresh.ETC


def definition():
    return decode(trusted(Path(__file__).resolve().parents[1] / 'profiles-pr75.json').read_bytes())


def validate_upgrade(old, fresh):
    require(set(fresh) == {'name', 'head', 'tree', 'locked', 'minimum_tests', 'maximum_skips'}
            and fresh['name'] == 'sn004' and fresh['head'] == PR75_REQUEST['head']
            and fresh['tree'] == PR75_REQUEST['tree'] and fresh['minimum_tests'] == 462
            and fresh['maximum_skips'] == 6 and fresh == definition(), 'pr75_definition')
    require(set(old['locked']) <= set(fresh['locked'])
            and {p for p, v in old['locked'].items() if fresh['locked'].get(p) != v} == ADVANCE,
            'pr75_locked_delta')


def historical_profiles(policy):
    definitions = decode(trusted(INSTALL / 'profiles.json').read_bytes())
    expected = refresh.targets(definitions, [dict(p, image=OLD_IMAGES[p['name']]) for p in definitions.values()])
    for p in expected:
        p.update(preparation='refresh-' + HISTORY_HEAD + '/' + p['name'] + '/acceptance.json',
                 preparation_sha256=OLD_RECEIPTS[p['name']])
    require(policy['profiles'] == expected, 'pr75_historical_profiles')
    return expected


def future_policy(policy, head, profile):
    plain = {k: v for k, v in profile.items() if k not in ('image', 'preparation', 'preparation_sha256')}
    validate_upgrade(next(p for p in policy['profiles'] if p['name'] == 'sn004'), plain)
    require(profile.get('preparation') == 'refresh-' + head + '/sn004/acceptance.json'
            and re.fullmatch(r'sha256:[0-9a-f]{64}', profile.get('image', ''))
            and re.fullmatch(r'[0-9a-f]{64}', profile.get('preparation_sha256', '')), 'pr75_new_receipt')
    result = copy.deepcopy(policy)
    result['profiles'] = [copy.deepcopy(profile) if p['name'] == 'sn004' else p for p in result['profiles']]
    result.update(installed_revision=head, owner_request=copy.deepcopy(PR75_REQUEST))
    return result


def paths(head):
    require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head) and head != BASE, 'pr75_reviewed_head')
    return (STATE / ('refresh-' + head), INSTALL.with_name(INSTALL.name + '-refresh-' + head),
            INSTALL.with_name(INSTALL.name + '-before-pr75-' + head))


def digest(path):
    h = hashlib.sha256()
    with trusted(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def history(policy, head):
    rows = daily_limit.journal_rows(STATE); files = {}
    roots = [STATE / 'attempts' / row[0] for row in rows]
    roots += [p for p in STATE.iterdir() if p.name.startswith(
        ('refresh-', 'source-contract-', 'review-transport-', 'daily-limit-', 'prepare-'))
        and p.name != 'refresh-' + head]
    # Source/attempt directories are intentionally 0755 for UID transfer. Their
    # enclosing STATE remains private 0700; do not require source bytes to be0600.
    for root in roots:
        trusted(root, directory=True)
        for path in root.rglob('*'):
            trusted(path, directory=path.is_dir())
            if path.is_file(): files[str(path.relative_to(STATE))] = digest(path)
    for profile in policy['profiles']:
        receipt = STATE / profile['preparation']
        require(digest(receipt) == profile['preparation_sha256'], 'pr75_history_receipt')
    return {'rows': rows, 'files': files}


def verify_history(saved):
    path = trusted(STATE / 'journal.sqlite3', private=True)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
        rows = {row[0]: list(row) for row in db.execute('SELECT key,target,policy,day,state,data FROM attempts')}
    require(all(rows.get(row[0]) == row for row in saved['rows']), 'pr75_history_rows')
    for name, expected in saved['files'].items():
        require(not name.startswith('/') and '..' not in name.split('/')
                and digest(STATE / name) == expected, 'pr75_history_files')


def preflight(owner, head, api, source):
    units = daily_limit.paused(owner); refresh.idle_native()
    raw = trusted(ETC / 'policy.json', private=True).read_bytes(); policy = decode(raw)
    require(sha256(raw) == POLICY_SHA and policy.get('installed_revision') == BASE
            and policy.get('enabled') is True and policy.get('daily_attempts') is None, 'pr75_policy_binding')
    owner.validate_policy(policy)
    require(trusted(INSTALL / 'revision').read_text() == BASE, 'pr75_installed_revision')
    require(policy['codex_binary'] == owner.BINARY and policy['codex_sha256'] == owner.BINARY_SHA
            and sha256(trusted(owner.BINARY).read_bytes()) == owner.BINARY_SHA, 'pr75_native_binding')
    commit = refresh.reviewed_commit(api, head, base=BASE)
    old_tree, old = source.tree(BASE); tree, new = source.tree(head)
    require(old_tree == BASE_TREE and tree == commit['tree']['sha'], 'pr75_package_tree')
    package = refresh.package_delta(old, new, DELTA); manifest = refresh.verify_package(old)
    historical_profiles(policy)
    for p in policy['profiles']:
        refresh.read_acceptance(STATE, p, policy['codex_sha256'], time.time(), fresh=False)
        require(owner.inspect_image(p['image']).get('Id') == p['image'], 'pr75_old_image')
        recover_retention.keeper_verify(owner, HISTORY_HEAD, p)
    validate_target(api.request('GET', API + '/pulls/75'), owner_request=PR75_REQUEST)
    validate_rules(api.request('GET', API + '/rulesets/' + str(RULESET)), policy['ruleset'])
    target_tree, entries = source.tree(PR75_REQUEST['head'])
    require(target_tree == PR75_REQUEST['tree'], 'pr75_target_tree')
    profile = definition()
    require(all(entries.get(p, {}).get('sha') == v for p, v in profile['locked'].items())
            and {p for p in entries if p.startswith('elixir/test/')} <= set(profile['locked']), 'pr75_source_locks')
    temporary = future_policy(policy, head, dict(profile, image=OLD_IMAGES['sn004'],
        preparation='refresh-' + head + '/sn004/acceptance.json', preparation_sha256='0' * 64))
    require(select_profile(entries, temporary)['name'] == 'sn004', 'pr75_profile_selection')
    return dict(policy=policy, policy_raw=raw, package=package, new=new, tree=tree,
                old_manifest=manifest, units=units, history=history(policy, head), entries=entries,
                seed=seed_identity(owner), daemon=recover_retention.daemon_identity(owner),
                recipe=trusted(INSTALL / 'Dependency.Dockerfile').read_bytes())


def saved_snapshot(snapshot):
    return {k: snapshot[k] for k in ('tree', 'old_manifest', 'units', 'history', 'seed', 'daemon', 'entries')}


def verify_prepared(owner, head, snapshot):
    directory, stage, previous = paths(head)
    require(not previous.exists() and not previous.is_symlink(), 'pr75_already_installed')
    saved = decode(trusted(directory / 'inputs.json', private=True).read_bytes())
    require(saved == saved_snapshot(snapshot)
            and trusted(directory / 'policy-before.json', private=True).read_bytes() == snapshot['policy_raw'],
            'pr75_prepared_inputs_changed')
    proof = decode(trusted(directory / 'PREPARED.json', private=True).read_bytes())
    require(proof.get('head') == head and proof.get('tree') == snapshot['tree']
            and proof.get('policy_before_sha256') == POLICY_SHA
            and proof.get('inputs_sha256') == sha256(canonical(saved))
            and proof.get('status') == 'IMAGE_PREPARED_ONLY', 'pr75_prepared_binding')
    root = directory / 'sn004'
    require(trusted(root / 'image.id', private=True).read_text().strip() == proof['image']
            and decode(trusted(root / 'seed.json', private=True).read_bytes()) == snapshot['seed']
            and trusted(root / 'Dependency.Dockerfile', private=True).read_bytes() == snapshot['recipe'],
            'pr75_prepared_image')
    owner.verify_seed_build(snapshot['seed'], proof['image'])
    profile = dict(definition(), image=proof['image'])
    retention = decode(trusted(root / 'retention.json', private=True).read_bytes())
    require(retention == proof['retention'] and retention['image'] == proof['image']
            and retention['container'] == recover_retention.keeper_verify(owner, head, profile)
            and owner.inspect_image(retention['tag']).get('Id') == proof['image'], 'pr75_prepared_retention')
    require(proof['native_probe_sha256'] == digest(directory / 'native-codex.log')
            and proof['build_log_sha256'] == digest(root / 'build.log'), 'pr75_prepared_logs')
    verify_stage(stage, snapshot['package'])
    for path, entry in snapshot['entries'].items():
        require(blob_hash(trusted(root / 'source' / path).read_bytes()) == entry['sha'], 'pr75_prepared_source')
    return proof


def prepare(owner, head, api, source):
    directory, stage, previous = paths(head)
    require(not any(p.exists() or p.is_symlink() for p in (directory, stage, previous)), 'pr75_already_claimed')
    snapshot = preflight(owner, head, api, source)
    directory.mkdir(mode=0o700); refresh.sync(STATE)
    write_new(directory / 'policy-before.json', snapshot['policy_raw'])
    saved = saved_snapshot(snapshot); write_new(directory / 'inputs.json', canonical(saved))
    stage = refresh.stage_package(head, snapshot, source)
    native = native_probe(stage, owner, snapshot['policy'], directory / 'native-codex.log')
    root = directory / 'sn004'; root.mkdir(mode=0o700)
    source.materialize(snapshot['entries'], root / 'source')
    write_new(root / 'Dependency.Dockerfile', snapshot['recipe'])
    write_new(root / '.dockerignore', b'*\n!Dependency.Dockerfile\n!source\n!source/**\n')
    print('PR75_IMAGE_BUILD_START', flush=True)
    image = owner.build_dependency_image(root); owner.verify_seed_build(snapshot['seed'], image)
    retention = recover_retention.retain(owner, head, dict(definition(), image=image))
    write_new(root / 'retention.json', canonical(retention))
    require(preflight(owner, head, api, source) == snapshot, 'pr75_inputs_changed')
    proof = dict(head=head, tree=snapshot['tree'], policy_before_sha256=POLICY_SHA,
                 inputs_sha256=sha256(canonical(saved)), status='IMAGE_PREPARED_ONLY', image=image,
                 retention=retention, native_probe_sha256=native, build_log_sha256=digest(root / 'build.log'))
    write_new(directory / 'PREPARED.json', canonical(proof)); verify_prepared(owner, head, snapshot)
    print('PR75_IMAGE_PREPARED_ONLY ' + head, flush=True)
    return proof


def commit(owner, stage, previous, snapshot, future):
    future_raw = canonical(future); INSTALL.rename(previous)
    try:
        refresh.sync(INSTALL.parent); stage.rename(INSTALL); refresh.sync(INSTALL.parent)
        owner.replace_policy(future)
    except Exception:
        current = trusted(ETC / 'policy.json', private=True).read_bytes()
        if current == snapshot['policy_raw']:
            if INSTALL.exists():
                require(not stage.exists(), 'pr75_unknown_commit'); INSTALL.rename(stage)
            previous.rename(INSTALL); refresh.sync(INSTALL.parent)
        else: require(current == future_raw, 'pr75_unknown_commit')
        raise
    require(trusted(ETC / 'policy.json', private=True).read_bytes() == future_raw, 'pr75_policy_readback')


def validate_preparation(state, policy, raw):
    """Read-only gate; pending NEW check publications must remain reconcilable."""
    head = policy['installed_revision']; directory = Path(state) / ('refresh-' + head)
    before = trusted(directory / 'policy-before.json', private=True).read_bytes()
    require(sha256(before) == POLICY_SHA and raw == canonical(policy), 'pr75_completion_policy')
    proof = decode(trusted(directory / 'COMPLETE.json', private=True).read_bytes())
    intent = decode(trusted(directory / 'commit-intent.json', private=True).read_bytes())
    saved_raw = trusted(directory / 'inputs.json', private=True).read_bytes(); saved = decode(saved_raw)
    expected = {'head': head, 'policy_sha256': sha256(raw), 'tree': saved['tree']}
    require(intent == expected and all(proof.get(k) == v for k, v in expected.items())
            and proof.get('status') == 'PR75_PROFILE_INSTALLED_PAUSED'
            and proof.get('inputs_sha256') == sha256(saved_raw), 'pr75_completion_binding')
    profile = next(p for p in policy['profiles'] if p['name'] == 'sn004')
    require(policy == future_policy(decode(before), head, profile), 'pr75_completion_delta')
    receipt = refresh.read_acceptance(state, profile, policy['codex_sha256'], time.time(), fresh=False)
    require(receipt.get('refresh_revision') == head and receipt.get('native_probe_sha256') ==
            digest(directory / 'native-codex.log'), 'pr75_completion_receipt')
    require(proof.get('manifest_sha256') == sha256(trusted(INSTALL / 'installed.json').read_bytes())
            and trusted(INSTALL / 'revision').read_text() == head, 'pr75_completion_package')
    daily_limit.verify_manifest(INSTALL, proof['manifest_sha256'], head)
    daily_limit.verify_manifest(INSTALL.with_name(INSTALL.name + '-before-pr75-' + head), saved['old_manifest'], BASE)
    verify_history(saved['history'])
    return proof


def install(owner, head, api, source):
    directory, stage, previous = paths(head); snapshot = preflight(owner, head, api, source)
    proof = verify_prepared(owner, head, snapshot)
    require(not any((directory / p).exists() or (directory / p).is_symlink()
                    for p in ('quality-started.json', 'commit-intent.json', 'COMPLETE.json')), 'pr75_quality_already_claimed')
    root = directory / 'sn004'; profile = dict(definition(), image=proof['image'])
    key = sha256(canonical({'pr75': head, 'head': profile['head'], 'image': profile['image']}))
    write_new(directory / 'quality-started.json', canonical({'key': key, 'head': head}))
    print('PR75_PROTECTED_QUALITY_START', flush=True)
    result = runner.validate_result(runner.run(root, key, snapshot['entries'], profile), profile)
    receipt = dict(profile='sn004', head=profile['head'], tree=profile['tree'], image=profile['image'],
                   codex_sha256=snapshot['policy']['codex_sha256'], time=int(time.time()), quality=result,
                   native_probe_sha256=proof['native_probe_sha256'], refresh_revision=head)
    raw = canonical(receipt); write_new(root / 'acceptance.json', raw)
    profile.update(preparation='refresh-' + head + '/sn004/acceptance.json', preparation_sha256=sha256(raw))
    future = future_policy(snapshot['policy'], head, profile); owner.validate_policy(future)
    require(preflight(owner, head, api, source) == snapshot, 'pr75_inputs_changed')
    verify_prepared(owner, head, snapshot)
    intent = dict(head=head, tree=snapshot['tree'], policy_sha256=sha256(canonical(future)))
    write_new(directory / 'commit-intent.json', canonical(intent)); commit(owner, stage, previous, snapshot, future)
    refresh.verify_package(snapshot['new']); daily_limit.paused(owner); verify_history(snapshot['history'])
    complete = dict(intent, status='PR75_PROFILE_INSTALLED_PAUSED', inputs_sha256=sha256(canonical(saved_snapshot(snapshot))),
                    manifest_sha256=sha256(trusted(INSTALL / 'installed.json').read_bytes()))
    try:
        write_new(directory / 'COMPLETE.json', canonical(complete)); validate_preparation(STATE, future, canonical(future))
    except Exception:
        (directory / 'COMPLETE.json').unlink(missing_ok=True); refresh.sync(directory); raise
    print('PR75_PROFILE_INSTALLED_PAUSED ' + head, flush=True)
    print(canonical({'completion': 'VERIFIED_PAUSED', 'revision': head, 'policy_sha256': intent['policy_sha256'],
        'target': PR75_REQUEST, 'profile': 'sn004', 'image': profile['image'],
        'receipt_sha256': profile['preparation_sha256'], 'quality': result, 'daily_attempts': None}).decode(), flush=True)
    return complete


@contextmanager
def bounded_commands(owner):
    """One1800s leaf; reserve120s for owned worker cleanup and readback."""
    deadline = time.monotonic() + 1800; original_run, original_command = owner.run, runner.command
    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    def expired(*_): raise Hold('pr75_deadline')
    signal.signal(signal.SIGALRM, expired); signal.setitimer(signal.ITIMER_REAL, 1800)
    def remaining(timeout, cleanup=False):
        left = deadline - time.monotonic() - (0 if cleanup else 120)
        require(left > 0, 'pr75_deadline'); return min(timeout, left)
    def run(args, **kwargs):
        kwargs['timeout'] = remaining(kwargs.get('timeout', 30)); return original_run(args, **kwargs)
    def command(args, timeout=30):
        return original_command(args, timeout=remaining(timeout, args[0] in ('ps', 'inspect', 'rm')))
    owner.run, runner.command = run, command
    try: yield
    finally:
        owner.run, runner.command = original_run, original_command
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, max(0.001, old_timer[0] - (time.monotonic() - deadline + 1800)), old_timer[1])


def apply(action, head):
    require(os.geteuid() == 0 and os.uname().nodename.split('.')[0] == '1c-db', 'pr75_owner_identity')
    import owner
    with bounded_commands(owner):
        return locked_apply(action, head, owner)


def locked_apply(action, head, owner):
    checkout = trusted(Path(__file__).resolve().parents[3], directory=True)
    require(owner.run(['git', 'rev-parse', 'HEAD'], cwd=checkout, capture_output=True).stdout.decode().strip() == head
            and not owner.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=checkout,
                              capture_output=True).stdout, 'pr75_clean_reviewed_checkout')
    trusted(STATE, private=True, directory=True); trusted(ETC, private=True, directory=True)
    path = STATE / 'controller.lock'; fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        trusted(path, private=True)
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise Hold('pr75_controller_busy') from None
        policy = owner.load_policy(); api = GitHub(policy['github'], policy['github_key']); source = Source(api, STATE / 'blobs')
        if action == 'prepare': return prepare(owner, head, api, source)
        if action == 'install': return install(owner, head, api, source)
        require(action == 'verify' and policy.get('installed_revision') == head, 'pr75_verify_revision')
        daily_limit.paused(owner)
        return validate_preparation(STATE, policy, trusted(ETC / 'policy.json', private=True).read_bytes())


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('prepare', 'install', 'verify'))
    parser.add_argument('--reviewed-head', required=True)
    args = parser.parse_args(); os.umask(0o077)
    try: apply(args.action, args.reviewed_head)
    except Hold as error: print('HOLD ' + str(error), flush=True); raise SystemExit(1)
    except Exception: print('HOLD pr75_internal_error', flush=True); raise SystemExit(1)


if __name__ == '__main__': main()
