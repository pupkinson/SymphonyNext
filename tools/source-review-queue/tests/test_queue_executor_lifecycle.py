"""Real files/processes with synthetic GitHub and model protocol peers."""
import base64
import copy
import contextlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import threading
import unittest
from unittest.mock import patch

from test_queue_context import q, FakeGit, B, BT, H, T
import test_queue_executor as executor_tests
from test_queue_executor import developer_row, developer_manifest
from test_queue_profiles import account_result


class DeveloperGit(FakeGit):
    def __init__(self,row):
        super().__init__()
        self.base.update({'change.py':b'value = 1\n',
                          'test_change.py':b'import change\nassert change.value == 2\n',
                          '.github/workflows/check.yml':b'name: unchanged\n'})
        self.row=copy.deepcopy(row);self.writes=[];self.refs={'main':B}
        self.blobs={q.git_blob_sha(raw):raw for raw in self.base.values()}
        self.trees={BT:{'sha':BT,'truncated':False,'tree':[
            dict(path=p,type='blob',mode='100644',sha=q.git_blob_sha(raw),size=len(raw))
            for p,raw in self.base.items()]}}
        self.commits={B:{'sha':B,'tree':{'sha':BT}}}
        self.prs=[];self.issues=[];self.comments=[]

    def blob_bytes(self,oid,size):
        raw=self.blobs[oid]
        assert len(raw)==size
        return raw

    def get(self,path):
        from urllib.parse import unquote
        if path=='':return {'id':q.REPO_ID}
        if path=='/issues/123':return copy.deepcopy(self.row)
        if path.startswith('/git/ref/heads/'):
            ref=unquote(path.removeprefix('/git/ref/heads/'))
            if ref not in self.refs:raise q.Hold('API_HTTP_404')
            return {'ref':'refs/heads/'+ref,'object':{'sha':self.refs[ref]}}
        if path.startswith('/git/commits/'):return copy.deepcopy(self.commits[path.split('/')[-1]])
        if path.startswith('/git/trees/'):return copy.deepcopy(self.trees[path.split('/')[-1].split('?')[0]])
        if path.startswith('/git/blobs/'):
            oid=path.split('/')[-1];raw=self.blobs[oid]
            return dict(sha=oid,encoding='base64',size=len(raw),content=base64.b64encode(raw).decode())
        if path.startswith('/pulls?'):return copy.deepcopy(self.prs)
        if path.startswith('/issues?'):return copy.deepcopy(self.issues)
        if path=='/pulls/555':return copy.deepcopy(self.prs[0])
        if path=='/issues/124':return copy.deepcopy(self.issues[0])
        if path.endswith('/comments?per_page=100'):return copy.deepcopy(self.comments)
        raise AssertionError('unexpected GET '+path)

    def request(self,method,path,body=None):
        from urllib.parse import unquote
        self.writes.append((method,path,copy.deepcopy(body)))
        if method=='POST' and path=='/git/refs':
            name=body['ref'].removeprefix('refs/heads/');self.refs[name]=body['sha']
            return self.get('/git/ref/heads/'+name)
        if method=='PATCH' and path.startswith('/git/refs/heads/'):
            name=unquote(path.removeprefix('/git/refs/heads/'));self.refs[name]=body['sha']
            return self.get('/git/ref/heads/'+name)
        if method=='POST' and path=='/git/blobs':
            raw=base64.b64decode(body['content']);oid=q.git_blob_sha(raw);self.blobs[oid]=raw
            return {'sha':oid}
        if method=='POST' and path=='/git/trees':
            oid='e'*40;entries={x['path']:x for x in self.trees[BT]['tree']}
            for x in body['tree']:
                if x['sha'] is None:entries.pop(x['path'],None)
                else:entries[x['path']]=dict(x,size=len(self.blobs[x['sha']]))
            self.trees[oid]=dict(sha=oid,truncated=False,tree=list(entries.values()))
            return {'sha':oid}
        if method=='POST' and path=='/git/commits':
            oid=H;self.commits[oid]=dict(sha=oid,tree={'sha':body['tree']})
            return {'sha':oid}
        if method=='POST' and path=='/pulls':
            pr=dict(number=555,state='open',merged=False,draft=True,body=body['body'],
                    html_url='https://github.com/pupkinson/SymphonyNext/pull/555',
                    head={'sha':H,'ref':body['head'],'repo':{'id':q.REPO_ID}},
                    base={'sha':B,'ref':body['base'],'repo':{'id':q.REPO_ID}})
            self.prs.append(pr);return copy.deepcopy(pr)
        if method=='POST' and path=='/issues':
            issue=dict(number=124,state='open',user={'login':q.OWNER},labels=[],**body)
            self.issues.append(issue);return copy.deepcopy(issue)
        if method=='POST' and path=='/issues/124/labels':
            self.issues[0]['labels']=[{'name':x} for x in body['labels']]
            return self.issues[0]['labels']
        if method=='POST' and path in ('/issues/123/comments','/issues/124/comments'):
            comment=dict(id=len(self.comments)+1,**body);self.comments.append(comment);return comment
        if method=='DELETE' and path==f'/issues/123/labels/{q.LABEL}':
            self.row['labels']=[];return None
        if method=='DELETE' and path==f'/issues/124/labels/{q.LABEL}':
            self.issues[0]['labels']=[];return None
        raise AssertionError('unexpected write '+method+' '+path)


class LifecycleTests(executor_tests.ExecutorTests):
    def prepare(self):
        self.assertTrue(hasattr(self.a,'prepare'),'developer is not connected to Symphony hooks')
        api=DeveloperGit(developer_row())
        with patch.object(self.a,'preflight',return_value={'status':'PASS','fixture':True}),\
             patch.object(q,'probe',side_effect=lambda *a,**kw:account_result(q.review_profile())):
            self.a.prepare(123,api)
        return api,self.a.current(123)

    def test_prepare_materializes_exact_base_and_deduplicates_polling(self):
        api,d=self.prepare();task=q.decode(q.read(d/'task.json'))
        self.assertEqual(task['manifest'],developer_manifest())
        self.assertEqual(task['profile'],self.a.profile())
        self.assertTrue((Path(task['workspace'])/'change.py').is_file())
        self.assertTrue((d/'ready').is_file())
        before=list(api.writes)
        with self.assertRaises(q.Hold):self.a.prepare(123,api)
        self.assertEqual(api.writes,before)

    def test_q_prepare_dispatches_developer_not_source_review(self):
        api=DeveloperGit(developer_row())
        with patch.object(q,'execution_adapter',return_value=self.a),\
             patch.object(self.a,'prepare') as prepare:
            q.prepare_task(123,api)
        prepare.assert_called_once()

    def test_native_sandbox_failure_prevents_auth_or_turn(self):
        self.assertTrue(hasattr(self.a,'prepare'),'developer prepare missing')
        api=DeveloperGit(developer_row())
        with patch.object(self.a,'preflight',side_effect=q.Hold('SANDBOX_PREFLIGHT_FAILED')),\
             patch.object(q,'probe') as probe:
            with self.assertRaisesRegex(q.Hold,'SANDBOX_PREFLIGHT_FAILED'):self.a.prepare(123,api)
        probe.assert_not_called()
        self.assertFalse(api.prs);self.assertFalse(api.issues)
        self.assertEqual(api.refs,{'main':B})
        self.assertTrue(all('/comments' in path or '/labels/' in path for _,path,_ in api.writes))

    def test_real_repository_metadata_can_be_read_without_becoming_writable(self):
        p=self.repo/'.github/workflows';p.mkdir(parents=True);(p/'ci.yml').write_text('read only\n')
        self.assertIn('.github/workflows/ci.yml',self.a.snapshot(self.repo))
        with self.assertRaises(q.Hold):self.a.path('.github/workflows/ci.yml',True)

    def test_worker_prompt_tamper_and_stale_attempt_fail_before_launch(self):
        api,d=self.prepare();task=q.decode(q.read(d/'task.json'))
        worker=self.a.worker(123,api)
        (d/'prompt.txt').write_text('injected commands')
        with self.assertRaisesRegex(q.Hold,'PROMPT_CHANGED'):worker.prompt_bytes()
        marker=self.queue/'jobs/GH-123/execution.json';q.save(marker,{'role':'developer','generation':2})
        with self.assertRaises(q.Hold):worker.check()

    def test_agent_entrypoint_uses_developer_dispatch(self):
        api,d=self.prepare()
        with patch.object(q.sys,'argv',['queue.py','_agent']),\
             patch.object(q.os,'geteuid',return_value=q.UID),\
             patch.object(q.os,'getegid',return_value=q.GID),\
             patch.object(q,'job_number',return_value=123),\
             patch.object(q,'Api',return_value=api),\
             patch.object(q,'execution_adapter',return_value=self.a),\
             patch.object(self.a,'agent',return_value=0) as agent:
            self.assertEqual(q.main(),0)
        agent.assert_called_once()

    def test_real_test_exit_is_recorded_and_new_write_invalidates_it(self):
        api,d=self.prepare();worker=self.a.worker(123,api)
        worker.command_runner=lambda repo,allowed,argv,seconds,check: self.real_test(repo,argv)
        failed=worker.call('snq_dev_test',{'test':'unit'})
        self.assertEqual(failed['exit_code'],1)
        old=q.sha((worker.repo/'change.py').read_bytes())
        worker.call('snq_dev_write',dict(path='change.py',text='value = 2\n',old_sha256=old))
        self.assertEqual(q.decode(q.read(d/'tests.json')),{})
        passed=worker.call('snq_dev_test',{'test':'unit'})
        self.assertEqual(passed['exit_code'],0)
        self.assertEqual(passed['input_sha256'],q.sha(q.wire_json(self.a.snapshot(worker.repo))))

    def real_test(self,repo,argv):
        # Deliberately isolated test double for bwrap only, using this test's
        # synthetic, owned Python fixture. This is not a sandbox attestation.
        p=subprocess.run(argv,cwd=repo,capture_output=True,env={'PYTHONDONTWRITEBYTECODE':'1'})
        return dict(exit_code=p.returncode,argv=argv,input_sha256=q.sha(q.wire_json(self.a.snapshot(repo))),
                    output_sha256=q.sha(p.stdout+p.stderr),sandbox='TEST_DOUBLE_NOT_NATIVE',duration_ms=1)

    def completed_candidate(self):
        api,d=self.prepare();worker=self.a.worker(123,api)
        worker.command_runner=lambda repo,allowed,argv,seconds,check:self.real_test(repo,argv)
        worker.call('snq_dev_write',dict(path='change.py',text='value = 2\n',old_sha256=q.sha(b'value = 1\n')))
        worker.call('snq_dev_test',{'test':'unit'})
        # Completion transport here is synthetic; native proxy is tested below.
        protocol=dict(thread_id='author-thread',turn_id='turn1',turn_request_id=3,
                      thread_requests=1,turn_requests=1,turn_status='completed',app_server_exit=0,
                      proxy_outcome='APP_SERVER_EOF',execution_profile=self.a.profile())
        context=worker.prompt_context();raw=worker.prompt_bytes()
        request=dict(id=3,method='turn/start',params=dict(threadId='author-thread',input=[dict(type='text',text=raw.decode())]))
        protocol['prompt_delivery']=q.prompt_delivery_receipt(context,request,q.wire_json(request)+b'\n')
        q.save(d/'run/protocol.json',protocol)
        q.save(d/'run/review.json',{'head':B,'text':'Completed assigned fixture for exact base '+B})
        result=self.a.finish(123,api)
        self.assertEqual(result['state'],'Review');self.assertEqual(result['head'],H)
        self.assertEqual(len(api.prs),1);self.assertTrue(api.prs[0]['draft'])
        self.assertEqual(len(api.issues),1)
        self.assertIn(H,api.issues[0]['body']);self.assertIn(B,api.issues[0]['body'])
        self.assertIn('snq-verdict',api.issues[0]['body'])
        before=list(api.writes);self.a.finish(123,api)
        self.assertEqual(before,api.writes)
        return api,d,result

    def test_handoff_creates_one_draft_pr_and_one_exact_head_review(self):
        api,d,result=self.completed_candidate()
        self.assertFalse(api.row['labels'],'completed owner task must leave dispatch admission')
        self.assertTrue(api.comments,'owner issue must contain a durable result')

    def test_review_text_mentioning_developer_schema_retains_old_dispatch(self):
        row=developer_row(dict(schema='snq-review/v1',pr=84,head_sha=H,base_sha=B,tree_sha=T,include_mix_reference=False))
        row['body']='Compare the future snq-develop/v1 format.\n'+row['body']
        api=DeveloperGit(row)
        with patch.object(q,'_prepare_task') as prepare:
            q.prepare_task(123,api)
        prepare.assert_called_once_with(123,api)

    def test_independent_verdict_accepts_artifact_and_new_head_invalidates_it(self):
        api,d,candidate=self.completed_candidate()
        result=dict(status=q.SUCCESS,protocol={'thread_id':'independent-reviewer'},
                    review_text='```snq-verdict\n'+json.dumps(dict(head_sha=H,base_sha=B,verdict='accepted'))+'\n```')
        accepted=self.a.review_finished(124,result,api)
        self.assertEqual(accepted['state'],'AcceptedSource')
        self.assertTrue((self.queue/'accepted/GH-123.json').is_file())
        api.prs[0]['head']['sha']='f'*40
        with self.assertRaisesRegex(q.Hold,'REVIEW_STALE'):self.a.review_finished(124,result,api)

    def test_failed_independent_review_blocks_without_done_or_artifact(self):
        api,d,candidate=self.completed_candidate()
        result=dict(status='SOURCE_REVIEW_INCOMPLETE',protocol={},review_text='')
        final=self.a.review_finished(124,result,api)
        self.assertEqual(final['state'],'Blocked')
        self.assertFalse((self.queue/'accepted/GH-123.json').exists())

    def test_prepare_failure_is_finalized_without_waiting_for_restart(self):
        api=DeveloperGit(developer_row())
        with patch.object(self.a,'preflight',side_effect=q.Hold('SANDBOX_PREFLIGHT_FAILED')):
            with self.assertRaises(q.Hold):self.a.prepare(123,api)
        d=self.a.current(123)
        self.assertEqual(q.decode(q.read(d/'final.json'))['state'],'Blocked')
        self.assertFalse(api.row['labels'])

    def test_recovery_does_not_launch_new_model_session(self):
        api,d=self.prepare()
        q.once(d/'run/model-session.claim',b'previous session\n')
        with patch.object(q,'proxy') as proxy:
            result=self.a.finish(123,api)
        proxy.assert_not_called();self.assertEqual(result['state'],'Blocked')
        self.assertFalse(api.prs);self.assertFalse(api.issues)

    def test_dependency_needs_accepted_artifact_not_status(self):
        self.assertTrue(hasattr(self.a,'dependencies'),'artifact dependency gate missing')
        self.policy['tasks']['123']['requires']=[{'issue':122,'head':H}];self.write_policy()
        grant=self.a.admit(developer_row(),developer_manifest())
        with self.assertRaisesRegex(q.Hold,'DEPENDENCY_ARTIFACT_UNAVAILABLE'):
            self.a.dependencies(grant,DeveloperGit(developer_row()),self.root/'inputs')

    def test_developer_api_write_scope_does_not_change_reviewer(self):
        api=q.Api('fixture-token',123)
        self.assertFalse(api.allowed('POST','/git/refs',{'ref':'refs/heads/main','sha':B}))
        self.assertFalse(api.allowed('POST','/issues',{'body':'arbitrary'}))
        self.assertTrue(hasattr(self.a,'scoped_api'),'scoped developer API missing')
        grant=self.a.admit(developer_row(),developer_manifest())
        scoped=self.a.scoped_api(api,123,grant)
        self.assertFalse(scoped.allowed('POST','/git/refs',{'ref':'refs/heads/main','sha':B}))
        self.assertFalse(scoped.allowed('PATCH','/git/refs/heads/main',{'sha':H,'force':True}))
        self.assertTrue(scoped.allowed('GET','/git/ref/heads/main',None))
        self.assertFalse(api.allowed('GET','/git/ref/heads/main',None))

    def test_gate_maps_supervisor_workspace_to_the_owned_branch_workspace(self):
        api,d=self.prepare();worker=self.a.worker(123,api);gate=worker.gate()
        with patch.object(q,'SPACE',worker.repo):
            gate.client({'id':1,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}})
            gate.server({'id':1,'result':{}});gate.client({'method':'initialized','params':{}})
            start=gate.client({'id':2,'method':'thread/start','params':{'cwd':str(worker.repo.parent)}})
        self.assertEqual(start['params']['cwd'],str(worker.repo))
        self.assertEqual({x['name'] for x in start['params']['dynamicTools']},
                         {'snq_dev_read','snq_dev_write','snq_dev_test'})

    def test_actual_proxy_round_trip_edits_and_tests_owned_fixture(self):
        api,d=self.prepare();worker=self.a.worker(123,api)
        worker.command_runner=lambda repo,allowed,argv,seconds,check:self.real_test(repo,argv)
        peer=d/'run/peer.py';received=d/'run/received.txt'
        peer.write_text(r'''
import json,sys
from pathlib import Path
def recv(): return json.loads(sys.stdin.readline())
def send(v): print(json.dumps(v),flush=True)
x=recv();send({'id':x['id'],'result':{}});assert recv()['method']=='initialized'
x=recv();assert len(x['params']['dynamicTools'])==3
send({'id':x['id'],'result':{'thread':{'id':'author-pipe'}}})
x=recv();Path(sys.argv[1]).write_text(x['params']['input'][0]['text'])
send({'id':x['id'],'result':{'turn':{'id':'turn-pipe'}}})
for n,tool,args in [(1,'snq_dev_write',dict(path='change.py',text='value = 2\n',old_sha256=sys.argv[2])),(2,'snq_dev_test',{'test':'unit'})]:
 item=dict(id='call'+str(n),type='dynamicToolCall',tool=tool,namespace=None,arguments=args,status='inProgress')
 send({'method':'item/started','params':{'threadId':'author-pipe','turnId':'turn-pipe','item':item}})
 send({'id':100+n,'method':'item/tool/call','params':{'threadId':'author-pipe','turnId':'turn-pipe','callId':item['id'],'tool':tool,'namespace':None,'arguments':args}})
 answer=recv();assert answer['result']['success']
 if n==2: assert json.loads(answer['result']['contentItems'][0]['text'])['exit_code']==0
 item['status']='completed';item['success']=True
 send({'method':'item/completed','params':{'threadId':'author-pipe','turnId':'turn-pipe','item':item}})
item=dict(id='report',type='agentMessage',text='Completed assigned fixture with actual test execution, base '+sys.argv[3])
for event in ['item/started','item/completed']:
 send({'method':event,'params':{'threadId':'author-pipe','turnId':'turn-pipe','item':item}})
send({'method':'turn/completed','params':{'threadId':'author-pipe','turn':{'id':'turn-pipe','status':'completed'}}})
assert sys.stdin.read()==''
''')
        client,endpoint=socket.socketpair();client.settimeout(4);errors=[]
        supervisor=str(worker.repo.parent)
        def drive():
            try:
                with client.makefile('rwb',buffering=0) as f:
                    def send(v):f.write(json.dumps(v).encode()+b'\n')
                    def recv():
                        line=f.readline()
                        if not line:raise EOFError('proxy closed before completion')
                        return json.loads(line)
                    send(dict(id=1,method='initialize',params={'clientInfo':{'name':'symphony-orchestrator'}}));recv()
                    send(dict(method='initialized',params={}))
                    send(dict(id=2,method='thread/start',params={'cwd':supervisor}));recv()
                    send(dict(id=3,method='turn/start',params={'cwd':supervisor,'threadId':'author-pipe','input':[]}));recv()
                    while recv().get('method')!='turn/completed':pass
                    client.shutdown(socket.SHUT_WR)
            except (OSError,ValueError,EOFError) as exc:errors.append(type(exc).__name__)
        thread=threading.Thread(target=drive);thread.start()
        try:
            with contextlib.ExitStack() as stack:
                for key in ('STATE','RUN','SPACE','HEAD','BASE','TREE'):stack.enter_context(patch.object(q,key,getattr(q,key)))
                q.bind_developer(123,1,worker.task['manifest'])
                gate,code=q.proxy([sys.executable,str(peer),str(received),q.sha(b'value = 1\n'),B],
                    input_fd=endpoint.fileno(),output_fd=endpoint.fileno(),limit=4,execution=worker,
                    env={'PATH':'/usr/bin:/bin'})
                endpoint.shutdown(socket.SHUT_WR);thread.join(4)
                self.assertEqual(errors,[]);self.assertFalse(thread.is_alive())
                self.assertTrue(gate.complete(),gate.state)
                self.assertEqual(gate.state['app_server_exit'],0)
                self.assertEqual(received.read_bytes(),(d/'prompt.txt').read_bytes())
                self.assertEqual(q.decode(q.read(d/'tests.json'))['unit']['exit_code'],0)
        finally:endpoint.close();client.close();thread.join(4)

    def test_native_tool_and_foreign_workspace_are_rejected(self):
        api,d=self.prepare();worker=self.a.worker(123,api);gate=worker.gate()
        gate.base.phase='inProgress';gate.base.thread='author';gate.base.turn='turn'
        with self.assertRaisesRegex(q.Hold,'NATIVE_TOOL_ACTIVITY_REFUSED'):
            gate.server({'method':'item/started','params':{'threadId':'author','turnId':'turn',
                        'item':{'id':'shell','type':'commandExecution'}}})
        with self.assertRaises(q.Hold):worker.call('snq_dev_test',{'test':'unit','argv':['/bin/sh']})
        with self.assertRaises(q.Hold):worker.call('shell',{'command':'id'})

    def test_real_command_timeout_stops_and_reaps_its_process_group(self):
        marker=self.root/'pid'
        program='import os,time,pathlib; pathlib.Path('+repr(str(marker))+').write_text(str(os.getpid())); time.sleep(20)'
        with patch.object(self.a,'sandbox_argv',return_value=[sys.executable,'-c',program]):
            started=time.monotonic()
            with self.assertRaisesRegex(q.Hold,'TEST_TIMEOUT'):
                self.a.run_test(self.repo,['change.py'],['fixed-fixture'],.15)
        self.assertLess(time.monotonic()-started,2)
        self.assertTrue(marker.is_file())
        with self.assertRaises(ProcessLookupError):os.kill(int(marker.read_text()),0)

    def test_process_group_cleanup_precedes_reaping_leader(self):
        events=[];real_popen=subprocess.Popen;real_kill=os.killpg
        def launch(*args,**kwargs):
            process=real_popen(*args,**kwargs);wait=process.wait
            def reap(*a,**kw):events.append('reap');return wait(*a,**kw)
            process.wait=reap;return process
        def kill(*args):events.append('kill-owned-group');return real_kill(*args)
        with patch.object(self.a,'sandbox_argv',return_value=[sys.executable,'-c','pass']),\
             patch.object(subprocess,'Popen',side_effect=launch),patch.object(os,'killpg',side_effect=kill):
            result=self.a.run_test(self.repo,['change.py'],['fixed-fixture'],2)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(events[0],'kill-owned-group','reaping first permits PID/process-group reuse')

    def test_changed_native_version_is_rejected_before_agent_launch(self):
        api,d=self.prepare()
        with patch.object(q,'validate_profile_runtime',side_effect=q.Hold('REVIEW_CODEX_VERSION')),\
             patch.object(q,'proxy',side_effect=AssertionError('model launch was attempted')) as launch:
            with self.assertRaisesRegex(q.Hold,'REVIEW_CODEX_VERSION'):self.a.agent(123,api)
        launch.assert_not_called()

    def test_descendant_receives_exact_accepted_source_bytes(self):
        api,d,candidate=self.completed_candidate()
        grant=self.a.admit(developer_row(),developer_manifest()) if api.row['labels'] else copy.deepcopy(self.policy['tasks']['123'])
        grant['requires']=[{'issue':122,'head':H}]
        predecessor=self.a.claim(122,dict(grant,generation=1))
        accepted={'state':'AcceptedSource','generation':1,'artifact':candidate['artifact']}
        (self.queue/'accepted').mkdir()
        q.save(self.queue/'accepted/GH-122.json',accepted)
        inputs=self.root/'consumer-inputs';self.a.dependencies(grant,api,inputs)
        self.assertEqual((inputs/'GH-122/change.py').read_bytes(),b'value = 2\n')
        q.save(self.queue/'jobs/GH-122/execution.json',{'role':'developer','generation':2})
        with self.assertRaisesRegex(q.Hold,'DEPENDENCY_ARTIFACT_UNAVAILABLE'):
            self.a.dependencies(grant,api,self.root/'stale-inputs')

    def test_installed_loader_rejects_unpinned_or_changed_sibling(self):
        module=Path(q.__file__).with_name('execution.py').read_bytes()
        (self.install/'execution.py').write_bytes(module)
        (self.install/'queue.py').write_text('# installed fixture\n')
        for metadata in [{}, {'execution_schema':'snq-execution-install/v1','execution_sha256':'0'*64}]:
            q.save(self.install/'installed.json',metadata)
            with patch.object(q,'__file__',str(self.install/'queue.py')),patch.object(q,'_EXECUTION_MODULE',None):
                with self.assertRaisesRegex(q.Hold,'EXECUTION_INSTALLATION_UNVERIFIED'):q.execution_adapter()

    def test_rollback_marker_skips_only_legacy_recovery_not_new_reconciliation(self):
        api,d=self.prepare()
        root=self.queue/'jobs/GH-123'
        self.assertTrue((root/'label-removed.json').is_file(),'old source-only controller must skip developer journals')
        with patch.object(q,'Api',return_value=api),patch.object(q,'execution_adapter',return_value=self.a),\
             patch.object(self.a,'finish',return_value={'state':'Blocked'}) as finish:
            q.recover_jobs()
        finish.assert_called_once_with(123,api)

    def test_stop_arriving_during_issue_read_prevents_file_write(self):
        api,d=self.prepare();worker=self.a.worker(123,api);old_get=worker.api.get
        def get(path):
            result=old_get(path)
            if path=='/issues/123':(d/'stop').write_text('stop during read')
            return result
        worker.api.get=get
        with self.assertRaisesRegex(q.Hold,'WORKER_STOP_REQUESTED'):
            worker.call('snq_dev_write',dict(path='change.py',text='too late\n',old_sha256=q.sha(b'value = 1\n')))
        self.assertEqual((worker.repo/'change.py').read_bytes(),b'value = 1\n')

    def test_monotonic_expiry_during_issue_read_prevents_write(self):
        api,d=self.prepare();worker=self.a.worker(123,api);old_get=worker.api.get
        def get(path):
            result=old_get(path)
            if path=='/issues/123':worker.end=time.monotonic()-1
            return result
        worker.api.get=get
        with self.assertRaisesRegex(q.Hold,'WORKER_TIMEOUT'):
            worker.call('snq_dev_write',dict(path='change.py',text='too late\n',old_sha256=q.sha(b'value = 1\n')))
        self.assertEqual((worker.repo/'change.py').read_bytes(),b'value = 1\n')

    def independent_result(self):
        return dict(issue=124,head=H,status=q.SUCCESS,protocol={'thread_id':'independent-reviewer'},
                    review_text='```snq-verdict\n'+json.dumps(dict(head_sha=H,base_sha=B,verdict='accepted'))+'\n```')

    def test_recovery_applies_review_after_its_delivery_was_retired(self):
        api,d,candidate=self.completed_candidate()
        review=self.queue/'jobs/GH-124';review.mkdir()
        q.save(review/'final.json',self.independent_result())
        q.once(review/'label-removed.json',b'{"confirmed":true}')
        with patch.object(q,'Api',return_value=api):q.recover_jobs()
        self.assertEqual(q.decode(q.read(d/'final.json'))['state'],'AcceptedSource')
        self.assertTrue((review/'linked-review-applied.json').is_file())
        before=list(api.writes)
        with patch.object(q,'Api',return_value=api):q.recover_jobs()
        self.assertEqual(api.writes,before,'second recovery must not republish results')

    def test_recovery_rebuilds_accepted_artifact_after_terminal_record(self):
        api,d,candidate=self.completed_candidate();save=q.save
        artifact=self.queue/'accepted/GH-123.json'
        def crash(path,value):
            if Path(path)==artifact:raise OSError('synthetic crash after final.json')
            return save(path,value)
        with patch.object(q,'save',side_effect=crash):
            with self.assertRaises(OSError):self.a.review_finished(124,self.independent_result(),api)
        self.assertEqual(q.decode(q.read(d/'final.json'))['state'],'AcceptedSource')
        self.assertFalse(artifact.exists())
        self.a.finish(123,api)
        self.assertTrue(artifact.is_file(),'recovery must converge accepted artifact with its terminal record')
        self.assertEqual(q.decode(q.read(artifact))['artifact'],candidate['artifact'])

    def test_uncertain_preparation_branch_is_read_back_without_repost(self):
        api=DeveloperGit(developer_row());request=api.request
        def lose_reply(method,path,body=None):
            result=request(method,path,body)
            if path=='/git/refs':raise q.Hold('WRITE_OUTCOME_UNKNOWN')
            return result
        api.request=lose_reply
        with patch.object(self.a,'preflight',return_value={'status':'PASS','fixture':True}),\
             patch.object(q,'probe',side_effect=lambda *a,**kw:account_result(q.review_profile())):
            with self.assertRaisesRegex(q.Hold,'WRITE_OUTCOME_UNKNOWN'):self.a.prepare(123,api)
        d=self.a.current(123)
        self.assertEqual(api.refs['snq/gh-123/g1'],B)
        with patch.object(q,'proxy') as proxy:
            result=self.a.finish(123,api)
        self.assertEqual(result['state'],'Blocked')
        self.assertTrue((d/'outbox/branch-receipt.json').exists())
        self.assertEqual(sum(path=='/git/refs' for _,path,_ in api.writes),1)
        proxy.assert_not_called()

    def test_unknown_branch_readback_refuses_a_different_remote_revision(self):
        api=DeveloperGit(developer_row());request=api.request
        def wrong_remote(method,path,body=None):
            result=request(method,path,body)
            if path=='/git/refs':
                api.refs['snq/gh-123/g1']='f'*40
                raise q.Hold('WRITE_OUTCOME_UNKNOWN')
            return result
        api.request=wrong_remote
        with patch.object(self.a,'preflight',return_value={'status':'PASS','fixture':True}),\
             patch.object(q,'probe',side_effect=lambda *a,**kw:account_result(q.review_profile())):
            with self.assertRaises(q.Hold):self.a.prepare(123,api)
        d=self.a.current(123)
        self.assertFalse((d/'outbox/branch-receipt.json').exists())
        self.assertEqual(q.decode(q.read(d/'final.json'))['state'],'Blocked')
        self.assertEqual(sum(path=='/git/refs' for _,path,_ in api.writes),1)


for name in list(executor_tests.ExecutorTests.__dict__):
    if name.startswith('test_'):setattr(LifecycleTests,name,None)

if __name__=='__main__':unittest.main()
