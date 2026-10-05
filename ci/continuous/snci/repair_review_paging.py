"""Single-use paused package repair preserving the exact PR75 profile and HOLD.

Source tests do not authorize this native leaf. Its owner invocation requires a
separate admission, the pinned native probe and a clean reviewed checkout.
"""
import argparse
import fcntl
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import API, RULESET, Hold, canonical, decode, require, sha256, trusted, write_new
from snci.github import GitHub
from snci.source import PR75_REQUEST, Source, select_profile, validate_rules, validate_target
from snci import daily_limit, pr75_profile, recover_retention, refresh
from snci.repair_review import verify_stage

BASE = 'e7f87ede8b4e93fd7ae2d83b8b19ab58dbb93207'
BASE_TREE = '15865f0b40c0a02fa28b068eebe29deff21ff58e'
POLICY_SHA = 'f50569540724f2be86dd77b529e6d0eb73d2ae0c8b6b23de27d354b859a2f414'
ORIGINAL_COMPLETE_SHA = 'f0d96dfd40222d351b42221eca7028d008bee3bda2e1f4f05d023ca2d019e0a5'
HOLD_KEY = '101338dff7f347525c15f66d27906872d67575733934a482a7fe511ad2ab748b'
INPUTS_SHA = 'e56393e303ef2b9c70499d6379e61008d02dd73d66deaff0e49c290cbb159d9d'
REVIEW_SHA = '9e608803afe2728718c7a4e7e328023faaf93cd639e32ed5a7c369a869a5df58'
IMAGE = 'sha256:13173082884c7fbe5bd03fc9db16a1deb0ec7af56d0dd71b4b391a252352c975'
RECEIPT_SHA = 'eaec1b7aef268e456d4342b6a0413b585c2879f4cc34a5c9718df5b52a7f6f13'
LEGACY_REVIEWER_BLOB = '4c95bbda74aea0541c54e0c3524ed2eb64bf5ca7'
DELTA = {'MANIFEST.sha256'} | {refresh.PREFIX + p for p in (
    'snci/reviewer.py', 'snci/pr75_profile.py', 'snci/controller.py', 'snci/repair_review_paging.py',
    'tests/test_review.py', 'tests/test_source_contract.py', 'tests/test_native_probe.py',
    'tests/native_codex_probe.py', 'tests/test_source_paging.py', 'tests/test_review_paging_repair.py',
    'tests/test_pr75_profile.py', 'tests/test_controller_flow.py', 'README.md')}
INSTALL = refresh.INSTALL
STATE = refresh.STATE
ETC = refresh.ETC


def paths(head):
    require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head) and head != BASE,
            'paging_reviewed_head')
    return (STATE / ('review-paging-' + head), INSTALL.with_name(INSTALL.name + '-refresh-' + head),
            INSTALL.with_name(INSTALL.name + '-before-review-paging-' + head))


def original_profile(policy):
    require(policy.get('installed_revision') == BASE and policy.get('enabled') is True
            and policy.get('daily_attempts') is None and policy.get('owner_request') == PR75_REQUEST,
            'paging_original_policy')
    profile = next(p for p in policy['profiles'] if p['name'] == 'sn004')
    require(profile.get('image') == IMAGE and profile.get('preparation_sha256') == RECEIPT_SHA
            and profile.get('preparation') == 'refresh-' + BASE + '/sn004/acceptance.json',
            'paging_original_profile')
    return profile


def hold_binding(state, saved):
    target = {k: PR75_REQUEST[k] for k in ('pr', 'head', 'base')}
    row = next((r for r in saved['rows'] if r[0] == HOLD_KEY), None)
    require(HOLD_KEY == sha256(canonical([target, POLICY_SHA])) and row is not None
            and decode(row[1].encode()) == target and row[2] == POLICY_SHA and row[4] == 'hold'
            and decode(row[5].encode()) == {'reason': 'review_not_ready'}, 'paging_original_hold')
    # Attempts are0755 for UID transfer inside the private0700 state boundary.
    root = trusted(Path(state) / 'attempts' / HOLD_KEY, directory=True)
    require(sha256(trusted(root / 'inputs.json', private=True).read_bytes()) == INPUTS_SHA
            and sha256(trusted(root / 'review.json', private=True).read_bytes()) == REVIEW_SHA
            and not (root / 'result.json').exists() and not (root / 'result.json').is_symlink(),
            'paging_original_hold_files')


def preflight(owner, head, api, source):
    units = daily_limit.paused(owner); refresh.idle_native()
    raw = trusted(ETC / 'policy.json', private=True).read_bytes(); policy = decode(raw)
    require(sha256(raw) == POLICY_SHA and raw == canonical(policy), 'paging_policy_binding')
    original_profile(policy); owner.validate_policy(policy)
    require(policy['codex_binary'] == owner.BINARY and policy['codex_sha256'] == owner.BINARY_SHA
            and sha256(trusted(owner.BINARY).read_bytes()) == owner.BINARY_SHA, 'paging_native_binding')
    commit = refresh.reviewed_commit(api, head, base=BASE)
    old_tree, old = source.tree(BASE); tree, new = source.tree(head)
    require(old_tree == BASE_TREE and tree == commit['tree']['sha'], 'paging_package_tree')
    package = refresh.package_delta(old, new, DELTA); manifest = refresh.verify_package(old)
    original = STATE / ('refresh-' + BASE) / 'COMPLETE.json'
    require(pr75_profile.digest(original) == ORIGINAL_COMPLETE_SHA, 'paging_original_complete')
    pr75_profile.validate_preparation(STATE, policy, raw)
    for profile in policy['profiles']:
        refresh.read_acceptance(STATE, profile, policy['codex_sha256'], time.time(), fresh=False)
        require(owner.inspect_image(profile['image']).get('Id') == profile['image'], 'paging_retained_image')
        origin = BASE if profile['name'] == 'sn004' else pr75_profile.HISTORY_HEAD
        recover_retention.keeper_verify(owner, origin, profile)
    validate_target(api.request('GET', API + '/pulls/75'), owner_request=PR75_REQUEST)
    validate_rules(api.request('GET', API + '/rulesets/' + str(RULESET)), policy['ruleset'])
    target_tree, entries = source.tree(PR75_REQUEST['head'])
    require(target_tree == PR75_REQUEST['tree'] and select_profile(entries, policy)['name'] == 'sn004',
            'paging_target_profile')
    history = pr75_profile.history(policy, head); hold_binding(STATE, history)
    return dict(policy=policy, policy_raw=raw, tree=tree, package=package, new=new,
                old_manifest=manifest, units=units, history=history,
                original_complete_sha256=ORIGINAL_COMPLETE_SHA)


def native_probe(stage, owner, policy, path):
    account = pwd.getpwnam('snci-review')
    require(account.pw_uid not in (0, 995, 997), 'paging_review_identity')
    with path.open('xb') as log:
        owner.run(['/usr/bin/python3', '-I', str(stage / 'tests/native_codex_probe.py'),
                   policy['codex_binary'], '--baseline-package', str(INSTALL)],
                  user=account.pw_uid, group=account.pw_gid, extra_groups=[], cwd=stage / 'review-empty',
                  stdout=log, stderr=subprocess.STDOUT, timeout=180)
        log.flush(); os.fsync(log.fileno())
    return sha256(trusted(path, private=True).read_bytes())


def probe_proof(directory, policy, expected):
    raw = trusted(directory / 'native-codex.log', private=True).read_bytes()
    require(sha256(raw) == expected, 'paging_native_log')
    lines = raw.splitlines(); require(bool(lines), 'paging_native_proof')
    proof = decode(lines[-1])
    require(proof == {'native_acceptance': 'PASS', 'source_paging_acceptance': 'PASS',
        'baseline_reviewer_blob': LEGACY_REVIEWER_BLOB, 'codex_sha256': policy['codex_sha256'], 'cases': 17},
        'paging_native_proof')


def saved_snapshot(snapshot):
    return {k: snapshot[k] for k in ('tree', 'old_manifest', 'units', 'history', 'original_complete_sha256')}


def validate_preparation(state, policy, raw):
    """Read-only completion, also usable while a NEW publication is pending."""
    head = policy.get('installed_revision'); directory, _, archive = paths(head)
    require(Path(state) == STATE and raw == canonical(policy), 'paging_completion_policy')
    before = trusted(directory / 'policy-before.json', private=True).read_bytes(); old = decode(before)
    require(sha256(before) == POLICY_SHA and policy == dict(old, installed_revision=head),
            'paging_completion_delta')
    original_profile(old)
    saved_raw = trusted(directory / 'inputs.json', private=True).read_bytes(); saved = decode(saved_raw)
    proof = decode(trusted(directory / 'COMPLETE.json', private=True).read_bytes())
    intent = decode(trusted(directory / 'commit-intent.json', private=True).read_bytes())
    expected = {'head': head, 'tree': saved['tree'], 'policy_sha256': sha256(raw)}
    require(intent == expected and all(proof.get(k) == v for k, v in expected.items())
            and proof.get('status') == 'REVIEW_PAGING_INSTALLED_PAUSED'
            and proof.get('inputs_sha256') == sha256(saved_raw), 'paging_completion_binding')
    daily_limit.verify_manifest(INSTALL, proof['manifest_sha256'], head)
    daily_limit.verify_manifest(archive, saved['old_manifest'], BASE)
    original = STATE / ('refresh-' + BASE) / 'COMPLETE.json'
    require(saved['original_complete_sha256'] == ORIGINAL_COMPLETE_SHA
            and pr75_profile.digest(original) == ORIGINAL_COMPLETE_SHA, 'paging_original_complete')
    pr75_profile.validate_preparation(state, old, before, package=archive)
    pr75_profile.verify_history(saved['history']); hold_binding(state, saved['history'])
    probe_proof(directory, policy, proof['native_probe_sha256'])
    return proof


def perform(owner, head, api, source):
    directory, stage, archive = paths(head)
    require(not any(p.exists() or p.is_symlink() for p in (directory, stage, archive)), 'paging_already_claimed')
    snapshot = preflight(owner, head, api, source)
    directory.mkdir(mode=0o700); refresh.sync(STATE)
    write_new(directory / 'policy-before.json', snapshot['policy_raw'])
    saved = saved_snapshot(snapshot); write_new(directory / 'inputs.json', canonical(saved))
    stage = refresh.stage_package(head, snapshot, source)
    native = native_probe(stage, owner, snapshot['policy'], directory / 'native-codex.log')
    probe_proof(directory, snapshot['policy'], native)
    require(preflight(owner, head, api, source) == snapshot, 'paging_inputs_changed')
    verify_stage(stage, snapshot['package'])
    future = dict(snapshot['policy'], installed_revision=head); owner.validate_policy(future)
    intent = dict(head=head, tree=snapshot['tree'], policy_sha256=sha256(canonical(future)))
    write_new(directory / 'commit-intent.json', canonical(intent))
    pr75_profile.commit(owner, stage, archive, snapshot, future)
    refresh.verify_package(snapshot['new']); daily_limit.paused(owner); refresh.idle_native()
    pr75_profile.verify_history(saved['history'])
    proof = dict(intent, status='REVIEW_PAGING_INSTALLED_PAUSED', inputs_sha256=sha256(canonical(saved)),
                 manifest_sha256=sha256(trusted(INSTALL / 'installed.json').read_bytes()),
                 native_probe_sha256=native)
    # Even a failed completion readback retains this new evidence and the claim.
    write_new(directory / 'COMPLETE.json', canonical(proof))
    validate_preparation(STATE, future, canonical(future))
    print('REVIEW_PAGING_INSTALLED_PAUSED ' + head, flush=True)
    return proof


def apply(action, head):
    require(os.geteuid() == 0 and os.uname().nodename.split('.')[0] == '1c-db', 'paging_owner_identity')
    import owner
    with pr75_profile.bounded_commands(owner):
        checkout = trusted(Path(__file__).resolve().parents[3], directory=True)
        require(owner.run(['git', 'rev-parse', 'HEAD'], cwd=checkout, capture_output=True).stdout.decode().strip() == head
                and not owner.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=checkout,
                                  capture_output=True).stdout, 'paging_clean_reviewed_checkout')
        trusted(STATE, private=True, directory=True); trusted(ETC, private=True, directory=True)
        lock_path = STATE / 'controller.lock'
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as lock:
            trusted(lock_path, private=True)
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise Hold('paging_controller_busy') from None
            daily_limit.paused(owner); refresh.idle_native()
            policy = owner.load_policy()
            if action == 'verify':
                require(policy.get('installed_revision') == head, 'paging_verify_revision')
                return validate_preparation(STATE, policy, trusted(ETC / 'policy.json', private=True).read_bytes())
            require(action == 'install', 'paging_action')
            api = GitHub(policy['github'], policy['github_key']); source = Source(api, STATE / 'blobs')
            return perform(owner, head, api, source)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('install', 'verify'))
    parser.add_argument('--reviewed-head', required=True)
    args = parser.parse_args(); os.umask(0o077)
    try: apply(args.action, args.reviewed_head)
    except Hold as error: print('HOLD ' + str(error), flush=True); raise SystemExit(1)
    except Exception: print('HOLD paging_internal_error', flush=True); raise SystemExit(1)


if __name__ == '__main__': main()
