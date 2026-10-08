"""GH92: real streams with deliberately chosen EOF readiness ordering."""
import json,os,socket,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from test_queue_context import q,H

PEER=r'''
import sys,json,time,os
from pathlib import Path
root=Path(sys.argv[1]);head=sys.argv[2];mode=sys.argv[3]
def send(v):print(json.dumps(v),flush=True)
def recv():return json.loads(sys.stdin.readline())
x=recv();send({'id':x['id'],'result':{}});assert recv()['method']=='initialized'
x=recv();send({'id':x['id'],'result':{'thread':{'id':'thread1'}}})
x=recv();send({'id':x['id'],'result':{'turn':{'id':'turn1'}}})
time.sleep(.1)
p={'threadId':'thread1','turnId':'turn1','item':{'id':'report1','type':'agentMessage','text':head+' ACCEPTED fixed peer result; not model/runtime evidence.'}}
raw=json.dumps({'method':'item/started','params':p})+'\n'
if mode=='fragment':
 sys.stdout.write(raw[:20]);sys.stdout.flush();(root/'fragment').touch()
 assert sys.stdin.read()==''
 sys.stdout.write(raw[20:]);sys.stdout.flush()
else:sys.stdout.write(raw);sys.stdout.flush()
send({'method':'item/completed','params':p})
send({'method':'turn/completed','params':{'threadId':'thread1','turn':{'id':'turn1','status':'completed'}}})
if mode!='fragment':assert sys.stdin.read()==''
if mode=='tail':
 end=time.monotonic()+3
 while not (root/'tail').exists() and time.monotonic()<end:time.sleep(.01)
 assert (root/'tail').exists()
'''

class OrderedSelector:
    """Control event order, not bytes or EOF values; delegate all actual I/O."""
    def __init__(self,factory,root,mode,suppress):
        self.inner=factory();self.root=root;self.mode=mode;self.suppress=suppress;self.server_first=False
    def register(self,*a):return self.inner.register(*a)
    def unregister(self,*a):return self.inner.unregister(*a)
    def close(self):return self.inner.close()
    def select(self,timeout=None):
        end=time.monotonic()+(timeout or 0)
        while True:
            events=self.inner.select(max(0,end-time.monotonic()))
            if self.mode=='tail' and self.suppress.is_set() and not self.server_first:
                server=[e for e in events if e[0].data=='server']
                if server:
                    if (self.root/'tail').exists():self.server_first=True
                    return server
                if time.monotonic()>=end:return []
                time.sleep(.005);continue
            if self.mode=='fragment':events.sort(key=lambda e:0 if e[0].data=='server' else 1)
            return events

class EOFOrderingTests(unittest.TestCase):
    def run_case(self,mode):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);peer=root/'peer.py';peer.write_text(PEER)
            client,local=socket.socketpair();client.settimeout(5);fail=[];release=threading.Event();suppress=threading.Event()
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
                    if mode=='tail':suppress.set()
                    if mode=='fragment':
                        end=time.monotonic()+3
                        while not (root/'fragment').exists() and time.monotonic()<end:time.sleep(.01)
                        assert (root/'fragment').exists();client.shutdown(socket.SHUT_WR)
                    while True:
                        v=recv()
                        if not v or v.get('method')=='turn/completed':break
                    if mode=='tail':f.write(b'{"id":');(root/'tail').touch();client.shutdown(socket.SHUT_WR)
                    elif mode=='open':release.wait(4);client.shutdown(socket.SHUT_WR)
                except BaseException as exc:fail.append(exc)
                finally:f.close()
            factory=q.selectors.DefaultSelector
            thread=threading.Thread(target=drive);thread.start()
            try:
                with patch.object(q,'HEAD',H),patch.object(q.selectors,'DefaultSelector',lambda:OrderedSelector(factory,root,mode,suppress)):
                    gate,code=q.proxy([sys.executable,str(peer),str(root),H,mode],input_fd=local.fileno(),output_fd=local.fileno(),run_dir=root,limit=1.2 if mode=='open' else 5,env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'})
                    local.shutdown(socket.SHUT_WR)
                    release.set();thread.join(4);self.assertFalse(thread.is_alive());self.assertEqual(fail,[])
                    state=json.loads((root/'protocol.json').read_text())
                    if mode=='fragment':self.assertTrue(gate.complete(),state);self.assertEqual(state['app_server_exit'],0)
                    else:
                        self.assertEqual(state.get('failure'),'RPC_PARTIAL_FRAME_EOF' if mode=='tail' else 'RPC_TRANSPORT_NOT_CLOSED',state)
                        self.assertFalse(gate.complete(),state)
                        self.assertFalse(q.completed(state,{'head':H,'text':gate.report},H),state)
            finally:release.set();client.close();local.close()
    def test_server_eof_first_does_not_skip_unread_client_tail(self):self.run_case('tail')
    def test_client_half_close_allows_fragmented_server_message(self):self.run_case('fragment')
    def test_client_without_eof_cannot_finish_successfully(self):self.run_case('open')

if __name__=='__main__':unittest.main()
