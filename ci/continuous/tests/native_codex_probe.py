"""Offline native capability acceptance: fixture provider, no login or model billing.

Built-in skills/request_user_input remain advertised in Codex 0.155.1. Require an
empty skills catalog, unavailable arbitrary packages, and absent execution tools.
This is transport/capability evidence, not a real model review.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, sha256
from snci.reviewer import codex_flags, ReadOnlyContext, Session, SCHEMA, thread_params

TARGET={'pr':1,'head':'a'*40,'base':'b'*40,'tree':'c'*40}
REQUESTS=[]
CALL=None
class Server(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        self.send_response(200);self.end_headers();self.wfile.write(b'{"data":[]}')
    def do_POST(self):
        request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        REQUESTS.append(request)
        verdict=dict(TARGET,verdict='READY',findings=[],limitations=['Synthetic transport probe only'])
        item={'id':'m1','type':'message','role':'assistant','status':'completed',
              'content':[{'type':'output_text','text':json.dumps(verdict),'annotations':[]}]}
        if len(REQUESTS)==1 and CALL:
            item=dict(CALL,id='fc1',type='function_call',call_id='call1')
        events=[('response.created',{'response':{'id':'r1','status':'in_progress','output':[]}}),
                ('response.output_item.added',{'output_index':0,'item':item}),
                ('response.output_item.done',{'output_index':0,'item':item}),
                ('response.completed',{'response':{'id':'r1','status':'completed','output':[item],
                  'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}})]
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        for name,data in events:
            self.wfile.write(('event: '+name+'\ndata: '+json.dumps(dict(data,type=name))+'\n\n').encode());self.wfile.flush()

class FixtureSource:
    def blob(self,_):return b'FIXTURE_SOURCE'

def probe(binary,call,expected):
    global CALL
    CALL=call;REQUESTS.clear()
    server=ThreadingHTTPServer(('127.0.0.1',0),Server)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='snci-native-') as tmp:
        Path(tmp,'canary').write_text('PRIVATE_FIXTURE_CANARY')
        flags=codex_flags(tmp)+['-c','model_provider="fixture"','-c','model="fixture-model"',
            '-c','model_providers.fixture.name="Fixture"','-c','model_providers.fixture.wire_api="responses"',
            '-c','model_providers.fixture.requires_openai_auth=false',
            '-c','model_providers.fixture.supports_websockets=false',
            '-c','model_providers.fixture.base_url="http://127.0.0.1:'+str(server.server_port)+'/v1"',
            '-c','features.enable_request_compression=false']
        if CALL and CALL.get('namespace')=='skills' and CALL['name']=='read':
            CALL['arguments']=json.dumps({'package':tmp+'/canary'})
        p=subprocess.Popen([binary,'app-server','--stdio','--strict-config']+flags,cwd=tmp,
            env={'PATH':'/usr/bin:/bin','HOME':tmp,'CODEX_HOME':tmp,'LANG':'C.UTF-8'},
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
        ctx=ReadOnlyContext(FixtureSource(),{'README.md':{}},{},[]);s=Session(p,ctx,30)
        held=False
        try:
            s.rpc('initialize',{'clientInfo':{'name':'snci-native-probe','version':'1'},'capabilities':{'experimentalApi':True}})
            s.send({'method':'initialized','params':{}})
            params=thread_params(tmp,'fixture-model');params['modelProvider']='fixture'
            started=s.rpc('thread/start',params);s.thread=started['thread']['id']
            assert started['sandbox']=={'type':'readOnly','networkAccess':False}
            assert started.get('instructionSources',[])==[]
            s.rpc('turn/start',{'threadId':s.thread,'environments':[],
                'input':[{'type':'text','text':'Synthetic fixture: emit the supplied verdict.'}],'outputSchema':SCHEMA})
            try:s.finish(TARGET)
            except Hold:held=True
            assert REQUESTS
            inventory=[]
            for t in REQUESTS[0]['tools']:
                if t['type']=='namespace':inventory.extend(t['name']+'.'+x['name'] for x in t['tools'])
                else:inventory.append(t['name'])
            assert sorted(inventory)==['read_source','request_user_input','skills.list','skills.read'],inventory
            all_input=json.dumps([r.get('input',[]) for r in REQUESTS])
            assert 'PRIVATE_FIXTURE_CANARY' not in all_input
            assert '<skills_instructions>' not in all_input
            if expected=='denied':assert held
            else:
                assert not held
                outputs=[i.get('output') for r in REQUESTS[1:] for i in r.get('input',[]) if i.get('type')=='function_call_output']
                if expected=='empty':assert any(json.loads(x).get('skills')==[] for x in outputs)
                if expected=='unavailable':assert outputs and 'not available' in outputs[-1]
                if expected=='source':assert ctx.calls==1 and 'FIXTURE_SOURCE' in all_input
        finally:s.close();server.shutdown();server.server_close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('codex');args=parser.parse_args()
    cases=[('final',None,'ready'),
      ('source',{'name':'read_source','arguments':json.dumps({'path':'README.md','revision':'head'})},'source'),
      ('outside-source',{'name':'read_source','arguments':json.dumps({'path':'/etc/passwd','revision':'head'})},'denied'),
      ('empty-skills',{'name':'list','namespace':'skills','arguments':json.dumps({'authority':{'kind':'executor'}})},'empty'),
      ('private-file',{'name':'read','namespace':'skills','arguments':'{}'},'unavailable')]
    for name,call,expected in cases:
        probe(args.codex,call,expected)
        print(json.dumps({'case':name,'result':'PASS'}),flush=True)
    print(json.dumps({'native_acceptance':'PASS','codex_sha256':sha256(Path(args.codex).read_bytes()),'cases':len(cases)}))

if __name__=='__main__':main()
