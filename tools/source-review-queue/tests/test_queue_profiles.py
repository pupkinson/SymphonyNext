"""Per-schema model binding; API/account boundaries are fixtures, never real auth."""
import contextlib
import copy
import json
import io
import os
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_queue_context import q, manifest, FakeGit, H

V1='snq-review/v1'
V2='snq-review/v2'


def row_for(m):
    return dict(state='open', number=887, user={'login':q.OWNER},
                labels=[{'name':q.LABEL}], title='review',
                body='```symphony-next\n'+json.dumps(m)+'\n```')


@contextlib.contextmanager
def environment(v2=True):
    """Actual temporary task/source files; replace only external Git/account data."""
    api=FakeGit();m=manifest(v2);row=row_for(m);old_get=api.get
    def get(path):
        if path=='/issues/887':return copy.deepcopy(row)
        if path=='':return {'id':q.REPO_ID}
        if path=='/pulls/84':return copy.deepcopy(api.pr)
        return old_get(path)
    api.get=get
    with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
        root=Path(directory);package=root/'package'
        meta=package/'node_modules/@openai/codex/package.json'
        meta.parent.mkdir(parents=True);meta.write_text('{"version":"0.159.3"}')
        (root/'workspaces/GH-887').mkdir(parents=True)
        for key,value in [('QROOT',root),('PACKAGE',package),
                          *[(key,getattr(q,key)) for key in ('STATE','RUN','SPACE','HEAD','BASE','TREE')]]:
            stack.enter_context(patch.object(q,key,value))
        yield root,api,m,row,meta


def account_result(profile):
    return dict(status='AUTH_AND_CATALOG_CHECKED_NO_TURN', model=profile['model'],
                review_profile=copy.deepcopy(profile), account_present=True,
                model_listed=True, auth_type='chatgpt', app_server_exit=0,
                quota=dict(has_quota_window=True,exhausted=False,primary_used_percent=5),
                model_entitlement='NOT_TESTED',model_turn='NOT_RUN')


def add_prompt_receipt(directory, protocol):
    """Synthetic unit completion only; real transport proofs are separate tests."""
    context=q.load_prompt_context(directory)
    raw=q.checked_prompt_bytes(directory,context)
    request={'id':3,'method':'turn/start','params':{'cwd':str(q.SPACE),'threadId':'thread1',
             'input':[{'type':'text','text':raw.decode('utf-8')}]}}
    protocol.update(thread_id='thread1',turn_id='turn1',turn_request_id=3,
                    prompt_delivery=q.prompt_delivery_receipt(context,request,q.wire_json(request)+b'\n'))
    return protocol


class ProfileTests(unittest.TestCase):
    def profile(self,schema=V2):
        self.assertTrue(hasattr(q,'review_profile'),'per-schema profile selector missing')
        return q.review_profile(schema)

    def test_v2_gate_uses_direct_model_not_legacy_global(self):
        a=FakeGit();reader=q.SourceReader(q.build_review_sources(a,manifest(),a.pr))
        gate=q.Gate(source_reader=reader)
        self.assertEqual(gate.state['model'],'gpt-5.5')
        self.assertEqual(q.MODEL,'gpt-6.1-sol')

    def test_v1_defaults_remain_unchanged(self):
        self.assertEqual(q.Gate().state['model'],'gpt-6.1-sol')
        self.assertIn('model="gpt-6.1-sol"',q.codex_args())

    def test_closed_profile_selection_and_copy(self):
        p=self.profile();self.assertEqual(p['model'],'gpt-5.5')
        self.assertEqual(p['task_schema'],V2)
        self.assertEqual(p['tools'],['snq_source_read'])
        p['model']='other';p['tools'].append('shell')
        self.assertEqual(self.profile()['model'],'gpt-5.5')
        self.assertEqual(self.profile()['tools'],['snq_source_read'])
        for value in (None,'snq-review/v3',{},False):
            with self.subTest(value=value),self.assertRaises(q.Hold):q.review_profile(value)

    def test_task_cannot_choose_model_or_profile(self):
        for name,value in [('model','other'),('review_profile',{'model':'other'})]:
            m=manifest();m[name]=value
            with self.subTest(name=name),self.assertRaisesRegex(q.Hold,'^TASK_FIELDS$'):
                q.parse_task(row_for(m))

    def test_cli_changes_only_model_for_paged_mode(self):
        old=q.codex_args();new=q.codex_args(profile=self.profile())
        self.assertEqual(len(old),len(new))
        self.assertEqual([(a,b) for a,b in zip(old,new) if a!=b],
                         [('model="gpt-6.1-sol"','model="gpt-5.5"')])
        for flag in q.DISABLED:self.assertIn(flag,new)
        self.assertIn('approval_policy="never"',new)

    def test_unknown_or_modified_profile_refused(self):
        p=self.profile()
        for key,value in [('model','gpt-6.1-sol'),('effort','high'),
                          ('tools',['shell']),('codex_version','0.160.0')]:
            bad=copy.deepcopy(p);bad[key]=value
            with self.subTest(key=key),self.assertRaises(q.Hold):q.codex_args(profile=bad)

    def test_gate_rejects_cross_schema_profile(self):
        a=FakeGit();reader=q.SourceReader(q.build_review_sources(a,manifest(),a.pr))
        with self.assertRaises(q.Hold):q.Gate(source_reader=reader,profile=self.profile(V1))
        with self.assertRaises(q.Hold):q.Gate(profile=self.profile(V2))

    def test_gate_binds_both_start_requests_and_records_profile(self):
        a=FakeGit();reader=q.SourceReader(q.build_review_sources(a,manifest(),a.pr))
        p=self.profile();g=q.Gate(source_reader=reader)
        g.client({'id':1,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}})
        g.server({'id':1,'result':{}});g.client({'method':'initialized','params':{}})
        start=g.client({'id':2,'method':'thread/start','params':{'cwd':str(q.SPACE),'model':'override'}})
        g.server({'id':2,'result':{'thread':{'id':'thread1'}}})
        turn=g.client({'id':3,'method':'turn/start','params':{'cwd':str(q.SPACE),'threadId':'thread1','model':'override'}})
        self.assertEqual(start['params']['model'],p['model']);self.assertEqual(turn['params']['model'],p['model'])
        self.assertEqual(turn['params']['effort'],p['effort'])
        self.assertEqual(g.state['review_profile'],p)
        self.assertEqual(start['params']['dynamicTools'],[q.source_tool_spec()])

    def test_runtime_version_is_checked_without_new_cli_or_metadata_override(self):
        p=self.profile()
        with environment() as (_,_,_,_,meta):
            q.validate_profile_runtime(p)
            meta.write_text('{"version":"0.159.4"}')
            with self.assertRaisesRegex(q.Hold,'^REVIEW_CODEX_VERSION$'):q.validate_profile_runtime(p)
            meta.unlink()
            with self.assertRaises(q.Hold):q.validate_profile_runtime(p)

    def test_job_snapshot_required_for_v2_but_not_old_v1(self):
        p=self.profile()
        with self.assertRaisesRegex(q.Hold,'^REVIEW_PROFILE_CHANGED$'):
            q.load_job_profile({'manifest':manifest()})
        task={'manifest':manifest(),'review_profile':p}
        self.assertEqual(q.load_job_profile(task),p)
        task['review_profile']['model']='gpt-6.1-sol'
        with self.assertRaises(q.Hold):q.load_job_profile(task)
        self.assertEqual(q.load_job_profile({'manifest':manifest(False)})['model'],'gpt-6.1-sol')

    def test_receipt_cannot_claim_wrong_model_or_profile(self):
        p=self.profile();proto=dict(model=p['model'],review_profile=copy.deepcopy(p))
        q.verify_profile_receipt(p,proto)
        for key,value in [('model','gpt-6.1-sol'),('review_profile',{}),('review_profile',None)]:
            bad=copy.deepcopy(proto);bad[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(q.Hold):q.verify_profile_receipt(p,bad)

    def test_probe_searches_chosen_model_not_legacy(self):
        p=self.profile();calls=[]
        class Rpc:
            def __init__(self,*args,**kwargs):pass
            def call(self,method,params=None):
                calls.append(method)
                if method=='initialize':return {}
                if method=='account/read':return {'account':{'type':'chatgpt'}}
                if method=='account/rateLimits/read':return {'rateLimits':{'primary':{'usedPercent':0}}}
                if method=='model/list':return {'data':[{'model':'gpt-5.5'}],'nextCursor':None}
                raise AssertionError('Unexpected method '+method)
            def send(self,value):self.value=value
            def close(self):return 0
        with patch.object(q,'Rpc',Rpc):out=q.probe(q.codex_args(p),{},profile=p)
        self.assertEqual(out['model'],'gpt-5.5');self.assertTrue(out['model_listed'])
        self.assertEqual(out['review_profile'],p);self.assertEqual(out['model_entitlement'],'NOT_TESTED')
        self.assertNotIn('turn/start',calls);q.check_auth(out,profile=p)

    def test_auth_cannot_use_legacy_model_evidence_for_v2(self):
        p=self.profile();out=account_result(p);q.check_auth(out,profile=p)
        out['model']='gpt-6.1-sol'
        with self.assertRaises(q.Hold):q.check_auth(out,profile=p)
        out=account_result(p);out['review_profile']['model']='gpt-6.1-sol'
        with self.assertRaises(q.Hold):q.check_auth(out,profile=p)

    def test_prepare_uses_paged_profile_and_persists_it(self):
        self.profile()
        seen=[]
        def probe(argv,env,profile=None):
            seen.append((argv,profile))
            return account_result(profile) if profile else {'status':'missing profile'}
        with environment() as (root,api,m,_,_),patch.object(q,'probe',side_effect=probe):
            q.prepare_task(887,api)
            task=json.loads((root/'jobs/GH-887/task.json').read_text())
            self.assertEqual(task['review_profile'],self.profile())
            self.assertEqual(seen[0][1],self.profile());self.assertIn('model="gpt-5.5"',seen[0][0])
            self.assertTrue((root/'jobs/GH-887/ready').exists())
            self.assertEqual(len(list((root/'reservations').glob('*/GH-*'))),1)

    def test_no_reservation_when_paged_model_is_unavailable(self):
        p=self.profile();out=account_result(p);out.update(model_listed=False,status='MODEL_NOT_LISTED')
        with environment() as (root,api,_,_,_),patch.object(q,'probe',return_value=out):
            with self.assertRaises(q.Hold):q.prepare_task(887,api)
            self.assertFalse((root/'jobs/GH-887/ready').exists())
            self.assertFalse(list(root.glob('reservations/*/GH-*')))

    def test_version_mismatch_blocks_before_probe_and_reservation(self):
        self.profile()
        with environment() as (root,api,_,_,meta),patch.object(q,'probe') as probe:
            meta.write_text('{"version":"0.160.0"}')
            with self.assertRaisesRegex(q.Hold,'^REVIEW_CODEX_VERSION$'):q.prepare_task(887,api)
            probe.assert_not_called();self.assertFalse(list(root.glob('reservations/*/GH-*')))

    def test_finalization_rejects_foreign_profile_despite_complete_pages(self):
        p=self.profile()
        with environment() as (root,api,m,_,_),patch.object(q,'probe',return_value=account_result(p)),patch.object(q,'deliver'):
            q.prepare_task(887,api);d=root/'jobs/GH-887';reader=q.load_source_reader(d,m)
            for sid,idx in sorted(reader.required):reader.read_page({'source_id':sid,'page':idx})
            proto=dict(thread_requests=1,turn_requests=1,turn_status='completed',app_server_exit=0,
                       proxy_outcome='APP_SERVER_EOF',model='gpt-6.1-sol',review_profile=p,source_read=reader.receipt())
            q.save(d/'run/protocol.json',add_prompt_receipt(d,proto))
            q.save(d/'run/review.json',dict(head=H,text=H+' A complete source-only fixture report, not native review.'))
            result=q.finish_task(887,api)
            self.assertEqual(result['status'],'REVIEW_PROFILE_CHANGED');self.assertFalse(result['release_approval'])

    def test_finalization_accepts_matching_profile_and_receipt(self):
        p=self.profile()
        with environment() as (root,api,m,_,_),patch.object(q,'probe',return_value=account_result(p)),patch.object(q,'deliver'):
            q.prepare_task(887,api);d=root/'jobs/GH-887';reader=q.load_source_reader(d,m)
            for sid,idx in sorted(reader.required):reader.read_page({'source_id':sid,'page':idx})
            proto=dict(thread_requests=1,turn_requests=1,turn_status='completed',app_server_exit=0,
                       proxy_outcome='APP_SERVER_EOF',model='gpt-5.5',review_profile=p,source_read=reader.receipt())
            q.save(d/'run/protocol.json',add_prompt_receipt(d,proto))
            q.save(d/'run/review.json',dict(head=H,text=H+' A complete source-only fixture report, not native review.'))
            result=q.finish_task(887,api)
            self.assertEqual(result['status'],q.SUCCESS);self.assertFalse(result['release_approval'])
            self.assertEqual(result['review_profile'],p)

    def test_worker_reloads_persisted_profile_for_cli_and_gate(self):
        p=self.profile();seen=[]
        with environment() as (root,api,_,_,_),patch.object(q,'probe',return_value=account_result(p)):
            q.prepare_task(887,api)
            def run(argv,**kwargs):
                seen.append((argv,kwargs))
                return SimpleNamespace(complete=lambda:True,state={'app_server_exit':0}), 'APP_SERVER_EOF'
            mask=os.umask(0o077);os.umask(mask)
            try:
                with patch.object(q.sys,'argv',['queue.py','_agent']),patch.object(q.os,'geteuid',return_value=q.UID),patch.object(q.os,'getegid',return_value=q.GID),patch.object(q,'job_number',return_value=887),patch.object(q,'proxy',side_effect=run),patch.object(q.signal,'signal'),patch.object(q.signal,'setitimer'):
                    self.assertEqual(q.main(),0)
            finally:os.umask(mask)
            self.assertEqual(seen[0][1]['profile'],p)
            self.assertIn('model="gpt-5.5"',seen[0][0])
            self.assertIsInstance(seen[0][1]['source_reader'],q.SourceReader)

    def test_worker_rejects_changed_snapshot_before_proxy(self):
        p=self.profile()
        with environment() as (root,api,_,_,_),patch.object(q,'probe',return_value=account_result(p)):
            q.prepare_task(887,api);path=root/'jobs/GH-887/task.json'
            task=json.loads(path.read_text());task['review_profile']['model']='gpt-6.1-sol';q.save(path,task)
            mask=os.umask(0o077);os.umask(mask)
            try:
                with patch.object(q.sys,'argv',['queue.py','_agent']),patch.object(q.os,'geteuid',return_value=q.UID),patch.object(q.os,'getegid',return_value=q.GID),patch.object(q,'job_number',return_value=887),patch.object(q,'proxy') as proxy:
                    with self.assertRaisesRegex(q.Hold,'^REVIEW_PROFILE_CHANGED$'):q.main()
                    proxy.assert_not_called()
            finally:os.umask(mask)

    def test_paged_auth_mode_uses_only_selected_profile_probe(self):
        p=self.profile();seen=[]
        def probe(argv,env,profile=None):
            seen.append((argv,profile));return account_result(profile)
        with environment() as (root,_,_,_,_),patch.object(q,'probe',side_effect=probe):
            mask=os.umask(0o077);os.umask(mask)
            try:
                with patch.object(q.sys,'argv',['queue.py','--auth-paged']),patch.object(q.os,'geteuid',return_value=q.UID),patch.object(q.os,'getegid',return_value=q.GID),contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(q.main(),0)
            finally:os.umask(mask)
            self.assertEqual(seen[0][1],p)
            self.assertEqual(json.loads(output.getvalue())['model_entitlement'],'NOT_TESTED')
            self.assertFalse(list(root.glob('reservations/*/GH-*')))

    def test_paged_auth_mode_requires_existing_service_identity(self):
        self.profile();mask=os.umask(0o077);os.umask(mask)
        try:
            with patch.object(q.sys,'argv',['queue.py','--auth-paged']),patch.object(q.os,'geteuid',return_value=997),patch.object(q,'probe') as probe:
                with self.assertRaisesRegex(q.Hold,'^SERVICE_IDENTITY_REQUIRED$'):q.main()
                probe.assert_not_called()
        finally:os.umask(mask)

if __name__=='__main__':unittest.main()
