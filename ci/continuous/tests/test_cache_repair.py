"""Bounded cache repair consumes fresh evidence once without widening setup."""
from contextlib import redirect_stdout
import importlib
import io
import json
from pathlib import Path
import sys
import tarfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold,canonical,sha256
from snci import runner
import test_dialyzer_repair as previous

HEAD=previous.HEAD
IMAGE=previous.IMAGE


class CacheRepairTests(unittest.TestCase):
    def setUp(self):
        previous.DialyzerRepairTests.setUp(self)
        try:self.repair=importlib.import_module('snci.repair_cache')
        except ImportError:self.fail('Single-use cache repair not implemented')
        for name,value in [('INSTALL',self.install),('STATE',self.state),('ETC',self.etc),
                           ('trusted',lambda p,**kw:Path(p))]:
            p=patch.object(self.repair,name,value);p.start();self.addCleanup(p.stop)
        (self.root/'reused-image.json').unlink()
        self.log=(b'SNCI_FAILURE '+json.dumps(dict(stage='setup',kind='worker_error',exit_code=None,
            timeout_seconds=0,duration_seconds=0,log_bytes=0,log_truncated=False,cleanup_exit_code=None),
            sort_keys=True).encode()+b'\nSNCI_WORKER_FAILED\n')
        (self.root/'worker.log').write_bytes(self.log)

    def fixture(self):
        fake,source,api,calls,policy,defs=previous.DialyzerRepairTests.fixture(self)
        status=json.loads((self.install/'preparation-status.json').read_bytes())
        status['hold_code']='worker_worker_error_setup'
        (self.install/'preparation-status.json').write_bytes(canonical(status))
        self.cache=previous.archive([('./',b'',tarfile.DIRTYPE),('fixture.plt',b'cache',tarfile.REGTYPE)])
        files=[dict(path='fixture.plt',size=5,sha256=sha256(b'cache'))]
        self.probe=sha256(canonical(dict(plt='prepared',profile='main',head=self.repair.BASE,image=IMAGE)))
        (self.root/('plt-'+self.probe+'.tar')).write_bytes(self.cache)
        (self.root/('plt-'+self.probe+'.json')).write_bytes(canonical(dict(image=IMAGE,key=self.probe,started=False)))
        self.plt=dict(image=IMAGE,head=defs['main']['head'],tree=defs['main']['tree'],files=files)
        (self.root/'plt.json').write_bytes(canonical(self.plt))
        for p in [patch.dict('sys.modules',{'owner':fake}),patch.object(self.repair,'GitHub',return_value=api),
                  patch.object(self.repair,'Source',return_value=source),patch.object(self.repair,'stopped'),
                  patch.object(self.repair.os,'geteuid',return_value=0),
                  patch.object(self.repair.os,'uname',return_value=types.SimpleNamespace(nodename='1c-db')),
                  patch.object(self.repair,'emit_status'),patch.object(runner,'command',return_value=b''),
                  patch.object(self.repair,'plt_files',return_value=files)]:
            p.start();self.addCleanup(p.stop)
        return fake,source,api,calls,policy,defs

    def evidence(self,defs):return self.repair.failed_main(self.root,self.entries,self.recipe,defs['main'])

    def test_apply_archives_all_evidence_preserves_policy_and_refuses_second_launch(self):
        fake,source,api,calls,policy,defs=self.fixture()
        old_files={p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        journal=self.state/'journal';journal.write_bytes(b'preserved')
        with redirect_stdout(io.StringIO()):self.repair.apply(HEAD)
        directory=self.state/('repair-cache-'+HEAD[:12])
        for name,raw in old_files.items():self.assertEqual((directory/'failed-main'/name).read_bytes(),raw,name)
        self.assertEqual(json.loads((directory/'policy-before.json').read_bytes()),policy)
        self.assertEqual(fake.load_policy(),dict(policy,installed_revision=HEAD))
        self.assertEqual(journal.read_bytes(),b'preserved');self.assertFalse(self.root.exists())
        inputs=json.loads((directory/'input.json').read_bytes())
        self.assertEqual(inputs['cache_before'],self.plt['files']);self.assertEqual(inputs['image'],IMAGE)
        self.assertNotIn(b'repair_dialyzer import apply',(directory/'driver.py').read_bytes())
        self.assertIn(b'repair_dialyzer import preparation_driver',(directory/'driver.py').read_bytes())
        self.assertEqual(len([c for c in calls if c[0]=='/usr/bin/tmux']),1)
        with self.assertRaises(Hold):self.repair.apply(HEAD)
        self.assertEqual(len([c for c in calls if c[0]=='/usr/bin/tmux']),1)

    def test_failure_log_and_cache_receipt_are_exact_before_archive(self):
        fake,source,api,calls,policy,defs=self.fixture()
        original=self.evidence(defs)
        self.assertEqual(original['cache_before'],self.plt['files'])
        for path,raw in [(self.root/'acceptance.json',b'accepted'),
                         (self.root/'worker.log',self.log+b'extra'),
                         (self.root/'plt.json',canonical(dict(self.plt,image='sha256:'+'d'*64))),
                         (self.root/('plt-'+self.probe+'.json'),canonical(dict(image=IMAGE,key=self.probe,started=True)))]:
            old=path.read_bytes() if path.exists() else None;path.write_bytes(raw)
            with self.subTest(path=path.name),self.assertRaises(Hold):self.evidence(defs)
            if old is None:path.unlink()
            else:path.write_bytes(old)
        self.assertEqual(self.evidence(defs),original)

    def test_empty_or_changed_cache_holds_without_native_launch(self):
        fake,source,api,calls,policy,defs=self.fixture()
        for files in ([],[dict(path='fixture.plt',size=5,sha256='d'*64)]):
            with patch.object(self.repair,'plt_files',return_value=files),self.assertRaises(Hold):self.repair.apply(HEAD)
        self.assertTrue(self.root.exists());self.assertEqual(fake.load_policy(),policy)
        self.assertFalse(any(c[0]=='/usr/bin/tmux' for c in calls))

    def test_source_or_installation_drift_during_staging_holds(self):
        fake,source,api,calls,policy,defs=self.fixture();blob=source.blob
        def drift(entry):(self.install/'worker.py').write_bytes(b'concurrent');return blob(entry)
        source.blob=drift
        with self.assertRaises(Hold):self.repair.apply(HEAD)
        self.assertTrue(self.root.exists());self.assertEqual(fake.load_policy(),policy)
        self.assertFalse(any(c[0]=='/usr/bin/tmux' for c in calls))

    def test_protected_failure_drift_during_staging_holds(self):
        fake,source,api,calls,policy,defs=self.fixture();blob=source.blob
        def drift(entry):(self.root/'build.log').write_bytes(b'changed evidence');return blob(entry)
        source.blob=drift
        with self.assertRaises(Hold):self.repair.apply(HEAD)
        self.assertTrue(self.root.exists());self.assertEqual(fake.load_policy(),policy)
        self.assertFalse(any(c[0]=='/usr/bin/tmux' for c in calls))

    def test_active_units_and_claimed_attempt_stop_before_archive(self):
        fake,source,api,calls,policy,defs=self.fixture()
        with patch.object(self.repair,'stopped',side_effect=Hold('repair_service_active')),self.assertRaises(Hold):self.repair.apply(HEAD)
        directory=self.state/('repair-cache-'+HEAD[:12]);self.assertFalse(directory.exists());directory.mkdir()
        with self.assertRaises(Hold):self.repair.apply(HEAD)
        self.assertTrue(self.root.exists());self.assertEqual(fake.load_policy(),policy)
        self.assertFalse(any(c[0]=='/usr/bin/tmux' for c in calls))

    def test_out_of_scope_recipe_profile_or_source_changes_are_refused(self):
        base={p:dict(sha='b'*40,mode='100644') for p in self.repair.DELTA}
        head={p:dict(sha='c'*40,mode='100644') for p in self.repair.DELTA}
        self.repair.package_delta(base,head)
        for name in ('elixir/mix.exs','ci/continuous/Dependency.Dockerfile','ci/continuous/profiles.json'):
            with self.assertRaises(Hold):self.repair.package_delta(base,dict(head,**{name:dict(sha='d'*40,mode='100644')}))
        with self.assertRaises(Hold):self.repair.package_delta(base,{p:e for p,e in head.items() if not p.endswith('README.md')})


if __name__=='__main__':unittest.main()
