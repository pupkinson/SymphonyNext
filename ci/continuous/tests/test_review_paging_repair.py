"""Real package/archive/journal contracts; only native boundaries are fixtures."""
import copy
import importlib
from pathlib import Path
import unittest
from unittest.mock import patch

import test_pr75_profile as fixture
from snci.common import Hold, blob_hash, canonical, decode, sha256, write_new
from snci import daily_limit, refresh
from snci.state import Journal
from snci.source import PR75_REQUEST

NEW = '9' * 40


class PagingRepairTests(unittest.TestCase):
    def setUp(self):
        try: self.repair = importlib.import_module('snci.repair_review_paging')
        except ModuleNotFoundError: self.fail('Closed paused paging repair is unavailable')
        self.real_preflight = self.repair.preflight
        fixture.TransitionTests.setUp(self)
        self.repair_preflight = self.repair.preflight
        self.profile = self.m; self.m = self.repair
        self.profile.prepare(self.owner, self.m.BASE, None, self.source)
        self.profile.install(self.owner, self.m.BASE, None, self.source)
        self.old_raw = (self.etc / 'policy.json').read_bytes(); old = decode(self.old_raw)
        j = Journal(self.state / 'journal.sqlite3')
        target = {k: PR75_REQUEST[k] for k in ('pr', 'head', 'base')}
        key = j.claim(target, sha256(self.old_raw), None)
        j.set(key, 'hold', {'reason': 'review_not_ready'})
        rows = [list(row) for row in j.db.execute('SELECT key,target,policy,day,state,data FROM attempts')]
        j.close()
        for row in rows: (self.state / 'attempts' / row[0]).mkdir(parents=True, exist_ok=True)
        attempt = self.state / 'attempts' / key
        inputs = canonical({'target': PR75_REQUEST})
        review = canonical({'verdict': dict(PR75_REQUEST, verdict='HOLD', findings=[])})
        write_new(attempt / 'inputs.json', inputs); write_new(attempt / 'review.json', review)
        files = {str(p.relative_to(self.state)): sha256(p.read_bytes())
                 for p in self.state.rglob('*') if p.is_file() and p.name != 'journal.sqlite3'}
        history = {'rows': rows, 'files': files}
        complete = self.state / ('refresh-' + self.m.BASE) / 'COMPLETE.json'
        new_data = {'worker.py': b'original installed worker', 'marker': b'paged package'}
        entries = {p: {'sha': blob_hash(raw), 'mode': '100644', 'size': len(raw)}
                   for p, raw in new_data.items()}
        self.snapshot = dict(policy=old, policy_raw=self.old_raw, tree='8' * 40,
            package=entries, new={'ci/continuous/' + p: e for p, e in entries.items()},
            old_manifest=sha256((self.inst / 'installed.json').read_bytes()),
            units={}, history=history, original_complete_sha256=sha256(complete.read_bytes()))
        class NewSource:
            def blob(_, entry):
                return next(raw for raw in new_data.values() if blob_hash(raw) == entry['sha'])
        self.source = NewSource()
        def probe(stage, owner, policy, path):
            proof = {'native_acceptance': 'PASS', 'source_paging_acceptance': 'PASS',
                'baseline_reviewer_blob': self.m.LEGACY_REVIEWER_BLOB,
                'codex_sha256': old['codex_sha256'], 'cases': 17}
            write_new(path, canonical(proof) + b'\n'); return sha256(path.read_bytes())
        sn004 = next(p for p in old['profiles'] if p['name'] == 'sn004')
        replacements = [(self.m, 'STATE', self.state), (self.m, 'ETC', self.etc),
            (self.m, 'INSTALL', self.inst), (self.m, 'POLICY_SHA', sha256(self.old_raw)),
            (self.m, 'ORIGINAL_COMPLETE_SHA', sha256(complete.read_bytes())),
            (self.m, 'HOLD_KEY', key), (self.m, 'INPUTS_SHA', sha256(inputs)),
            (self.m, 'REVIEW_SHA', sha256(review)), (self.m, 'IMAGE', sn004['image']),
            (self.m, 'RECEIPT_SHA', sn004['preparation_sha256']),
            (self.m, 'preflight', lambda *a: copy.deepcopy(self.snapshot)),
            (self.m, 'native_probe', probe), (refresh, 'idle_native', lambda: None),
            (self.m, 'trusted', lambda p, **kw: Path(p))]
        for obj, name, value in replacements:
            p = patch.object(obj, name, value); p.start(); self.addCleanup(p.stop)
        self.held = {p: p.read_bytes() for p in attempt.iterdir()}

    def perform(self):
        return self.m.perform(self.owner, NEW, None, self.source)

    def test_transition_rebinds_original_proof_to_archive_and_preserves_hold_policy_and_receipts(self):
        proof = self.perform()
        raw = (self.etc / 'policy.json').read_bytes(); policy = decode(raw)
        self.assertEqual(policy, dict(self.snapshot['policy'], installed_revision=NEW))
        archive = self.m.paths(NEW)[2]
        self.assertEqual((archive / 'marker').read_bytes(), b'new package')
        self.assertEqual((self.inst / 'marker').read_bytes(), b'paged package')
        self.assertEqual({p: p.read_bytes() for p in self.held}, self.held)
        self.assertEqual(proof, self.m.validate_preparation(self.state, policy, raw))
        self.assertEqual((archive / 'revision').read_text(), self.m.BASE)
        j = Journal(self.state / 'journal.sqlite3')
        key = j.claim({k: PR75_REQUEST[k] for k in ('pr', 'head', 'base')}, sha256(raw), None)
        self.assertNotEqual(key, self.m.HOLD_KEY)
        j.set(key, 'publishing', {'synthetic': 'pending reconciliation'}); j.close()
        self.m.validate_preparation(self.state, policy, raw)

    def test_complete_does_not_mask_current_or_archived_package_mutation(self):
        self.perform(); raw = (self.etc / 'policy.json').read_bytes(); policy = decode(raw)
        for root in (self.inst, self.m.paths(NEW)[2]):
            path = root / 'worker.py'; before = path.read_bytes()
            path.write_bytes(b'tampered actual package bytes')
            with self.assertRaisesRegex(Hold, 'daily_limit_package'):
                self.m.validate_preparation(self.state, policy, raw)
            path.write_bytes(before)

    def test_receipt_and_historical_hold_mutations_are_rejected(self):
        self.perform(); raw = (self.etc / 'policy.json').read_bytes(); policy = decode(raw)
        receipt = self.state / next(p for p in policy['profiles'] if p['name'] == 'sn004')['preparation']
        original = receipt.read_bytes(); receipt.write_bytes(b'changed receipt')
        with self.assertRaises(Hold): self.m.validate_preparation(self.state, policy, raw)
        receipt.write_bytes(original)
        j = Journal(self.state / 'journal.sqlite3')
        with j.db: j.db.execute("UPDATE attempts SET state='success' WHERE key=?", (self.m.HOLD_KEY,))
        j.close()
        with self.assertRaisesRegex(Hold, 'pr75_history_rows'):
            self.m.validate_preparation(self.state, policy, raw)

    def test_probe_failure_preserves_original_and_single_use_claim(self):
        with patch.object(self.m, 'native_probe', side_effect=Hold('fixture_transport')):
            with self.assertRaisesRegex(Hold, 'fixture_transport'): self.perform()
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.old_raw)
        self.assertFalse(self.m.paths(NEW)[2].exists())
        with self.assertRaisesRegex(Hold, 'paging_already_claimed'): self.perform()

    def test_post_commit_unknown_write_keeps_archive_and_intent_without_complete(self):
        def unknown(policy):
            (self.etc / 'policy.json').write_bytes(canonical(policy))
            raise RuntimeError('unknown successful policy write')
        with patch.object(self.owner, 'replace_policy', side_effect=unknown):
            with self.assertRaises(RuntimeError): self.perform()
        directory, _, archive = self.m.paths(NEW)
        self.assertTrue(archive.exists()); self.assertTrue((directory / 'commit-intent.json').exists())
        self.assertFalse((directory / 'COMPLETE.json').exists())
        self.assertEqual(decode((self.etc / 'policy.json').read_bytes())['installed_revision'], NEW)
        with self.assertRaisesRegex(Hold, 'paging_already_claimed'): self.perform()

    def test_pre_commit_unknown_write_restores_original_but_does_not_remove_claim(self):
        with patch.object(self.owner, 'replace_policy', side_effect=RuntimeError('before write')):
            with self.assertRaises(RuntimeError): self.perform()
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.old_raw)
        self.assertEqual((self.inst / 'revision').read_text(), self.m.BASE)
        self.assertFalse(self.m.paths(NEW)[2].exists())
        with self.assertRaisesRegex(Hold, 'paging_already_claimed'): self.perform()

    def test_probe_pass_label_without_paging_proof_cannot_commit(self):
        def old_probe(stage, owner, policy, path):
            write_new(path, canonical({'native_acceptance': 'PASS', 'cases': 11}) + b'\n')
            return sha256(path.read_bytes())
        with patch.object(self.m, 'native_probe', side_effect=old_probe):
            with self.assertRaisesRegex(Hold, 'paging_native_proof'): self.perform()
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.old_raw)
        self.assertFalse(self.m.paths(NEW)[2].exists())

    def test_closed_delta_rejects_omission_or_any_product_profile_owner_path(self):
        old = {p: {'sha': 'old', 'mode': '100644'} for p in self.m.DELTA}
        new = {p: {'sha': 'new', 'mode': '100644'} for p in self.m.DELTA}
        refresh.package_delta(old, new, self.m.DELTA)
        for forbidden in ('ci/continuous/owner.py', 'ci/continuous/profiles-pr75.json', 'elixir/mix.exs'):
            with self.assertRaisesRegex(Hold, 'refresh_package_scope'):
                refresh.package_delta(old, dict(new, **{forbidden: {'sha': 'new', 'mode': '100644'}}), self.m.DELTA)
        with self.assertRaisesRegex(Hold, 'refresh_package_scope'):
            refresh.package_delta(old, {p: v for p, v in new.items() if p != next(iter(new))}, self.m.DELTA)

    def test_policy_drift_and_nonpaused_units_cannot_create_claim(self):
        (self.etc / 'policy.json').write_bytes(canonical(dict(self.snapshot['policy'], daily_attempts=4)))
        with patch.object(self.m, 'preflight', self.repair_preflight):
            with self.assertRaisesRegex(Hold, 'paging_policy_binding'): self.perform()
        self.assertFalse(self.m.paths(NEW)[0].exists())
        with patch.object(self.m, 'preflight', self.repair_preflight), \
             patch.object(daily_limit, 'paused', side_effect=Hold('daily_limit_units')):
            with self.assertRaisesRegex(Hold, 'daily_limit_units'): self.perform()
        self.assertFalse(self.m.paths(NEW)[0].exists())

    def test_preflight_drift_after_probe_retains_claim_without_commit(self):
        changed = dict(self.snapshot, tree='7' * 40)
        with patch.object(self.m, 'preflight', side_effect=[copy.deepcopy(self.snapshot), changed]):
            with self.assertRaisesRegex(Hold, 'paging_inputs_changed'): self.perform()
        self.assertEqual((self.etc / 'policy.json').read_bytes(), self.old_raw)
        directory, _, archive = self.m.paths(NEW)
        self.assertTrue((directory / 'native-codex.log').exists()); self.assertFalse(archive.exists())
