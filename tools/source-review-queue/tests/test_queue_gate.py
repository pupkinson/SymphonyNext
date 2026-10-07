"""Strict source-tool protocol and preparation/finalization boundaries."""
import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from test_queue_context import q, manifest, FakeGit, H, B, T

class GateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(q,'build_review_sources'))
        a=FakeGit();self.m=manifest();self.store=q.build_review_sources(a,self.m,a.pr)
        self.reader=q.SourceReader(self.store)
        self.assertIn('source_reader',__import__('inspect').signature(q.Gate).parameters,'missing source gate integration')
        self.g=q.Gate(source_reader=self.reader)
        self.head=patch.object(q,'HEAD',H);self.head.start();self.addCleanup(self.head.stop)
        self.g.client({'id':1,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}})
        self.start=self.g.client({'id':2,'method':'thread/start','params':{'cwd':str(q.SPACE)}})
        self.g.server({'id':2,'result':{'thread':{'id':'thread1'}}})
        self.g.client({'id':3,'method':'turn/start','params':{'cwd':str(q.SPACE),'threadId':'thread1'}})
        self.g.server({'id':3,'result':{'turn':{'id':'turn1'}}})
    def item(self,sid,page,call='call1',method='item/started'):
        return {'method':method,'params':{'threadId':'thread1','turnId':'turn1','item':{
            'type':'dynamicToolCall','id':call,'tool':q.SOURCE_TOOL,'arguments':{'source_id':sid,'page':page},
            'status':'inProgress' if method=='item/started' else 'completed','success':True}}}
    def request(self,sid,page,call='call1',rid=60):
        return {'id':rid,'method':'item/tool/call','params':{'threadId':'thread1','turnId':'turn1',
                'callId':call,'tool':q.SOURCE_TOOL,'arguments':{'source_id':sid,'page':page}}}
    def one(self,sid,page,call,rid):
        self.g.server(self.item(sid,page,call))
        reply=self.g.server(self.request(sid,page,call,rid))
        self.g.server(self.item(sid,page,call,'item/completed'))
        return reply
    def report_and_complete(self):
        self.g.server({'method':'item/completed','params':{'item':{'type':'agentMessage','text':H+' ACCEPTED source only; execution not performed.'}}})
        self.g.server({'method':'turn/completed','params':{'threadId':'thread1','turn':{'id':'turn1','status':'completed'}}})
    def test_only_source_tool_advertised(self):
        self.assertEqual(self.start['params']['dynamicTools'],[q.source_tool_spec()])
        self.assertEqual(self.start['params']['approvalPolicy'],'never')
    def test_full_delivery_and_receipt_required(self):
        rid=60
        for sid, pages in self.reader.pages.items():
            for page in range(len(pages)):
                self.assertTrue(self.one(sid,page,'call'+str(rid),rid)['result']['success']);rid+=1
        self.report_and_complete();self.assertTrue(self.g.complete())
        self.g.state['app_server_exit']=0
        self.assertTrue(q.completed(self.g.state,{'head':H,'text':self.g.report},H))
        q.verify_source_receipt(q.SourceReader(self.store),self.g.state['source_read'])
    def test_early_completion_is_not_success(self):
        with self.assertRaisesRegex(q.Hold,'^SOURCE_CONTEXT_INCOMPLETE$'):self.report_and_complete()
        self.assertFalse(self.g.complete())
    def test_foreign_thread_request_refused(self):
        sid=next(iter(self.reader.pages));self.g.server(self.item(sid,0));r=self.request(sid,0)
        r['params']['threadId']='other'
        with self.assertRaisesRegex(q.Hold,'^SOURCE_TOOL_TARGET$'):self.g.server(r)
        self.assertEqual(self.reader.calls,0)
    def test_unadvertised_tool_refused(self):
        sid=next(iter(self.reader.pages));r=self.request(sid,0);r['params']['tool']='shell'
        with self.assertRaisesRegex(q.Hold,'^SOURCE_TOOL_TARGET$'):self.g.server(r)
    def test_namespace_mismatch_refused(self):
        sid=next(iter(self.reader.pages));r=self.request(sid,0);r['params']['namespace']='terminal'
        with self.assertRaisesRegex(q.Hold,'^SOURCE_TOOL_TARGET$'):self.g.server(r)
    def test_approval_still_refused(self):
        with self.assertRaisesRegex(q.Hold,'^SERVER_TOOL_OR_APPROVAL_REFUSED$'):
            self.g.server({'id':90,'method':'item/commandExecution/requestApproval','params':{}})
    def test_native_execution_still_refused(self):
        with self.assertRaisesRegex(q.Hold,'^NATIVE_TOOL_ACTIVITY_REFUSED$'):
            self.g.server({'method':'item/started','params':{'item':{'type':'commandExecution'}}})
    def test_request_without_started_item_refused(self):
        sid=next(iter(self.reader.pages))
        with self.assertRaisesRegex(q.Hold,'^SOURCE_TOOL_SEQUENCE$'):self.g.server(self.request(sid,0))
    def test_request_arguments_cannot_change_after_started(self):
        sid=next(iter(self.reader.pages));self.g.server(self.item(sid,0));r=self.request(sid,0)
        r['params']['arguments']['page']=1
        with self.assertRaisesRegex(q.Hold,'^SOURCE_TOOL_SEQUENCE$'):self.g.server(r)
    def test_duplicate_request_id_refused(self):
        sid=next(iter(self.reader.pages));self.one(sid,0,'c1',60);self.g.server(self.item(sid,0,'c2'))
        with self.assertRaisesRegex(q.Hold,'^SOURCE_TOOL_SEQUENCE$'):self.g.server(self.request(sid,0,'c2',60))
    def test_completion_without_response_refused(self):
        sid=next(iter(self.reader.pages));self.g.server(self.item(sid,0))
        with self.assertRaisesRegex(q.Hold,'^SOURCE_TOOL_SEQUENCE$'):self.g.server(self.item(sid,0,method='item/completed'))
    def test_second_turn_refused(self):
        with self.assertRaisesRegex(q.Hold,'^SECOND_OR_EARLY_TURN_REFUSED$'):
            self.g.client({'id':9,'method':'turn/start','params':{'cwd':str(q.SPACE),'threadId':'thread1'}})

class PersistenceTests(unittest.TestCase):
    def make(self):
        a=FakeGit();m=manifest();store=q.build_review_sources(a,m,a.pr)
        return a,m,store
    def test_store_load_detects_drift(self):
        a,m,s=self.make()
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);raw=q.wire_json(s);(p/'sources.json').write_bytes(raw)
            (p/'packet.json').write_bytes(q.wire_json({'source_store_sha256':q.sha(raw)}))
            r=q.load_source_reader(p,m);self.assertEqual(r.store,s)
            (p/'sources.json').write_bytes(raw+b'\n')
            with self.assertRaisesRegex(q.Hold,'^SOURCE_STORE_CHANGED$'):q.load_source_reader(p,m)
    def test_old_jobs_need_no_new_file(self):
        self.assertIsNone(q.load_source_reader('/does-not-exist',manifest(False)))
    def test_incomplete_or_forged_receipt_refused(self):
        a,m,s=self.make();r=q.SourceReader(s)
        for sid,ps in r.pages.items():
            for page in range(len(ps)):r.read_page({'source_id':sid,'page':page})
        receipt=r.receipt();q.verify_source_receipt(q.SourceReader(s),receipt)
        for field,value in [('deliveries',receipt['deliveries'][:-1]),('complete',False),('calls',100),('source_store_sha256','0'*64)]:
            bad=copy.deepcopy(receipt);bad[field]=value
            with self.subTest(field=field),self.assertRaises(q.Hold):q.verify_source_receipt(q.SourceReader(s),bad)
    def test_prepare_writes_index_and_store_not_monolith(self):
        a,m,s=self.make();a=FakeGit(large=True)
        row=dict(state='open',number=887,user={'login':q.OWNER},labels=[{'name':q.LABEL}],
                 title='review',body='```symphony-next\n'+json.dumps(m)+'\n```')
        old=a.get
        def get(path):
            if path=='/issues/887':return copy.deepcopy(row)
            if path=='':return {'id':q.REPO_ID}
            if path=='/pulls/84':return copy.deepcopy(a.pr)
            return old(path)
        a.get=get
        with tempfile.TemporaryDirectory() as t,patch.object(q,'QROOT',Path(t)),patch.object(q,'probe',return_value={}),patch.object(q,'check_auth'):
            space=Path(t)/'workspaces/GH-887';space.mkdir(parents=True)
            saved={k:getattr(q,k) for k in ('STATE','RUN','SPACE','HEAD','BASE','TREE')}
            try:
                q.prepare_task(887,a);d=Path(t)/'jobs/GH-887'
                self.assertTrue((d/'sources.json').is_file(),'missing prepared source store')
                self.assertLess((d/'prompt.txt').stat().st_size,100000)
                self.assertIn('snq_source_read',(d/'prompt.txt').read_text())
                self.assertTrue((d/'ready').exists())
                self.assertEqual(q.load_source_reader(d,m).store['target']['head_sha'],H)
            finally:
                for k,v in saved.items():setattr(q,k,v)

if __name__=='__main__':unittest.main()
