"""Offline source/RPC regressions. GitHub and Codex are test doubles, not live proof."""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('SNQ_TEST_SOURCE', ROOT / 'candidate/queue.py'))
spec = importlib.util.spec_from_file_location('snq_under_test', SOURCE)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
H, B, T, BT = 'a'*40, 'b'*40, 'c'*40, 'd'*40
SCOPE = ('PROJECT_RULES.md', 'AGENTS.md', 'SPECIFICATION.md',
         'policies/project-policy.json', 'planning/spec-index.json')

def manifest(v2=True):
    m = dict(schema='snq-review/v2' if v2 else 'snq-review/v1', pr=84,
             head_sha=H, base_sha=B, tree_sha=T, include_mix_reference=False)
    if v2: m['context_sources'] = []
    return m

class FakeGit:
    def __init__(self, extra=None, *, large=False):
        self.base = {p:(b'{}\n' if p.endswith('.json') else b'# Scope\n') for p in SCOPE}
        self.base['planning/spec-index.json'] = json.dumps(dict(schema='symphony-next-spec-composition/v1',base_files=[],required_addenda=[],task_refinements=[],implementation_plans=[])).encode()
        self.base['docs/contract.md'] = b'REQUIRED CONTRACT\n'
        self.head = dict(self.base, **{'change.md': b'changed\n'})
        if large:
            self.head['evidence.md'] = b'X'*445155 + b'\n'
        if extra: self.head.update(extra)
        self.calls=[]
        self.rows = self.make_rows()
        self.pr=dict(number=84,state='open',merged=False,changed_files=len(self.rows),body='',
                     head={'sha':H,'repo':{'id':q.REPO_ID}},base={'sha':B,'repo':{'id':q.REPO_ID}})
    def make_rows(self):
        return [dict(filename=p,sha=q.git_blob_sha(self.head.get(p,self.base.get(p))),
                     status='removed' if p not in self.head else 'modified' if p in self.base else 'added')
                for p in sorted(self.head.keys()|self.base.keys()) if self.head.get(p)!=self.base.get(p)]
    def get(self, path):
        self.calls.append(path)
        if path == '/git/commits/'+H: return {'sha':H,'tree':{'sha':T}}
        if path == '/git/commits/'+B: return {'sha':B,'tree':{'sha':BT}}
        if path.startswith('/git/trees/'):
            oid=path.split('/')[3].split('?')[0]
            contents=self.head if oid==T else self.base
            return {'sha':oid,'truncated':False,'tree':[
                dict(path=p,type='blob',mode='100644',sha=q.git_blob_sha(raw),size=len(raw))
                for p,raw in sorted(contents.items())]}
        if path == '/pulls/84/files?per_page=100': return copy.deepcopy(self.rows)
        if path.startswith('/git/blobs/'):
            oid=path.split('/')[-1]
            for raw in list(self.head.values())+list(self.base.values()):
                if q.git_blob_sha(raw)==oid:
                    return dict(sha=oid,encoding='base64',size=len(raw),content=base64.b64encode(raw).decode())
        raise AssertionError('unexpected Git request '+path)

class SourceTests(unittest.TestCase):
    def build(self, api=None, m=None):
        self.assertTrue(hasattr(q, 'build_review_sources'), 'missing paged source builder')
        api=api or FakeGit(); m=m or manifest()
        return q.build_review_sources(api,m,api.pr)
    def test_original_overflow_reproduces(self):
        a=FakeGit(large=True)
        with self.assertRaisesRegex(q.Hold, '^SOURCE_PACKET_LIMIT$'):
            q.source_packet(a,manifest(False),a.pr)
    def test_original_omits_unchanged_contract(self):
        a=FakeGit(); text=q.source_packet(a,manifest(False),a.pr)
        self.assertNotIn('REQUIRED CONTRACT',text)
    def test_v2_large_source_is_paged_not_duplicated(self):
        a=FakeGit(large=True); store=self.build(a)
        reader=q.SourceReader(store)
        self.assertLess(len(reader.prompt().encode()),q.MAX_PACKET)
        self.assertEqual(len([d for d in store['documents'] if len(d['text'])>400000]),1)
        self.assertFalse(reader.complete())
        for doc in reader.catalog()['documents']:
            chunks=[reader.read_page({'source_id':doc['id'],'page':i}) for i in range(doc['pages'])]
            data=''.join(x['text'] for x in chunks).encode()
            self.assertEqual(q.sha(data),doc['sha256'])
        self.assertTrue(reader.complete())
    def test_explicit_unchanged_context_included(self):
        a=FakeGit(); m=manifest(); m['context_sources']=[dict(revision='base',path='docs/contract.md',blob_sha=q.git_blob_sha(a.base['docs/contract.md']))]
        s=self.build(a,m)
        self.assertIn('REQUIRED CONTRACT\n',[d['text'] for d in s['documents']])
    def test_wrong_context_blob_refused(self):
        m=manifest();m['context_sources']=[dict(revision='base',path='docs/contract.md',blob_sha='e'*40)]
        with self.assertRaisesRegex(q.Hold,'^CONTEXT_BLOB_CHANGED$'): self.build(m=m)
    def test_missing_context_refused(self):
        m=manifest();m['context_sources']=[dict(revision='head',path='missing.md',blob_sha='e'*40)]
        with self.assertRaisesRegex(q.Hold,'^CONTEXT_SOURCE_MISSING$'): self.build(m=m)
    def test_duplicate_content_preserves_all_path_aliases(self):
        a=FakeGit(extra={'alias.md':b'changed\n'})
        s=self.build(a);d=next(d for d in s['documents'] if d['text']=='changed\n')
        self.assertEqual({a['path'] for a in d['aliases']},{'change.md','alias.md'})
    def test_source_tamper_rejected(self):
        s=self.build();s['documents'][0]['text']+='tamper'
        with self.assertRaisesRegex(q.Hold,'^SOURCE_STORE_HASH$'): q.SourceReader(s)
    def test_total_source_budget(self):
        a=FakeGit(extra={f'x{i}.md':str(i).encode()+b'x'*440000 for i in range(5)})
        with self.assertRaisesRegex(q.Hold,'^SOURCE_TOTAL_LIMIT$'): self.build(a)
    def test_truncated_tree_refused(self):
        a=FakeGit();old=a.get
        def get(p):
            d=old(p)
            if '/git/trees/' in p: d['truncated']=True
            return d
        a.get=get
        with self.assertRaisesRegex(q.Hold,'^TREE_INCOMPLETE$'): self.build(a)
    def test_blob_encoding_or_hash_refused(self):
        a=FakeGit();old=a.get
        def get(p):
            d=old(p)
            if '/git/blobs/' in p: d['content']=base64.b64encode(b'tamper').decode()
            return d
        a.get=get
        with self.assertRaisesRegex(q.Hold,'^BLOB_HASH_OR_SIZE$'): self.build(a)
    def test_deleted_source_keeps_base(self):
        a=FakeGit();del a.head['docs/contract.md'];a.rows=a.make_rows();a.pr['changed_files']=len(a.rows)
        s=self.build(a)
        c=next(c for c in s['changes'] if c['path']=='docs/contract.md')
        self.assertIsNone(c['head']);self.assertIsNotNone(c['base'])

class ReaderTests(SourceTests):
    # Only reader-specific methods; inherited source cases are removed below.
    def test_utf8_and_long_line_round_trip(self):
        raw=('Денис🙂' * 4000 + '\n' + '\u0000'*1200).encode()
        s=self.build(FakeGit(extra={'unicode.md':raw}));r=q.SourceReader(s)
        d=next(x for x in r.catalog()['documents'] if any(a['path']=='unicode.md' for a in x['aliases']))
        pages=[r.read_page({'source_id':d['id'],'page':i}) for i in range(d['pages'])]
        self.assertEqual(''.join(x['text'] for x in pages).encode(),raw)
        for x in pages: self.assertLessEqual(len(q.wire_json({'contentItems':[{'type':'inputText','text':q.wire_json(x).decode()}],'success':True})),q.SOURCE_PAGE_LIMIT)
    def test_unknown_source_refused(self):
        r=q.SourceReader(self.build())
        with self.assertRaisesRegex(q.Hold,'^SOURCE_READ_ARGUMENTS$'): r.read_page({'source_id':'../../etc/passwd','page':0})
    def test_bad_page_arguments(self):
        s=self.build();r=q.SourceReader(s);sid=s['documents'][0]['id']
        for args in ({'source_id':sid,'page':True},{'source_id':sid,'page':-1},{'source_id':sid,'page':999999},{'source_id':sid,'page':0,'path':'x'}):
            with self.subTest(args=args),self.assertRaisesRegex(q.Hold,'^SOURCE_READ_ARGUMENTS$'):r.read_page(args)
    def test_duplicate_page_does_not_complete_unread_set(self):
        r=q.SourceReader(self.build());d=r.catalog()['documents'][0]
        r.read_page({'source_id':d['id'],'page':0});r.read_page({'source_id':d['id'],'page':0})
        self.assertFalse(r.complete());self.assertEqual(r.receipt()['unique_pages'],1)
    def test_read_call_budget_enforced(self):
        r=q.SourceReader(self.build());d=r.catalog()['documents'][0]
        with patch.object(q,'SOURCE_CALL_LIMIT',2):
            for _ in range(2):r.read_page({'source_id':d['id'],'page':0})
            with self.assertRaisesRegex(q.Hold,'^SOURCE_READ_BUDGET$'):r.read_page({'source_id':d['id'],'page':0})

# Avoid counting inherited test cases a second time.
for name in list(SourceTests.__dict__):
    if name.startswith('test_'): setattr(ReaderTests,name,None)

class ManifestTests(unittest.TestCase):
    def row(self,m):
        return dict(state='open',number=87,user={'login':q.OWNER},labels=[{'name':q.LABEL}],
                    body='```symphony-next\n'+json.dumps(m)+'\n```')
    def test_v1_preserved(self): self.assertEqual(q.parse_task(self.row(manifest(False))),manifest(False))
    def test_v2_accepted(self):
        try:result=q.parse_task(self.row(manifest()))
        except q.Hold as e:self.fail('new manifest rejected: '+str(e))
        self.assertEqual(result,manifest())
    def test_context_traversal_refused(self):
        m=manifest();m['context_sources']=[dict(revision='head',path='../a',blob_sha='f'*40)]
        with self.assertRaisesRegex(q.Hold,'^CONTEXT_SOURCE_FIELDS$'):q.parse_task(self.row(m))

if __name__=='__main__': unittest.main()
