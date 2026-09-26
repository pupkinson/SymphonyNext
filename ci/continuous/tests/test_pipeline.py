from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, APP_ID, CHECK
from snci.controller import publish, reconcile, check_matches
from snci.state import Journal
from snci.runner import create_args, validate_result

T={'pr':1,'head':'a'*40,'base':'b'*40,'tree':'c'*40}
class API:
    def __init__(self):self.calls=[];self.fail=False;self.checks=[]
    def request(self,method,path,body=None):
        self.calls.append((method,path,body))
        if method=='POST':
            if self.fail:raise Hold('github_transport')
            self.checks=[dict(body,id=10,app={'id':APP_ID})];return self.checks[0]
        return self.checks[0]
    def pages(self,path,field=None):return self.checks

class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.j=Journal(Path(self.tmp.name)/'db');self.key=self.j.claim(T,'p',4);self.api=API()
        self.body={'name':CHECK,'head_sha':T['head'],'external_id':'x','status':'completed','conclusion':'success',
                   'output':{'title':'Verified','summary':'digest'}}
    def tearDown(self):self.j.close();self.tmp.cleanup()
    def test_publish_and_readback(self):
        publish(self.api,self.j,self.key,self.body,lambda:None)
        self.assertEqual(self.j.get(self.key)['state'],'success')
    def test_intent_committed_before_post(self):
        original=self.api.request
        def request(method,path,body=None):
            if method=='POST':self.assertEqual(self.j.get(self.key)['state'],'publishing')
            return original(method,path,body)
        self.api.request=request
        publish(self.api,self.j,self.key,self.body,lambda:None)
    def test_unknown_post_does_not_repeat(self):
        self.api.fail=True
        with self.assertRaises(Hold):publish(self.api,self.j,self.key,self.body,lambda:None)
        self.assertEqual(self.j.get(self.key)['state'],'publishing')
        reconcile(self.api,self.j,self.key,lambda:None)
        self.assertEqual(sum(c[0]=='POST' for c in self.api.calls),1)
        self.assertEqual(self.j.get(self.key)['state'],'publishing')
    def test_recovery_accepts_exact_existing_check(self):
        self.api.fail=True
        with self.assertRaises(Hold):publish(self.api,self.j,self.key,self.body,lambda:None)
        self.api.checks=[dict(self.body,id=8,app={'id':APP_ID})]
        reconcile(self.api,self.j,self.key,lambda:None)
        self.assertEqual(self.j.get(self.key)['state'],'success')
    def test_duplicate_or_wrong_app_not_accepted(self):
        self.j.set(self.key,'publishing',{'check_body':self.body})
        self.api.checks=[dict(self.body,id=8,app={'id':APP_ID})]*2
        with self.assertRaises(Hold):reconcile(self.api,self.j,self.key,lambda:None)
        wrong=dict(self.body,id=8,app={'id':1})
        self.assertFalse(check_matches(wrong,self.body))
    def test_stale_guard_blocks_post(self):
        def guard():raise Hold('stale')
        with self.assertRaises(Hold):publish(self.api,self.j,self.key,self.body,guard)
        self.assertFalse(self.api.calls)
    def test_container_has_no_secret_or_socket_mount(self):
        args=create_args(Path('/var/lib/symphony-next-ci/attempts')/self.key,'sha256:'+'a'*64,self.key)
        self.assertIn('--network=none',args);self.assertIn('--cap-drop=ALL',args)
        self.assertIn('--read-only',args);self.assertIn('--user=0:0',args)
        for capability in ('CHOWN','SETUID','SETGID','KILL'):
            self.assertIn('--cap-add='+capability,args)
        mounts=[x for x in args if x.startswith('type=bind')]
        self.assertEqual(len(mounts),3)
        self.assertTrue(all(',readonly,' in x for x in mounts))
        self.assertFalse(any('docker.sock' in x or 'private' in x.split(',target=')[0] for x in mounts))
    def test_bad_or_incomplete_stage_result_fails(self):
        good={'stages':{'build':0,'format':0,'lint':0,'coverage':0,'dialyzer':0},'tests':328,'failures':0,'skipped':6,
              'coverage':100.0,'dialyzer_errors':0,'cleanup':0,'source_before':True,'source_after':True}
        profile={'minimum_tests':328,'maximum_skips':6}
        self.assertEqual(validate_result(good,profile),good)
        for field,value in [('tests',327),('cleanup',1),('source_after',False),('coverage',99),('skipped',7)]:
            with self.subTest(field=field),self.assertRaises(Hold):validate_result(dict(good,**{field:value}),profile)

if __name__=='__main__':unittest.main()
