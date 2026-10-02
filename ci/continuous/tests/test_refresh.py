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


if __name__ == '__main__':
    unittest.main()
