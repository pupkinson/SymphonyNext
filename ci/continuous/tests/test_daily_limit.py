"""Explicit unlimited admission; durable accounting and paused owner transition."""
import copy
import importlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, canonical, decode, sha256
from snci.controller import validate_policy
from snci.state import Journal
from snci import refresh, repair_review


def policy(limit):
    rules = {'id': 23980199, 'target': 'branch', 'source': 'pupkinson/SymphonyNext',
             'source_type': 'Repository', 'enforcement': 'active', 'updated_at': 'fixture',
             'conditions': {'ref_name': {'include': ['~DEFAULT_BRANCH'], 'exclude': []}},
             'rules': [{'type': 'required_status_checks', 'parameters': {'required_status_checks': [
                 {'context': 'symphony-next/verified-tests', 'integration_id': 5069157}]}}],
             'bypass_actors': []}
    return {'schema': 'snci-policy/v1', 'repository': 'pupkinson/SymphonyNext',
            'enabled': True, 'daily_attempts': limit, 'review_seconds': 900,
            'codex_binary': '/usr/bin/fixture-codex', 'codex_sha256': 'a' * 64,
            'profiles': [{'name': 'fixture', 'minimum_tests': 305, 'maximum_skips': 6,
                          'image': 'sha256:' + 'b' * 64, 'locked': {
                              'elixir/mix.exs': 'c' * 40, 'elixir/mix.lock': 'd' * 40,
                              'elixir/test/test_helper.exs': 'e' * 40,
                              'elixir/test/fixture_test.exs': 'f' * 40}}], 'ruleset': rules}


def target(index):
    return {'pr': 14, 'head': f'{index:040x}', 'base': 'b' * 40}


class UnlimitedPolicyTests(unittest.TestCase):
    def test_explicit_null_accepts_a_complete_policy(self):
        try:
            validate_policy(policy(None))
        except Hold as error:
            self.fail('Explicit unlimited policy rejected: ' + str(error))

    def test_missing_limit_is_not_implicit_unlimited(self):
        value = policy(None)
        del value['daily_attempts']
        with self.assertRaisesRegex(Hold, 'policy_limits'):
            validate_policy(value)

    def test_finite_policy_still_requires_integer_one_through_four(self):
        for value in (1, 2, 3, 4):
            validate_policy(policy(value))
        for value in (False, True, 0, -1, 5, 1.0, 'unlimited', [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(Hold, 'policy_limits'):
                validate_policy(policy(value))


class UnlimitedJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'journal.sqlite3'
        self.j = Journal(self.path)

    def tearDown(self):
        self.j.close()
        self.tmp.cleanup()

    def unlimited_claim(self, value):
        try:
            return self.j.claim(value, 'unlimited-policy', None)
        except (Hold, TypeError) as error:
            self.fail('Unlimited journal admission failed: ' + str(error))

    def test_unlimited_admits_new_work_after_four_existing_holds(self):
        old = []
        for index in range(1, 5):
            key = self.j.claim(target(index), 'old-policy', 4)
            self.j.set(key, 'hold', {'reason': 'review_not_ready'})
            old.append(self.j.get(key))
        for index in range(5, 8):
            self.assertIsNotNone(self.unlimited_claim(target(index)))
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM attempts').fetchone()[0], 7)
        self.assertEqual([self.j.get(row['key']) for row in old], old)

    def test_unlimited_accounting_survives_restart_and_exact_hold_is_not_replayed(self):
        key = self.unlimited_claim(target(1))
        self.j.set(key, 'hold', {'reason': 'review_not_ready'})
        saved = copy.deepcopy(self.j.get(key))
        self.j.close()
        self.j = Journal(self.path)
        self.assertIsNone(self.unlimited_claim(target(1)))
        self.assertIsNotNone(self.unlimited_claim(target(2)))
        self.assertEqual(self.j.get(key), saved)
        with self.assertRaisesRegex(Hold, 'terminal_attempt'):
            self.j.set(key, 'running', {})

    def test_finite_mode_counts_attempts_previously_admitted_without_ceiling(self):
        self.unlimited_claim(target(1))
        with self.assertRaisesRegex(Hold, 'daily_budget'):
            self.j.claim(target(2), 'finite-policy', 1)
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM attempts').fetchone()[0], 1)

    def test_invalid_limit_creates_no_journal_row(self):
        for index, value in enumerate((False, True, 0, -1, 5, 1.0, 'unlimited', [], {}), 1):
            with self.subTest(value=value), self.assertRaisesRegex(Hold, 'policy_limits'):
                self.j.claim(target(index), 'bad-policy', value)
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM attempts').fetchone()[0], 0)


class PausedDailyLimitTests(unittest.TestCase):
    """Real files, SQLite and atomic policy writes; only external reads are doubled."""
    def setUp(self):
        try:
            self.r = importlib.import_module('snci.daily_limit')
        except ImportError:
            self.fail('Paused owner transition for unlimited admission is absent')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.install = self.root / 'install'
        self.state = self.root / 'state'
        self.etc = self.root / 'etc'
        for path in (self.install, self.state, self.etc):
            path.mkdir()
        self.head = 'a' * 40
        self.blobs = {}

        def entry(raw):
            digest = blob_hash(raw)
            self.blobs[digest] = raw
            return {'sha': digest, 'size': len(raw), 'mode': '100644'}

        self.old = {'ci/continuous/owner.py': entry(b'UNCHANGED_OWNER'),
                    'ci/continuous/snci/reviewer.py': entry(b'UNCHANGED_REVIEWER'),
                    'ci/continuous/snci/runner.py': entry(b'UNCHANGED_WORKER')}
        for name in self.r.DELTA:
            if not name.endswith(('daily_limit.py', 'test_daily_limit.py')):
                self.old[name] = entry(('old:' + name).encode())
        self.new = copy.deepcopy(self.old)
        for name in self.r.DELTA:
            self.new[name] = entry(('new:' + name).encode())
        self.manifest = {}
        for name, value in self.old.items():
            relative = name[len('ci/continuous/'):]
            path = self.install / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.blobs[value['sha']])
            self.manifest[relative] = sha256(path.read_bytes())
        (self.install / 'installed.json').write_bytes(canonical(self.manifest))
        (self.install / 'revision').write_text(self.r.BASE)
        (self.install / 'review-empty').mkdir()
        self.binary = self.root / 'codex'
        self.binary.write_bytes(b'UNCHANGED_NATIVE_BINARY')
        self.policy = policy(4)
        self.policy.update(installed_revision=self.r.BASE, codex_binary=str(self.binary),
                           codex_sha256=sha256(self.binary.read_bytes()))
        profile = self.policy['profiles'][0]
        profile['preparation'] = 'refresh-old/fixture/acceptance.json'
        receipt = self.state / profile['preparation']
        receipt.parent.mkdir(parents=True)
        receipt.write_bytes(b'IMMUTABLE_QUALITY_RECEIPT')
        profile['preparation_sha256'] = sha256(receipt.read_bytes())
        (receipt.parent / 'retention.json').write_bytes(b'IMMUTABLE_RETENTION_BINDING')
        prior = self.state / 'source-contract-old'
        prior.mkdir()
        (prior / 'COMPLETE.json').write_bytes(b'IMMUTABLE_PREDECESSOR_PROOF')
        self.before = canonical(self.policy)
        (self.etc / 'policy.json').write_bytes(self.before)
        self.digest = sha256(self.before)
        self.key = sha256(canonical([self.r.TARGET, self.digest]))
        self.attempt = self.state / 'attempts' / self.key
        self.attempt.mkdir(parents=True)
        self.inputs = canonical({'target': dict(self.r.TARGET, tree=self.r.TREE),
                                 'policy_sha256': self.digest, 'profile': 'fixture'})
        self.review = canonical({'verdict': dict(self.r.TARGET, tree=self.r.TREE,
                                  verdict='CHANGES_REQUESTED', findings=[{'severity': 'high'}])})
        (self.attempt / 'inputs.json').write_bytes(self.inputs)
        (self.attempt / 'review.json').write_bytes(self.review)
        with sqlite3.connect(self.state / 'journal.sqlite3') as db:
            db.execute('CREATE TABLE attempts(key TEXT PRIMARY KEY,target TEXT,policy TEXT,day TEXT,state TEXT,data TEXT)')
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?)',
                       (self.key, canonical(self.r.TARGET).decode(), self.digest, '2026-10-03',
                        'hold', canonical({'reason': 'review_not_ready'}).decode()))
        trees = {self.r.BASE: (self.r.BASE_TREE, self.old), self.head: ('c' * 40, self.new)}
        self.source = types.SimpleNamespace(tree=lambda head: copy.deepcopy(trees[head]),
                                            blob=lambda value: self.blobs[value['sha']])
        self.events = []

        def run(args, **kwargs):
            self.events.append(args)
            if args[:2] != ['systemctl', 'show']:
                raise AssertionError('Unexpected native action: ' + str(args))
            unit = args[2]
            fields = dict(Id=unit, LoadState='loaded', ActiveState='inactive', SubState='dead',
                          UnitFileState='disabled', MainPID='0', ControlPID='0')
            if unit.endswith('.service'):
                fields.update(ActiveState='failed', SubState='failed', UnitFileState='static')
            return types.SimpleNamespace(stdout=''.join(f'{key}={value}\n' for key, value in fields.items()).encode())

        def replace(value):
            pending = self.etc / 'policy.new'
            pending.write_bytes(canonical(value))
            pending.replace(self.etc / 'policy.json')

        self.owner = types.SimpleNamespace(run=run, validate_policy=lambda value: None,
                                          replace_policy=replace, BINARY=str(self.binary),
                                          BINARY_SHA=sha256(self.binary.read_bytes()))
        self.api = types.SimpleNamespace()
        for module in (self.r, refresh, repair_review):
            self.patched(module, 'trusted', lambda path, **kwargs: Path(path))
        for module in (self.r, refresh):
            for name, value in [('INSTALL', self.install), ('STATE', self.state), ('ETC', self.etc)]:
                self.patched(module, name, value)
        for name, value in [('POLICY_SHA', self.digest), ('ATTEMPT_KEY', self.key),
                            ('INPUTS_SHA', sha256(self.inputs)), ('REVIEW_SHA', sha256(self.review))]:
            self.patched(self.r, name, value)
        self.patched(refresh, 'reviewed_commit', lambda *args, **kwargs: {'tree': {'sha': 'c' * 40}})

    def patched(self, module, name, value):
        active = patch.object(module, name, value)
        active.start()
        self.addCleanup(active.stop)

    def perform(self):
        return self.r.perform(self.owner, self.head, self.api, self.source)

    def retained(self):
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.before)
        self.assertEqual((self.install / 'revision').read_text(), self.r.BASE)

    def test_install_removes_only_ceiling_and_revision_preserves_history_and_stays_paused(self):
        journal = (self.state / 'journal.sqlite3').read_bytes()
        old_files = {str(path.relative_to(self.state)): path.read_bytes()
                     for path in self.state.rglob('*.json')}
        proof = self.perform()
        future = dict(self.policy, installed_revision=self.head, daily_attempts=None)
        self.assertEqual(decode((self.etc / 'policy.json').read_bytes()), future)
        self.assertEqual((self.state / 'journal.sqlite3').read_bytes(), journal)
        for name, raw in old_files.items():
            self.assertEqual((self.state / name).read_bytes(), raw)
        self.assertEqual((self.r.backup(self.head) / 'revision').read_text(), self.r.BASE)
        self.assertEqual(proof['status'], 'DAILY_LIMIT_REMOVED_PAUSED')
        self.r.completed(self.state, future, canonical(future), self.owner)
        self.assertTrue(self.events)
        self.assertTrue(all(event[:2] == ['systemctl', 'show'] for event in self.events))

    def test_wrong_policy_inputs_or_review_refuses_without_claim(self):
        for name in ('POLICY_SHA', 'INPUTS_SHA', 'REVIEW_SHA'):
            with self.subTest(name=name), patch.object(self.r, name, 'f' * 64), self.assertRaises(Hold):
                self.perform()
            self.retained()
            self.assertFalse((self.state / ('daily-limit-' + self.head)).exists())

    def test_running_attempt_refuses_without_claim(self):
        with sqlite3.connect(self.state / 'journal.sqlite3') as db:
            db.execute("UPDATE attempts SET state='running'")
        with self.assertRaisesRegex(Hold, 'daily_limit_pending'):
            self.perform()
        self.retained()

    def test_active_timer_or_nonzero_control_pid_refuses_without_claim(self):
        original = self.owner.run
        for before, after in [(b'ActiveState=inactive', b'ActiveState=active'),
                              (b'ControlPID=0', b'ControlPID=123')]:
            def active(args, **kwargs):
                result = original(args, **kwargs)
                result.stdout = result.stdout.replace(before, after)
                return result
            self.owner.run = active
            with self.subTest(after=after), self.assertRaisesRegex(Hold, 'daily_limit_units'):
                self.perform()
            self.retained()

    def test_delta_cannot_change_reviewer_worker_or_any_other_path(self):
        for name in ('ci/continuous/snci/reviewer.py', 'ci/continuous/snci/runner.py', 'outside.py'):
            changed = copy.deepcopy(self.new)
            changed[name] = changed['ci/continuous/snci/daily_limit.py']
            source = types.SimpleNamespace(tree=lambda head: (self.r.BASE_TREE, self.old)
                                           if head == self.r.BASE else ('c' * 40, changed))
            with self.subTest(path=name), self.assertRaisesRegex(Hold, 'daily_limit_scope'):
                self.r.preflight(self.owner, self.head, self.api, source)
        self.retained()

    def test_receipt_drift_is_detected_before_replacement_and_blocks_replay(self):
        original = refresh.stage_package
        def drift(head, snapshot, source):
            stage = original(head, snapshot, source)
            (self.state / self.policy['profiles'][0]['preparation']).write_bytes(b'DRIFT')
            return stage
        self.patched(refresh, 'stage_package', drift)
        with self.assertRaisesRegex(Hold, 'daily_limit_receipt'):
            self.perform()
        self.retained()
        with self.assertRaisesRegex(Hold, 'daily_limit_already_claimed'):
            self.perform()

    def test_staged_byte_drift_is_detected_before_replacement(self):
        original = refresh.stage_package
        def drift(head, snapshot, source):
            stage = original(head, snapshot, source)
            (stage / 'owner.py').write_bytes(b'DRIFT')
            return stage
        self.patched(refresh, 'stage_package', drift)
        with self.assertRaisesRegex(Hold, 'review_install_stage_bytes'):
            self.perform()
        self.retained()

    def test_package_drift_before_claim_is_rejected(self):
        (self.install / 'owner.py').write_bytes(b'DRIFT')
        with self.assertRaisesRegex(Hold, 'refresh_installed_changed'):
            self.perform()
        self.assertFalse((self.state / ('daily-limit-' + self.head)).exists())

    def test_failed_policy_write_restores_old_package_and_blocks_replay(self):
        def fail(value):
            raise OSError('controlled failure before policy replacement')
        self.owner.replace_policy = fail
        with self.assertRaises(OSError):
            self.perform()
        self.retained()
        self.assertTrue((self.state / ('daily-limit-' + self.head) / 'commit-intent.json').exists())
        self.assertFalse((self.state / ('daily-limit-' + self.head) / 'COMPLETE.json').exists())
        with self.assertRaisesRegex(Hold, 'daily_limit_already_claimed'):
            self.perform()

    def test_error_after_policy_replacement_keeps_matching_package_and_intent(self):
        original = self.owner.replace_policy
        def fail(value):
            original(value)
            raise OSError('controlled failure after policy replacement')
        self.owner.replace_policy = fail
        with self.assertRaises(OSError):
            self.perform()
        self.assertEqual(decode((self.etc / 'policy.json').read_bytes()),
                         dict(self.policy, installed_revision=self.head, daily_attempts=None))
        self.assertEqual((self.install / 'revision').read_text(), self.head)
        self.assertTrue(self.r.backup(self.head).exists())
        self.assertFalse((self.state / ('daily-limit-' + self.head) / 'COMPLETE.json').exists())

    def test_completion_checks_old_rows_as_immutable_subset_after_future_work(self):
        self.perform()
        value = decode((self.etc / 'policy.json').read_bytes())
        with sqlite3.connect(self.state / 'journal.sqlite3') as db:
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?)',
                       (sha256(canonical([target(99), sha256(canonical(value))])),
                        canonical(target(99)).decode(), sha256(canonical(value)), '2026-10-04', 'hold', '{}'))
        self.r.completed(self.state, value, canonical(value), self.owner)
        with sqlite3.connect(self.state / 'journal.sqlite3') as db:
            db.execute("UPDATE attempts SET data='{}' WHERE key=?", (self.key,))
        with self.assertRaisesRegex(Hold, 'daily_limit_history'):
            self.r.completed(self.state, value, canonical(value), self.owner)

    def test_partial_completion_is_removed_and_cannot_certify_installation(self):
        original = self.r.write_new
        def fail(path, raw, *args):
            if path.name == 'COMPLETE.json':
                path.write_bytes(b'{"partial":true}')
                raise OSError('controlled completion write failure')
            return original(path, raw, *args)
        self.patched(self.r, 'write_new', fail)
        with self.assertRaises(OSError):
            self.perform()
        directory = self.state / ('daily-limit-' + self.head)
        self.assertFalse((directory / 'COMPLETE.json').exists())
        future = decode((self.etc / 'policy.json').read_bytes())
        with self.assertRaises(OSError):
            self.r.completed(self.state, future, canonical(future), self.owner)
        with self.assertRaisesRegex(Hold, 'daily_limit_already_claimed'):
            self.perform()

    def test_non_owner_cannot_enter_apply_path(self):
        with patch.object(self.r.os, 'geteuid', return_value=997), self.assertRaisesRegex(Hold, 'daily_limit_owner_identity'):
            self.r.apply(self.head)


if __name__ == '__main__':
    unittest.main()
