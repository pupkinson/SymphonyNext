from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci import repair_seed as repair
from snci.common import Hold, blob_hash, sha256
import owner

class RepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        self.root=self.path/'prepare-main';self.root.mkdir()
        self.source=self.root/'source';self.source.mkdir()
        self.entries={}
        for i in range(180):
            name=f'f{i:03}';raw=b'source'
            p=self.source/name;p.write_bytes(raw);p.chmod(0o644)
            self.entries[name]={'sha':blob_hash(raw),'size':len(raw),'mode':'100644'}
        self.recipe=b'ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n'
        (self.root/'Dependency.Dockerfile').write_bytes(self.recipe)
        (self.root/'.dockerignore').write_bytes(b'*\n!Dependency.Dockerfile\n!source\n!source/**\n')
        self.log=b'docker.io/library/'+owner.SEED.encode()+b' pull access denied\nfailed to solve\n'
        (self.root/'build.log').write_bytes(self.log)
        self.trust=patch.object(repair,'trusted',lambda p,**kw:Path(p));self.trust.start();self.addCleanup(self.trust.stop)
    def check(self):return repair.failed_build(self.root,self.entries,self.recipe)
    def test_known_pre_run_failure_with_complete_source_can_be_preserved(self):
        self.assertEqual(self.check(),{'build_log_sha256':sha256(self.log),'source_count':180})
    def test_started_worker_or_completed_build_refuses(self):
        for name in ('image.id','seed.json','source.json','worker.log','acceptance.json'):
            with self.subTest(name=name):
                p=self.root/name;p.write_bytes(b'evidence')
                with self.assertRaises(Hold):self.check()
                p.unlink()
    def test_other_build_failure_refuses(self):
        (self.root/'build.log').write_bytes(b'compiler failed')
        with self.assertRaises(Hold):self.check()
    def test_recipe_change_refuses(self):
        (self.root/'Dependency.Dockerfile').write_bytes(b'FROM ubuntu')
        with self.assertRaises(Hold):self.check()
    def test_source_change_or_missing_file_refuses(self):
        (self.source/'f000').write_bytes(b'changed')
        with self.assertRaises(Hold):self.check()
        (self.source/'f000').unlink()
        with self.assertRaises(Hold):self.check()
    def test_symlink_refuses(self):
        p=self.source/'f000';p.unlink();p.symlink_to('f001')
        with self.assertRaises(Hold):self.check()
    def test_package_scope_is_exact_and_forbids_application_changes(self):
        base={p:{'sha':'a'*40,'mode':'100644'} for p in repair.DELTA}
        head={p:{'sha':'b'*40,'mode':'100644'} for p in repair.DELTA}
        self.assertEqual(len(repair.package_delta(base,head)),len(repair.DELTA))
        with self.assertRaises(Hold):repair.package_delta(base,dict(head,**{'elixir/mix.exs':{'sha':'c'*40}}))
        with self.assertRaises(Hold):repair.package_delta(base,{k:v for k,v in head.items() if not k.endswith('README.md')})
        changed=dict(head);changed[next(iter(changed))]=dict(changed[next(iter(changed))],mode='100755')
        with self.assertRaises(Hold):repair.package_delta(base,changed)
    def status(self):
        return {'schema':'snci-prepare-status/v1','installed_revision':'a'*40,'phase':'preparing',
                'profile':'main','pid':123,'started':1,'updated':2,'prepared':[]}
    def test_public_status_refuses_unknown_secret_field(self):
        with patch.object(repair,'INSTALL',self.path):
            with self.assertRaises(Hold):repair.emit_status(dict(self.status(),credentials='PRIVATE_FIXTURE'))
    def test_public_status_refuses_arbitrary_profile_or_revision(self):
        with patch.object(repair,'INSTALL',self.path):
            for field in ('profile','installed_revision'):
                with self.subTest(field=field),self.assertRaises(Hold):repair.emit_status(dict(self.status(),**{field:'private_fixture_credential'}))
    def test_status_is_readable_metadata_and_contains_no_logs(self):
        with patch.object(repair,'INSTALL',self.path):repair.emit_status(self.status())
        p=self.path/'preparation-status.json'
        self.assertEqual(p.stat().st_mode&0o777,0o644)
        self.assertEqual(json.loads(p.read_bytes()),self.status())
    def test_driver_does_not_export_arbitrary_exception_text(self):
        fake=types.SimpleNamespace(prepare=lambda _:(_ for _ in ()).throw(RuntimeError('private_fixture_credential')))
        status=[]
        with patch.dict('sys.modules',{'owner':fake}),patch.object(repair.os,'dup2'),patch.object(repair,'emit_status',side_effect=lambda s:status.append(json.loads(json.dumps(s)))),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):repair.preparation_driver('a'*40,self.path)
        self.assertEqual(status[-1]['phase'],'hold')
        self.assertNotIn('private_fixture_credential',json.dumps(status))
    def test_driver_prepares_two_profiles_and_never_activates(self):
        state=self.path/'state';state.mkdir()
        called=[];status=[]
        def prepare(name):
            called.append(name);p=state/('prepare-'+name);p.mkdir()
            receipt={'profile':name,'head':'b'*40,'tree':'c'*40,'image':'sha256:'+'d'*64,
                     'quality':{'tests':305 if name=='main' else 328,'skipped':6,'coverage':100.0,'dialyzer_errors':0},
                     'credentials':'PRIVATE_FIXTURE'}
            (p/'acceptance.json').write_text(json.dumps(receipt))
        fake=types.SimpleNamespace(prepare=prepare,load_policy=lambda:{'enabled':False})
        with patch.dict('sys.modules',{'owner':fake}),patch.object(repair,'STATE',state),patch.object(repair.os,'dup2'),patch.object(repair,'emit_status',side_effect=lambda s:status.append(json.loads(json.dumps(s)))),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            repair.preparation_driver('a'*40,self.path)
        self.assertEqual(called,['main','sn004'])
        self.assertEqual(status[-1]['phase'],'all_profiles_prepared_disabled')
        self.assertEqual([r['tests'] for r in status[-1]['prepared']],[305,328])
        self.assertNotIn('PRIVATE_FIXTURE',json.dumps(status))
    def test_driver_cannot_claim_success_if_policy_activates(self):
        state=self.path/'state';state.mkdir()
        def prepare(name):
            p=state/('prepare-'+name);p.mkdir()
            (p/'acceptance.json').write_text(json.dumps({'profile':name,'head':'b'*40,'tree':'c'*40,'image':'sha256:'+'d'*64,
                'quality':{'tests':305 if name=='main' else 328,'skipped':6,'coverage':100.0,'dialyzer_errors':0}}))
        fake=types.SimpleNamespace(prepare=prepare,load_policy=lambda:{'enabled':True})
        statuses=[]
        with patch.dict('sys.modules',{'owner':fake}),patch.object(repair,'STATE',state),patch.object(repair.os,'dup2'),patch.object(repair,'emit_status',side_effect=lambda s:statuses.append(dict(s))),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):repair.preparation_driver('a'*40,self.path)
        self.assertEqual(statuses[-1]['phase'],'hold')
        self.assertEqual(statuses[-1]['hold_code'],'unexpected_activation')

    def install_fixture(self):
        install=self.path/'install';install.mkdir()
        etc=self.path/'etc';etc.mkdir()
        raw_files={'owner.py':b'previous owner implementation\n','README.md':b'previous README\n',
                   'Dependency.Dockerfile':self.recipe,
                   'profiles.json':json.dumps({'main':{'head':'e'*40,'tree':'f'*40}}).encode()}
        manifest={}
        for name,raw in raw_files.items():
            (install/name).write_bytes(raw);manifest[name]=sha256(raw)
        (install/'installed.json').write_text(json.dumps(manifest));(install/'revision').write_text(repair.BASE)
        policy={'enabled':False,'profiles':[],'installed_revision':repair.BASE,
                'github':{},'github_key':'private-fixture-path','unchanged_setting':123}
        (etc/'policy.json').write_text(json.dumps(policy))
        base={repair.PREFIX+k:{'sha':blob_hash(v),'size':len(v),'mode':'100644'} for k,v in raw_files.items()}
        head=dict(base);blobs={}
        for name in repair.DELTA:
            raw=(name+' reviewed change\n').encode();e={'sha':blob_hash(raw),'size':len(raw),'mode':'100644'}
            head[name]=e;blobs[e['sha']]=raw
        class Source:
            def tree(self,revision):
                if revision==repair.BASE:return '1'*40,base
                if revision=='a'*40:return '2'*40,head
                return 'f'*40,self_entries
            def blob(self,e):return blobs[e['sha']]
        self_entries=self.entries;source=Source();calls=[]
        def run(args,**kwargs):
            calls.append(args)
            return types.SimpleNamespace(stdout=owner.SEED.encode()+b'\n',returncode=0)
        def replace_policy(p):(etc/'policy.json').write_text(json.dumps(p))
        fake=types.SimpleNamespace(SEED=owner.SEED,runner=types.SimpleNamespace(DOCKER=owner.runner.DOCKER),
                load_policy=lambda:json.loads((etc/'policy.json').read_text()),run=run,replace_policy=replace_policy)
        return install,etc,policy,fake,source,calls

    def test_full_repair_preserves_failed_build_policy_and_journal_and_launches_once(self):
        install,etc,policy,fake,source,calls=self.install_fixture()
        (self.path/'attempts').mkdir();journal=self.path/'attempts/journal';journal.write_bytes(b'unchanged history')
        oldmask=repair.os.umask(0o077)
        try:
            with patch.object(repair,'INSTALL',install),patch.object(repair,'STATE',self.path),patch.object(repair,'ETC',etc),patch.object(repair.os,'geteuid',return_value=0),patch.object(repair.os,'uname',return_value=types.SimpleNamespace(nodename='1c-db')),patch.dict('sys.modules',{'owner':fake}),patch.object(repair,'stopped'),patch.object(repair,'GitHub'),patch.object(repair,'Source',return_value=source),redirect_stdout(io.StringIO()):
                repair.apply('a'*40)
                self.assertEqual((install/'revision').read_text(),'a'*40)
                after=json.loads((etc/'policy.json').read_text())
                self.assertEqual(after,dict(policy,installed_revision='a'*40))
                self.assertFalse(after['enabled'])
                archived=self.path/'repair-local-seed-aaaaaaaaaaaa/failed-build'
                self.assertEqual((archived/'build.log').read_bytes(),self.log)
                self.assertEqual(len(list((archived/'source').iterdir())),180)
                self.assertEqual(journal.read_bytes(),b'unchanged history')
                self.assertEqual(len([c for c in calls if c[0]=='/usr/bin/tmux']),1)
                with self.assertRaises(Hold):repair.apply('a'*40)
                self.assertEqual(len([c for c in calls if c[0]=='/usr/bin/tmux']),1)
        finally:repair.os.umask(oldmask)

    def test_active_service_refuses_before_any_repair_mutation(self):
        fake=types.SimpleNamespace(run=lambda *a,**kw:types.SimpleNamespace(stdout=b'active\n'))
        with self.assertRaises(Hold):repair.stopped(fake)

if __name__=='__main__':unittest.main()
