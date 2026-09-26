from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold
from snci.reviewer import ReadOnlyContext, thread_params, validate_verdict, handle_request, check_event

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
        self.assertEqual([t['name'] for t in p['dynamicTools']],['read_source'])
    def test_only_verified_source_can_be_read(self):
        self.assertEqual(self.c.read({'path':'x','revision':'head'}),'code')
        for p in ['/etc/passwd','../auth.json','auth.json']:
            with self.assertRaises(Hold):self.c.read({'path':p,'revision':'head'})
    def test_other_tools_are_denied(self):
        with self.assertRaises(Hold):handle_request({'method':'item/commandExecution/requestApproval','id':9},self.c,'t')
        with self.assertRaises(Hold):handle_request({'method':'item/tool/call','id':9,'params':{'threadId':'t','tool':'shell','arguments':{}}},self.c,'t')
    def test_dynamic_read_response_format(self):
        out=handle_request({'method':'item/tool/call','id':9,'params':{'threadId':'t','tool':'read_source','arguments':{'path':'x','revision':'head'}}},self.c,'t')
        self.assertEqual(out['contentItems'],[{'type':'inputText','text':'code'}])
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
