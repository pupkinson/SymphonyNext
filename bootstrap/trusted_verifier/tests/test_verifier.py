import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

class VerifierTests(unittest.TestCase):
    def setUp(self):
        try:self.v=importlib.import_module('verifier')
        except ImportError:self.fail('operator implementation is missing')
    def test_existing_attempt_is_never_reexecuted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);job=self.v.claim_attempt(root,'a'*40)
            self.assertTrue((job/'intent.json').is_file())
            with self.assertRaises(FileExistsError):self.v.claim_attempt(root,'a'*40)
    def test_untrusted_attempt_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ['../x','a'*39,'a'*40+'/x']:
                with self.subTest(name=name),self.assertRaises(ValueError):self.v.claim_attempt(Path(d),name)
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_systemd_command_has_no_host_secret_or_network_mount(self):
        cmd=self.v.unit_command(Path('/var/lib/symphony-next-verifier/jobs/'+'a'*40),'symphony-next-verify-'+('a'*12))
        props=[x.removeprefix('--property=') for x in cmd if x.startswith('--property=')]
        self.assertIn('DynamicUser=yes',props);self.assertIn('PrivateNetwork=yes',props)
        self.assertIn('CapabilityBoundingSet=',props);self.assertIn('NoNewPrivileges=yes',props)
        self.assertIn('MemoryMax=2147483648',props);self.assertIn('RuntimeMaxSec=600',props)
        mounts=[x for x in props if x.startswith('BindReadOnlyPaths=')]
        self.assertEqual(len(mounts),1)
        self.assertNotIn('/etc',mounts[0]);self.assertNotIn('bootstrap',mounts[0]);self.assertNotIn('app.pem',str(cmd))
        self.assertEqual(cmd[-4:],['/venv/bin/python3','-I','-B','/verifier/worker.py'])
    def test_malformed_or_multiple_reports_are_not_accepted(self):
        for raw in [b'',b'SNV_REPORT={}\nSNV_REPORT={}\n',b'SNV_REPORT={']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):self.v.read_worker_report(raw)
    def test_single_structured_report_is_parsed(self):
        self.assertEqual(self.v.read_worker_report(b'noise\nSNV_REPORT={"v":1}\n'),{'v':1})
    def test_ambiguous_publication_preserves_intent_and_has_one_post(self):
        class API:
            def __init__(self):self.posts=0
            def request(self,method,path,body=None):
                if method=='POST':self.posts+=1;raise TimeoutError()
                raise AssertionError('unexpected read')
        with tempfile.TemporaryDirectory() as d:
            api=API();job=Path(d)
            with self.assertRaises(TimeoutError):self.v.publish_once(api,job,{'head':'a'*40,'app_id':3,'external_id':'job','name':'check'},{'name':'check'})
            self.assertEqual(api.posts,1);self.assertTrue((job/'publication-intent.json').is_file())
            with self.assertRaises(FileExistsError):self.v.publish_once(api,job,{}, {})
            self.assertEqual(api.posts,1)
    def test_publication_requires_independent_readback(self):
        class API:
            def request(self,method,path,body=None):
                if method=='POST':return {'id':44}
                return {'id':44,'head_sha':'b'*40,'app':{'id':3},'external_id':'job','name':'check','status':'completed','conclusion':'success'}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):self.v.publish_once(API(),Path(d),{'head':'a'*40,'app_id':3,'external_id':'job','name':'check'}, {})
            self.assertFalse((Path(d)/'check-verified.json').exists())

    def test_root_and_worker_are_traversable_under_umask077(self):
        import os
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            job=Path(d);observed={}
            def fake_process(argv, **kw):
                if argv[0].endswith('systemd-run'):
                    observed.update({str(p.relative_to(job)):p.stat().st_mode & 0o777
                        for p in [job/'root',job/'root/etc',job/'root/source',job/'worker']})
                    kw['stdout'].write(b'SNV_REPORT={}\n')
                    return SimpleNamespace(returncode=0)
                if argv[1]=='stop':return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
                return SimpleNamespace(returncode=0,stdout=b'LoadState=not-found\nActiveState=inactive\nMainPID=0\n',stderr=b'')
            old=os.umask(0o077)
            try:
                with patch.object(self.v,'INSTALL',Path(self.v.__file__).parent),patch.object(self.v.subprocess,'run',side_effect=fake_process):
                    self.v.execute_unit(job,{'head':'a'*40})
            finally:os.umask(old)
            self.assertEqual(observed,{'root':0o755,'root/etc':0o755,'root/source':0o755,'worker':0o755})
    def test_bounded_scratch_does_not_conflict_with_dynamic_user_private_tmp(self):
        cmd=self.v.unit_command(Path('/var/lib/symphony-next-verifier/jobs/'+'a'*40),'symphony-next-verify-'+('a'*12))
        props=[x.removeprefix('--property=') for x in cmd if x.startswith('--property=')]
        tmp=next(x for x in props if x.startswith('TemporaryFileSystem='))
        self.assertIn('/worktmp:rw,nosuid,nodev,size=512M,mode=1777',tmp)
        self.assertNotIn('/tmp:',tmp)
        self.assertIn('InaccessiblePaths=/tmp /var/tmp',props)
        self.assertIn('TMPDIR=/worktmp',next(x for x in props if x.startswith('Environment=')))

