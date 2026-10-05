"""Offline capability acceptance with direct and model-forced code-mode catalogs.

Use the native bundled gpt-6-astra metadata, fake localhost provider and fresh
unauthenticated home. This is transport evidence, not a real model review.
"""
import argparse
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, sha256
from snci.reviewer import codex_flags, ReadOnlyContext, Session, SCHEMA, thread_params, SOURCE_NAMESPACE

TARGET={'pr':1,'head':'a'*40,'base':'b'*40,'tree':'c'*40}
REQUESTS=[]
CALLS=[]
LEGACY_REVIEWER_BLOB='4c95bbda74aea0541c54e0c3524ed2eb64bf5ca7'
LARGE_FILES={(rev,'README.md'):('START_'+rev+'\r\n'+'a'*40000+'MIDDLE_'+rev+'_Ж😀\\\"\x00\r\n'+
                                  'z'*40000+'END_'+rev).encode() for rev in ('head','base')}


def verify_pages(outputs, expected):
    """Verify provider-visible bytes, independently of context.seen/counters."""
    found={}
    for output in outputs:
        try:page=json.loads(output)
        except (ValueError,TypeError):raise AssertionError('Provider output is not a complete page JSON') from None
        assert isinstance(page,dict) and page.get('schema')=='snci-source-page/v1'
        key=(page.get('revision'),page.get('path'));assert key in expected
        n=page.get('page');assert type(n) is int and n>=0
        old=found.setdefault(key,{}).get(n)
        assert old is None or old==page,'Conflicting provider page'
        found[key][n]=page
    assert set(found)==set(expected),'Missing provider source version'
    total=0;count=0
    for key,raw in expected.items():
        pages=found[key];number=pages.get(0,{}).get('page_count')
        assert type(number) is int and number>0 and set(pages)==set(range(number)),'Missing source pages'
        offset=0;parts=[]
        for n in range(number):
            p=pages[n];part=p['content'].encode('utf-8')
            assert p['status']=='source_page' and p['page_count']==number and p['source_bytes']==len(raw)
            assert p['blob_sha1']==blob_hash(raw) and p['source_sha256']==sha256(raw)
            assert p['byte_start']==offset and p['page_sha256']==sha256(part)
            offset+=len(part);assert p['byte_end']==offset
            assert p['next_page']==(n+1 if n+1<number else None)
            parts.append(part)
        assert b''.join(parts)==raw,'Provider-visible source differs from immutable bytes'
        total+=len(raw);count+=number
    return {'bytes':total,'pages':count,'source_sha256':sorted(sha256(x) for x in expected.values())}


def legacy_reviewer(package):
    """Only the exact frozen e7 reviewer is a valid characterization baseline."""
    root=Path(package);path=root/'snci/reviewer.py'
    assert blob_hash(path.read_bytes())==LEGACY_REVIEWER_BLOB,'Baseline reviewer drift'
    spec=importlib.util.spec_from_file_location('snci_legacy',root/'snci/__init__.py',
                                              submodule_search_locations=[str(root/'snci')])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return __import__('snci_legacy.reviewer',fromlist=['reviewer'])

def request_tools(request):
    tools=list(request.get('tools',[]))
    for item in request.get('input',[]):
        if item.get('type')=='additional_tools':tools.extend(item.get('tools',[]))
    assert tools,'Native request has no capability inventory'
    return tools

def inventory(request):
    names=[]
    for tool in request_tools(request):
        if tool['type']=='namespace':names.extend(tool['name']+'.'+x['name'] for x in tool['tools'])
        else:names.append(tool['name'])
    return sorted(names)

def tool_outputs(requests):
    return [i.get('output') for r in requests for i in r.get('input',[])
            if i.get('type') in ('function_call_output','custom_tool_call_output')]

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
        index=len(REQUESTS)-1
        if index<len(CALLS):
            item=dict(CALLS[index],id='fc'+str(index),call_id='call'+str(index))
            item.setdefault('type','function_call')
        events=[('response.created',{'response':{'id':'r1','status':'in_progress','output':[]}}),
                ('response.output_item.added',{'output_index':0,'item':item}),
                ('response.output_item.done',{'output_index':0,'item':item}),
                ('response.completed',{'response':{'id':'r1','status':'completed','output':[item],
                  'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}})]
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        for name,data in events:
            self.wfile.write(('event: '+name+'\ndata: '+json.dumps(dict(data,type=name))+'\n\n').encode());self.wfile.flush()

class FixtureSource:
    def blob(self,entry):return entry['data']

def probe(binary,calls,expected,model='fixture-model',legacy=None):
    global CALLS
    CALLS=[dict(c) for c in calls];REQUESTS.clear()
    server=ThreadingHTTPServer(('127.0.0.1',0),Server)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='snci-native-') as tmp:
        Path(tmp,'canary').write_text('PRIVATE_FIXTURE_CANARY')
        flags=codex_flags(tmp)+['-c','model_provider="fixture"','-c','model='+json.dumps(model),
            '-c','model_providers.fixture.name="Fixture"','-c','model_providers.fixture.wire_api="responses"',
            '-c','model_providers.fixture.requires_openai_auth=false',
            '-c','model_providers.fixture.supports_websockets=false',
            '-c','model_providers.fixture.base_url="http://127.0.0.1:'+str(server.server_port)+'/v1"',
            '-c','features.enable_request_compression=false']
        for call in CALLS:
            if call.get('namespace')=='skills' and call['name']=='read':
                call['arguments']=json.dumps({'package':tmp+'/canary'})
        p=subprocess.Popen([binary,'app-server','--stdio','--strict-config']+flags,cwd=tmp,
            env={'PATH':'/usr/bin:/bin','HOME':tmp,'CODEX_HOME':tmp,'LANG':'C.UTF-8'},
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
        ctx=ReadOnlyContext(FixtureSource(),{'README.md':{'data':b'FIXTURE_HEAD_SOURCE'}},
                            {'README.md':{'data':b'FIXTURE_BASE_SOURCE'}},['README.md'])
        if expected=='versions':
            ctx=ReadOnlyContext(FixtureSource(),
                {'README.md':{'data':b'FIXTURE_HEAD_SOURCE'},'added.txt':{'data':b'FIXTURE_ADDED_SOURCE'}},
                {'README.md':{'data':b'FIXTURE_BASE_SOURCE'},'deleted.txt':{'data':b'FIXTURE_DELETED_SOURCE'}},
                ['README.md','added.txt','deleted.txt'])
        if expected in ('large','partial','baseline'):
            cls=legacy.ReadOnlyContext if legacy else ReadOnlyContext
            ctx=cls(FixtureSource(),{'README.md':{'data':LARGE_FILES[('head','README.md')]}},
                    {'README.md':{'data':LARGE_FILES[('base','README.md')]}},['README.md'])
        s=Session(p,ctx,30)
        held=False;reason=None
        try:
            s.rpc('initialize',{'clientInfo':{'name':'snci-native-probe','version':'1'},'capabilities':{'experimentalApi':True}})
            s.send({'method':'initialized','params':{}})
            params=(legacy.thread_params if legacy else thread_params)(tmp,model,paths=ctx.paths)
            params['modelProvider']='fixture'
            started=s.rpc('thread/start',params);s.thread=started['thread']['id']
            assert started['sandbox']=={'type':'readOnly','networkAccess':False}
            assert started['approvalPolicy']=='never'
            assert started.get('instructionSources',[])==[]
            s.rpc('turn/start',{'threadId':s.thread,'environments':[],
                'input':[{'type':'text','text':'Synthetic fixture: emit the supplied verdict.'}],'outputSchema':SCHEMA})
            try:s.finish(TARGET)
            except Hold as error:held=True;reason=str(error)
            assert REQUESTS
            names=inventory(REQUESTS[0])
            source_name=SOURCE_NAMESPACE+'.read_source'
            expected_names=([source_name,'request_user_input','skills.list','skills.read']
                            if model=='fixture-model' else
                            [source_name,'functions.exec','functions.wait','functions.request_user_input',
                             'functions.request_user_input_async'])
            assert names==sorted(expected_names),names
            source=next(t for t in request_tools(REQUESTS[0]) if t.get('name')==SOURCE_NAMESPACE)['tools'][0]
            assert source['name']=='read_source' and source['type']=='function',source
            assert source['parameters']['required']==(['path','revision'] if legacy else ['path','revision','page'])
            assert source['parameters']['properties']['path']['enum']==ctx.paths
            assert source['parameters']['properties']['revision']['enum']==['head','base']
            for t in request_tools(REQUESTS[0]):
                if t.get('name')=='functions':
                    for nested in t.get('tools',[]):
                        if nested['name']=='exec':
                            assert 'read_source' not in nested['description']
                            assert 'collaboration__' not in nested['description']
            all_input=json.dumps([r.get('input',[]) for r in REQUESTS])
            assert 'PRIVATE_FIXTURE_CANARY' not in all_input
            assert '<skills_instructions>' not in all_input
            outputs=tool_outputs(REQUESTS[1:])
            delivery=None
            if expected=='source':
                assert not held
                assert ctx.calls==2 and ctx.reads==2 and ctx.complete()
                assert all(x in all_input for x in ('FIXTURE_HEAD_SOURCE','FIXTURE_BASE_SOURCE'))
            elif expected=='versions':
                assert not held
                assert ctx.calls==6 and ctx.reads==4 and ctx.complete()
                assert ctx.seen=={('head','README.md'),('base','README.md'),('head','added.txt'),('base','deleted.txt')}
                assert all(x in all_input for x in ('FIXTURE_HEAD_SOURCE','FIXTURE_BASE_SOURCE',
                                                    'FIXTURE_ADDED_SOURCE','FIXTURE_DELETED_SOURCE'))
                assert 'missing_revision' in all_input
                assert any('"revision":"base"' in x and '"path":"added.txt"' in x for x in outputs)
                assert any('"revision":"head"' in x and '"path":"deleted.txt"' in x for x in outputs)
            elif expected=='large':
                assert not held and ctx.complete()
                delivery=verify_pages(outputs,LARGE_FILES)
            elif expected=='partial':
                assert held and reason=='review_incomplete_source' and ctx.reads>0 and not ctx.complete()
                try:verify_pages(outputs,LARGE_FILES)
                except AssertionError:delivery={'incomplete_provider_pages_rejected':True}
                else:raise AssertionError('Partial fixture incorrectly reconstructed')
            elif expected=='baseline':
                assert not held and ctx.complete()
                for (revision,_),raw in LARGE_FILES.items():
                    visible=[x for x in outputs if isinstance(x,str) and 'START_'+revision in x]
                    assert visible and all(sha256(x.encode())!=sha256(raw) for x in visible)
                    assert all('MIDDLE_'+revision not in x for x in visible),'Baseline middle unexpectedly visible'
                delivery={'whole_file_baseline_truncated':True,'baseline_reviewer_blob':LEGACY_REVIEWER_BLOB}
            else:
                assert held
                assert ctx.calls==0 and not ctx.complete()
                assert reason==('review_source_only' if expected=='outside' else 'review_incomplete_source'),reason
                if expected=='empty':assert any(json.loads(x).get('skills')==[] for x in outputs)
                elif expected=='unavailable':assert outputs and 'not available' in outputs[-1]
                elif expected=='host-disabled':
                    assert outputs and 'code-mode host is disabled' in json.dumps(outputs)
                    assert 'EXECUTED_FIXTURE_CANARY' not in json.dumps(outputs)
            return {'model':model,'inventory':names,'read_count':ctx.reads,'request_count':ctx.calls,
                    'source_bytes':ctx.bytes,'verdict_held':held,'hold_reason':reason,'result':'PASS',
                    'provider_delivery':delivery}
        finally:s.close();server.shutdown();server.server_close()

def main():
    sys.dont_write_bytecode=True
    parser=argparse.ArgumentParser();parser.add_argument('codex')
    parser.add_argument('--baseline-package',required=True);args=parser.parse_args()
    legacy=legacy_reviewer(args.baseline_package)
    source=[{'name':'read_source','namespace':SOURCE_NAMESPACE,
             'arguments':json.dumps({'path':'README.md','revision':rev,'page':0})} for rev in ('head','base')]
    outside=[dict(source[0],arguments=json.dumps({'path':'/etc/passwd','revision':'head','page':0}))]
    versions=[{'name':'read_source','namespace':SOURCE_NAMESPACE,'arguments':json.dumps({'path':path,'revision':rev,'page':0})}
              for path,rev in [('added.txt','base'),('deleted.txt','head'),('added.txt','head'),
                               ('deleted.txt','base'),('README.md','head'),('README.md','base')]]
    common=[('unread-ready',[],'denied'),('source-both-versions',source,'source'),
            ('outside-source',outside,'outside'),('added-deleted-versions',versions,'versions')]
    cases=[('fixture-model',name,calls,expected) for name,calls,expected in common+[
      ('empty-skills',[{'name':'list','namespace':'skills','arguments':json.dumps({'authority':{'kind':'executor'}})}],'empty'),
      ('private-file',[{'name':'read','namespace':'skills','arguments':'{}'}],'unavailable')]]
    cases += [('gpt-6-astra',name,calls,expected) for name,calls,expected in common+[
      ('host-disabled',[{'type':'custom_tool_call','namespace':'functions','name':'exec',
                        'input':'text("EXECUTED_FIXTURE_CANARY")'}],'host-disabled')]]
    for model,name,calls,expected in cases:
        report=probe(args.codex,calls,expected,model)
        print(json.dumps(dict(report,case=name)),flush=True)
    large=[]
    ctx=ReadOnlyContext(FixtureSource(),{'README.md':{'data':LARGE_FILES[('head','README.md')]}},
                        {'README.md':{'data':LARGE_FILES[('base','README.md')]}},['README.md'])
    for rev in ('head','base'):
        count=json.loads(ctx.read({'path':'README.md','revision':rev,'page':0}))['page_count']
        large.extend({'name':'read_source','namespace':SOURCE_NAMESPACE,
                      'arguments':json.dumps({'path':'README.md','revision':rev,'page':n})} for n in range(count))
    missing=len(large)//4
    for model in ('fixture-model','gpt-6-astra'):
        old=[dict(c,arguments=json.dumps({'path':'README.md','revision':rev}))
             for c,rev in zip(source,('head','base'))]
        for name,calls,expected,baseline in [('whole-file-baseline',old,'baseline',legacy),
                                            ('large-paged-source',large,'large',None),
                                            ('missing-middle-page',large[:missing]+large[missing+1:],'partial',None)]:
            report=probe(args.codex,calls,expected,model,baseline)
            print(json.dumps(dict(report,case=name)),flush=True)
    print(json.dumps({'native_acceptance':'PASS','source_paging_acceptance':'PASS',
                     'baseline_reviewer_blob':LEGACY_REVIEWER_BLOB,
                     'codex_sha256':sha256(Path(args.codex).read_bytes()),'cases':len(cases)+6}))

if __name__=='__main__':main()
