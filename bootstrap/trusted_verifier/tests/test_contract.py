import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest

class ContractTests(unittest.TestCase):
    def setUp(self):
        try: self.c = importlib.import_module('contract')
        except ImportError: self.fail('locked acceptance implementation is missing')
        self.target = {'head': 'a'*40, 'tree': 'b'*40, 'test_ids': ['test_x.T.test_a','test_x.T.test_b']}
        self.report = {'schema':'symphony-next-test-report/v1','head':'a'*40,'tree':'b'*40,
            'test_ids':['test_x.T.test_a','test_x.T.test_b'],'passed':['test_x.T.test_a','test_x.T.test_b'],
            'failures':[],'errors':[],'skipped':[],'expected_failures':[],'unexpected_successes':[],
            'tests_run':2,'successful':True,
            'isolation':{'uid':12345,'mount_namespace_separate':True,'network_namespace_separate':True,
                         'source_readonly':True,'venv_readonly':True,
                         'scratch_bounded':True,'host_tmp_inaccessible':True}}
    def test_complete_report_is_accepted(self):
        self.c.validate_report(self.target,self.report)
    def test_wrong_commit_is_rejected(self):
        self.report['head']='c'*40
        with self.assertRaises(ValueError): self.c.validate_report(self.target,self.report)
    def test_missing_duplicate_and_extra_test_are_rejected(self):
        for ids in [[],['test_x.T.test_a']*2,self.report['test_ids']+['test_x.T.test_c']]:
            with self.subTest(ids=ids):
                r=copy.deepcopy(self.report);r['test_ids']=ids;r['passed']=ids
                with self.assertRaises(ValueError): self.c.validate_report(self.target,r)
    def test_skip_error_failure_and_zero_exit_cannot_claim_pass(self):
        for key in ['failures','errors','skipped','expected_failures','unexpected_successes']:
            r=copy.deepcopy(self.report);r[key]=['test_x.T.test_b']
            with self.subTest(key=key),self.assertRaises(ValueError): self.c.validate_report(self.target,r)
    def test_root_or_unverified_isolation_is_rejected(self):
        for key,value in [('uid',0),('uid',True),('mount_namespace_separate',False),
                          ('network_namespace_separate',False),('source_readonly',False),('venv_readonly',False),
                          ('scratch_bounded',False),('host_tmp_inaccessible',False)]:
            r=copy.deepcopy(self.report);r['isolation'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): self.c.validate_report(self.target,r)
    def test_bool_is_not_a_test_count(self):
        self.report['tests_run']=True
        with self.assertRaises(ValueError): self.c.validate_report(self.target,self.report)
    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(ValueError): self.c.decode_json(b'{"head":"a","head":"b"}')
    def test_readback_requires_app_sha_external_id_and_success(self):
        expected={'head':'a'*40,'app_id':42,'external_id':'job-1','name':'symphony-next/verified-tests'}
        actual={'head_sha':'a'*40,'app':{'id':42},'external_id':'job-1','name':expected['name'],
                'status':'completed','conclusion':'success','id':25}
        self.c.validate_check(expected,actual)
        for key,val in [('head_sha','b'*40),('app',{'id':43}),('external_id','other'),
                        ('name','other'),('status','queued'),('conclusion','skipped')]:
            other=copy.deepcopy(actual);other[key]=val
            with self.subTest(key=key),self.assertRaises(ValueError): self.c.validate_check(expected,other)
    def test_artifacts_cannot_be_replaced_or_follow_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'result.json';self.c.write_new_json(p,{'v':1})
            with self.assertRaises(FileExistsError):self.c.write_new_json(p,{'v':2})
            alias=Path(d)/'alias';alias.symlink_to(p)
            with self.assertRaises(FileExistsError):self.c.write_new_json(alias,{'v':3})
            self.assertEqual(json.loads(p.read_text()),{'v':1})
    def test_trust_rejects_writable_file_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('x');p.chmod(0o666)
            with self.assertRaises(ValueError):self.c.trusted_file(p,owner=p.stat().st_uid,check_parents=False)
            p.chmod(0o600);self.c.trusted_file(p,owner=p.stat().st_uid,check_parents=False)
            alias=Path(d)/'link';alias.symlink_to(p)
            with self.assertRaises(ValueError):self.c.trusted_file(alias,owner=p.stat().st_uid,check_parents=False)
