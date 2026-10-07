"""Real subprocess/pipe test with a fake Codex peer, never a model call."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from test_queue_context import q, FakeGit, manifest, H

PEER = r'''
import json,sys
spec=json.load(open(sys.argv[1]))
def send(x):print(json.dumps(x,ensure_ascii=False),flush=True)
def recv():return json.loads(sys.stdin.readline())
x=recv();send({'id':x['id'],'result':{}})
assert recv()['method']=='initialized'
x=recv();assert x['params']['dynamicTools'][0]['name']=='snq_source_read'
send({'id':x['id'],'result':{'thread':{'id':'thread1'}}})
x=recv();send({'id':x['id'],'result':{'turn':{'id':'turn1'}}})
for n,(sid,page) in enumerate(spec['pages']):
    args={'source_id':sid,'page':page};item={'id':'call'+str(n),'type':'dynamicToolCall',
        'tool':'snq_source_read','arguments':args,'status':'inProgress'}
    send({'method':'item/started','params':{'threadId':'thread1','turnId':'turn1','item':item}})
    send({'id':100+n,'method':'item/tool/call','params':{'threadId':'thread1','turnId':'turn1',
        'callId':item['id'],'tool':'snq_source_read','arguments':args}})
    out=recv();assert out['id']==100+n and out['result']['success'] is True
    content=json.loads(out['result']['contentItems'][0]['text'])
    assert content['source_id']==sid and content['page']==page
    item.update(status='completed',success=True)
    send({'method':'item/completed','params':{'threadId':'thread1','turnId':'turn1','item':item}})
send({'method':'item/started','params':{'threadId':'thread1','turnId':'turn1','item':{'id':'report1','type':'agentMessage','text':''}}})
send({'method':'item/completed','params':{'threadId':'thread1','turnId':'turn1','item':{'id':'report1','type':'agentMessage',
    'text':spec['head']+' ACCEPTED finite offline peer; no runtime evidence.'}}})
send({'method':'turn/completed','params':{'threadId':'thread1','turn':{'id':'turn1','status':'completed'}}})
assert sys.stdin.read()==''
'''

class ProxyTests(unittest.TestCase):
    def test_actual_pipe_round_trip(self):
        api=FakeGit(extra={'test.md':('Денис🙂\n'*1500).encode()})
        store=q.build_review_sources(api,manifest(),api.pr);reader=q.SourceReader(store)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);peer=root/'peer.py';peer.write_text(PEER)
            case=root/'case.json';case.write_text(json.dumps({'head':H,'pages':sorted(reader.required)}))
            client, proxy_end=socket.socketpair();failure=[];notifications=[]
            def drive():
                try:
                    f=client.makefile('rwb',buffering=0)
                    def send(v):f.write(json.dumps(v).encode()+b'\n')
                    def recv():
                        line=f.readline()
                        if not line:raise AssertionError('early proxy EOF')
                        return json.loads(line)
                    send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'symphony-orchestrator'}}});assert recv()['id']==1
                    send({'method':'initialized','params':{}})
                    send({'id':2,'method':'thread/start','params':{'cwd':str(q.SPACE)}});assert recv()['id']==2
                    send({'id':3,'method':'turn/start','params':{'cwd':str(q.SPACE),'threadId':'thread1'}});assert recv()['id']==3
                    while True:
                        v=recv();notifications.append(v)
                        assert not (v.get('method')=='item/tool/call' and 'id' in v)
                        if v.get('method')=='turn/completed':break
                    f.close()
                except BaseException as e:failure.append(e)
            client.settimeout(10);thread=threading.Thread(target=drive);thread.start()
            try:
                with patch.object(q,'HEAD',H):
                    gate,code=q.proxy([sys.executable,str(peer),str(case)],input_fd=proxy_end.fileno(),
                         output_fd=proxy_end.fileno(),run_dir=root,limit=10,
                         env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'},source_reader=reader)
                    thread.join(12)
                    self.assertFalse(thread.is_alive());self.assertEqual(failure,[])
                    self.assertEqual(gate.state['app_server_exit'],0)
                    self.assertTrue(gate.complete(),gate.state)
                    self.assertTrue((root/'protocol.json').is_file())
                    q.verify_source_receipt(q.SourceReader(store),gate.state['source_read'])
                    self.assertTrue(notifications)
            finally:client.close();proxy_end.close()

if __name__=='__main__':unittest.main()
