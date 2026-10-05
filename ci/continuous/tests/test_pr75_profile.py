"""Owner transition contracts; native Docker/transport are external boundaries."""
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import types
import signal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, canonical, decode, sha256, write_new
from snci import daily_limit, refresh, repair_review, runner
from snci.state import Journal
from snci.source import select_profile

ROOT = Path(__file__).resolve().parents[1]
HEAD = 'be5371e71db363d5a07c7109d6dd010a6ceca7ef'
TREE = 'b0f828141ca90851f6e037d6f1741aaaa28496de'
CI_HEAD = 'a' * 40
IMAGE = 'sha256:' + 'b' * 64


def module(test):
    try:
        return importlib.import_module('snci.pr75_profile')
    except ModuleNotFoundError:
        test.fail('Closed owner profile transition has not been implemented yet')


def quality():
    return {'stages': dict.fromkeys(('build', 'format', 'lint', 'coverage', 'dialyzer'), 0),
            'tests': 462, 'failures': 0, 'skipped': 6, 'coverage': 100.0, 'dialyzer_errors': 0,
            'source_before': True, 'source_after': True, 'cleanup': 0}


class DefinitionTests(unittest.TestCase):
    def setUp(self):
        # This executor's parent directories are writable; native trusted() is
        # exercised by the existing trust tests, not weakened for installation.
        try: m = importlib.import_module('snci.pr75_profile')
        except ModuleNotFoundError: return
        trust = patch.object(m, 'trusted', lambda p, **kw: Path(p))
        trust.start(); self.addCleanup(trust.stop)
    def definition(self):
        path = ROOT / 'profiles-pr75.json'
        self.assertTrue(path.exists(), 'No dependency-compatible protected profile exists yet')
        return decode(path.read_bytes())

    def test_reviewed_fixture_tampering_and_deletion_fail_profile_selection(self):
        profile = self.definition()
        entries = {path: {'sha': sha} for path, sha in profile['locked'].items()}
        policy = {'profiles': [profile]}
        self.assertEqual(select_profile(entries, policy)['name'], 'sn004')
        for path in ('elixir/test/support/auth_oidc_fixture.exs',
                     'elixir/test/symphony_control/auth/oidc_test.exs',
                     'elixir/test/symphony_control/project_read_http_test.exs',
                     'elixir/test/symphony_elixir/core_test.exs'):
            for replacement in ({'sha': '0' * 40}, None):
                bad = copy.deepcopy(entries)
                if replacement: bad[path] = replacement
                else: del bad[path]
                with self.subTest(path=path, replacement=replacement), self.assertRaises(Hold):
                    select_profile(bad, policy)

    def test_native_quality_must_reach_reviewed_count_and_keep_all_checks(self):
        profile = self.definition()
        self.assertEqual(runner.validate_result(quality(), profile)['tests'], 462)
        for key, value in [('tests', 461), ('skipped', 7), ('coverage', 99.99),
                           ('failures', 1), ('dialyzer_errors', 1), ('cleanup', 1),
                           ('source_after', False), ('stages', {})]:
            bad = quality(); bad[key] = value
            with self.subTest(key=key), self.assertRaises(Hold):
                runner.validate_result(bad, profile)

    def test_owner_transition_preserves_main_and_only_advances_reviewed_locks(self):
        m = module(self)
        definitions = decode((ROOT / 'profiles.json').read_bytes())
        profiles = refresh.targets(definitions, [dict(p, image=IMAGE) for p in definitions.values()])
        for p in profiles:
            p.update(preparation='refresh-' + 'f' * 40 + '/' + p['name'] + '/acceptance.json',
                     preparation_sha256='c' * 64)
        p = {'profiles': profiles, 'installed_revision': m.BASE, 'daily_attempts': None,
             'enabled': True, 'untouched': {'opaque': 'preserve'}}
        fresh = dict(self.definition(), image=IMAGE,
                     preparation='refresh-' + CI_HEAD + '/sn004/acceptance.json', preparation_sha256='d' * 64)
        before = copy.deepcopy(p)
        future = m.future_policy(p, CI_HEAD, fresh)
        self.assertEqual(p, before)
        self.assertEqual(future['profiles'][0], before['profiles'][0])
        self.assertEqual(future['untouched'], before['untouched'])
        self.assertIsNone(future['daily_attempts']); self.assertIs(future['enabled'], True)
        self.assertEqual(future['profiles'][1]['head'], HEAD)
        self.assertEqual(future['profiles'][1]['tree'], TREE)
        self.assertEqual(future['owner_request']['pr'], 75)

    def test_profile_cannot_delete_old_locks_or_introduce_unreviewed_suite_changes(self):
        m = module(self)
        defs = decode((ROOT / 'profiles.json').read_bytes())
        old = refresh.targets(defs, [dict(p, image=IMAGE) for p in defs.values()])[1]
        fresh = self.definition()
        m.validate_upgrade(old, fresh)
        for path in ('elixir/test/support/test_support.exs', 'elixir/config/runtime.exs'):
            bad = copy.deepcopy(fresh); bad['locked'][path] = '0' * 40
            with self.subTest(path=path), self.assertRaises(Hold):
                m.validate_upgrade(old, bad)
        bad = copy.deepcopy(fresh); del bad['locked']['elixir/test/symphony_control/http_test.exs']
        with self.assertRaises(Hold): m.validate_upgrade(old, bad)

    def test_commit_failure_before_policy_write_restores_old_package_and_keeps_evidence(self):
        m = module(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); install = root / 'installed'; stage = root / 'stage'; previous = root / 'old'
            install.mkdir(); stage.mkdir(); (install / 'marker').write_text('old'); (stage / 'marker').write_text('new')
            policy_path = root / 'policy.json'; before = b'{"old":true}'; after = b'{"new":true}'
            policy_path.write_bytes(before)
            class Owner:
                def replace_policy(self, _): raise OSError('synthetic write failure')
            with patch.object(m, 'INSTALL', install), patch.object(m, 'ETC', root), \
                 self.assertRaises(OSError):
                m.commit(Owner(), stage, previous, {'policy_raw': before}, {'new': True})
            self.assertEqual((install / 'marker').read_text(), 'old')
            self.assertEqual((stage / 'marker').read_text(), 'new')
            self.assertEqual(policy_path.read_bytes(), before)

    def test_unknown_successful_policy_write_keeps_new_package_without_replay(self):
        m = module(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); install = root / 'installed'; stage = root / 'stage'; previous = root / 'old'
            install.mkdir(); stage.mkdir(); (install / 'marker').write_text('old'); (stage / 'marker').write_text('new')
            policy_path = root / 'policy.json'; before = b'{"old":true}'; policy_path.write_bytes(before)
            class Owner:
                def replace_policy(self, value):
                    policy_path.write_bytes(canonical(value)); raise OSError('lost fsync response')
            with patch.object(m, 'INSTALL', install), patch.object(m, 'ETC', root), \
                 self.assertRaises(OSError):
                m.commit(Owner(), stage, previous, {'policy_raw': before}, {'new': True})
            self.assertEqual((install / 'marker').read_text(), 'new')
            self.assertEqual((previous / 'marker').read_text(), 'old')
            self.assertFalse(stage.exists())
            self.assertEqual(decode(policy_path.read_bytes()), {'new': True})


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.m = module(self)
        self.real_preflight = self.m.preflight
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.state = self.root / 'state'; self.etc = self.root / 'etc'
        self.inst = self.root / 'installed'
        for path in (self.state, self.etc, self.inst): path.mkdir(mode=0o700)
        defs = decode((ROOT / 'profiles.json').read_bytes())
        profiles = refresh.targets(defs, [dict(p, image=IMAGE) for p in defs.values()])
        for p in profiles:
            p.update(preparation='refresh-' + 'f' * 40 + '/' + p['name'] + '/acceptance.json',
                     preparation_sha256='c' * 64)
        self.policy = {'profiles': profiles, 'installed_revision': self.m.BASE, 'daily_attempts': None,
                       'enabled': True, 'codex_sha256': 'd' * 64, 'opaque': 'retained-fixture'}
        self.raw = canonical(self.policy); (self.etc / 'policy.json').write_bytes(self.raw)
        (self.inst / 'revision').write_text(self.m.BASE)
        write_new(self.inst / 'worker.py', b'original installed worker', 0o644)
        old_manifest = canonical({'worker.py': sha256(b'original installed worker')})
        write_new(self.inst / 'installed.json', old_manifest, 0o644)
        j = Journal(self.state / 'journal.sqlite3')
        old_key = j.claim({'pr': 14, 'head': 'e' * 40, 'base': 'f' * 40}, 'historical', None)
        j.set(old_key, 'hold', {'reason': 'historical-fixture'})
        rows = [list(row) for row in j.db.execute('SELECT key,target,policy,day,state,data FROM attempts')]
        j.close(); (self.state / 'old-evidence').write_bytes(b'immutable prior evidence')
        self.snapshot = {'policy': self.policy, 'policy_raw': self.raw, 'tree': 'c' * 40,
            'old_manifest': sha256(old_manifest), 'units': {},
            'history': {'rows': rows, 'files': {'old-evidence': sha256(b'immutable prior evidence')}},
            'seed': {'fixture': 'seed'}, 'daemon': {'fixture': 'daemon'}, 'recipe': b'unchanged recipe',
            'entries': {'candidate.exs': {'sha': blob_hash(b'candidate bytes'),
                                         'mode': '100644', 'size': 15}}}
        package_data = {'worker.py': b'original installed worker', 'marker': b'new package'}
        self.snapshot['package'] = {p: {'sha': blob_hash(raw),
                                       'mode': '100644', 'size': len(raw)} for p, raw in package_data.items()}
        self.snapshot['new'] = {'ci/continuous/' + p: e for p, e in self.snapshot['package'].items()}
        class Source:
            def blob(_, entry):
                return next(raw for raw in package_data.values()
                            if blob_hash(raw) == entry['sha'])
            def materialize(_, entries, directory):
                Path(directory).mkdir(); (Path(directory) / 'candidate.exs').write_bytes(b'candidate bytes')
        self.source = Source()
        root = self.root
        class Owner:
            def build_dependency_image(_, directory):
                write_new(directory / 'seed.json', canonical({'fixture': 'seed'}))
                write_new(directory / 'image.id', IMAGE.encode()); write_new(directory / 'build.log', b'fixture build')
                return IMAGE
            def verify_seed_build(_, seed, image):
                if seed != {'fixture': 'seed'} or image != IMAGE: raise Hold('fixture_image_identity')
            def inspect_image(_, ref): return {'Id': IMAGE}
            def validate_policy(_, p): pass  # Complete policy schema is covered separately.
            def replace_policy(_, p): (root / 'etc' / 'policy.json').write_bytes(canonical(p))
        self.owner = Owner()
        def probe(stage, owner, policy, path):
            write_new(path, b'fixture native transport'); return sha256(b'fixture native transport')
        retention = {'container': 'keeper-fixture', 'tag': 'localhost/fixture:retained', 'image': IMAGE}
        replacements = [(self.m, 'STATE', self.state), (self.m, 'ETC', self.etc), (self.m, 'INSTALL', self.inst),
            (self.m, 'POLICY_SHA', sha256(self.raw)),
            (refresh, 'INSTALL', self.inst), (self.m, 'preflight', lambda *a: copy.deepcopy(self.snapshot)),
            (self.m, 'native_probe', probe), (self.m.recover_retention, 'retain', lambda *a: retention),
            (self.m.recover_retention, 'keeper_verify', lambda *a: 'keeper-fixture'),
            (daily_limit, 'paused', lambda *a: {}), (runner, 'run', lambda *a: quality())]
        for mod in (self.m, refresh, repair_review, daily_limit):
            replacements.append((mod, 'trusted', lambda p, **kw: Path(p)))
        for obj, name, value in replacements:
            p = patch.object(obj, name, value); p.start(); self.addCleanup(p.stop)

    def test_prepare_is_not_acceptance_and_install_preserves_old_package_and_history(self):
        self.m.prepare(self.owner, CI_HEAD, None, self.source)
        directory, stage, previous = self.m.paths(CI_HEAD)
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.raw)
        self.assertFalse((directory / 'sn004/acceptance.json').exists())
        self.assertFalse((directory / 'COMPLETE.json').exists())
        self.m.install(self.owner, CI_HEAD, None, self.source)
        new = decode((self.etc / 'policy.json').read_bytes())
        self.assertEqual(new['profiles'][0], self.policy['profiles'][0])
        self.assertEqual((previous / 'worker.py').read_bytes(), b'original installed worker')
        self.assertEqual((self.state / 'old-evidence').read_bytes(), b'immutable prior evidence')
        self.assertEqual((self.inst / 'marker').read_bytes(), b'new package')
        self.assertEqual(self.m.validate_preparation(self.state, new, canonical(new))['status'],
                         'PR75_PROFILE_INSTALLED_PAUSED')
        # A new unresolved check row does not prevent read-only reconciliation.
        j = Journal(self.state / 'journal.sqlite3')
        key = j.claim({'pr': 75, 'head': HEAD, 'base': '1' * 40}, 'new-policy', None)
        j.set(key, 'publishing', {'check_body': 'synthetic'}); j.close()
        self.m.validate_preparation(self.state, new, canonical(new))

    def test_completed_owner_verification_rejects_current_package_tampering(self):
        self.m.prepare(self.owner, CI_HEAD, None, self.source)
        self.m.install(self.owner, CI_HEAD, None, self.source)
        raw = (self.etc / 'policy.json').read_bytes(); policy = decode(raw)
        previous = self.m.paths(CI_HEAD)[2]
        self.assertEqual(self.m.validate_preparation(self.state, policy, raw)['status'],
                         'PR75_PROFILE_INSTALLED_PAUSED')
        preserved = {path: path.read_bytes() for root in (self.state, previous)
                     for path in root.rglob('*') if path.is_file()}
        preserved.update({path: path.read_bytes() for path in
                          (self.etc / 'policy.json', self.inst / 'installed.json', self.inst / 'revision')})
        worker = self.inst / 'worker.py'; original_stat = worker.stat()
        worker.write_bytes(b'changed current installed worker')
        self.assertEqual((worker.stat().st_uid, worker.stat().st_mode),
                         (original_stat.st_uid, original_stat.st_mode))
        with self.assertRaisesRegex(Hold, 'daily_limit_package'):
            self.m.validate_preparation(self.state, policy, raw)
        self.assertEqual({path: path.read_bytes() for path in preserved}, preserved)

    def test_quality_failure_leaves_old_policy_and_blocks_replay(self):
        self.m.prepare(self.owner, CI_HEAD, None, self.source)
        bad = quality(); bad['cleanup'] = 1
        with patch.object(runner, 'run', return_value=bad), self.assertRaises(Hold):
            self.m.install(self.owner, CI_HEAD, None, self.source)
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.raw)
        self.assertFalse(self.m.paths(CI_HEAD)[2].exists())
        with self.assertRaisesRegex(Hold, 'pr75_quality_already_claimed'):
            self.m.install(self.owner, CI_HEAD, None, self.source)

    def test_archived_profile_proof_uses_actual_archive_without_rebinding_predecessor(self):
        self.m.prepare(self.owner, CI_HEAD, None, self.source)
        self.m.install(self.owner, CI_HEAD, None, self.source)
        raw = (self.etc / 'policy.json').read_bytes(); policy = decode(raw)
        archive = self.inst.with_name('archived-current')
        self.inst.rename(archive)
        self.inst.mkdir(); (self.inst / 'worker.py').write_bytes(b'different current package')
        try:
            proof = self.m.validate_preparation(self.state, policy, raw, package=archive)
        except TypeError:
            self.fail('Profile proof cannot validate its original archived package')
        self.assertEqual(proof['status'], 'PR75_PROFILE_INSTALLED_PAUSED')
        (archive / 'worker.py').write_bytes(b'changed archived worker')
        with self.assertRaisesRegex(Hold, 'daily_limit_package'):
            self.m.validate_preparation(self.state, policy, raw, package=archive)

    def test_prepared_source_tampering_cannot_start_quality_or_change_policy(self):
        self.m.prepare(self.owner, CI_HEAD, None, self.source)
        directory = self.m.paths(CI_HEAD)[0]
        (directory / 'sn004/source/candidate.exs').write_bytes(b'tampered bytes')
        with self.assertRaisesRegex(Hold, 'pr75_prepared_source'):
            self.m.install(self.owner, CI_HEAD, None, self.source)
        self.assertFalse((directory / 'quality-started.json').exists())
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.raw)

    def test_policy_drift_and_non_idle_preflight_cannot_claim_prepare(self):
        (self.etc / 'policy.json').write_bytes(canonical(dict(self.policy, daily_attempts=4)))
        with patch.object(self.m, 'preflight', self.real_preflight), patch.object(refresh, 'idle_native'):
            with self.assertRaisesRegex(Hold, 'pr75_policy_binding'):
                self.m.prepare(self.owner, CI_HEAD, None, self.source)
        self.assertFalse(self.m.paths(CI_HEAD)[0].exists())
        with patch.object(self.m, 'preflight', self.real_preflight), \
             patch.object(daily_limit, 'paused', side_effect=Hold('daily_limit_units')):
            with self.assertRaisesRegex(Hold, 'daily_limit_units'):
                self.m.prepare(self.owner, CI_HEAD, None, self.source)
        self.assertFalse(self.m.paths(CI_HEAD)[0].exists())

    def test_claimed_prepare_is_never_replayed(self):
        self.m.prepare(self.owner, CI_HEAD, None, self.source)
        with self.assertRaisesRegex(Hold, 'pr75_already_claimed'):
            self.m.prepare(self.owner, CI_HEAD, None, self.source)


class BudgetTests(unittest.TestCase):
    def test_whole_leaf_deadline_interrupts_code_outside_subprocess_waits(self):
        m = module(self)
        old = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, lambda *a: None)
        owner = types.SimpleNamespace(run=lambda *a, **kw: None)
        try:
            with m.bounded_commands(owner), self.assertRaisesRegex(Hold, 'pr75_deadline'):
                signal.getsignal(signal.SIGALRM)(signal.SIGALRM, None)
        finally:
            signal.signal(signal.SIGALRM, old)


if __name__ == '__main__':
    unittest.main()
