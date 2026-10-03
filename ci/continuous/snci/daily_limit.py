"""Owner-requested unlimited daily admission; single-use installation while paused."""
import argparse
from contextlib import closing
import datetime
import fcntl
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, canonical, decode, require, sha256, trusted, write_new
from snci.github import GitHub
from snci.source import Source, changed_paths
from snci import refresh
from snci.repair_review import verify_stage

BASE = '344ea8d5129b7815c212d8a16c207b937dd825a5'
BASE_TREE = '9c1de0d5fd90a2591287f45bb733421c0862c2b2'
POLICY_SHA = '5cc7926d787c0689894d22a7aea714a9b45aed27aa1d9d0cac89c5e7e42889c3'
ATTEMPT_KEY = '280dd9ed672cd49c5a17ce052e1d58e6b1e8a0d05babd8092d2b612b822a2f21'
INPUTS_SHA = '3fb39dc5a74610618cb52e4a3c618476ac32cef76a300f6c58549b18d484899f'
REVIEW_SHA = '5fdd719b9013e75f36b20e7e3b8815bcbf7a98800c9b4c823d3d5cfeb00f96b4'
TARGET = {'pr': 14, 'head': 'e356c2681b63c2139873a8e75afbb8752d8793d5',
          'base': '2bf21950e0725bc9228b262e1495f5af5eeea1d6'}
TREE = '3fd9a4c63c6ad4b36e9e129d6d4581b520a2376f'
PREFIX = 'ci/continuous/'
DELTA = {PREFIX + path for path in ('snci/state.py', 'snci/controller.py', 'snci/daily_limit.py',
                                   'tests/test_daily_limit.py', 'README.md')}
INSTALL = refresh.INSTALL
STATE = refresh.STATE
ETC = refresh.ETC


def backup(head):
    return INSTALL.with_name(INSTALL.name + '-before-daily-limit-' + head)


def paused(owner):
    """A terminal failed oneshot with both PIDs zero is idle, without resetting it."""
    result = {}
    for suffix in ('service', 'timer'):
        unit = 'symphony-next-ci.' + suffix
        fields = ('Id', 'LoadState', 'ActiveState', 'SubState', 'UnitFileState', 'MainPID', 'ControlPID')
        args = ['systemctl', 'show', unit]
        for field in fields:
            args.extend(['-p', field])
        raw = owner.run(args, capture_output=True, timeout=30).stdout.decode()
        value = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
        require(value.get('Id') == unit and value.get('LoadState') == 'loaded', 'daily_limit_units')
        if suffix == 'timer':
            require(value.get('ActiveState') == 'inactive' and value.get('SubState') == 'dead'
                    and value.get('UnitFileState') == 'disabled', 'daily_limit_units')
        else:
            require((value.get('ActiveState'), value.get('SubState')) in
                    (('inactive', 'dead'), ('failed', 'failed'))
                    and value.get('MainPID') == '0' and value.get('ControlPID') == '0', 'daily_limit_units')
        result[suffix] = value
    return result


def journal_rows(state):
    path = trusted(Path(state) / 'journal.sqlite3', private=True)
    for suffix in ('-wal', '-shm'):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            trusted(sidecar, private=True)
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
            rows = [list(row) for row in db.execute(
                'SELECT key,target,policy,day,state,data FROM attempts ORDER BY key')]
    except sqlite3.Error:
        raise Hold('daily_limit_journal') from None
    require(all(row[4] in ('success', 'hold', 'stale') for row in rows), 'daily_limit_pending')
    require(len({row[0] for row in rows}) == len(rows)
            and all(isinstance(row[0], str) and re.fullmatch(r'[0-9a-f]{64}', row[0]) for row in rows),
            'daily_limit_journal')
    return rows


def file_digest(path):
    value = hashlib.sha256()
    with trusted(path, private=True).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def saved_files(state, policy, rows):
    """Bind old attempt artifacts and receipt/retention/transition metadata, not blobs."""
    state = Path(state)
    paths = set()
    for row in rows:
        root = trusted(state / 'attempts' / row[0], private=True, directory=True)
        for path in root.rglob('*'):
            trusted(path, private=True, directory=path.is_dir())
            if path.is_file():
                paths.add(path)
    for profile in policy['profiles']:
        relative = profile.get('preparation')
        require(isinstance(relative, str) and relative and not relative.startswith('/')
                and '..' not in relative.split('/'), 'daily_limit_receipt')
        receipt = state / relative
        require(file_digest(receipt) == profile.get('preparation_sha256'), 'daily_limit_receipt')
        paths.update((receipt, receipt.parent / 'retention.json'))
    for root in state.iterdir():
        if root.name.startswith(('refresh-', 'source-contract-', 'review-transport-', 'daily-limit-')):
            trusted(root, private=True, directory=True)
            for name in ('policy-before.json', 'inputs.json', 'commit-intent.json', 'COMPLETE.json'):
                path = root / name
                if path.exists() or path.is_symlink():
                    paths.add(path)
    return {str(path.relative_to(state)): file_digest(path) for path in sorted(paths)}


def latest_hold(state, rows):
    matches = [row for row in rows if row[0] == ATTEMPT_KEY]
    require(ATTEMPT_KEY == sha256(canonical([TARGET, POLICY_SHA])) and len(matches) == 1
            and decode(matches[0][1]) == TARGET and matches[0][2] == POLICY_SHA
            and matches[0][4] == 'hold' and decode(matches[0][5]) == {'reason': 'review_not_ready'},
            'daily_limit_hold')
    root = trusted(Path(state) / 'attempts' / ATTEMPT_KEY, private=True, directory=True)
    require({path.name for path in root.iterdir()} == {'inputs.json', 'review.json'}, 'daily_limit_review_only')
    inputs = trusted(root / 'inputs.json', private=True).read_bytes()
    review = trusted(root / 'review.json', private=True).read_bytes()
    require(sha256(inputs) == INPUTS_SHA and sha256(review) == REVIEW_SHA, 'daily_limit_review')
    value = decode(inputs)
    require(value.get('target') == dict(TARGET, tree=TREE)
            and value.get('policy_sha256') == POLICY_SHA, 'daily_limit_inputs')
    verdict = decode(review).get('verdict', {})
    require(all(verdict.get(key) == val for key, val in dict(TARGET, tree=TREE).items())
            and verdict.get('verdict') == 'CHANGES_REQUESTED', 'daily_limit_review')


def preflight(owner, head, api, source):
    units = paused(owner)
    raw = trusted(ETC / 'policy.json', private=True).read_bytes()
    policy = decode(raw)
    require(sha256(raw) == POLICY_SHA and policy.get('installed_revision') == BASE
            and policy.get('enabled') is True and type(policy.get('daily_attempts')) is int
            and policy['daily_attempts'] == 4, 'daily_limit_policy')
    owner.validate_policy(policy)
    require(policy['codex_binary'] == owner.BINARY and policy['codex_sha256'] == owner.BINARY_SHA
            and sha256(trusted(owner.BINARY).read_bytes()) == owner.BINARY_SHA, 'daily_limit_native')
    commit = refresh.reviewed_commit(api, head, base=BASE)
    base_tree, old = source.tree(BASE)
    tree, new = source.tree(head)
    require(base_tree == BASE_TREE and tree == commit['tree']['sha'], 'daily_limit_tree')
    require(set(changed_paths(new, old)) == DELTA and DELTA <= set(new), 'daily_limit_scope')
    package = {path[len(PREFIX):]: entry for path, entry in new.items() if path.startswith(PREFIX)}
    require(all(entry.get('mode') == '100644' for entry in package.values()), 'daily_limit_mode')
    require(trusted(INSTALL / 'revision').read_text() == BASE, 'daily_limit_revision')
    manifest = refresh.verify_package(old)
    rows = journal_rows(STATE)
    latest_hold(STATE, rows)
    files = saved_files(STATE, policy, rows)
    return dict(policy=policy, policy_raw=raw, package=package, new=new, tree=tree,
                rows=rows, files=files, units=units, old_manifest_sha256=manifest)


def verify_manifest(root, digest, revision):
    raw = trusted(root / 'installed.json').read_bytes()
    require(sha256(raw) == digest and trusted(root / 'revision').read_text() == revision, 'daily_limit_manifest')
    for name, expected in decode(raw).items():
        require(not name.startswith('/') and '..' not in name.split('/')
                and sha256(trusted(root / name).read_bytes()) == expected, 'daily_limit_package')


def verify_history(state, saved):
    current = {row[0]: row for row in journal_rows(state)}
    require(all(current.get(row[0]) == row for row in saved['rows']), 'daily_limit_history')
    for name, digest in saved['files'].items():
        require(not name.startswith('/') and '..' not in name.split('/')
                and file_digest(Path(state) / name) == digest, 'daily_limit_history')
    latest_hold(state, list(current.values()))


def completed(state, policy, raw, owner):
    head = policy.get('installed_revision')
    require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head) and head != BASE,
            'daily_limit_completion')
    directory = trusted(Path(state) / ('daily-limit-' + head), private=True, directory=True)
    before = trusted(directory / 'policy-before.json', private=True).read_bytes()
    require(sha256(before) == POLICY_SHA and policy == dict(decode(before), installed_revision=head, daily_attempts=None)
            and raw == canonical(policy) and trusted(ETC / 'policy.json', private=True).read_bytes() == raw,
            'daily_limit_completion_policy')
    saved = decode(trusted(directory / 'inputs.json', private=True).read_bytes())
    intent = decode(trusted(directory / 'commit-intent.json', private=True).read_bytes())
    proof = decode(trusted(directory / 'COMPLETE.json', private=True).read_bytes())
    expected = dict(head=head, tree=saved['tree'], policy_sha256=sha256(raw))
    require(saved.get('head') == head and saved.get('base') == BASE and intent == expected
            and all(proof.get(key) == value for key, value in expected.items())
            and proof.get('status') == 'DAILY_LIMIT_REMOVED_PAUSED'
            and proof.get('inputs_sha256') == sha256(canonical(saved)), 'daily_limit_completion')
    verify_history(state, saved)
    verify_manifest(backup(head), saved['old_manifest_sha256'], BASE)
    verify_manifest(INSTALL, proof['manifest_sha256'], head)
    paused(owner)
    return proof


def perform(owner, head, api, source):
    require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head) and head != BASE, 'daily_limit_head')
    directory = STATE / ('daily-limit-' + head)
    stage = INSTALL.with_name(INSTALL.name + '-refresh-' + head)
    predecessor = backup(head)
    require(not any(path.exists() or path.is_symlink() for path in (directory, stage, predecessor)),
            'daily_limit_already_claimed')
    snapshot = preflight(owner, head, api, source)
    directory.mkdir(mode=0o700)
    refresh.sync(STATE)
    write_new(directory / 'policy-before.json', snapshot['policy_raw'])
    saved = dict(head=head, base=BASE, **{key: snapshot[key] for key in
                 ('tree', 'rows', 'files', 'units', 'old_manifest_sha256')})
    write_new(directory / 'inputs.json', canonical(saved))
    stage = refresh.stage_package(head, snapshot, source)
    # The newly written claim is not part of the old metadata snapshot.
    check = preflight(owner, head, api, source)
    for name in list(check['files']):
        if name.startswith(directory.name + '/'):
            del check['files'][name]
    require(check == snapshot, 'daily_limit_inputs_changed')
    verify_stage(stage, snapshot['package'])
    future = dict(snapshot['policy'], installed_revision=head, daily_attempts=None)
    owner.validate_policy(future)
    future_raw = canonical(future)
    intent = dict(head=head, tree=snapshot['tree'], policy_sha256=sha256(future_raw))
    write_new(directory / 'commit-intent.json', canonical(intent))
    INSTALL.rename(predecessor)
    try:
        refresh.sync(INSTALL.parent)
        stage.rename(INSTALL)
        refresh.sync(INSTALL.parent)
        owner.replace_policy(future)
    except Exception:
        current = trusted(ETC / 'policy.json', private=True).read_bytes()
        if current == snapshot['policy_raw']:
            if INSTALL.exists():
                require(not stage.exists(), 'daily_limit_unknown_commit')
                INSTALL.rename(stage)
            predecessor.rename(INSTALL)
            refresh.sync(INSTALL.parent)
        else:
            # A write can succeed before its fsync reports an error. Preserve the
            # matching package and durable intent; do not guess or replay.
            require(current == future_raw, 'daily_limit_unknown_commit')
        raise
    require(trusted(ETC / 'policy.json', private=True).read_bytes() == future_raw, 'daily_limit_policy_readback')
    refresh.verify_package(snapshot['new'])
    verify_history(STATE, saved)
    paused(owner)
    day = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    proof = dict(intent, status='DAILY_LIMIT_REMOVED_PAUSED', inputs_sha256=sha256(canonical(saved)),
                 manifest_sha256=sha256(trusted(INSTALL / 'installed.json').read_bytes()),
                 budget=dict(day=day, used=sum(row[3] == day for row in snapshot['rows']), limit=None, remaining=None))
    try:
        write_new(directory / 'COMPLETE.json', canonical(proof))
        completed(STATE, future, future_raw, owner)
    except Exception:
        (directory / 'COMPLETE.json').unlink(missing_ok=True)
        refresh.sync(directory)
        raise
    print('DAILY_LIMIT_REMOVED_PAUSED ' + head, flush=True)
    print(canonical(dict(completion='VERIFIED_PAUSED', revision=head, policy_sha256=sha256(future_raw),
                         enabled=future['enabled'], daily_attempts=None, budget=proof['budget'])).decode(), flush=True)
    return proof


def apply(head):
    require(os.geteuid() == 0 and os.uname().nodename.split('.')[0] == '1c-db', 'daily_limit_owner_identity')
    import owner
    checkout = trusted(Path(__file__).resolve().parents[3], directory=True)
    require(owner.run(['git', 'rev-parse', 'HEAD'], cwd=checkout, capture_output=True).stdout.decode().strip() == head
            and not owner.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=checkout,
                              capture_output=True).stdout, 'daily_limit_clean_checkout')
    trusted(STATE, private=True, directory=True)
    trusted(ETC, private=True, directory=True)
    path = STATE / 'controller.lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        trusted(path, private=True)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Hold('daily_limit_controller_busy') from None
        policy = owner.load_policy()
        api = GitHub(policy['github'], policy['github_key'])
        perform(owner, head, api, Source(api, STATE / 'blobs'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reviewed-head', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        apply(args.reviewed_head)
    except Hold as error:
        print('HOLD ' + str(error))
        raise SystemExit(1)
    except Exception:
        print('HOLD daily_limit_internal_error')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
