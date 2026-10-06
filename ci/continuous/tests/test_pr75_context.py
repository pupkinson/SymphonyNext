"""PR75 dependency-context admission is exact and preserves its predecessor."""
import copy
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, canonical, decode, sha256, blob_hash, write_new
from snci.source import PR75_REQUEST, PR75_SUCCESSOR_REQUEST, validate_owner_request, validate_target, select_profile
from snci import controller, repair_pr75_target, runner

REQUEST = dict(PR75_REQUEST, head='6925de7e291d8cb36f83493d254679527a83c34d',
               tree='b10931da9fa383bb5f22ca36f5f89e0038385e25')
ADVANCES = {'elixir/test/support/auth_oidc_fixture.exs': '8656a8602b7641b1f0a6450ab95f221b2d8b3405',
            'elixir/test/symphony_control/auth/oidc_test.exs': 'be43772cf9dfb2ec029203d59b66becbd4ac1b05'}


def candidate(request=REQUEST):
    return dict(number=75, state='open', merged=False, draft=True, labels=[], **{
        side: dict(sha=request[side], ref=request[side+'_ref'], repo={'id': request['repository_id']})
        for side in ('head', 'base')})


class ContextAdmissionTests(unittest.TestCase):
    def setUp(self):
        from snci import pr75_profile
        for module in (pr75_profile, repair_pr75_target):
            guard = patch.object(module, 'trusted', lambda p, **kw: Path(p))
            guard.start(); self.addCleanup(guard.stop)

    def test_exact_context_request_is_admitted(self):
        validate_owner_request(REQUEST)
        self.assertEqual(validate_target(candidate(), owner_request=REQUEST),
                         {k: REQUEST[k] for k in ('pr', 'head', 'base')})

    def test_reviewed_two_lock_profile_matches_new_source(self):
        old = repair_pr75_target.definition()
        expected = dict(old, head=REQUEST['head'], tree=REQUEST['tree'], minimum_tests=507,
                        locked=dict(old['locked'], **ADVANCES))
        entries = {p: {'sha': b} for p, b in expected['locked'].items()}
        try: module = importlib.import_module('snci.repair_pr75_context')
        except ModuleNotFoundError: module = repair_pr75_target
        with patch.object(module, 'trusted', lambda p, **kw: Path(p)):
            actual = module.definition()
        self.assertEqual(select_profile(entries, {'profiles': [actual]}), expected)

    def test_all_other_sixty_six_locks_reject_source_drift(self):
        old = repair_pr75_target.definition()
        profile = dict(old, head=REQUEST['head'], tree=REQUEST['tree'], minimum_tests=507,
                       locked=dict(old['locked'], **ADVANCES))
        entries = {p: {'sha': b} for p, b in profile['locked'].items()}
        unchanged = set(profile['locked']) - set(ADVANCES)
        self.assertEqual(len(unchanged), 66)
        for path in unchanged:
            changed = copy.deepcopy(entries); changed[path]['sha'] = '0'*40
            with self.subTest(path=path), self.assertRaisesRegex(Hold, 'no_unique_quality_profile'):
                select_profile(changed, {'profiles': [profile]})

    def test_old_policy_rejects_new_live_target(self):
        for old in (PR75_REQUEST, PR75_SUCCESSOR_REQUEST):
            with self.subTest(old=old['head']), self.assertRaisesRegex(Hold, 'owner_request_target'):
                validate_target(candidate(), owner_request=old)

    def test_unreviewed_or_extended_requests_remain_closed(self):
        for key, value in (('head', 'a'*40), ('tree', 'a'*40), ('base', 'b'*40),
                           ('head_ref', 'other'), ('base_ref', 'main'), ('draft', False), ('extra', True)):
            with self.subTest(key=key), self.assertRaises(Hold):
                validate_owner_request(dict(REQUEST, **{key: value}))


class ContextTransitionTests(unittest.TestCase):
    def setUp(self):
        import test_pr75_target as fixture
        fixture.SuccessorTransitionTests.setUp(self)
        predecessor = self.m
        self.m = importlib.import_module('snci.repair_pr75_context')
        predecessor.perform(self.owner, self.m.BASE, None, self.source)
        self.original_raw = (self.etc / 'policy.json').read_bytes()
        old = decode(self.original_raw)
        from snci.state import Journal
        from snci import daily_limit
        journal = Journal(self.state / 'journal.sqlite3')
        key = journal.claim({k: PR75_SUCCESSOR_REQUEST[k] for k in ('pr', 'head', 'base')},
                            sha256(self.original_raw), None)
        journal.set(key, 'hold', {'reason': 'review_not_ready'}); journal.close()
        root = self.state / 'attempts' / key; root.mkdir()
        inputs = canonical({'target': PR75_SUCCESSOR_REQUEST})
        review = canonical({'verdict': {'verdict': 'CHANGES_REQUESTED'}})
        write_new(root / 'inputs.json', inputs); write_new(root / 'review.json', review)
        data = {'worker.py': b'original installed worker', 'marker': b'context package'}
        entries = {p: {'sha': blob_hash(raw), 'mode': '100644', 'size': len(raw)} for p, raw in data.items()}
        patches = [(self.m, 'STATE', self.state), (self.m, 'ETC', self.etc), (self.m, 'INSTALL', self.inst),
            (self.m, 'trusted', lambda p, **kw: Path(p)), (self.m, 'POLICY_SHA', sha256(self.original_raw)),
            (self.m, 'ORIGINAL_COMPLETE_SHA', sha256((self.state / ('pr75-target-' + self.m.BASE) / 'COMPLETE.json').read_bytes())),
            (self.m, 'HOLD_KEY', key), (self.m, 'INPUTS_SHA', sha256(inputs)), (self.m, 'REVIEW_SHA', sha256(review)),
            (self.m, 'IMAGE', old['profiles'][1]['image'])]
        for obj, name, value in patches:
            guard = patch.object(obj, name, value); guard.start(); self.addCleanup(guard.stop)
        locked = {p: {'sha': b, 'mode': '100644', 'size': 1} for p, b in self.m.definition()['locked'].items()}
        self.snapshot = dict(policy=old, policy_raw=self.original_raw, tree='6'*40, package=entries,
            new={'ci/continuous/'+p: e for p, e in entries.items()},
            old_manifest=sha256((self.inst / 'installed.json').read_bytes()), units={},
            history=self.m.history(old, 'c'*40), entries=locked)
        self.real_preflight = self.m.preflight
        guard = patch.object(self.m, 'preflight', lambda *a: copy.deepcopy(self.snapshot))
        guard.start(); self.addCleanup(guard.stop)
        class Source:
            def blob(_, entry): return next(raw for raw in data.values() if blob_hash(raw) == entry['sha'])
            def materialize(_, entries, directory):
                Path(directory).mkdir(); (Path(directory) / 'candidate.exs').write_bytes(b'fixture')
        self.source = Source()
        self.worker.return_value = dict(self.worker.return_value, tests=507)
        self.worker.reset_mock()
        self.held = {p: p.read_bytes() for p in root.iterdir()}

    def perform(self): return self.m.perform(self.owner, 'c'*40, None, self.source)

    def proof(self):
        raw = (self.etc / 'policy.json').read_bytes()
        return self.m.validate_preparation(self.state, decode(raw), raw)

    def test_fresh_quality_advances_exactly_two_locks_and_preserves_every_predecessor_artifact(self):
        old = decode(self.original_raw); result = self.perform()
        new = decode((self.etc / 'policy.json').read_bytes())
        self.assertEqual(result['status'], 'PR75_CONTEXT_INSTALLED_PAUSED')
        self.assertEqual(new['owner_request'], REQUEST)
        self.assertEqual(new['profiles'][0], old['profiles'][0])
        a, b = old['profiles'][1], new['profiles'][1]
        self.assertEqual(a['image'], b['image']); self.assertEqual(b['minimum_tests'], 507)
        self.assertEqual(b['maximum_skips'], 6); self.assertEqual(len(b['locked']), 68)
        self.assertEqual({p for p in a['locked'] if a['locked'][p] != b['locked'][p]}, set(ADVANCES))
        self.assertEqual({p: p.read_bytes() for p in self.held}, self.held)
        self.worker.assert_called_once(); self.proof()
        self.assertTrue(any(p.startswith('pr75-target-') for p in self.snapshot['history']['files']))
        self.assertTrue(any(p.startswith('review-paging-') for p in self.snapshot['history']['files']))

    def test_new_pending_publication_does_not_change_historical_rows(self):
        from snci.state import Journal
        self.perform(); raw = (self.etc / 'policy.json').read_bytes()
        journal = Journal(self.state / 'journal.sqlite3')
        key = journal.claim({k: REQUEST[k] for k in ('pr', 'head', 'base')}, sha256(raw), None)
        journal.set(key, 'publishing', {'fixture': 'unknown outcome'}); journal.close(); self.proof()

    def test_current_and_all_archived_packages_are_rehashed(self):
        self.perform()
        roots = [self.inst, self.m.paths('c'*40)[2]] + sorted(self.inst.parent.glob('installed-before-*'))
        self.assertGreaterEqual(len(roots), 3)
        for root in roots:
            path = root / 'worker.py'; raw = path.read_bytes(); path.write_bytes(b'changed package')
            with self.subTest(root=root.name), self.assertRaisesRegex(Hold, 'daily_limit_package'): self.proof()
            path.write_bytes(raw)

    def test_predecessor_proof_inputs_intent_logs_and_hold_artifacts_are_immutable(self):
        # Add a pre-existing log, then rebuild the snapshot as a native preflight would.
        log = self.state / ('pr75-target-' + self.m.BASE) / 'quality.log'
        log.write_bytes(b'predecessor quality log')
        self.snapshot['history'] = self.m.history(self.snapshot['policy'], 'c'*40)
        self.perform()
        paths = [log, self.state / ('pr75-target-' + self.m.BASE) / 'COMPLETE.json',
                 self.state / ('pr75-target-' + self.m.BASE) / 'inputs.json',
                 self.state / ('pr75-target-' + self.m.BASE) / 'commit-intent.json', *self.held]
        for path in paths:
            raw = path.read_bytes(); path.write_bytes(b'changed predecessor')
            with self.subTest(path=path.name), self.assertRaises(Hold): self.proof()
            path.write_bytes(raw)

    def test_historical_rows_and_latest_hold_result_cannot_change(self):
        from snci.state import Journal
        self.perform(); journal = Journal(self.state / 'journal.sqlite3')
        with journal.db: journal.db.execute("UPDATE attempts SET state='success' WHERE key=?", (self.m.HOLD_KEY,))
        journal.close()
        with self.assertRaisesRegex(Hold, 'pr75_history_rows'): self.proof()

    def test_latest_hold_cannot_acquire_a_result_or_be_replayed(self):
        self.perform()
        write_new(self.state / 'attempts' / self.m.HOLD_KEY / 'result.json', b'forged result')
        with self.assertRaisesRegex(Hold, 'pr75_context_original_hold_files'): self.proof()

    def test_forged_extra_policy_fields_other_locks_image_and_thresholds_are_rejected(self):
        self.perform(); path = self.etc / 'policy.json'; raw = path.read_bytes(); old = decode(raw)
        mutations = [lambda p: p.update(extra=True), lambda p: p.update(owner_request=PR75_SUCCESSOR_REQUEST),
            lambda p: p['profiles'][0].update(minimum_tests=1),
            lambda p: p['profiles'][1].update(minimum_tests=506),
            lambda p: p['profiles'][1].update(maximum_skips=7),
            lambda p: p['profiles'][1].update(image='sha256:'+'0'*64),
            lambda p: p['profiles'][1].update(extra=True),
            lambda p: p['profiles'][1]['locked'].update({'elixir/mix.lock': '0'*40})]
        for mutate in mutations:
            forged = copy.deepcopy(old); mutate(forged); path.write_bytes(canonical(forged))
            with self.assertRaises(Hold): self.proof()
        path.write_bytes(raw); self.proof()

    def test_receipt_completion_and_actual_policy_mismatch_fail_closed(self):
        self.perform(); policy = decode((self.etc / 'policy.json').read_bytes())
        directory = self.m.paths('c'*40)[0]
        paths = [self.state / policy['profiles'][1]['preparation'], directory / 'COMPLETE.json',
                 directory / 'inputs.json', self.inst / 'installed.json']
        for path in paths:
            raw = path.read_bytes(); path.write_bytes(canonical({'forged': True}))
            with self.subTest(path=path.name), self.assertRaises((Hold, KeyError)): self.proof()
            path.write_bytes(raw)
        with self.assertRaisesRegex(Hold, 'pr75_context_completion_policy'):
            self.m.validate_preparation(self.state, policy, canonical(dict(policy, extra=True)))

    def test_every_native_quality_failure_refuses_install_and_preserves_single_use_claim(self):
        bad = dict(self.worker.return_value, tests=506)
        with patch.object(runner, 'run', return_value=bad), self.assertRaisesRegex(Hold, 'quality_assertions'):
            self.perform()
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.original_raw)
        self.assertEqual((self.inst / 'revision').read_text(), self.m.BASE)
        self.assertFalse(self.m.paths('c'*40)[2].exists())
        with self.assertRaisesRegex(Hold, 'pr75_context_already_claimed'): self.perform()

    def test_skips_coverage_source_and_stage_failures_cannot_create_receipt(self):
        profile = dict(self.m.definition(), image=self.m.IMAGE)
        for fields in ({'skipped': 7}, {'coverage': 99.9}, {'failures': 1}, {'tests': 464},
                       {'source_before': False}, {'source_after': False}, {'cleanup': 1},
                       {'stages': dict(self.worker.return_value['stages'], lint=1)}):
            with self.subTest(fields=fields), self.assertRaises(Hold):
                runner.validate_result(dict(self.worker.return_value, **fields), profile)

    def test_unknown_policy_write_keeps_intent_archive_and_never_replays(self):
        def unknown(policy):
            (self.etc / 'policy.json').write_bytes(canonical(policy)); raise OSError('unknown write')
        with patch.object(self.owner, 'replace_policy', side_effect=unknown), self.assertRaises(OSError): self.perform()
        directory, _, archive = self.m.paths('c'*40)
        self.assertTrue(archive.exists()); self.assertTrue((directory / 'commit-intent.json').exists())
        self.assertFalse((directory / 'COMPLETE.json').exists())
        with self.assertRaisesRegex(Hold, 'pr75_context_already_claimed'): self.perform()

    def test_prewrite_failure_restores_predecessor_and_preserves_claim(self):
        with patch.object(self.owner, 'replace_policy', side_effect=OSError('before write')), self.assertRaises(OSError):
            self.perform()
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.original_raw)
        self.assertEqual((self.inst / 'revision').read_text(), self.m.BASE)
        with self.assertRaisesRegex(Hold, 'pr75_context_already_claimed'): self.perform()

    def test_stale_inputs_after_quality_refuse_commit(self):
        changed = dict(self.snapshot, tree='f'*40)
        with patch.object(self.m, 'preflight', side_effect=[copy.deepcopy(self.snapshot), changed]), \
             self.assertRaisesRegex(Hold, 'pr75_context_inputs_changed'): self.perform()
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.original_raw)
        self.assertFalse(self.m.paths('c'*40)[2].exists())

    def test_nonpaused_or_wrong_predecessor_policy_refuses_claim(self):
        from snci import daily_limit
        directory = self.m.paths('c'*40)[0]
        with patch.object(self.m, 'preflight', self.real_preflight), \
             patch.object(daily_limit, 'paused', side_effect=Hold('daily_limit_units')), \
             self.assertRaisesRegex(Hold, 'daily_limit_units'): self.perform()
        self.assertFalse(directory.exists())
        (self.etc / 'policy.json').write_bytes(self.original_raw + b' ')
        with patch.object(self.m, 'preflight', self.real_preflight), \
             self.assertRaisesRegex(Hold, 'pr75_context_original_policy'): self.perform()
        self.assertFalse(directory.exists())

    def test_closed_package_delta_has_exactly_nine_paths(self):
        from snci import refresh
        self.assertEqual(len(self.m.DELTA), 9)
        old = {p: {'sha': 'old', 'mode': '100644'} for p in self.m.DELTA}
        new = {p: {'sha': 'new', 'mode': '100644'} for p in self.m.DELTA}
        refresh.package_delta(old, new, self.m.DELTA)
        for path in ('ci/continuous/owner.py', 'ci/continuous/profiles.json', 'ci/continuous/reviewer.py', 'elixir/mix.lock'):
            with self.assertRaises(Hold): refresh.package_delta(old, dict(new, **{path: {'sha': 'new', 'mode': '100644'}}), self.m.DELTA)


class ContextDispatchTests(unittest.TestCase):
    def test_context_requires_its_byte_bound_completion(self):
        from snci import repair_pr75_context, pr75_profile, repair_review_paging
        with patch.object(repair_pr75_context, 'validate_preparation', side_effect=Hold('missing context proof')) as own, \
             patch.object(repair_pr75_target, 'validate_preparation') as predecessor, \
             patch.object(pr75_profile, 'validate_preparation') as original, \
             patch.object(repair_review_paging, 'validate_preparation') as paging:
            with self.assertRaisesRegex(Hold, 'missing context proof'):
                controller.validate_owner_preparation(Path('/fixture'), {'owner_request': REQUEST}, b'fixture')
            own.assert_called_once(); predecessor.assert_not_called(); original.assert_not_called(); paging.assert_not_called()


class RealPreflightFixupTests(unittest.TestCase):
    def setUp(self):
        import test_pr75_profile as initial_fixture
        from test_daily_limit import policy as fixture_policy
        from snci import refresh
        # Provision a valid main receipt in the initial predecessor fixture,
        # before any real predecessor completions are produced. This changes
        # fixture input serialization only; no receipt/proof validator is mocked.
        receipt_holder = {}
        def seed_policy(value):
            if isinstance(value, dict) and 'profiles' in value and 'codex_sha256' in value:
                value.setdefault('ruleset', fixture_policy(None)['ruleset'])
                main = value['profiles'][0]
                if main.get('preparation_sha256') == 'c'*64:
                    raw = canonical(dict(profile='main', head=main['head'], tree=main['tree'],
                        image=main['image'], codex_sha256=value['codex_sha256'], time=0,
                        native_probe_sha256='1'*64,
                        quality=dict(stages=dict.fromkeys(('build','format','lint','coverage','dialyzer'), 0),
                            tests=507, failures=0, skipped=6, coverage=100.0, dialyzer_errors=0,
                            source_before=True, source_after=True, cleanup=0)))
                    main['preparation_sha256'] = sha256(raw); receipt_holder['raw'] = raw
            return canonical(value)
        with patch.object(initial_fixture, 'canonical', seed_policy):
            ContextTransitionTests.setUp(self)
        main = self.snapshot['policy']['profiles'][0]
        path = self.state / main['preparation']; path.parent.mkdir(parents=True, exist_ok=True)
        write_new(path, receipt_holder['raw'])
        self.snapshot['history'] = self.m.history(self.snapshot['policy'], 'c'*40)
        self.api_calls = []
        test = self
        class API:
            def request(_, method, path):
                test.api_calls.append((method, path))
                if '/git/commits/' in path:
                    return dict(sha='c'*40, parents=[{'sha': test.m.BASE}], tree={'sha': '6'*40})
                if '/pulls/75' in path: return candidate()
                if '/rulesets/' in path: return copy.deepcopy(test.snapshot['policy']['ruleset'])
                raise AssertionError('unexpected external request')
        old = {'ci/continuous/'+name: dict(sha=blob_hash((self.inst/name).read_bytes()),
                    mode='100644', size=len((self.inst/name).read_bytes()))
               for name in decode((self.inst/'installed.json').read_bytes())}
        new = dict(old)
        data = {}
        for path in self.m.DELTA:
            raw = ('new exact package '+path).encode(); data[path] = raw
            new[path] = dict(sha=blob_hash(raw), mode='100644', size=len(raw))
        class Source:
            def tree(_, head):
                if head == test.m.BASE: return test.m.BASE_TREE, copy.deepcopy(old)
                if head == 'c'*40: return '6'*40, copy.deepcopy(new)
                if head == REQUEST['head']: return REQUEST['tree'], copy.deepcopy(test.snapshot['entries'])
                raise AssertionError('unexpected source identity')
        self.api, self.remote_source = API(), Source()

    def check(self): return self.real_preflight(self.owner, 'c'*40, self.api, self.remote_source)

    def test_exact_predecessor_real_preflight_accepts_target_receipt_pointer(self):
        result = self.check()
        self.assertEqual(result['policy_raw'], self.original_raw)
        self.assertEqual(result['entries'], self.snapshot['entries'])
        self.assertFalse(self.m.paths('c'*40)[0].exists()); self.worker.assert_not_called()

    def test_bad_predecessor_receipt_or_proof_refuses_before_claim(self):
        profile = self.snapshot['policy']['profiles'][1]
        receipt_path = self.state / profile['preparation']; raw = receipt_path.read_bytes()
        receipt = decode(raw)
        for field, value in [('profile','main'), ('head','0'*40), ('tree','0'*40),
                             ('image','sha256:'+'0'*64), ('time',-1), ('time',True),
                             ('quality',dict(receipt['quality'], tests=463)),
                             ('native_probe_sha256','0'*64)]:
            changed = canonical(dict(receipt, **{field:value}))
            receipt_path.write_bytes(changed)
            policy = decode(self.original_raw); policy['profiles'][1]['preparation_sha256'] = sha256(changed)
            policy_raw = canonical(policy); (self.etc/'policy.json').write_bytes(policy_raw)
            directory = self.state / ('pr75-target-'+self.m.BASE)
            proof_path, intent_path = directory/'COMPLETE.json', directory/'commit-intent.json'
            proof_raw, intent_raw = proof_path.read_bytes(), intent_path.read_bytes()
            proof, intent = decode(proof_raw), decode(intent_raw)
            proof['policy_sha256'] = intent['policy_sha256'] = sha256(policy_raw)
            proof_path.write_bytes(canonical(proof)); intent_path.write_bytes(canonical(intent))
            with patch.object(self.m, 'POLICY_SHA', sha256(policy_raw)), \
                 patch.object(self.m, 'ORIGINAL_COMPLETE_SHA', sha256(canonical(proof))), \
                 self.subTest(field=field), self.assertRaises(Hold): self.check()
            proof_path.write_bytes(proof_raw); intent_path.write_bytes(intent_raw)
            (self.etc/'policy.json').write_bytes(self.original_raw)
            self.assertFalse(self.m.paths('c'*40)[0].exists()); self.worker.assert_not_called()
        receipt_path.write_bytes(raw)
        proof = self.state / ('pr75-target-'+self.m.BASE) / 'COMPLETE.json'
        saved = proof.read_bytes(); proof.write_bytes(b'changed predecessor proof')
        with self.assertRaisesRegex(Hold, 'pr75_context_original_complete'): self.check()
        proof.write_bytes(saved)

    def test_wrong_pointer_or_digest_refuses_even_with_rebound_top_policy_digest(self):
        path = self.etc / 'policy.json'
        for field, value in [('preparation','refresh-'+'c'*40+'/sn004/acceptance.json'),
                             ('preparation_sha256','0'*64)]:
            policy = decode(self.original_raw); policy['profiles'][1][field] = value; raw = canonical(policy)
            path.write_bytes(raw)
            with patch.object(self.m, 'POLICY_SHA', sha256(raw)), self.assertRaises(Hold): self.check()
            self.assertFalse(self.m.paths('c'*40)[0].exists()); self.worker.assert_not_called()
        path.write_bytes(self.original_raw)


class CompletionEvidenceFixupTests(unittest.TestCase):
    def setUp(self): ContextTransitionTests.setUp(self)
    def perform(self): return self.m.perform(self.owner, 'c'*40, None, self.source)

    def assert_retained(self, output):
        directory, _, archive = self.m.paths('c'*40)
        self.assertTrue(archive.exists()); self.assertTrue((directory/'commit-intent.json').exists())
        self.assertTrue((directory/'COMPLETE.json').exists())
        self.assertEqual(decode((directory/'COMPLETE.json').read_bytes())['status'], 'PR75_CONTEXT_INSTALLED_PAUSED')
        self.assertNotIn('PR75_CONTEXT_INSTALLED_PAUSED ', output)
        self.assertNotIn('VERIFIED_INSTALLED_PAUSED', output)
        with self.assertRaisesRegex(Hold, 'pr75_context_already_claimed'): self.perform()
        # Corrupt evidence remains present and the real controller gate refuses it.
        (directory/'COMPLETE.json').write_bytes(canonical({'status':'invalid partial proof'}))
        raw = (self.etc/'policy.json').read_bytes()
        with self.assertRaisesRegex(Hold, 'pr75_context_completion_binding'):
            controller.validate_owner_preparation(self.state, decode(raw), raw)

    def test_failed_completion_validation_preserves_durable_complete_without_success(self):
        import contextlib, io
        output = io.StringIO()
        with contextlib.redirect_stdout(output), \
             patch.object(self.m, 'validate_preparation', side_effect=Hold('postwrite readback failed')), \
             self.assertRaisesRegex(Hold, 'postwrite readback failed'): self.perform()
        self.assert_retained(output.getvalue())

    def sync_failure(self, target_kind):
        import contextlib, io, os
        original_write = self.m.write_new
        def write_with_sync_failure(path, raw, *args, **kwargs):
            if Path(path).name != 'COMPLETE.json':
                return original_write(path, raw, *args, **kwargs)
            original_sync = os.fsync
            target = Path(path) if target_kind == 'file' else Path(path).parent
            def failed_sync(fd):
                if Path(os.readlink('/proc/self/fd/'+str(fd))) == target:
                    raise OSError(target_kind+' fsync failed during COMPLETE write')
                return original_sync(fd)
            # Injection lasts only for this exact COMPLETE write, including its
            # real file flush/fsync and parent-directory fsync implementation.
            with patch.object(os, 'fsync', failed_sync):
                return original_write(path, raw, *args, **kwargs)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(self.m, 'write_new', write_with_sync_failure), \
             self.assertRaisesRegex(OSError, target_kind+' fsync failed during COMPLETE write'):
            self.perform()
        self.assert_retained(output.getvalue())

    def test_complete_sync_failure_preserves_created_bytes_without_success(self):
        self.sync_failure('directory')

    def test_complete_file_fsync_failure_preserves_created_bytes_without_success(self):
        self.sync_failure('file')


if __name__ == '__main__': unittest.main()

