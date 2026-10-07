import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from test_queue_context import q, FakeGit, manifest, H

class NegativeTests(unittest.TestCase):
    def build(self,a=None,m=None):
        a=a or FakeGit();return q.build_review_sources(a,m or manifest(),a.pr)
    def test_composition_loads_and_validates_unchanged_source(self):
        a=FakeGit();a.head['planning/spec-index.json']=json.dumps(dict(schema='symphony-next-spec-composition/v1',
            base_files=[{'path':'docs/contract.md','sha256':q.sha(a.base['docs/contract.md'])}],
            required_addenda=[],task_refinements=[],implementation_plans=[])).encode()
        a.rows=a.make_rows();a.pr['changed_files']=len(a.rows)
        s=self.build(a);self.assertIn('REQUIRED CONTRACT\n',[d['text'] for d in s['documents']])
        bad=json.loads(a.head['planning/spec-index.json']);bad['base_files'][0]['sha256']='0'*64
        a.head['planning/spec-index.json']=json.dumps(bad).encode();a.rows=a.make_rows()
        with self.assertRaisesRegex(q.Hold,'^CONTEXT_HASH_CHANGED$'):self.build(a)
    def test_unknown_composition_refused(self):
        a=FakeGit(extra={'planning/spec-index.json':b'{}'})
        with self.assertRaisesRegex(q.Hold,'^SOURCE_COMPOSITION_UNSUPPORTED$'):self.build(a)
    def test_rename_preserves_both_versions(self):
        a=FakeGit();a.head['renamed.md']=a.head.pop('docs/contract.md')
        a.rows=[r for r in a.make_rows() if r['filename']!='docs/contract.md']
        next(r for r in a.rows if r['filename']=='renamed.md')['previous_filename']='docs/contract.md'
        a.pr['changed_files']=len(a.rows);s=self.build(a)
        c=next(c for c in s['changes'] if c['path']=='renamed.md')
        self.assertEqual(c['base'],c['head'])
        doc=next(d for d in s['documents'] if d['id']==c['head'])
        self.assertEqual({x['path'] for x in doc['aliases']},{'renamed.md','docs/contract.md'})
    def test_foreign_repo_and_stale_head_refused(self):
        for field,value,code in [('sha','f'*40,'PR_SHA_CHANGED'),('repo',{'id':42},'FOREIGN_REPOSITORY')]:
            a=FakeGit();a.pr['head'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(q.Hold,'^'+code+'$'):self.build(a)
            self.assertEqual(a.calls,[])
    def test_symlink_source_rejected(self):
        a=FakeGit();get=a.get
        def wrapped(p):
            v=get(p)
            if '/git/trees/' in p:
                for e in v['tree']:
                    if e['path']=='change.md':e['mode']='120000'
            return v
        a.get=wrapped
        with self.assertRaisesRegex(q.Hold,'^SOURCE_TYPE$'):self.build(a)
    def test_duplicate_tree_paths_rejected(self):
        a=FakeGit();get=a.get
        def wrapped(p):
            v=get(p)
            if '/git/trees/' in p:v['tree'].append(v['tree'][0])
            return v
        a.get=wrapped
        with self.assertRaisesRegex(q.Hold,'^SOURCE_PATH$'):self.build(a)
    def test_changed_files_mismatch_rejected(self):
        a=FakeGit();a.pr['changed_files']+=1
        with self.assertRaisesRegex(q.Hold,'^PR_FILES_INCOMPLETE$'):self.build(a)
    def test_same_page_cannot_replace_missing_page_in_receipt(self):
        s=self.build(FakeGit(extra={'long.md':b'z'*10000}));r=q.SourceReader(s)
        for sid,ps in r.pages.items():
            for n in range(len(ps)):r.read_page({'source_id':sid,'page':n})
        bad=r.receipt();bad['deliveries'][-1]=bad['deliveries'][0]
        with self.assertRaises(q.Hold):q.verify_source_receipt(q.SourceReader(s),bad)
    def test_cross_target_store_rejected(self):
        s=self.build();m=manifest();m['head_sha']='f'*40
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);raw=q.wire_json(s);(d/'sources.json').write_bytes(raw)
            (d/'packet.json').write_bytes(q.wire_json({'source_store_sha256':q.sha(raw)}))
            with self.assertRaisesRegex(q.Hold,'^SOURCE_STORE_TARGET$'):q.load_source_reader(d,m)
    def test_preflight_budget_before_any_model_probe(self):
        a=FakeGit(extra={'long.md':b'z'*10000})
        with patch.object(q,'SOURCE_CALL_LIMIT',1),patch.object(q,'probe',side_effect=AssertionError('model must not start')):
            with self.assertRaisesRegex(q.Hold,'^SOURCE_PREFLIGHT_BUDGET$'):self.build(a)
    def test_snapshot_refs_do_not_grant_external_paths(self):
        for path in ('/etc/passwd','../key','a/../key','a\\b','https://example.invalid/key','.git/config'):
            m=manifest();m['context_sources']=[dict(revision='head',path=path,blob_sha='a'*40)]
            with self.subTest(path=path),self.assertRaisesRegex(q.Hold,'^CONTEXT_SOURCE_FIELDS$'):self.build(m=m)
    def test_legacy_gate_rejects_all_tools(self):
        g=q.Gate()
        with self.assertRaisesRegex(q.Hold,'^SERVER_TOOL_OR_APPROVAL_REFUSED$'):
            g.server({'id':1,'method':'item/tool/call','params':{'tool':'snq_source_read'}})
    def test_legacy_journal_claim_cannot_be_reset(self):
        with tempfile.TemporaryDirectory() as t:
            d=q.claim(t,85);before=(d/'claim.json').read_bytes()
            with self.assertRaisesRegex(q.Hold,'^TASK_ALREADY_CLAIMED_NO_REPLAY$'):q.claim(t,85)
            self.assertEqual((d/'claim.json').read_bytes(),before)
    def test_legacy_daily_reservation_cannot_be_reset(self):
        with tempfile.TemporaryDirectory() as t:
            q.reserve(t,85,day='2026-10-07',maximum=1)
            with self.assertRaisesRegex(q.Hold,'^TURN_ALREADY_RESERVED$'):q.reserve(t,85,day='2026-10-07',maximum=1)
            with self.assertRaisesRegex(q.Hold,'^DAILY_TURN_LIMIT$'):q.reserve(t,86,day='2026-10-07',maximum=1)

if __name__=='__main__':unittest.main()
