import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, decode
from snci.source import parse_tree, verify_blob, select_profile, validate_target, validate_rules
from snci.state import Journal

SHA = 'a' * 40
TREE = 'b' * 40
BASE = 'c' * 40

def pr():
    return {'number': 14, 'state': 'open', 'merged': False, 'draft': False,
            'head': {'sha': SHA, 'repo': {'id': 1381693716}},
            'base': {'sha': BASE, 'ref': 'main', 'repo': {'id': 1381693716}}}

class ContractTest(unittest.TestCase):
    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(Hold): decode(b'{"a":1,"a":2}')

    def test_nonfinite_json_rejected(self):
        with self.assertRaises(Hold): decode(b'{"a":NaN}')

    def test_blob_tampering_rejected(self):
        b = b'hello\n'
        wire = {'sha': blob_hash(b), 'encoding': 'base64', 'content': base64.b64encode(b).decode(), 'size': len(b)}
        self.assertEqual(verify_blob(wire, blob_hash(b)), b)
        wire['content'] = base64.b64encode(b'evil').decode()
        with self.assertRaises(Hold): verify_blob(wire, blob_hash(b))

    def test_unsafe_tree_rejected(self):
        for path, mode in [('../key', '100644'), ('/key', '100644'), ('a/../b','100644'), ('a','120000'), ('a','160000'), ('a\nb','100644')]:
            with self.subTest(path=path,mode=mode), self.assertRaises(Hold):
                parse_tree({'sha': TREE, 'truncated': False, 'tree': [{'path': path, 'mode': mode, 'type': 'blob', 'sha': SHA, 'size': 2}]},TREE)

    def test_truncated_tree_rejected(self):
        with self.assertRaises(Hold): parse_tree({'sha':TREE,'truncated':True,'tree':[]},TREE)

    def test_duplicate_tree_path_rejected(self):
        entry={'path':'a','mode':'100644','type':'blob','sha':SHA,'size':2}
        with self.assertRaises(Hold): parse_tree({'sha':TREE,'truncated':False,'tree':[entry,entry]},TREE)

    def test_fork_and_stale_head_rejected(self):
        target = validate_target(pr())
        for kind in ['fork','head','base']:
            p=pr()
            if kind=='fork': p['head']['repo']['id']=1
            elif kind=='head': p['head']['sha']='d'*40
            else: p['base']['sha']='e'*40
            with self.subTest(kind=kind), self.assertRaises(Hold): validate_target(p,target)

    def test_draft_requires_explicit_label(self):
        p=pr();p['draft']=True
        with self.assertRaises(Hold): validate_target(p)
        p['labels']=[{'name':'snv:verify'}]
        self.assertEqual(validate_target(p)['head'],SHA)

    def test_profile_rejects_locked_test_changes_and_deletions(self):
        profile={'name':'test','locked':{'elixir/mix.exs':SHA,'elixir/test/a.exs':BASE}}
        policy={'profiles':[profile]}
        entries={'elixir/mix.exs':{'sha':SHA},'elixir/test/a.exs':{'sha':BASE}}
        self.assertEqual(select_profile(entries,policy)['name'],'test')
        for value in [{'sha':'d'*40},None]:
            bad=dict(entries)
            if value:bad['elixir/test/a.exs']=value
            else:del bad['elixir/test/a.exs']
            with self.assertRaises(Hold): select_profile(bad,policy)

    def test_rules_revision_or_bypass_change_rejected(self):
        r={'id':23980199,'target':'branch','source':'pupkinson/SymphonyNext','source_type':'Repository','enforcement':'active',
           'conditions':{'ref_name':{'include':['~DEFAULT_BRANCH'],'exclude':[]}},'updated_at':'2026-09-25',
           'rules':[{'type':'required_status_checks','parameters':{'required_status_checks':[{'context':'symphony-next/verified-tests','integration_id':5069157}]}}], 'bypass_actors':[]}
        self.assertEqual(validate_rules(r,r),'visible_empty')
        public=dict(r);del public['bypass_actors']
        self.assertEqual(validate_rules(public,r),'pinned_empty_revision_matched')
        public['updated_at']='changed'
        with self.assertRaises(Hold):validate_rules(public,r)
        bad=dict(r);bad['bypass_actors']=[{'actor_id':1}]
        with self.assertRaises(Hold):validate_rules(bad,r)

class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db'
        self.j=Journal(self.path)
    def tearDown(self):
        self.j.close();self.tmp.cleanup()
    def test_claim_exact_once(self):
        t=validate_target(pr())
        key=self.j.claim(t,'p',4)
        self.assertIsNotNone(key)
        self.assertIsNone(self.j.claim(t,'p',4))
        t=dict(t,head='d'*40)
        self.assertIsNotNone(self.j.claim(t,'p',4))
    def test_budget_persists(self):
        self.j.claim(validate_target(pr()),'p',1)
        self.j.close();self.j=Journal(self.path)
        with self.assertRaises(Hold):self.j.claim(dict(validate_target(pr()),head='e'*40),'p',1)
    def test_publish_intent_survives_restart(self):
        key=self.j.claim(validate_target(pr()),'p',4)
        self.j.set(key,'publishing',{'external_id':'x','check_body':{'head_sha':SHA}})
        self.j.close();self.j=Journal(self.path)
        self.assertEqual(self.j.pending()[0]['state'],'publishing')
        self.assertEqual(self.j.get(key)['data']['external_id'],'x')
    def test_failed_attempt_not_automatically_retried(self):
        t=validate_target(pr());key=self.j.claim(t,'p',4)
        self.j.set(key,'hold',{'reason':'error'})
        self.assertIsNone(self.j.claim(t,'p',4))

if __name__=='__main__':unittest.main()
