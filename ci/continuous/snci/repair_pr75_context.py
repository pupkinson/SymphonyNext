"""Closed paused PR75 dependency-context admission; never starts the controller."""
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
from snci.source import PR75_SUCCESSOR_REQUEST, PR75_CONTEXT_REQUEST, Source, select_profile, validate_rules, validate_target
from snci import daily_limit, pr75_profile, recover_retention, refresh, repair_review_paging, repair_pr75_target, runner
from snci.repair_review import verify_stage

BASE = 'b7561f97dab3684a9e281987952e5e25c6e60e45'
BASE_TREE = 'fa5e7717db065b09913936b0725c709647c7f90a'
POLICY_SHA = '7eba3a12bd9c4ec783fc4ef8a4fd9260094449e0511858d08fa6797df264d939'
ORIGINAL_COMPLETE_SHA = '746938c1227b882d9196bff8f8a75176725ca95bc1fc9741217eaf65e13555a3'
HOLD_KEY = '7cd15ad385f5cbfeed5f0dbb94e04e063fd8b0bcd40e84712aaf1aecec50a5ee'
INPUTS_SHA = 'adb056145ace67659363ff3150c401aee330be0241f008c67b3493fbf18ca921'
REVIEW_SHA = 'ead2022821820071c040780f3cf7586d15c599e0d98ba3f696d7cb97ad58d223'
ADVANCES = {
    'elixir/test/support/auth_oidc_fixture.exs': '8656a8602b7641b1f0a6450ab95f221b2d8b3405',
    'elixir/test/symphony_control/auth/oidc_test.exs': 'be43772cf9dfb2ec029203d59b66becbd4ac1b05'}
DEFINITION_SHA = 'c909df305e471f49d92628517153e64b0d7e6015f8ab8726511b8b338fb55400'
IMAGE = 'sha256:13173082884c7fbe5bd03fc9db16a1deb0ec7af56d0dd71b4b391a252352c975'
DELTA = {'MANIFEST.sha256'} | {refresh.PREFIX + p for p in (
    'README.md', 'profiles-pr75-context.json', 'snci/source.py', 'snci/controller.py',
    'snci/repair_pr75_target.py', 'snci/repair_pr75_context.py',
    'tests/test_pr75_context.py', 'tests/test_pr75_target.py')}
INSTALL, STATE, ETC = refresh.INSTALL, refresh.STATE, refresh.ETC


def paths(head):
    require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head) and head != BASE,
            'pr75_context_reviewed_head')
    return (STATE / ('pr75-context-' + head), INSTALL.with_name(INSTALL.name + '-refresh-' + head),
            INSTALL.with_name(INSTALL.name + '-before-pr75-context-' + head))


def definition():
    old = repair_pr75_target.definition()
    expected = dict(old, head=PR75_CONTEXT_REQUEST['head'], tree=PR75_CONTEXT_REQUEST['tree'],
                    minimum_tests=507, locked=dict(old['locked'], **ADVANCES))
    raw = trusted(Path(__file__).resolve().parents[1] / 'profiles-pr75-context.json').read_bytes()
    new = decode(raw)
    require(sha256(raw) == DEFINITION_SHA and new == expected and len(old['locked']) == 68
            and old['minimum_tests'] == 464 and old['maximum_skips'] == 6,
            'pr75_context_definition')
    return new


def future_policy(old, head, profile):
    previous = next(p for p in old['profiles'] if p['name'] == 'sn004')
    plain = {k: v for k, v in profile.items() if k not in ('image', 'preparation', 'preparation_sha256')}
    require(sha256(canonical(old)) == POLICY_SHA and old.get('installed_revision') == BASE and old.get('owner_request') == PR75_SUCCESSOR_REQUEST
            and plain == definition() and profile.get('image') == previous['image'] == IMAGE
            and profile.get('preparation') == 'pr75-context-' + head + '/sn004/acceptance.json'
            and re.fullmatch(r'[0-9a-f]{64}', profile.get('preparation_sha256', '')),
            'pr75_context_policy_delta')
    require({k: v for k, v in previous.items() if k not in ('image', 'preparation', 'preparation_sha256')}
            == repair_pr75_target.definition(), 'pr75_context_original_profile')
    future = copy.deepcopy(old)
    future.update(installed_revision=head, owner_request=copy.deepcopy(PR75_CONTEXT_REQUEST))
    future['profiles'] = [copy.deepcopy(profile) if p['name'] == 'sn004' else p for p in future['profiles']]
    return future


def hold_binding(saved):
    target = {k: PR75_SUCCESSOR_REQUEST[k] for k in ('pr', 'head', 'base')}
    row = next((r for r in saved['rows'] if r[0] == HOLD_KEY), None)
    require(HOLD_KEY == sha256(canonical([target, POLICY_SHA])) and row is not None
            and decode(row[1].encode()) == target and row[2] == POLICY_SHA and row[4] == 'hold'
            and decode(row[5].encode()) == {'reason': 'review_not_ready'}, 'pr75_context_original_hold')
    root = trusted(STATE / 'attempts' / HOLD_KEY, directory=True)
    require(sha256(trusted(root / 'inputs.json', private=True).read_bytes()) == INPUTS_SHA
            and sha256(trusted(root / 'review.json', private=True).read_bytes()) == REVIEW_SHA
            and not (root / 'result.json').exists() and not (root / 'result.json').is_symlink(),
            'pr75_context_original_hold_files')


def original_proof(policy, raw, package=None):
    complete = STATE / ('pr75-target-' + BASE) / 'COMPLETE.json'
    require(sha256(trusted(complete, private=True).read_bytes()) == ORIGINAL_COMPLETE_SHA,
            'pr75_context_original_complete')
    return repair_pr75_target.validate_preparation(STATE, policy, raw, package=package)


def previous_receipt(policy):
    profile = next(p for p in policy['profiles'] if p['name'] == 'sn004')
    raw = trusted(STATE / profile['preparation'], private=True).read_bytes()
    require(sha256(raw) == profile['preparation_sha256'], 'pr75_context_predecessor_receipt')
    return decode(raw)


def history(policy, head):
    """Freeze every predecessor claim/artifact, including paging and target proofs."""
    saved = {'rows': daily_limit.journal_rows(STATE), 'files': {}}
    excluded = {'blobs', 'pr75-context-' + head}
    for root in STATE.iterdir():
        if root.name in excluded or root.name.startswith('journal.sqlite3') or root.name == 'controller.lock':
            continue
        trusted(root, directory=root.is_dir())
        paths = root.rglob('*') if root.is_dir() else [root]
        for path in paths:
            trusted(path, directory=path.is_dir())
            if path.is_file(): saved['files'][str(path.relative_to(STATE))] = pr75_profile.digest(path)
    return saved


def preflight(owner, head, api, source):
    units = daily_limit.paused(owner); refresh.idle_native()
    raw = trusted(ETC / 'policy.json', private=True).read_bytes(); policy = decode(raw)
    require(sha256(raw) == POLICY_SHA and raw == canonical(policy) and policy.get('installed_revision') == BASE
            and policy.get('enabled') is True and policy.get('daily_attempts') is None
            and policy.get('owner_request') == PR75_SUCCESSOR_REQUEST, 'pr75_context_original_policy')
    owner.validate_policy(policy); original_proof(policy, raw)
    commit = refresh.reviewed_commit(api, head, base=BASE)
    old_tree, old = source.tree(BASE); tree, new = source.tree(head)
    require(old_tree == BASE_TREE and tree == commit['tree']['sha'], 'pr75_context_package_tree')
    package = refresh.package_delta(old, new, DELTA); manifest = refresh.verify_package(old)
    for profile in policy['profiles']:
        refresh.read_acceptance(STATE, profile, policy['codex_sha256'], time.time(), fresh=False)
        require(owner.inspect_image(profile['image']).get('Id') == profile['image'], 'pr75_context_retained_image')
        origin = repair_review_paging.BASE if profile['name'] == 'sn004' else pr75_profile.HISTORY_HEAD
        recover_retention.keeper_verify(owner, origin, profile)
    validate_target(api.request('GET', API + '/pulls/75'), owner_request=PR75_CONTEXT_REQUEST)
    validate_rules(api.request('GET', API + '/rulesets/' + str(RULESET)), policy['ruleset'])
    target_tree, entries = source.tree(PR75_CONTEXT_REQUEST['head'])
    require(target_tree == PR75_CONTEXT_REQUEST['tree'], 'pr75_context_source_tree')
    previous = next(p for p in policy['profiles'] if p['name'] == 'sn004')
    fresh = dict(definition(), image=previous['image'], preparation='pr75-context-' + head + '/sn004/acceptance.json',
                 preparation_sha256='0' * 64)
    require(select_profile(entries, future_policy(policy, head, fresh)) == fresh, 'pr75_context_source_locks')
    saved_history = history(policy, head); hold_binding(saved_history)
    return dict(policy=policy, policy_raw=raw, tree=tree, package=package, new=new,
                old_manifest=manifest, units=units, history=saved_history, entries=entries)


def saved_snapshot(snapshot):
    return {k: snapshot[k] for k in ('tree', 'old_manifest', 'units', 'history', 'entries')}


def validate_preparation(state, policy, raw):
    head = policy.get('installed_revision'); directory, _, archive = paths(head)
    require(Path(state) == STATE and raw == canonical(policy)
            and trusted(ETC / 'policy.json', private=True).read_bytes() == raw,
            'pr75_context_completion_policy')
    before = trusted(directory / 'policy-before.json', private=True).read_bytes(); old = decode(before)
    require(sha256(before) == POLICY_SHA, 'pr75_context_completion_predecessor')
    profile = next(p for p in policy['profiles'] if p['name'] == 'sn004')
    require(policy == future_policy(old, head, profile), 'pr75_context_completion_delta')
    saved_raw = trusted(directory / 'inputs.json', private=True).read_bytes(); saved = decode(saved_raw)
    proof = decode(trusted(directory / 'COMPLETE.json', private=True).read_bytes())
    intent = decode(trusted(directory / 'commit-intent.json', private=True).read_bytes())
    expected = dict(head=head, tree=saved['tree'], policy_sha256=sha256(raw))
    require(intent == expected and all(proof.get(k) == v for k, v in expected.items())
            and proof.get('status') == 'PR75_CONTEXT_INSTALLED_PAUSED'
            and proof.get('inputs_sha256') == sha256(saved_raw), 'pr75_context_completion_binding')
    daily_limit.verify_manifest(INSTALL, proof['manifest_sha256'], head)
    daily_limit.verify_manifest(archive, saved['old_manifest'], BASE)
    original_proof(old, before, package=archive)
    receipt_raw = trusted(STATE / profile['preparation'], private=True).read_bytes(); receipt = decode(receipt_raw)
    require(sha256(receipt_raw) == profile['preparation_sha256'] and receipt == dict(
        profile='sn004', head=profile['head'], tree=profile['tree'], image=profile['image'],
        codex_sha256=policy['codex_sha256'], time=receipt.get('time'), quality=receipt.get('quality'),
        native_probe_sha256=previous_receipt(old)['native_probe_sha256'],
        predecessor_completion_sha256=ORIGINAL_COMPLETE_SHA, refresh_revision=head), 'pr75_context_receipt')
    require(type(receipt['time']) is int and 0 <= receipt['time'] <= time.time(), 'pr75_context_receipt_time')
    runner.validate_result(receipt['quality'], profile)
    require(select_profile(saved['entries'], policy) == profile, 'pr75_context_completion_source_locks')
    pr75_profile.verify_history(saved['history']); hold_binding(saved['history'])
    return proof


def perform(owner, head, api, source):
    directory, stage, archive = paths(head)
    require(not any(p.exists() or p.is_symlink() for p in (directory, stage, archive)), 'pr75_context_already_claimed')
    snapshot = preflight(owner, head, api, source)
    directory.mkdir(mode=0o700); refresh.sync(STATE)
    write_new(directory / 'policy-before.json', snapshot['policy_raw'])
    saved = saved_snapshot(snapshot); write_new(directory / 'inputs.json', canonical(saved))
    stage = refresh.stage_package(head, snapshot, source); root = directory / 'sn004'; root.mkdir(mode=0o700)
    previous = next(p for p in snapshot['policy']['profiles'] if p['name'] == 'sn004')
    profile = dict(definition(), image=previous['image'])
    source.materialize(snapshot['entries'], root / 'source')
    key = sha256(canonical({'pr75_context': head, 'head': profile['head'], 'image': profile['image']}))
    write_new(directory / 'quality-started.json', canonical(dict(key=key, head=head)))
    print('PR75_CONTEXT_PROTECTED_QUALITY_START', flush=True)
    quality = runner.validate_result(runner.run(root, key, snapshot['entries'], profile), profile)
    original_proof(snapshot['policy'], snapshot['policy_raw'])
    receipt = dict(profile='sn004', head=profile['head'], tree=profile['tree'], image=profile['image'],
                   codex_sha256=snapshot['policy']['codex_sha256'], time=int(time.time()), quality=quality,
                   native_probe_sha256=previous_receipt(snapshot['policy'])['native_probe_sha256'],
                   predecessor_completion_sha256=ORIGINAL_COMPLETE_SHA, refresh_revision=head)
    raw = canonical(receipt); write_new(root / 'acceptance.json', raw)
    profile.update(preparation='pr75-context-' + head + '/sn004/acceptance.json', preparation_sha256=sha256(raw))
    future = future_policy(snapshot['policy'], head, profile); owner.validate_policy(future)
    require(preflight(owner, head, api, source) == snapshot, 'pr75_context_inputs_changed')
    verify_stage(stage, snapshot['package'])
    intent = dict(head=head, tree=snapshot['tree'], policy_sha256=sha256(canonical(future)))
    write_new(directory / 'commit-intent.json', canonical(intent))
    pr75_profile.commit(owner, stage, archive, snapshot, future)
    refresh.verify_package(snapshot['new']); daily_limit.paused(owner); refresh.idle_native()
    pr75_profile.verify_history(saved['history']); hold_binding(saved['history'])
    proof = dict(intent, status='PR75_CONTEXT_INSTALLED_PAUSED', inputs_sha256=sha256(canonical(saved)),
                 manifest_sha256=sha256(trusted(INSTALL / 'installed.json').read_bytes()))
    try:
        write_new(directory / 'COMPLETE.json', canonical(proof))
        validate_preparation(STATE, future, canonical(future))
    except Exception:
        (directory / 'COMPLETE.json').unlink(missing_ok=True); refresh.sync(directory); raise
    print('PR75_CONTEXT_INSTALLED_PAUSED ' + head, flush=True)
    print(canonical(dict(completion='VERIFIED_INSTALLED_PAUSED', revision=head, target=PR75_CONTEXT_REQUEST,
        policy_sha256=intent['policy_sha256'], profile='sn004', image=profile['image'], quality=quality,
        receipt_sha256=profile['preparation_sha256'], trusted_check='NOT_RUN')).decode(), flush=True)
    return proof


def apply(action, head):
    require(os.geteuid() == 0 and os.uname().nodename.split('.')[0] == '1c-db', 'pr75_context_owner_identity')
    import owner
    with pr75_profile.bounded_commands(owner):
        checkout = trusted(Path(__file__).resolve().parents[3], directory=True)
        require(owner.run(['git', 'rev-parse', 'HEAD'], cwd=checkout, capture_output=True).stdout.decode().strip() == head
                and not owner.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=checkout,
                                  capture_output=True).stdout, 'pr75_context_clean_reviewed_checkout')
        lock_path = STATE / 'controller.lock'; fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as lock:
            trusted(lock_path, private=True)
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise Hold('pr75_context_controller_busy') from None
            daily_limit.paused(owner); refresh.idle_native(); policy = owner.load_policy()
            if action == 'verify':
                require(policy.get('installed_revision') == head, 'pr75_context_verify_revision')
                return validate_preparation(STATE, policy, trusted(ETC / 'policy.json', private=True).read_bytes())
            require(action == 'install', 'pr75_context_action')
            api = GitHub(policy['github'], policy['github_key']); source = Source(api, STATE / 'blobs')
            return perform(owner, head, api, source)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('install', 'verify'))
    parser.add_argument('--reviewed-head', required=True); args = parser.parse_args(); os.umask(0o077)
    try: apply(args.action, args.reviewed_head)
    except Hold as error: print('HOLD ' + str(error), flush=True); raise SystemExit(1)
    except Exception: print('HOLD pr75_context_internal_error', flush=True); raise SystemExit(1)


if __name__ == '__main__': main()
