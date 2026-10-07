"""GH91 regressions: report binding, one-use RPC replies and partial EOF."""
import json,os,socket,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from test_queue_context import q,H


def ready():
    g=q.Gate()
    g.client({'id':1,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}})
    g.server({'id':1,'result':{}})
    g.client({'method':'initialized','params':{}})
    g.client({'id':2,'method':'thread/start','params':{'cwd':str(q.SPACE)}})
    g.server({'id':2,'result':{'thread':{'id':'thread1'}}})
    g.client({'id':3,'method':'turn/start','params':{'cwd':str(q.SPACE),'threadId':'thread1'}})
    g.server({'id':3,'result':{'turn':{'id':'turn1'}}})
    return g


def message(method='item/completed',thread='thread1',turn='turn1',ident='report1'):
    return {'method':method,'params':{'threadId':thread,'turnId':turn,'item':{
        'id':ident,'type':'agentMessage','text':H+' ACCEPTED fixture source review only; tests not executed.'}}}


def finish(g):
    g.server(message('item/started'));g.server(message())
    g.server({'method':'turn/completed','params':{'threadId':'thread1','turn':{'id':'turn1','status':'completed'}}})


class ReportBindingTests(unittest.TestCase):
    def test_report_from_wrong_or_missing_thread_turn_refused(self):
        for thread,turn in [('foreign','turn1'),('thread1','foreign'),(None,'turn1'),('thread1',None)]:
            g=ready();g.server(message('item/started'))
            with self.subTest(thread=thread,turn=turn),self.assertRaisesRegex(q.Hold,'^REPORT_TARGET$'):
                g.server(message(thread=thread,turn=turn))
            self.assertEqual(g.report,'')
    def test_report_without_started_item_refused(self):
        g=ready()
        with self.assertRaisesRegex(q.Hold,'^REPORT_LIFECYCLE$'):g.server(message())
        self.assertEqual(g.report,'')
    def test_late_and_duplicate_report_refused(self):
        for terminal in (False,True):
            g=ready()
            if terminal:finish(g)
            else:g.server(message('item/started'));g.server(message())
            before=g.report
            with self.subTest(terminal=terminal),self.assertRaises(q.Hold):g.server(message())
            self.assertEqual(g.report,before)
    def test_valid_report_lifecycle_completes(self):
        g=ready()
        with patch.object(q,'HEAD',H):finish(g);self.assertTrue(g.complete())


class ReplyBindingTests(unittest.TestCase):
    def test_request_ids_reject_invalid_types_and_values(self):
        for rid in (None,True,False,{},[],1.0,'',-1,2**63,'x'*129):
            g=q.Gate()
            with self.subTest(rid=rid),self.assertRaisesRegex(q.Hold,'^RPC_REQUEST_ID$'):
                g.client({'id':rid,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}})
    def test_reused_client_request_id_refused(self):
        g=q.Gate();g.client({'id':1,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}})
        g.server({'id':1,'result':{}});g.client({'method':'initialized','params':{}})
        with self.assertRaisesRegex(q.Hold,'^RPC_REQUEST_ID_REUSED$'):
            g.client({'id':1,'method':'thread/start','params':{'cwd':str(q.SPACE)}})
    def test_duplicate_start_replies_cannot_rebind(self):
        for rid,field in [(2,'thread'),(3,'turn')]:
            for terminal in (False,True):
                g=ready()
                if terminal:finish(g)
                before=(g.thread,g.turn,g.state['turn_status'])
                with self.subTest(field=field,terminal=terminal),self.assertRaisesRegex(q.Hold,'^RPC_REPLY_NOT_PENDING$'):
                    g.server({'id':rid,'result':{field:{'id':'other'}}})
                self.assertEqual((g.thread,g.turn,g.state['turn_status']),before)
    def test_unknown_response_refused(self):
        g=ready()
        with self.assertRaisesRegex(q.Hold,'^RPC_REPLY_NOT_PENDING$'):g.server({'id':987,'result':{}})
    def test_reply_id_type_not_coerced(self):
        g=q.Gate();g.client({'id':1,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}})
        with self.assertRaisesRegex(q.Hold,'^RPC_REQUEST_ID$'):g.server({'id':True,'result':{}})
    def test_early_thread_start_refused(self):
        g=q.Gate()
        with self.assertRaisesRegex(q.Hold,'^RPC_CLIENT_SEQUENCE$'):
            g.client({'id':2,'method':'thread/start','params':{'cwd':str(q.SPACE)}})
    def test_pending_error_is_terminal(self):
        g=q.Gate();g.client({'id':1,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}})
        with self.assertRaisesRegex(q.Hold,'^CODEX_RPC_REJECTED$'):g.server({'id':1,'error':{'code':-1,'message':'synthetic'}})
        with self.assertRaises(q.Hold):g.server({'id':1,'result':{}})


PEER=r'''
import sys,json,time
head=sys.argv[1];tail=sys.argv[2]
def send(v):print(json.dumps(v),flush=True)
def recv():return json.loads(sys.stdin.readline())
x=recv();send({'id':x['id'],'result':{}})
assert recv()['method']=='initialized'
x=recv();send({'id':x['id'],'result':{'thread':{'id':'thread1'}}})
x=recv();send({'id':x['id'],'result':{'turn':{'id':'turn1'}}})
time.sleep(.1)
p={'threadId':'thread1','turnId':'turn1','item':{'id':'report1','type':'agentMessage','text':head+' ACCEPTED synthetic peer source only, not runtime evidence.'}}
send({'method':'item/started','params':p});send({'method':'item/completed','params':p})
send({'method':'turn/completed','params':{'threadId':'thread1','turn':{'id':'turn1','status':'completed'}}})
assert sys.stdin.read()==''
if tail=='server':sys.stdout.write('{"id":');sys.stdout.flush()
'''

class PartialEOFTests(unittest.TestCase):
    def run_case(self,tail):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);peer=root/'peer.py';peer.write_text(PEER)
            client,local=socket.socketpair();client.settimeout(5);fail=[]
            def drive():
                f=client.makefile('rwb',buffering=0)
                try:
                    def send(v):f.write(json.dumps(v).encode()+b'\n')
                    def recv():
                        raw=f.readline()
                        return json.loads(raw) if raw else None
                    send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}});assert recv()['id']==1
                    send({'method':'initialized','params':{}})
                    send({'id':2,'method':'thread/start','params':{'cwd':str(q.SPACE)}});assert recv()['id']==2
                    send({'id':3,'method':'turn/start','params':{'cwd':str(q.SPACE),'threadId':'thread1'}});assert recv()['id']==3
                    if tail=='client':f.write(b'{"id":')
                    while True:
                        v=recv()
                        if not v or v.get('method')=='turn/completed':break
                    client.shutdown(socket.SHUT_WR)
                except BaseException as exc:fail.append(exc)
                finally:f.close()
            thread=threading.Thread(target=drive);thread.start()
            try:
                with patch.object(q,'HEAD',H):
                    gate,code=q.proxy([sys.executable,str(peer),H,tail],input_fd=local.fileno(),output_fd=local.fileno(),run_dir=root,limit=5,env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'})
                    thread.join(6);self.assertFalse(thread.is_alive());self.assertEqual(fail,[])
                    state=json.loads((root/'protocol.json').read_text())
                    if tail=='clean':
                        self.assertTrue(gate.complete(),state);self.assertEqual(state['app_server_exit'],0)
                    else:
                        self.assertEqual(state.get('failure'),'RPC_PARTIAL_FRAME_EOF',state)
                        self.assertFalse(gate.complete(),state)
                        self.assertFalse(q.completed(state,{'head':H,'text':gate.report},H),state)
            finally:client.close();local.close()
    def test_partial_server_eof_after_valid_turn_refused(self):self.run_case('server')
    def test_partial_client_eof_after_valid_turn_refused(self):self.run_case('client')
    def test_clean_eof_still_succeeds(self):self.run_case('clean')

if __name__=='__main__':unittest.main()
