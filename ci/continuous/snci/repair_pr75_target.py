"""Closed paused PR75 successor/profile admission; never starts the controller."""
import argparse
import copy
import fcntl
import os
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import API, RULESET, Hold, canonical, decode, require, sha256, trusted, write_new
from snci.github import GitHub
from snci.source import PR75_REQUEST, PR75_SUCCESSOR_REQUEST, Source, select_profile, validate_rules, validate_target
from snci import daily_limit, pr75_profile, recover_retention, refresh, repair_review_paging, runner
from snci.repair_review import verify_stage

BASE = 'df9db5b37d0227c3d66170b4b952ecca32484620'
BASE_TREE = 'd820c69f6539ca3290f9d7133520c8ce8d34fd03'
POLICY_SHA = 'a18ce73bec402947d7cde1ceaf5ff4aca3da7bc307cb6b502cd9135331e8fcdf'
ORIGINAL_COMPLETE_SHA = '9f1a7b0ac3f3db6f912fa34e697c2f3d740710e9a570043dbdc60c7fd5f57818'
HOLD_KEY = 'ff24dcedcfa5a07177b0af828fb4888b0a99f6e0bd97ac6737f4df45ae484139'
INPUTS_SHA = 'eebe158e0633268a70b98d9d0b24865de548c144b007b3b1a658a4c4f60aa45a'
REVIEW_SHA = '5f3d943779504cb3efd29f874a7fbd0ff2c8fd7a514c40df6f14e5fcecaa361f'
ADVANCE = 'elixir/test/symphony_control/auth/oidc_test.exs'
TEST_BLOB = '06440d55937db19d77a336ee18dbc0ee95d41349'
DELTA = {'MANIFEST.sha256'} | {refresh.PREFIX + p for p in (
    'README.md', 'profiles-pr75-successor.json', 'snci/source.py', 'snci/controller.py',
    'snci/repair_review_paging.py', 'snci/repair_pr75_target.py', 'tests/test_pr75_target.py')}
INSTALL, STATE, ETC = refresh.INSTALL, refresh.STATE, refresh.ETC


def paths(head):
    require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head) and head != BASE,
            'pr75_target_reviewed_head')
    return (STATE / ('pr75-target-' + head), INSTALL.with_name(INSTALL.name + '-refresh-' + head),
            INSTALL.with_name(INSTALL.name + '-before-pr75-target-' + head))


def definition():
    old = pr75_profile.definition()
    expected = dict(old, head=PR75_SUCCESSOR_REQUEST['head'], tree=PR75_SUCCESSOR_REQUEST['tree'],
                    minimum_tests=464, locked=dict(old['locked'], **{ADVANCE: TEST_BLOB}))
    new = decode(trusted(Path(__file__).resolve().parents[1] / 'profiles-pr75-successor.json').read_bytes())
    require(new == expected and old['minimum_tests'] == 462 and old['maximum_skips'] == 6,
            'pr75_target_definition')
    return new


def future_policy(old, head, profile):
    previous = next(p for p in old['profiles'] if p['name'] == 'sn004')
    plain = {k: v for k, v in profile.items() if k not in ('image', 'preparation', 'preparation_sha256')}
    require(old.get('installed_revision') == BASE and old.get('owner_request') == PR75_REQUEST
            and plain == definition() and profile.get('image') == previous['image']
            and profile.get('preparation') == 'pr75-target-' + head + '/sn004/acceptance.json'
            and re.fullmatch(r'[0-9a-f]{64}', profile.get('preparation_sha256', '')),
            'pr75_target_policy_delta')
    require({k: v for k, v in previous.items() if k not in ('image', 'preparation', 'preparation_sha256')}
            == pr75_profile.definition(), 'pr75_target_original_profile')
    future = copy.deepcopy(old)
    future.update(installed_revision=head, owner_request=copy.deepcopy(PR75_SUCCESSOR_REQUEST))
    future['profiles'] = [copy.deepcopy(profile) if p['name'] == 'sn004' else p for p in future['profiles']]
    return future


def hold_binding(saved):
    target = {k: PR75_REQUEST[k] for k in ('pr', 'head', 'base')}
    row = next((r for r in saved['rows'] if r[0] == HOLD_KEY), None)
    require(HOLD_KEY == sha256(canonical([target, POLICY_SHA])) and row is not None
            and decode(row[1].encode()) == target and row[2] == POLICY_SHA and row[4] == 'hold'
            and decode(row[5].encode()) == {'reason': 'review_not_ready'}, 'pr75_target_original_hold')
    root = trusted(STATE / 'attempts' / HOLD_KEY, directory=True)
    require(sha256(trusted(root / 'inputs.json', private=True).read_bytes()) == INPUTS_SHA
            and sha256(trusted(root / 'review.json', private=True).read_bytes()) == REVIEW_SHA
            and not (root / 'result.json').exists() and not (root / 'result.json').is_symlink(),
            'pr75_target_original_hold_files')


def original_proof(policy, raw, package=None):
    complete = STATE / ('review-paging-' + BASE) / 'COMPLETE.json'
    require(sha256(trusted(complete, private=True).read_bytes()) == ORIGINAL_COMPLETE_SHA,
            'pr75_target_original_complete')
    return repair_review_paging.validate_preparation(STATE, policy, raw, package=package)


def preflight(owner, head, api, source):
    units = daily_limit.paused(owner); refresh.idle_native()
    raw = trusted(ETC / 'policy.json', private=True).read_bytes(); policy = decode(raw)
    require(sha256(raw) == POLICY_SHA and raw == canonical(policy) and policy.get('installed_revision') == BASE
            and policy.get('enabled') is True and policy.get('daily_attempts') is None
            and policy.get('owner_request') == PR75_REQUEST, 'pr75_target_original_policy')
    owner.validate_policy(policy); original_proof(policy, raw)
    commit = refresh.reviewed_commit(api, head, base=BASE)
    old_tree, old = source.tree(BASE); tree, new = source.tree(head)
    require(old_tree == BASE_TREE and tree == commit['tree']['sha'], 'pr75_target_package_tree')
    package = refresh.package_delta(old, new, DELTA); manifest = refresh.verify_package(old)
    for profile in policy['profiles']:
        refresh.read_acceptance(STATE, profile, policy['codex_sha256'], time.time(), fresh=False)
        require(owner.inspect_image(profile['image']).get('Id') == profile['image'], 'pr75_target_retained_image')
        origin = repair_review_paging.BASE if profile['name'] == 'sn004' else pr75_profile.HISTORY_HEAD
        recover_retention.keeper_verify(owner, origin, profile)
    validate_target(api.request('GET', API + '/pulls/75'), owner_request=PR75_SUCCESSOR_REQUEST)
    validate_rules(api.request('GET', API + '/rulesets/' + str(RULESET)), policy['ruleset'])
    target_tree, entries = source.tree(PR75_SUCCESSOR_REQUEST['head'])
    require(target_tree == PR75_SUCCESSOR_REQUEST['tree'], 'pr75_target_source_tree')
    previous = next(p for p in policy['profiles'] if p['name'] == 'sn004')
    fresh = dict(definition(), image=previous['image'], preparation='pr75-target-' + head + '/sn004/acceptance.json',
                 preparation_sha256='0' * 64)
    require(select_profile(entries, future_policy(policy, head, fresh)) == fresh, 'pr75_target_source_locks')
    history = pr75_profile.history(policy, head); hold_binding(history)
    return dict(policy=policy, policy_raw=raw, tree=tree, package=package, new=new,
                old_manifest=manifest, units=units, history=history, entries=entries)


def saved_snapshot(snapshot):
    return {k: snapshot[k] for k in ('tree', 'old_manifest', 'units', 'history', 'entries')}


def validate_preparation(state, policy, raw, *, package=None):
    head = policy.get('installed_revision'); directory, _, archive = paths(head)
    require(Path(state) == STATE and raw == canonical(policy), 'pr75_target_completion_policy')
    before = trusted(directory / 'policy-before.json', private=True).read_bytes(); old = decode(before)
    require(sha256(before) == POLICY_SHA, 'pr75_target_completion_predecessor')
    profile = next(p for p in policy['profiles'] if p['name'] == 'sn004')
    require(policy == future_policy(old, head, profile), 'pr75_target_completion_delta')
    saved_raw = trusted(directory / 'inputs.json', private=True).read_bytes(); saved = decode(saved_raw)
    proof = decode(trusted(directory / 'COMPLETE.json', private=True).read_bytes())
    intent = decode(trusted(directory / 'commit-intent.json', private=True).read_bytes())
    expected = dict(head=head, tree=saved['tree'], policy_sha256=sha256(raw))
    require(intent == expected and all(proof.get(k) == v for k, v in expected.items())
            and proof.get('status') == 'PR75_TARGET_INSTALLED_PAUSED'
            and proof.get('inputs_sha256') == sha256(saved_raw), 'pr75_target_completion_binding')
    current = INSTALL if package is None else trusted(Path(package), directory=True)
    daily_limit.verify_manifest(current, proof['manifest_sha256'], head)
    daily_limit.verify_manifest(archive, saved['old_manifest'], BASE)
    original = original_proof(old, before, package=archive)
    receipt_raw = trusted(STATE / profile['preparation'], private=True).read_bytes(); receipt = decode(receipt_raw)
    require(sha256(receipt_raw) == profile['preparation_sha256'] and receipt == dict(
        profile='sn004', head=profile['head'], tree=profile['tree'], image=profile['image'],
        codex_sha256=policy['codex_sha256'], time=receipt.get('time'), quality=receipt.get('quality'),
        native_probe_sha256=original['native_probe_sha256'], refresh_revision=head), 'pr75_target_receipt')
    require(type(receipt['time']) is int and 0 <= receipt['time'] <= time.time(), 'pr75_target_receipt_time')
    runner.validate_result(receipt['quality'], profile)
    require(select_profile(saved['entries'], policy) == profile, 'pr75_target_completion_source_locks')
    pr75_profile.verify_history(saved['history']); hold_binding(saved['history'])
    return proof


def perform(owner, head, api, source):
    directory, stage, archive = paths(head)
    require(not any(p.exists() or p.is_symlink() for p in (directory, stage, archive)), 'pr75_target_already_claimed')
    snapshot = preflight(owner, head, api, source)
    directory.mkdir(mode=0o700); refresh.sync(STATE)
    write_new(directory / 'policy-before.json', snapshot['policy_raw'])
    saved = saved_snapshot(snapshot); write_new(directory / 'inputs.json', canonical(saved))
    stage = refresh.stage_package(head, snapshot, source); root = directory / 'sn004'; root.mkdir(mode=0o700)
    previous = next(p for p in snapshot['policy']['profiles'] if p['name'] == 'sn004')
    profile = dict(definition(), image=previous['image'])
    source.materialize(snapshot['entries'], root / 'source')
    key = sha256(canonical({'pr75_target': head, 'head': profile['head'], 'image': profile['image']}))
    write_new(directory / 'quality-started.json', canonical(dict(key=key, head=head)))
    print('PR75_SUCCESSOR_PROTECTED_QUALITY_START', flush=True)
    quality = runner.validate_result(runner.run(root, key, snapshot['entries'], profile), profile)
    original = original_proof(snapshot['policy'], snapshot['policy_raw'])
    receipt = dict(profile='sn004', head=profile['head'], tree=profile['tree'], image=profile['image'],
                   codex_sha256=snapshot['policy']['codex_sha256'], time=int(time.time()), quality=quality,
                   native_probe_sha256=original['native_probe_sha256'], refresh_revision=head)
    raw = canonical(receipt); write_new(root / 'acceptance.json', raw)
    profile.update(preparation='pr75-target-' + head + '/sn004/acceptance.json', preparation_sha256=sha256(raw))
    future = future_policy(snapshot['policy'], head, profile); owner.validate_policy(future)
    require(preflight(owner, head, api, source) == snapshot, 'pr75_target_inputs_changed')
    verify_stage(stage, snapshot['package'])
    intent = dict(head=head, tree=snapshot['tree'], policy_sha256=sha256(canonical(future)))
    write_new(directory / 'commit-intent.json', canonical(intent))
    pr75_profile.commit(owner, stage, archive, snapshot, future)
    refresh.verify_package(snapshot['new']); daily_limit.paused(owner); refresh.idle_native()
    pr75_profile.verify_history(saved['history']); hold_binding(saved['history'])
    proof = dict(intent, status='PR75_TARGET_INSTALLED_PAUSED', inputs_sha256=sha256(canonical(saved)),
                 manifest_sha256=sha256(trusted(INSTALL / 'installed.json').read_bytes()))
    write_new(directory / 'COMPLETE.json', canonical(proof)); validate_preparation(STATE, future, canonical(future))
    print('PR75_TARGET_INSTALLED_PAUSED ' + head, flush=True)
    print(canonical(dict(completion='VERIFIED_INSTALLED_PAUSED', revision=head, target=PR75_SUCCESSOR_REQUEST,
        policy_sha256=intent['policy_sha256'], profile='sn004', image=profile['image'], quality=quality,
        receipt_sha256=profile['preparation_sha256'], trusted_check='NOT_RUN')).decode(), flush=True)
    return proof


def apply(action, head):
    require(os.geteuid() == 0 and os.uname().nodename.split('.')[0] == '1c-db', 'pr75_target_owner_identity')
    import owner
    with pr75_profile.bounded_commands(owner):
        checkout = trusted(Path(__file__).resolve().parents[3], directory=True)
        require(owner.run(['git', 'rev-parse', 'HEAD'], cwd=checkout, capture_output=True).stdout.decode().strip() == head
                and not owner.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=checkout,
                                  capture_output=True).stdout, 'pr75_target_clean_reviewed_checkout')
        lock_path = STATE / 'controller.lock'; fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as lock:
            trusted(lock_path, private=True)
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise Hold('pr75_target_controller_busy') from None
            daily_limit.paused(owner); refresh.idle_native(); policy = owner.load_policy()
            if action == 'verify':
                require(policy.get('installed_revision') == head, 'pr75_target_verify_revision')
                return validate_preparation(STATE, policy, trusted(ETC / 'policy.json', private=True).read_bytes())
            require(action == 'install', 'pr75_target_action')
            api = GitHub(policy['github'], policy['github_key']); source = Source(api, STATE / 'blobs')
            return perform(owner, head, api, source)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('install', 'verify'))
    parser.add_argument('--reviewed-head', required=True); args = parser.parse_args(); os.umask(0o077)
    try: apply(args.action, args.reviewed_head)
    except Hold as error: print('HOLD ' + str(error), flush=True); raise SystemExit(1)
    except Exception: print('HOLD pr75_target_internal_error', flush=True); raise SystemExit(1)


if __name__ == '__main__': main()
