"""Owner-only transition from two successful preparations; never activate CI.

Run only from a root-owned checkout of the independently reviewed commit.
The old installer and failed-cache repairs are not invoked.
"""
import argparse
import copy
from contextlib import closing
import fcntl
import os
from pathlib import Path
import pwd
import re
import sqlite3
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import API, Hold, blob_hash, canonical, decode, require, sha256, trusted, write_new
from snci.github import GitHub
from snci.source import Source, changed_paths, quality_control, select_profile, validate_rules
from snci import runner

BASE = '10b56bc96f764dabdf498aef3c1ed869f3845fb8'
SN004_HEAD = '21ce4282e7ef8330cc1155bcb7b94fbf132032a8'
SN004_TREE = '29fe41a2873a3db13ac2c0dc74b7f149391c9eeb'
TEST_PATH = 'elixir/test/symphony_control/runtime_config_test.exs'
OLD_TEST = 'db578aa009e93724a98618b34daaa19eb2802d66'
NEW_TEST = '5ca85121e627a8e085083fc2ea25b404c2fcd9c7'
INSTALL = Path('/opt/symphony-next-ci')
STATE = Path('/var/lib/symphony-next-ci')
ETC = Path('/etc/symphony-next-ci')
PREFIX = 'ci/continuous/'
DELTA = {PREFIX + p for p in ('owner.py', 'snci/refresh.py', 'tests/test_refresh.py', 'README.md')}


def targets(definitions, profiles):
    require(set(definitions) == {'main', 'sn004'} and isinstance(profiles, list)
            and len(profiles) == 2, 'refresh_profiles')
    by_name = {p['name']: p for p in profiles}
    require(set(by_name) == set(definitions), 'refresh_profiles')
    out = []
    for name in ('main', 'sn004'):
        old = by_name[name]
        require(isinstance(old.get('image'), str)
                and re.fullmatch(r'sha256:[0-9a-f]{64}', old['image']), 'refresh_image')
        require(old == dict(definitions[name], image=old['image']), 'refresh_profile_drift')
        out.append(copy.deepcopy(old))
    require(out[0]['minimum_tests'] == 305 and out[1]['minimum_tests'] == 328
            and out[1]['locked'][TEST_PATH] == OLD_TEST, 'refresh_baseline')
    out[1].update(head=SN004_HEAD, tree=SN004_TREE, minimum_tests=331)
    out[1]['locked'][TEST_PATH] = NEW_TEST
    return out


def read_acceptance(state, profile, codex_sha, now, fresh=True):
    name = profile.get('name')
    require(name in ('main', 'sn004'), 'receipt_profile')
    relative = profile.get('preparation')
    if relative is None:
        require('preparation_sha256' not in profile, 'receipt_pointer')
        path = Path(state) / ('prepare-' + name) / 'acceptance.json'
    else:
        require(isinstance(relative, str) and re.fullmatch(
            r'refresh-[0-9a-f]{40}/' + name + r'/acceptance\.json', relative), 'receipt_pointer')
        require(isinstance(profile.get('preparation_sha256'), str)
                and re.fullmatch(r'[0-9a-f]{64}', profile['preparation_sha256']), 'receipt_digest')
        path = Path(state) / relative
    raw = trusted(path, private=True).read_bytes()
    if relative is not None:
        require(sha256(raw) == profile['preparation_sha256'], 'receipt_digest')
    receipt = decode(raw)
    require(isinstance(receipt, dict) and receipt.get('profile') == name
            and all(receipt.get(k) == profile[k] for k in ('head', 'tree', 'image'))
            and receipt.get('codex_sha256') == codex_sha, 'receipt_identity')
    require(type(receipt.get('time')) is int and 0 <= receipt['time'] <= now
            and (not fresh or now - receipt['time'] < 86400), 'native_acceptance_stale')
    require(isinstance(receipt.get('native_probe_sha256'), str)
            and re.fullmatch(r'[0-9a-f]{64}', receipt['native_probe_sha256']), 'receipt_native_probe')
    runner.validate_result(receipt.get('quality', {}), profile)
    return receipt


def package_delta(base, head, delta=DELTA):
    require(set(changed_paths(head, base)) == delta and delta <= set(head), 'refresh_package_scope')
    package = {p[len(PREFIX):]: e for p, e in head.items() if p.startswith(PREFIX)}
    require(all(e['mode'] == '100644' for e in package.values()), 'refresh_package_mode')
    return package


def reviewed_commit(api, head, base=BASE):
    """One initial commit plus at most two linear repairs above the approved base."""
    candidate = None
    seen = set()
    for _ in range(3):
        require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head)
                and head not in seen and head != BASE, 'refresh_commit_parent')
        seen.add(head)
        commit = api.request('GET', API + '/git/commits/' + head)
        parents = commit.get('parents', [])
        require(commit.get('sha') == head and len(parents) == 1, 'refresh_commit_parent')
        if candidate is None:
            candidate = commit
        head = parents[0].get('sha')
        if head == base:
            return candidate
    raise Hold('refresh_commit_parent')


def completed_refresh(state, policy, policy_raw):
    """Activation requires the disabled-policy commit's matching completion proof."""
    head = policy['installed_revision']
    require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head), 'refresh_completion_revision')
    attempt = Path(state) / ('refresh-' + head)
    profiles = policy['profiles']
    if not any('preparation' in p for p in profiles) and not attempt.exists():
        return  # Original first-use preparations retain their existing activation gate.
    require(len(profiles) == 2 and {p['name'] for p in profiles} == {'main', 'sn004'}
            and all(p.get('preparation') == 'refresh-' + head + '/' + p['name'] + '/acceptance.json'
                    for p in profiles), 'refresh_completion_pointer')
    expected = dict(head=head, policy_sha256=sha256(policy_raw))
    try:
        intent = decode(trusted(attempt / 'commit-intent.json', private=True).read_bytes())
        complete = decode(trusted(attempt / 'COMPLETE.json', private=True).read_bytes())
    except OSError:
        raise Hold('refresh_completion_missing') from None
    require(intent == expected and complete == dict(expected, status='REFRESHED_DISABLED', profiles=profiles),
            'refresh_completion_mismatch')


def sync(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stopped(owner):
    for suffix in ('service', 'timer'):
        unit = 'symphony-next-ci.' + suffix
        raw = owner.run(['systemctl', 'show', unit, '-p', 'Id', '-p', 'ActiveState',
                         '-p', 'SubState', '-p', 'UnitFileState', '-p', 'MainPID'],
                        capture_output=True, timeout=30).stdout.decode()
        fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
        require(fields.get('Id') == unit and fields.get('ActiveState') == 'inactive'
                and fields.get('SubState') == 'dead', 'refresh_service_active')
        if suffix == 'timer':
            require(fields.get('UnitFileState') == 'disabled', 'refresh_timer_enabled')
        else:
            require(fields.get('MainPID') == '0', 'refresh_process_active')


def no_pending():
    path = STATE / 'journal.sqlite3'
    if not path.exists():
        require(not path.is_symlink(), 'refresh_journal_type')
        return
    trusted(path, private=True)
    for suffix in ('-wal', '-shm'):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            trusted(sidecar, private=True)
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
            pending = db.execute("SELECT count(*) FROM attempts WHERE state NOT IN ('success','hold','stale') OR state IS NULL").fetchone()[0]
            require(pending == 0, 'refresh_pending_attempts')
    except sqlite3.Error:
        raise Hold('refresh_journal_invalid') from None


def idle_native():
    no_pending()
    require(not runner.command(['ps', '-a', '--filter', 'label=snci.attempt', '--format', '{{.Names}}']).strip(),
            'refresh_existing_worker')


def verify_package(entries):
    manifest_raw = trusted(INSTALL / 'installed.json').read_bytes()
    manifest = decode(manifest_raw)
    package = {p[len(PREFIX):]: e for p, e in entries.items() if p.startswith(PREFIX)}
    require(set(manifest) == set(package), 'refresh_manifest_scope')
    for name, entry in package.items():
        raw = trusted(INSTALL / name).read_bytes()
        require(blob_hash(raw) == entry['sha'] and len(raw) == entry['size']
                and sha256(raw) == manifest[name], 'refresh_installed_changed')
    return sha256(manifest_raw)


def preflight(owner, head, api, source, rebuild=False):
    require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head) and head != BASE,
            'refresh_reviewed_head')
    stopped(owner)
    idle_native()
    require(trusted(INSTALL / 'revision').read_text() == BASE, 'refresh_base_revision')
    raw = trusted(ETC / 'policy.json', private=True).read_bytes()
    policy = decode(raw)
    require(policy.get('enabled') is False and policy.get('installed_revision') == BASE, 'refresh_policy')
    owner.validate_policy(policy)
    require(policy['codex_binary'] == owner.BINARY and policy['codex_sha256'] == owner.BINARY_SHA
            and sha256(trusted(owner.BINARY).read_bytes()) == owner.BINARY_SHA, 'refresh_codex')
    if rebuild:
        from snci import rebuild_missing as recovery
        commit = reviewed_commit(api, head, base=recovery.SOURCE_BASE)
    else:
        commit = reviewed_commit(api, head)
    _, old = source.tree(BASE)
    tree, new = source.tree(head)
    require(tree == commit['tree']['sha'], 'refresh_commit_tree')
    if rebuild:
        reviewed_tree, reviewed = source.tree(recovery.SOURCE_BASE)
        require(reviewed_tree == recovery.SOURCE_TREE, 'rebuild_source_base')
        package = recovery.package(old, reviewed, new)
    else:
        package = package_delta(old, new)
    manifest_sha = verify_package(old)
    definitions = decode(trusted(INSTALL / 'profiles.json').read_bytes())
    future = targets(definitions, policy['profiles'])
    receipts = {}
    recipe = trusted(INSTALL / 'Dependency.Dockerfile').read_bytes()
    for profile in policy['profiles']:
        root = STATE / ('prepare-' + profile['name'])
        read_acceptance(STATE, profile, policy['codex_sha256'], time.time(), fresh=False)
        require(trusted(root / 'Dependency.Dockerfile').read_bytes() == recipe, 'refresh_recipe')
        require(trusted(root / 'image.id').read_text().strip() == profile['image'], 'refresh_image_receipt')
        receipts[profile['name']] = sha256(trusted(root / 'acceptance.json', private=True).read_bytes())
        if not rebuild:
            require(owner.inspect_image(profile['image']).get('Id') == profile['image'], 'refresh_image_unavailable')
    validate_rules(api.request('GET', API + '/rulesets/23980199'), policy['ruleset'])
    snapshot = dict(policy=policy, policy_raw=raw, definitions=definitions, targets=future,
                    old=old, package=package, tree=tree, receipts=receipts, manifest_sha=manifest_sha,
                    recipe=recipe)
    if rebuild:
        snapshot.update(recovery.preflight(owner, head, policy['profiles']))
    return snapshot


def source_entries(snapshot, api, source):
    require(api.request('GET', API + '/branches/main')['commit']['sha'] == snapshot['targets'][0]['head'],
            'refresh_main_changed')
    pr = api.request('GET', API + '/pulls/14')
    require(pr.get('state') == 'open' and pr.get('merged') is False and pr['head']['sha'] == SN004_HEAD
            and pr['head']['repo']['id'] == 1381693716, 'refresh_sn004_changed')
    output = {}
    for profile in snapshot['targets']:
        name = profile['name']
        tree, entries = source.tree(profile['head'])
        require(tree == profile['tree'], 'refresh_profile_tree')
        require(select_profile(entries, {'profiles': snapshot['targets']})['name'] == name, 'refresh_profile_selection')
        old_tree, old = source.tree(snapshot['definitions'][name]['head'])
        require(old_tree == snapshot['definitions'][name]['tree'], 'refresh_original_tree')
        # Only reuse the immutable dependency image when all dependency/config inputs match.
        control = {p for p in entries.keys() | old.keys() if quality_control(p)}
        require(all(entries.get(p) == old.get(p) for p in control), 'refresh_dependency_change')
        output[name] = entries
    return output


def recheck(owner, snapshot, api, source, rebuild=False):
    stopped(owner)
    idle_native()
    require(trusted(ETC / 'policy.json', private=True).read_bytes() == snapshot['policy_raw']
            and trusted(INSTALL / 'revision').read_text() == BASE, 'refresh_inputs_changed')
    require(verify_package(snapshot['old']) == snapshot['manifest_sha'], 'refresh_manifest_changed')
    require(sha256(trusted(owner.BINARY).read_bytes()) == owner.BINARY_SHA, 'refresh_codex_changed')
    for profile in snapshot['policy']['profiles']:
        name = profile['name']
        require(sha256(trusted(STATE / ('prepare-' + name) / 'acceptance.json', private=True).read_bytes())
                == snapshot['receipts'][name], 'refresh_history_changed')
        if not rebuild:
            require(owner.inspect_image(profile['image']).get('Id') == profile['image'], 'refresh_image_unavailable')
    validate_rules(api.request('GET', API + '/rulesets/23980199'), snapshot['policy']['ruleset'])
    source_entries(snapshot, api, source)


def native_quality(root, profile, entries, owner, policy, head):
    account = pwd.getpwnam('snci-review')
    with (root / 'native-codex.log').open('xb') as log:
        owner.run(['/usr/bin/python3', '-I', str(INSTALL / 'tests/native_codex_probe.py'), policy['codex_binary']],
                  user=account.pw_uid, group=account.pw_gid, extra_groups=[], cwd=INSTALL / 'review-empty',
                  stdout=log, stderr=subprocess.STDOUT, timeout=180)
    key = sha256(canonical(dict(refresh=head, profile=profile['name'], head=profile['head'], image=profile['image'])))
    result = runner.run(root, key, entries, profile)
    return result, sha256((root / 'native-codex.log').read_bytes())


def stage_package(head, snapshot, source):
    stage = INSTALL.with_name(INSTALL.name + '-refresh-' + head)
    require(not stage.exists(), 'refresh_stage_exists')
    stage.mkdir(mode=0o755)
    manifest = {}
    for name, entry in snapshot['package'].items():
        raw = source.blob(entry)
        require(blob_hash(raw) == entry['sha'] and len(raw) == entry['size'], 'refresh_blob')
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        write_new(path, raw, 0o644)
        manifest[name] = sha256(raw)
    write_new(stage / 'installed.json', canonical(manifest), 0o644)
    write_new(stage / 'revision', head.encode(), 0o644)
    (stage / 'review-empty').mkdir(mode=0o755)
    for path in [stage] + [p for p in stage.rglob('*') if p.is_dir()]:
        path.chmod(0o755)
    sync(stage.parent)
    return stage


def perform(owner, head, api, source, rebuild=False):
    if rebuild:
        from snci import rebuild_missing as recovery
        snapshot = preflight(owner, head, api, source, rebuild=True)
    else:
        snapshot = preflight(owner, head, api, source)
    entries = source_entries(snapshot, api, source)
    attempt = STATE / ('refresh-' + head)
    backup = INSTALL.with_name(INSTALL.name + '-before-refresh-' + head)
    require(not attempt.exists() and not backup.exists(), 'refresh_already_claimed')
    attempt.mkdir(mode=0o700)
    sync(STATE)
    write_new(attempt / 'policy-before.json', snapshot['policy_raw'])
    inputs = dict(head=head, base=BASE, targets=snapshot['targets'])
    if rebuild:
        inputs.update(mode='rebuild_missing', source_base=recovery.SOURCE_BASE, seed=snapshot['seed'])
    write_new(attempt / 'inputs.json', canonical(inputs))
    future = copy.deepcopy(snapshot['policy'])
    future['profiles'] = []
    for profile in snapshot['targets']:
        name = profile['name']
        root = attempt / name
        root.mkdir(mode=0o700)
        source.materialize(entries[name], root / 'source')
        if rebuild:
            profile = recovery.build(owner, root, profile, snapshot, head)
        print('REFRESH_QUALITY_START ' + name, flush=True)
        quality, probe_sha = native_quality(root, profile, entries[name], owner, snapshot['policy'], head)
        runner.validate_result(quality, profile)
        receipt = dict(profile=name, head=profile['head'], tree=profile['tree'], image=profile['image'],
                       codex_sha256=future['codex_sha256'], time=int(time.time()), quality=quality,
                       native_probe_sha256=probe_sha, refresh_revision=head)
        raw = canonical(receipt)
        write_new(root / 'acceptance.json', raw)
        updated = dict(profile, preparation='refresh-' + head + '/' + name + '/acceptance.json',
                       preparation_sha256=sha256(raw))
        read_acceptance(STATE, updated, future['codex_sha256'], time.time())
        future['profiles'].append(updated)
    future['installed_revision'] = head
    owner.validate_policy(future)
    stage = stage_package(head, snapshot, source)
    if rebuild:
        recheck(owner, snapshot, api, source, rebuild=True)
        recovery.recheck(owner, snapshot, head, attempt, future['profiles'])
    else:
        recheck(owner, snapshot, api, source)
    for profile in future['profiles']:
        read_acceptance(STATE, profile, future['codex_sha256'], time.time())
    committed = dict(head=head, policy_sha256=sha256(canonical(future)))
    write_new(attempt / 'commit-intent.json', canonical(committed))
    INSTALL.rename(backup)
    sync(INSTALL.parent)
    try:
        stage.rename(INSTALL)
    except Exception:
        backup.rename(INSTALL)
        sync(INSTALL.parent)
        raise
    try:
        sync(INSTALL.parent)
    except OSError:
        raise Hold('refresh_reconcile_package_sync') from None
    # The policy is one atomic commit for BOTH profiles. Any error after intent is a hold,
    # not a retry or automatic rollback; the full old package/policy remains preserved.
    owner.replace_policy(future)
    require(owner.load_policy() == future
            and trusted(ETC / 'policy.json', private=True).read_bytes() == canonical(future),
            'refresh_policy_readback')
    result = attempt / 'COMPLETE.json'
    try:
        write_new(result, canonical(dict(committed, status='REFRESHED_DISABLED', profiles=future['profiles'])))
    except Exception:
        # An interrupted/failed completion write must not become activation proof.
        result.unlink(missing_ok=True)
        sync(attempt)
        raise
    print('REFRESHED_DISABLED ' + head, flush=True)
    return result


def apply(head, rebuild=False):
    require(os.geteuid() == 0 and os.uname().nodename.split('.')[0] == '1c-db', 'refresh_owner_identity')
    import owner
    checkout = trusted(Path(__file__).resolve().parents[3], directory=True)
    actual = owner.run(['git', 'rev-parse', 'HEAD'], cwd=checkout, capture_output=True).stdout.decode().strip()
    require(actual == head and not owner.run(['git', 'status', '--porcelain', '--untracked-files=all'],
                                            cwd=checkout, capture_output=True).stdout, 'refresh_clean_reviewed_checkout')
    trusted(STATE, private=True, directory=True)
    trusted(ETC, private=True, directory=True)
    lock_path = STATE / 'controller.lock'
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        trusted(lock_path, private=True)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Hold('refresh_controller_busy') from None
        policy = owner.load_policy()
        api = GitHub(policy['github'], policy['github_key'])
        source = Source(api, STATE / 'blobs')
        perform(owner, head, api, source, rebuild=rebuild)


def main(rebuild=False):
    parser = argparse.ArgumentParser()
    parser.add_argument('--reviewed-head', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        apply(args.reviewed_head, rebuild=rebuild)
    except Hold as error:
        print('HOLD ' + str(error))
        raise SystemExit(1)
    except Exception:
        print('HOLD refresh_internal_error')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
