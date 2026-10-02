"""Successful preparations refresh without rewriting historical evidence."""
import copy
import importlib
import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, canonical, sha256
from snci import runner

PACKAGE = Path(__file__).resolve().parents[1]
HEAD = 'a' * 40
IMAGE = 'sha256:' + 'b' * 64
CODEX = 'c' * 64
NOW = 1790960000


def quality(n):
    return dict(stages=dict.fromkeys(('build', 'format', 'lint', 'coverage', 'dialyzer'), 0),
                source_before=True, source_after=True, cleanup=0, tests=n, failures=0,
                skipped=6, coverage=100.0, dialyzer_errors=0, dialyzer_skipped=0,
                dialyzer_unnecessary_skips=0)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        try:
            self.r = importlib.import_module('snci.refresh')
        except ImportError:
            self.fail('successful-preparation refresh is not implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.install = self.root / 'install'
        self.state = self.root / 'state'
        self.etc = self.root / 'etc'
        for p in (self.install, self.state, self.etc):
            p.mkdir()
        for key, value in [('INSTALL', self.install), ('STATE', self.state), ('ETC', self.etc),
                           ('trusted', lambda p, **kw: Path(p))]:
            mock = patch.object(self.r, key, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.defs = json.loads((PACKAGE / 'profiles.json').read_text())
        self.profiles = [dict(v, image=IMAGE) for v in self.defs.values()]

    def accepted(self, profile, when=NOW):
        return dict(profile=profile['name'], head=profile['head'], tree=profile['tree'],
                    image=profile['image'], codex_sha256=CODEX, time=when,
                    native_probe_sha256='d' * 64, quality=quality(profile['minimum_tests']))

    def save_receipt(self, p, body=None):
        rel = p.get('preparation', 'prepare-' + p['name'] + '/acceptance.json')
        dest = self.state / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(canonical(body or self.accepted(p)))
        return dest

    def test_transition_changes_only_reviewed_sn004_binding_and_preserves_main(self):
        result = self.r.targets(self.defs, self.profiles)
        self.assertEqual(result[0], self.profiles[0])
        expected = copy.deepcopy(self.profiles[1])
        expected.update(head='21ce4282e7ef8330cc1155bcb7b94fbf132032a8',
                        tree='29fe41a2873a3db13ac2c0dc74b7f149391c9eeb', minimum_tests=331)
        expected['locked']['elixir/test/symphony_control/runtime_config_test.exs'] = '5ca85121e627a8e085083fc2ea25b404c2fcd9c7'
        self.assertEqual(result[1], expected)
        self.assertEqual(self.profiles[1]['minimum_tests'], 328)

    def test_missing_duplicate_or_drifted_profile_cannot_be_refreshed(self):
        for profiles in [self.profiles[:1], self.profiles + self.profiles[:1],
                         [self.profiles[0], dict(self.profiles[1], minimum_tests=327)],
                         [dict(self.profiles[0], image='foreign'), self.profiles[1]]]:
            with self.subTest(profiles=profiles), self.assertRaises(Hold):
                self.r.targets(self.defs, profiles)

    def test_new_receipt_is_read_without_changing_legacy_receipt(self):
        p = self.profiles[0]
        legacy = self.save_receipt(p, self.accepted(p, NOW - 90000))
        old = legacy.read_bytes()
        current = dict(p, preparation='refresh-' + HEAD + '/main/acceptance.json')
        receipt = self.save_receipt(current)
        current['preparation_sha256'] = sha256(receipt.read_bytes())
        self.assertEqual(self.r.read_acceptance(self.state, current, CODEX, NOW)['time'], NOW)
        self.assertEqual(legacy.read_bytes(), old)

    def test_receipt_paths_are_closed_and_hash_is_required(self):
        p = self.profiles[0]
        for path in ['../outside', '/etc/passwd', 'refresh-' + HEAD + '/sn004/acceptance.json',
                     'refresh-' + HEAD + '/main/other.json', 'prepare-main/acceptance.json']:
            with self.subTest(path=path), self.assertRaises(Hold):
                self.r.read_acceptance(self.state, dict(p, preparation=path), CODEX, NOW)
        p = dict(p, preparation='refresh-' + HEAD + '/main/acceptance.json')
        self.save_receipt(p)
        with self.assertRaises(Hold):
            self.r.read_acceptance(self.state, p, CODEX, NOW)

    def test_changed_stale_future_or_wrong_identity_receipt_is_not_accepted(self):
        p = self.profiles[0]
        cases = [dict(time=NOW - 86400), dict(time=NOW + 1), dict(time=True),
                 dict(head='e' * 40), dict(tree='e' * 40), dict(profile='sn004'),
                 dict(codex_sha256='e' * 64), dict(image='sha256:' + 'e' * 64),
                 dict(quality=quality(304))]
        for delta in cases:
            self.save_receipt(p, dict(self.accepted(p), **delta))
            with self.subTest(delta=delta), self.assertRaises(Hold):
                self.r.read_acceptance(self.state, p, CODEX, NOW)

    def test_successful_but_stale_receipt_only_allowed_as_historical_input(self):
        p = self.profiles[0]
        self.save_receipt(p, self.accepted(p, NOW - 90000))
        self.assertEqual(self.r.read_acceptance(self.state, p, CODEX, NOW, fresh=False)['time'], NOW - 90000)
        with self.assertRaises(Hold):
            self.r.read_acceptance(self.state, p, CODEX, NOW)

    def flow(self):
        """Real filesystem and policy writes; only native/GitHub boundaries replaced."""
        self.policy = dict(installed_revision=self.r.BASE, enabled=False, profiles=self.profiles,
                           codex_sha256=CODEX, codex_binary='/usr/bin/fixture-codex',
                           github={}, github_key='private-reference', ruleset={})
        self.policy_path = self.etc / 'policy.json'
        self.policy_path.write_bytes(canonical(self.policy))
        (self.install / 'revision').write_text(self.r.BASE)
        (self.install / 'profiles.json').write_bytes(canonical(self.defs))
        (self.install / 'worker.py').write_text('fixture worker')
        (self.install / 'Dependency.Dockerfile').write_text('fixture recipe')
        self.historical = {}
        for p in self.profiles:
            receipt = self.save_receipt(p, self.accepted(p, NOW - 90000))
            (receipt.parent / 'Dependency.Dockerfile').write_text('fixture recipe')
            (receipt.parent / 'image.id').write_text(IMAGE)
            self.historical[p['name']] = receipt.read_bytes()
        self.native = []
        self.published = []
        self.o = types.SimpleNamespace(
            load_policy=lambda: json.loads(self.policy_path.read_bytes()),
            replace_policy=lambda p: (self.published.append(copy.deepcopy(p)), self.policy_path.write_bytes(canonical(p))),
            validate_policy=lambda p: None,
            BINARY='/usr/bin/fixture-codex', BINARY_SHA=CODEX)
        snapshot = {'policy': self.policy, 'policy_raw': self.policy_path.read_bytes(),
                    'definitions': self.defs, 'targets': self.r.targets(self.defs, self.profiles)}
        self.snapshot = snapshot
        self.api = types.SimpleNamespace()
        self.source = types.SimpleNamespace(materialize=lambda entries, p: p.mkdir())
        self.entries = {p['name']: {'elixir/mix.lock': {'sha': 'f' * 40}} for p in self.profiles}
        def check(*args):
            self.assertEqual(self.o.load_policy(), self.policy)
        def native(root, profile, *args):
            self.native.append(profile['name'])
            return quality(profile['minimum_tests']), 'd' * 64
        self.native_run = native
        for key, value in [('preflight', lambda *a: snapshot), ('recheck', check),
                           ('source_entries', lambda *a: self.entries), ('native_quality', native),
                           ('stage_package', self.stage), ('time', types.SimpleNamespace(time=lambda: NOW))]:
            mock = patch.object(self.r, key, value)
            mock.start()
            self.addCleanup(mock.stop)

    def stage(self, head, *args):
        dest = self.install.with_name(self.install.name + '-refresh-' + head)
        dest.mkdir()
        (dest / 'revision').write_text(head)
        return dest

    def test_both_pass_before_atomic_policy_publication_and_legacy_is_unchanged(self):
        self.flow()
        result = self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(self.native, ['main', 'sn004'])
        self.assertEqual(len(self.published), 1)
        policy = self.o.load_policy()
        self.assertFalse(policy['enabled'])
        self.assertEqual(policy['installed_revision'], HEAD)
        self.assertEqual(policy['profiles'][1]['minimum_tests'], 331)
        for p in policy['profiles']:
            self.r.read_acceptance(self.state, p, CODEX, NOW)
            self.assertEqual((self.state / ('prepare-' + p['name']) / 'acceptance.json').read_bytes(), self.historical[p['name']])
        self.assertTrue(result.is_file())
        self.assertEqual((self.install.with_name('install-before-refresh-' + HEAD) / 'revision').read_text(), self.r.BASE)

    def test_second_profile_failure_does_not_publish_or_replace_installation(self):
        self.flow()
        def fail(root, profile, *args):
            if profile['name'] == 'sn004':
                raise Hold('synthetic_quality_failure')
            return self.native_run(root, profile)
        with patch.object(self.r, 'native_quality', side_effect=fail), self.assertRaises(Hold):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(self.o.load_policy(), self.policy)
        self.assertEqual((self.install / 'revision').read_text(), self.r.BASE)
        self.assertEqual(self.published, [])
        self.assertTrue((self.state / ('refresh-' + HEAD) / 'main' / 'acceptance.json').exists())

    def test_existing_claim_prevents_repeating_native_work(self):
        self.flow()
        (self.state / ('refresh-' + HEAD)).mkdir()
        with self.assertRaises(Hold):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(self.native, [])

    def test_drift_before_commit_keeps_old_policy_and_installation(self):
        self.flow()
        with patch.object(self.r, 'recheck', side_effect=Hold('input_changed')), self.assertRaises(Hold):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(self.o.load_policy(), self.policy)
        self.assertEqual((self.install / 'revision').read_text(), self.r.BASE)
        self.assertEqual(self.published, [])

    def test_native_success_with_invalid_quality_never_publishes(self):
        self.flow()
        with patch.object(self.r, 'native_quality', return_value=(quality(1), 'd' * 64)), self.assertRaises(Hold):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(self.published, [])

    def test_package_scope_rejects_worker_or_threshold_changes(self):
        base = {'ci/continuous/owner.py': {'sha': 'b' * 40, 'mode': '100644'}}
        head = {p: {'sha': 'a' * 40, 'mode': '100644'} for p in self.r.DELTA}
        self.r.package_delta(base, head)
        for path in ['ci/continuous/worker.py', 'ci/continuous/profiles.json', 'elixir/mix.exs']:
            with self.subTest(path=path), self.assertRaises(Hold):
                self.r.package_delta(base, dict(head, **{path: {'sha': 'c' * 40, 'mode': '100644'}}))

    def test_receipt_digest_catches_post_verification_edit(self):
        p = dict(self.profiles[0], preparation='refresh-' + HEAD + '/main/acceptance.json')
        path = self.save_receipt(p)
        p['preparation_sha256'] = sha256(path.read_bytes())
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(Hold):
            self.r.read_acceptance(self.state, p, CODEX, NOW)

    def test_pending_publication_or_running_attempt_is_never_abandoned(self):
        self.assertTrue(hasattr(self.r, 'no_pending'), 'pending-attempt preflight missing')
        db = sqlite3.connect(self.state / 'journal.sqlite3')
        db.execute('CREATE TABLE attempts (state TEXT)')
        for state in ('running', 'publishing', 'unknown'):
            db.execute('DELETE FROM attempts')
            db.execute('INSERT INTO attempts VALUES (?)', (state,))
            db.commit()
            with self.subTest(state=state), self.assertRaises(Hold):
                self.r.no_pending()
        db.execute('DELETE FROM attempts')
        db.execute("INSERT INTO attempts VALUES ('success')")
        db.commit()
        self.r.no_pending()
        self.assertEqual(db.execute('SELECT state FROM attempts').fetchall(), [('success',)])
        db.close()

    def test_missing_journal_does_not_create_one(self):
        self.assertTrue(hasattr(self.r, 'no_pending'), 'pending-attempt preflight missing')
        self.r.no_pending()
        self.assertFalse((self.state / 'journal.sqlite3').exists())

    def test_service_and_timer_must_both_be_idle_and_disabled(self):
        def invoke(args, **kwargs):
            unit = args[2]
            out = ('Id=' + unit + '\nActiveState=inactive\nSubState=dead\n'
                   'MainPID=0\nUnitFileState=disabled\n')
            return types.SimpleNamespace(stdout=out.encode())
        owner = types.SimpleNamespace(run=invoke)
        self.r.stopped(owner)
        for old, new in [('inactive', 'active'), ('dead', 'running'),
                         ('MainPID=0', 'MainPID=10'), ('disabled', 'enabled')]:
            def bad(args, **kwargs):
                return types.SimpleNamespace(stdout=invoke(args).stdout.replace(old.encode(), new.encode()))
            with self.subTest(new=new), self.assertRaises(Hold):
                self.r.stopped(types.SimpleNamespace(run=bad))

    def test_package_integrity_checks_actual_bytes_and_manifest_membership(self):
        raw = b'original'
        (self.install / 'worker.py').write_bytes(raw)
        entries = {'ci/continuous/worker.py': dict(sha=blob_hash(raw), size=len(raw), mode='100644')}
        manifest = {'worker.py': sha256(raw)}
        (self.install / 'installed.json').write_bytes(canonical(manifest))
        self.r.verify_package(entries)
        (self.install / 'worker.py').write_bytes(b'changed')
        with self.assertRaises(Hold):
            self.r.verify_package(entries)
        (self.install / 'worker.py').write_bytes(raw)
        (self.install / 'installed.json').write_bytes(canonical({}))
        with self.assertRaises(Hold):
            self.r.verify_package(entries)

    def test_partial_install_failure_restores_original_package_and_keeps_evidence(self):
        self.flow()
        rename = Path.rename
        def fail(path, target):
            if path.name == 'install-refresh-' + HEAD:
                raise OSError('injected rename failure')
            return rename(path, target)
        with patch.object(Path, 'rename', fail), self.assertRaises(OSError):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual((self.install / 'revision').read_text(), self.r.BASE)
        self.assertEqual(self.o.load_policy(), self.policy)
        self.assertTrue((self.state / ('refresh-' + HEAD) / 'commit-intent.json').exists())

    def test_policy_failure_after_swap_is_uncommitted_and_cannot_replay(self):
        self.flow()
        self.o.replace_policy = lambda p: (_ for _ in ()).throw(OSError('injected policy failure'))
        with self.assertRaises(OSError):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(self.o.load_policy(), self.policy)
        self.assertEqual((self.install / 'revision').read_text(), HEAD)
        self.assertFalse((self.state / ('refresh-' + HEAD) / 'COMPLETE.json').exists())
        with self.assertRaises(Hold):
            self.r.perform(self.o, HEAD, self.api, self.source)

    def test_owner_guard_rejects_non_owner_before_policy_or_native_access(self):
        with patch.object(self.r.os, 'geteuid', return_value=997), self.assertRaisesRegex(Hold, 'owner_identity'):
            self.r.apply(HEAD)

    def activation(self):
        owner = importlib.import_module('owner')
        (self.install / 'installed.json').write_bytes(canonical({}))
        binary = self.root / 'codex'
        binary.write_bytes(b'fixture binary')
        for key, value in [('INSTALL', self.install), ('STATE', self.state), ('ETC', self.etc),
                           ('trusted', lambda p, **kw: binary if str(p) == '/usr/bin/fixture-codex' else Path(p)),
                           ('load_policy', self.o.load_policy), ('replace_policy', self.o.replace_policy),
                           ('validate_policy', lambda p: None), ('sha256', lambda b: CODEX),
                           ('time', types.SimpleNamespace(time=lambda: NOW)),
                           ('validate_rules', lambda *a: None)]:
            mock = patch.object(owner, key, value)
            mock.start()
            self.addCleanup(mock.stop)
        return owner

    def test_activation_requires_matching_completion_intent_policy_and_revision(self):
        self.flow()
        result = self.r.perform(self.o, HEAD, self.api, self.source)
        owner = self.activation()
        complete = result.read_bytes()
        intent_path = result.parent / 'commit-intent.json'
        intent = intent_path.read_bytes()
        policy = self.o.load_policy()
        cases = ('missing', 'partial', 'wrong_head', 'wrong_digest', 'intent', 'missing_intent',
                 'policy', 'pointer', 'stripped_pointers')
        for case in cases:
            result.write_bytes(complete)
            intent_path.write_bytes(intent)
            self.policy_path.write_bytes(canonical(policy))
            if case == 'missing': result.unlink()
            elif case == 'partial': result.write_bytes(b'{')
            elif case == 'intent': intent_path.write_bytes(canonical({'head': HEAD, 'policy_sha256': '0' * 64}))
            elif case == 'missing_intent': intent_path.unlink()
            elif case == 'policy': self.policy_path.write_bytes(canonical(dict(policy, extra='changed')))
            elif case == 'stripped_pointers':
                changed = copy.deepcopy(policy)
                for profile in changed['profiles']:
                    profile.pop('preparation')
                    profile.pop('preparation_sha256')
                self.policy_path.write_bytes(canonical(changed))
            elif case == 'pointer':
                changed = copy.deepcopy(policy)
                changed['profiles'][0]['preparation'] = 'refresh-' + 'e' * 40 + '/main/acceptance.json'
                self.policy_path.write_bytes(canonical(changed))
            else:
                record = json.loads(complete)
                record['head' if case == 'wrong_head' else 'policy_sha256'] = '0' * (40 if case == 'wrong_head' else 64)
                result.write_bytes(canonical(record))
            with self.subTest(case=case), patch.object(owner, 'GitHub') as github, patch.object(owner, 'run') as run:
                with self.assertRaises((Hold, OSError)):
                    owner.activate()
                github.assert_not_called()
                run.assert_not_called()
                self.assertFalse(self.o.load_policy()['enabled'])

    def test_completed_refresh_allows_existing_activation_checks(self):
        self.flow()
        self.r.perform(self.o, HEAD, self.api, self.source)
        owner = self.activation()
        with patch.object(owner, 'GitHub'), patch.object(owner, 'run') as run, \
                patch.object(owner.pwd, 'getpwnam', return_value=types.SimpleNamespace(pw_uid=1, pw_gid=1)), \
                patch.object(owner.subprocess, 'run'):
            owner.activate()
        self.assertTrue(self.o.load_policy()['enabled'])
        run.assert_called_once_with(['systemctl', 'enable', '--now', 'symphony-next-ci.timer'])

    def test_activation_rejects_changed_policy_bytes_with_identical_json(self):
        self.flow()
        self.r.perform(self.o, HEAD, self.api, self.source)
        owner = self.activation()
        policy = self.o.load_policy()
        raw = self.policy_path.read_bytes()
        variants = [raw + b'\n', json.dumps(policy, indent=2).encode(),
                    json.dumps(dict(reversed(list(policy.items()))), separators=(',', ':')).encode()]
        for changed in variants:
            self.assertNotEqual(changed, raw)
            self.assertEqual(json.loads(changed), policy)
            self.policy_path.write_bytes(changed)
            with self.subTest(serialization=changed[:30]), \
                    patch.object(owner, 'GitHub', side_effect=AssertionError('must hold before GitHub')) as github:
                with self.assertRaisesRegex(Hold, 'completion_mismatch'):
                    owner.activate()
                github.assert_not_called()
            self.assertFalse(self.o.load_policy()['enabled'])

    def test_policy_byte_readback_must_match_intent_before_completion(self):
        self.flow()
        publish = self.o.replace_policy
        def altered_serialization(policy):
            publish(policy)
            self.policy_path.write_bytes(self.policy_path.read_bytes() + b'\n')
        self.o.replace_policy = altered_serialization
        with self.assertRaisesRegex(Hold, 'policy_readback'):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(self.o.load_policy()['installed_revision'], HEAD)
        self.assertFalse((self.state / ('refresh-' + HEAD) / 'COMPLETE.json').exists())

    def test_failure_after_real_policy_publish_cannot_activate(self):
        self.flow()
        publish = self.o.replace_policy
        def fail(policy):
            publish(policy)
            raise OSError('injected failure after policy replace')
        self.o.replace_policy = fail
        with self.assertRaises(OSError):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(self.o.load_policy()['installed_revision'], HEAD)
        owner = self.activation()
        with patch.object(owner, 'GitHub') as github, self.assertRaises((Hold, OSError)):
            owner.activate()
        github.assert_not_called()
        self.assertFalse(self.o.load_policy()['enabled'])

    def test_completion_write_failure_after_file_creation_removes_activation_proof(self):
        self.flow()
        write = self.r.write_new
        def fail(path, *args):
            write(path, *args)
            if path.name == 'COMPLETE.json':
                raise OSError('injected completion durability failure')
        with patch.object(self.r, 'write_new', side_effect=fail), self.assertRaises(OSError):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(self.o.load_policy()['installed_revision'], HEAD)
        self.assertFalse((self.state / ('refresh-' + HEAD) / 'COMPLETE.json').exists())
        owner = self.activation()
        with patch.object(owner, 'GitHub') as github, self.assertRaises(Hold):
            owner.activate()
        github.assert_not_called()

    def test_failed_policy_readback_never_writes_completion_proof(self):
        self.flow()
        publish = self.o.replace_policy
        load = self.o.load_policy
        def stale_readback(policy):
            publish(policy)
            self.o.load_policy = lambda: self.policy
        self.o.replace_policy = stale_readback
        with self.assertRaisesRegex(Hold, 'policy_readback'):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual(load()['installed_revision'], HEAD)
        self.assertFalse((self.state / ('refresh-' + HEAD) / 'COMPLETE.json').exists())

    def test_directory_sync_failure_after_swap_preserves_both_packages(self):
        self.flow()
        sync = self.r.sync
        def fail(directory):
            if directory == self.install.parent and (self.install / 'revision').exists() \
                    and (self.install / 'revision').read_text() == HEAD:
                raise OSError('injected sync after swap')
            sync(directory)
        with patch.object(self.r, 'sync', side_effect=fail), self.assertRaisesRegex(Hold, 'reconcile_package_sync'):
            self.r.perform(self.o, HEAD, self.api, self.source)
        self.assertEqual((self.install / 'revision').read_text(), HEAD)
        self.assertEqual((self.install.with_name('install-before-refresh-' + HEAD) / 'revision').read_text(), self.r.BASE)
        self.assertEqual(self.o.load_policy(), self.policy)
        self.assertFalse((self.state / ('refresh-' + HEAD) / 'COMPLETE.json').exists())

    def test_reviewed_history_allows_bounded_repairs_without_rewriting_branch(self):
        commits = {}
        parent = self.r.BASE
        for sha in ['a' * 40, 'b' * 40, 'c' * 40, 'd' * 40]:
            commits[sha] = dict(sha=sha, parents=[{'sha': parent}], tree={'sha': 'f' * 40})
            parent = sha
        api = types.SimpleNamespace(request=lambda method, url: commits[url.rsplit('/', 1)[1]])
        for sha in ['a' * 40, 'b' * 40, 'c' * 40]:
            self.assertEqual(self.r.reviewed_commit(api, sha), commits[sha])
        with self.assertRaises(Hold):
            self.r.reviewed_commit(api, 'd' * 40)
        for parents in [[], [{'sha': self.r.BASE}, {'sha': 'e' * 40}], [{'sha': 'a' * 40}], [{'sha': '../bad'}]]:
            commits['a' * 40]['parents'] = parents
            with self.subTest(parents=parents), self.assertRaises(Hold):
                self.r.reviewed_commit(api, 'a' * 40)


if __name__ == '__main__':
    unittest.main()
