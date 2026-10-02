from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold
from snci.reviewer import ReadOnlyContext, thread_params, validate_verdict, handle_request, check_event, codex_flags

T={'pr':1,'head':'a'*40,'base':'b'*40,'tree':'c'*40}
class BlobSource:
    def blob(self,e):return e['data']
class ReviewerTest(unittest.TestCase):
    def setUp(self):
        self.c=ReadOnlyContext(BlobSource(),{'x':{'data':b'code'}},{'x':{'data':b'old'}},['x'])
    def test_environment_is_disabled(self):
        p=thread_params('/empty',None)
        self.assertEqual(p['environments'],[])
        self.assertEqual(p['sandbox'],'read-only')
        self.assertFalse(p['config']['features']['shell_tool'])
        self.assertFalse(p['config']['features']['multi_agent'])
        self.assertEqual([t['name'] for t in p['dynamicTools']],['snci_source'])
        namespace=p['dynamicTools'][0]
        self.assertEqual(namespace['type'],'namespace')
        self.assertEqual([t['name'] for t in namespace['tools']],['read_source'])
    def test_model_forced_code_mode_keeps_source_direct_and_host_disabled(self):
        p=thread_params('/empty','gpt-6-astra')
        config=p['config']['features']
        self.assertEqual(config['code_mode'],{'enabled':False,'direct_only_tool_namespaces':['snci_source']})
        self.assertFalse(config['code_mode_host'])
        self.assertFalse(config['multi_agent_v2'])
        self.assertFalse(config['sleep_tool'])
        self.assertEqual(p['config']['agents'],{'enabled':False})
        self.assertEqual(p['model'],'gpt-6-astra')
        flags=codex_flags('/empty')
        self.assertIn('features.code_mode={enabled=false,direct_only_tool_namespaces=["snci_source"]}',flags)
        self.assertIn('features.code_mode_host=false',flags)
        self.assertIn('agents.enabled=false',flags)
    def test_only_verified_source_can_be_read(self):
        self.assertEqual(self.c.read({'path':'x','revision':'head'}),'code')
        for p in ['/etc/passwd','../auth.json','auth.json']:
            with self.assertRaises(Hold):self.c.read({'path':p,'revision':'head'})
    def test_other_tools_are_denied(self):
        with self.assertRaises(Hold):handle_request({'method':'item/commandExecution/requestApproval','id':9},self.c,'t')
        with self.assertRaises(Hold):handle_request({'method':'item/tool/call','id':9,'params':{'threadId':'t','tool':'shell','arguments':{}}},self.c,'t')
    def test_dynamic_read_response_format(self):
        out=handle_request({'method':'item/tool/call','id':9,'params':{'threadId':'t','namespace':'snci_source','tool':'read_source','arguments':{'path':'x','revision':'head'}}},self.c,'t')
        self.assertEqual(out['contentItems'],[{'type':'inputText','text':'code'}])
    def test_source_name_in_another_namespace_or_thread_is_denied(self):
        for namespace in (None,'','skills','functions','other'):
            with self.subTest(namespace=namespace),self.assertRaises(Hold):
                handle_request({'method':'item/tool/call','id':9,'params':{'threadId':'t','namespace':namespace,
                    'tool':'read_source','arguments':{'path':'x','revision':'head'}}},self.c,'t')
        with self.assertRaises(Hold):
            handle_request({'method':'item/tool/call','id':9,'params':{'threadId':'other','namespace':'snci_source',
                'tool':'read_source','arguments':{'path':'x','revision':'head'}}},self.c,'t')
        self.assertEqual(self.c.calls,0)
    def test_source_events_require_exact_namespace(self):
        for method in ('item/started','item/completed'):
            good={'method':method,'params':{'item':{'type':'dynamicToolCall','namespace':'snci_source','tool':'read_source'}}}
            check_event(good)
            for namespace in (None,'','other'):
                good['params']['item']['namespace']=namespace
                with self.subTest(method=method,namespace=namespace),self.assertRaises(Hold):check_event(good)
    def test_forbidden_tool_event_holds(self):
        for kind in ['commandExecution','fileChange','mcpToolCall','collabAgentToolCall','webSearch']:
            with self.subTest(kind=kind),self.assertRaises(Hold):check_event({'method':'item/started','params':{'item':{'type':kind}}})
    def test_ready_requires_exact_source_and_file_coverage(self):
        v=dict(T,verdict='READY',findings=[],limitations=[])
        with self.assertRaises(Hold):validate_verdict(v,T,self.c)
        self.c.read({'path':'x','revision':'head'})
        self.c.read({'path':'x','revision':'base'})
        self.assertEqual(validate_verdict(v,T,self.c)['verdict'],'READY')
        v['head']='d'*40
        with self.assertRaises(Hold):validate_verdict(v,T,self.c)
    def test_blocking_finding_cannot_be_ready(self):
        self.c.read({'path':'x','revision':'head'});self.c.read({'path':'x','revision':'base'})
        v=dict(T,verdict='READY',findings=[{'severity':'high','path':'x','message':'bad'}],limitations=[])
        with self.assertRaises(Hold):validate_verdict(v,T,self.c)
    def test_context_request_budget(self):
        self.c.calls=400
        with self.assertRaises(Hold):self.c.read({'path':'x','revision':'head'})

if __name__=='__main__':unittest.main()
