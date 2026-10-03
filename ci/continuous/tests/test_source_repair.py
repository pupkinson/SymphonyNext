"""Real package/policy/history files across the final paused source repair."""
import copy
import datetime
import importlib
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, canonical, sha256
from snci.source import OMITTED_BLOBS, changed_paths
from snci import refresh
import test_retention_recovery as recovery_fixture

HEAD='f'*40


class SourceRepairTests(unittest.TestCase):
    def setUp(self):
        try:self.r=importlib.import_module('snci.repair_source')
        except ImportError:self.fail('Single-use paused source-contract installation is absent')
        recovery=recovery_fixture.RetentionRecoveryTests('test_new_images_require_fresh_receipts_and_old_history_is_preserved')
        recovery.setUp();self.addCleanup(recovery.doCleanups);self.recovery=recovery;self.h=recovery.h
        recovery.perform();h=self.h;self.policy=h.owner.load_policy();self.before=canonical(self.policy)
        self.base=recovery_fixture.HEAD
        for name in ('INSTALL','STATE','ETC'):self.swap(self.r,name,getattr(h.r,name))
        self.swap(self.r,'BASE',self.base);self.swap(self.r,'BASE_TREE','c'*40)
        self.swap(self.r,'POLICY_SHA',sha256(self.before));self.swap(self.r,'trusted',lambda p,**kw:Path(p))
        bindings={p['name']:{'image':p['image'],'preparation_sha256':p['preparation_sha256']} for p in self.policy['profiles']}
        self.swap(self.r,'BINDINGS',bindings)
        self.swap(self.r,'eligible_target',lambda api:copy.deepcopy(h.r.TARGET))
        self.swap(self.r,'validate_rules',lambda *a:None)
        self.swap(self.r,'native_probe',lambda stage,owner,policy,path:self.probe(path))
        base_tree,base=h.source.tree(self.base);new=copy.deepcopy(base)
        for path in self.r.DELTA:
            raw=('SOURCE_REPAIR:'+path).encode();digest=blob_hash(raw);h.blobs[digest]=raw
            new[path]={'sha':digest,'size':len(raw),'mode':'100644'}
        h.trees[HEAD]=('c'*40,new)
        self.swap(refresh,'reviewed_commit',lambda *a,**kw:{'tree':{'sha':'c'*40}})
        digest=sha256(self.before);self.key=sha256(canonical([h.r.TARGET,digest]))
        root=h.state/'attempts'/self.key;root.mkdir()
        tree,head=h.source.tree(h.r.TARGET['head']);base_tree,base=h.source.tree(h.r.TARGET['base'])
        inputs={'target':dict(h.r.TARGET,tree=tree),'base_tree':base_tree,'profile':'sn004',
                'policy_sha256':digest,'changed':changed_paths(head,base),'omitted_unchanged_blobs':OMITTED_BLOBS}
        (root/'inputs.json').write_bytes(canonical(inputs));self.attempt=root
        with sqlite3.connect(h.state/'journal.sqlite3') as db:
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?)',(self.key,canonical(h.r.TARGET).decode(),digest,
                datetime.datetime.now(datetime.timezone.utc).date().isoformat(),'hold',canonical({'reason':'review_source_only'}).decode()))
        recovery.events.clear();h.events.clear()

    def swap(self,module,name,value):
        p=patch.object(module,name,value);p.start();self.addCleanup(p.stop)

    def probe(self,path):path.write_bytes(b'NATIVE_11_PASS');return sha256(path.read_bytes())
    def perform(self):return self.r.perform(self.h.owner,HEAD,self.h.api,self.h.source)
    def unchanged(self):
        self.assertEqual((self.h.etc/'policy.json').read_bytes(),self.before)
        self.assertEqual((self.h.install/'revision').read_text(),self.base)

    def test_changes_only_revision_and_keeps_receipts_journal_parent_proof_and_keepers(self):
        h=self.h;journal=(h.state/'journal.sqlite3').read_bytes()
        parent=h.state/('refresh-'+self.base)/'COMPLETE.json';parent_raw=parent.read_bytes()
        receipts={p['preparation']:(h.state/p['preparation']).read_bytes() for p in self.policy['profiles']}
        containers=copy.deepcopy(self.recovery.containers)
        proof=self.perform()
        self.assertEqual(h.owner.load_policy(),dict(self.policy,installed_revision=HEAD))
        self.assertEqual((h.state/'journal.sqlite3').read_bytes(),journal)
        self.assertEqual(parent.read_bytes(),parent_raw)
        self.assertEqual(self.recovery.containers,containers)
        for name,raw in receipts.items():self.assertEqual((h.state/name).read_bytes(),raw)
        backup=h.install.with_name(h.install.name+'-before-source-contract-'+HEAD)
        self.assertEqual((backup/'revision').read_text(),self.base)
        self.assertEqual(proof['history']['attempt_key'],self.key)
        self.assertFalse(any(a[:2] in (['systemctl','start'],['systemctl','enable']) for a in h.events))
        self.assertFalse(any(a[0] in ('build','quality','create','start','image') for a in self.recovery.events))
        self.r.completed(h.state,h.owner.load_policy(),(h.etc/'policy.json').read_bytes(),h.owner)

    def test_only_one_new_exact_hold_can_extend_parent_history(self):
        with sqlite3.connect(self.h.state/'journal.sqlite3') as db:
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?)',('other','{}','other','2026-10-02','hold','{}'))
        with self.assertRaisesRegex(Hold,'source_repair_parent_history'):self.perform()
        self.unchanged();self.assertFalse((self.h.state/('source-contract-'+HEAD)).exists())

    def test_unexpected_attempt_artifact_or_data_prevents_claim(self):
        (self.attempt/'result.json').write_bytes(b'{}')
        with self.assertRaisesRegex(Hold,'source_repair_attempt_files'):self.perform()
        self.unchanged()

    def test_attempt_inputs_are_exactly_bound_to_both_source_trees(self):
        (self.attempt/'inputs.json').write_bytes(b'{}')
        with self.assertRaisesRegex(Hold,'source_repair_attempt_inputs'):self.perform()
        self.unchanged()

    def test_worker_change_is_denied_before_claim(self):
        self.h.trees[HEAD][1]['ci/continuous/snci/worker.py']=self.h.trees[HEAD][1]['ci/continuous/snci/reviewer.py']
        with self.assertRaisesRegex(Hold,'source_repair_scope'):self.perform()
        self.unchanged()

    def test_failed_native_probe_retains_claim_and_prevents_replay(self):
        def fail(*a):raise Hold('native_fixture_failed')
        self.swap(self.r,'native_probe',fail)
        with self.assertRaisesRegex(Hold,'native_fixture_failed'):self.perform()
        self.unchanged()
        with self.assertRaisesRegex(Hold,'source_repair_already_claimed'):self.perform()

    def test_staged_drift_is_denied_before_commit(self):
        def drift(stage,owner,policy,path):
            (stage/'snci/reviewer.py').write_bytes(b'DRIFT');return self.probe(path)
        self.swap(self.r,'native_probe',drift)
        with self.assertRaisesRegex(Hold,'review_install_stage_bytes'):self.perform()
        self.unchanged()

    def test_parent_probe_drift_is_denied_before_claim(self):
        (self.h.state/('refresh-'+self.base)/'native-codex.log').write_bytes(b'DRIFT')
        with self.assertRaisesRegex(Hold,'source_repair_parent_native'):self.perform()
        self.unchanged()

    def test_expired_receipt_is_not_reissued_or_accepted(self):
        with patch.object(self.recovery.n.time,'time',return_value=10**11),self.assertRaisesRegex(Hold,'native_acceptance_stale'):
            self.perform()
        self.unchanged()

    def test_completion_rejects_unrelated_policy_delta(self):
        self.perform();policy=self.h.owner.load_policy();policy['daily_attempts']=3
        with self.assertRaisesRegex(Hold,'source_repair_completion_delta'):
            self.r.completed(self.h.state,policy,canonical(policy),self.h.owner)

    def test_daily_budget_counts_every_existing_attempt(self):
        day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        rows=[('k','{}','p',day,'hold','{}')]*4
        with self.assertRaisesRegex(Hold,'source_repair_daily_budget'):self.r.budget(rows,4)


if __name__=='__main__':unittest.main()
