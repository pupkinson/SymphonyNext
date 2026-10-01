"""Fail-closed cache inspection and durable, single-use owner preparation."""
import copy
from contextlib import redirect_stdout, redirect_stderr
import importlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold,blob_hash,canonical,sha256
from snci import runner
import owner

HEAD='a'*40
IMAGE='sha256:'+'b'*64


def archive(members):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w') as tar:
        for name,raw,kind in members:
            entry=tarfile.TarInfo(name);entry.type=kind
            if kind==tarfile.REGTYPE:
                entry.size=len(raw);tar.addfile(entry,io.BytesIO(raw))
            else:entry.linkname='outside';tar.addfile(entry)
    return out.getvalue()


class DialyzerRepairTests(unittest.TestCase):
    def setUp(self):
        try:self.repair=importlib.import_module('snci.repair_dialyzer')
        except ImportError:self.fail('Bounded Dialyzer repair not implemented')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        self.install=self.path/'install';self.install.mkdir()
        self.state=self.path/'state';self.state.mkdir()
        self.etc=self.path/'etc';self.etc.mkdir()
        self.root=self.state/'prepare-main';self.root.mkdir()
        (self.root/'source').mkdir();self.entries={}
        for i in range(180):
            name=f'f{i:03}';raw=b'unchanged locked fixture'
            (self.root/'source'/name).write_bytes(raw)
            (self.root/'source'/name).chmod(0o644)
            self.entries[name]=dict(sha=blob_hash(raw),size=len(raw),mode='100644')
        self.seed=dict(id=owner.SEED,reference='localhost/symphony-next-ci-seed:'+owner.SEED.split(':')[1],
                       layers=['sha256:'+'c'*64])
        self.recipe=b'previous reviewed recipe\n'
        self.trace=b'snci.common.Hold: worker_failed\n'
        self.log=(''.join('SNCI_STAGE '+s+' 0\n' for s in ['isolation','pg-init','pg-start','pg-create','deps',
                           'build','format','lint','coverage'])+
                  '305 tests, 0 failures, 6 skipped\n| 100.00% | Total |\nSNCI_WORKER_FAILED\n').encode()
        contents={'Dependency.Dockerfile':self.recipe,'.dockerignore':b'*\n!Dependency.Dockerfile\n!source\n!source/**\n',
                  'image.id':IMAGE.encode(),'seed.json':canonical(self.seed),'source.json':canonical(self.entries),
                  'build.log':b'build succeeded','native-codex.log':b'old offline probe',
                  'worker.log':self.log,'reused-image.json':canonical(dict(image=IMAGE,origin=str(self.state/'old-failure'),
                                                     build_log_sha256=sha256(b'build succeeded')))}
        for name,raw in contents.items():(self.root/name).write_bytes(raw)
        for name,value in [('INSTALL',self.install),('STATE',self.state),('ETC',self.etc),
                           ('WORKER_LOG_SHA',sha256(self.log)),('trusted',lambda p,**kw:Path(p))]:
            p=patch.object(self.repair,name,value);p.start();self.addCleanup(p.stop)

    def cache(self,members):
        path=self.path/'cache.tar';path.write_bytes(archive(members))
        return self.repair.plt_files(path)

    def test_regular_project_plt_is_hashed_without_extracting_archive(self):
        result=self.cache([('dev/',b'',tarfile.DIRTYPE),('dev/dialyxir_fixture.plt',b'cache',tarfile.REGTYPE),
                           ('dev/lib/app/ebin/a.beam',b'beam',tarfile.REGTYPE)])
        self.assertEqual(result,[dict(path='dev/dialyxir_fixture.plt',size=5,sha256=sha256(b'cache'))])
        self.assertFalse((self.path/'dev').exists())

    def test_missing_project_cache_is_empty_not_successful_native_acceptance(self):
        self.assertEqual(self.cache([('dev/lib/app/a.beam',b'x',tarfile.REGTYPE)]),[])

    def test_inert_probe_never_starts_container_and_keeps_private_replay_claim(self):
        key='c'*64;name='snci-plt-'+key;calls=[];created=False
        data=dict(Name='/'+name,Image=IMAGE,Config=dict(User='10001:10001',Labels={'snci.plt':key},
                  Entrypoint=['/usr/bin/true'],Cmd=[],Volumes=None),Mounts=[],
                  HostConfig=dict(NetworkMode='none',ReadonlyRootfs=True,Privileged=False,CapDrop=['ALL'],
                         CapAdd=None,SecurityOpt=['no-new-privileges:true'],RestartPolicy=dict(Name='no')),
                  State=dict(Status='created',Running=False))
        def command(args,**kwargs):
            nonlocal created
            calls.append(args)
            if args[0]=='ps':return name.encode() if created else b''
            if args[0]=='create':created=True;return b'container-id'
            if args[0]=='inspect':return canonical([data])
            if args[0]=='rm':created=False;return b''
            self.fail('Unexpected Docker command')
        def copy_cache(args,**kwargs):
            self.assertEqual(args[-3:],['cp',name+':/seed/source/elixir/_build/dev/.','-'])
            kwargs['stdout'].write(archive([('./',b'',tarfile.DIRTYPE),('a.plt',b'cache',tarfile.REGTYPE)]))
            return types.SimpleNamespace(returncode=0)
        with patch.object(runner,'command',side_effect=command),patch.object(self.repair.subprocess,'run',side_effect=copy_cache):
            files=self.repair.inspect_plt(IMAGE,self.path,key)
            self.assertEqual(files,[dict(path='a.plt',size=5,sha256=sha256(b'cache'))])
            self.assertFalse(created);self.assertFalse(any(c[0]=='start' for c in calls))
            with self.assertRaises(Hold):self.repair.inspect_plt(IMAGE,self.path,key)
        self.assertTrue((self.path/('plt-'+key+'.json')).exists())
        self.assertEqual(len([c for c in calls if c[0]=='create']),1)

    def test_scope_rejects_application_changes_deletions_and_executable_package(self):
        base={p:dict(sha='b'*40,mode='100644') for p in self.repair.DELTA}
        head={p:dict(sha='c'*40,mode='100644') for p in self.repair.DELTA}
        self.repair.package_delta(base,head)
        with self.assertRaises(Hold):self.repair.package_delta(base,dict(head,**{'elixir/mix.exs':dict(sha='d'*40)}))
        with self.assertRaises(Hold):self.repair.package_delta(base,{p:e for p,e in head.items() if not p.endswith('README.md')})
        head[self.repair.PREFIX+'worker.py']['mode']='100755'
        with self.assertRaises(Hold):self.repair.package_delta(base,head)

    def test_traversal_symlink_duplicate_and_empty_cache_hold(self):
        for members in [[('../outside.plt',b'x',tarfile.REGTYPE)],
                        [('dev/a.plt',b'',tarfile.SYMTYPE)],
                        [('dev/a.plt',b'x',tarfile.REGTYPE),('dev/a.plt',b'y',tarfile.REGTYPE)],
                        [('dev/a.plt',b'',tarfile.REGTYPE)]]:
            with self.subTest(members=members),self.assertRaises(Hold):self.cache(members)

    def test_failure_evidence_requires_exact_unaccepted_worker_log_and_source(self):
        evidence=self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)
        self.assertEqual(evidence['worker_log_sha256'],sha256(self.log))
        for path in [self.root/'acceptance.json',self.root/'unexpected']:
            path.write_bytes(b'x')
            with self.assertRaises(Hold):self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)
            path.unlink()
        (self.root/'worker.log').write_bytes(self.log+b'changed')
        with self.assertRaises(Hold):self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)

    def test_changed_missing_and_symlink_source_are_refused(self):
        path=self.root/'source/f000';path.write_bytes(b'changed')
        with self.assertRaises(Hold):self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)
        path.unlink()
        with self.assertRaises(Hold):self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)
        path.symlink_to('f001')
        with self.assertRaises(Hold):self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)

    def fixture(self):
        base=self.repair.BASE
        defs={name:dict(name=name,head=('e' if name=='main' else 'd')*40,tree=('f' if name=='main' else 'c')*40,
                       minimum_tests=305 if name=='main' else 328,maximum_skips=6,locked={}) for name in ('main','sn004')}
        binary=self.path/'codex';binary.write_bytes(b'fixture binary')
        policy=dict(enabled=False,profiles=[],installed_revision=base,github={},github_key='fixture-key-path',
                    codex_binary=str(binary),codex_sha256=sha256(binary.read_bytes()),ruleset={},unchanged=123)
        (self.etc/'policy.json').write_bytes(canonical(policy))
        files={'README.md':b'old readme','worker.py':b'old worker','snci/runner.py':b'old runner',
               'Dependency.Dockerfile':self.recipe,'profiles.json':canonical(defs)}
        manifest={}
        for name,raw in files.items():
            path=self.install/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);manifest[name]=sha256(raw)
        (self.install/'installed.json').write_bytes(canonical(manifest));(self.install/'revision').write_text(base)
        status=dict(schema='snci-prepare-status/v1',installed_revision=base,phase='hold',profile='main',pid=2147483647,
                    started=1,updated=2,prepared=[],hold_code='worker_failed',error_type='Hold',exit_code=1)
        (self.install/'preparation-status.json').write_bytes(canonical(status))
        trace=self.state/('repair-cap-names-'+base[:12]);trace.mkdir();(trace/'prepare.log').write_bytes(self.trace)
        tree={self.repair.PREFIX+n:dict(sha=blob_hash(raw),size=len(raw),mode='100644') for n,raw in files.items()}
        new=dict(tree);blobs={}
        for name in self.repair.DELTA:
            raw=(name+' reviewed\n').encode();entry=dict(sha=blob_hash(raw),size=len(raw),mode='100644')
            new[name]=entry;blobs[entry['sha']]=raw
        entries=self.entries
        class Source:
            def tree(self,revision):
                if revision==base:return '1'*40,tree
                if revision==HEAD:return '2'*40,new
                d=next(d for d in defs.values() if d['head']==revision);return d['tree'],entries
            def blob(self,entry):return blobs[entry['sha']]
            def materialize(self,values,directory):
                Path(directory).mkdir()
                for name in values:
                    (Path(directory)/name).write_bytes(b'unchanged locked fixture')
                    (Path(directory)/name).chmod(0o644)
        calls=[]
        def run(args,**kw):
            calls.append(args)
            if args[0]=='/usr/bin/systemctl':return types.SimpleNamespace(stdout=b'disabled' if 'UnitFileState' in args else b'inactive')
            if args[0]=='/usr/bin/tmux':return types.SimpleNamespace(stdout=b'')
            if args[:2]==['/usr/bin/python3','-I']:
                kw['stdout'].write(b'fresh offline probe');return types.SimpleNamespace(stdout=b'')
            raise AssertionError(args)
        def replace(value):(self.etc/'policy.json').write_bytes(canonical(value))
        def build(root):
            calls.append(['dependency-build']);(root/'build.log').write_bytes(b'new build')
            (root/'seed.json').write_bytes(canonical(self.seed));(root/'image.id').write_text(IMAGE);return IMAGE
        fake=types.SimpleNamespace(SEED=owner.SEED,BINARY=str(binary),BINARY_SHA=policy['codex_sha256'],
                 load_policy=lambda:json.loads((self.etc/'policy.json').read_bytes()),replace_policy=replace,
                 run=run,verify_seed_build=lambda seed,image:None,validate_policy=lambda p:None,
                 validate_rules=lambda *args:None,build_dependency_image=build)
        api=types.SimpleNamespace(request=lambda method,path:dict(sha=HEAD,parents=[dict(sha=base)]))
        return fake,Source(),api,calls,policy,defs

    def apply_patches(self,fake,source,api):
        patches=[patch.dict('sys.modules',{'owner':fake}),patch.object(self.repair,'GitHub',return_value=api),
                 patch.object(self.repair,'Source',return_value=source),patch.object(self.repair,'stopped'),
                 patch.object(self.repair.os,'geteuid',return_value=0),
                 patch.object(self.repair.os,'uname',return_value=types.SimpleNamespace(nodename='1c-db')),
                 patch.object(self.repair,'emit_status'),patch.object(runner,'command',return_value=b''),
                 patch.object(self.repair,'inspect_plt',return_value=[dict(path='dev/a.plt',size=5,sha256=sha256(b'cache'))])]
        for p in patches:p.start();self.addCleanup(p.stop)

    def test_apply_archives_exact_failed_attempt_preserves_policy_journal_and_refuses_replay(self):
        fake,source,api,calls,policy,defs=self.fixture();self.apply_patches(fake,source,api)
        journal=self.state/'journal';journal.write_bytes(b'preserved')
        with redirect_stdout(io.StringIO()):self.repair.apply(HEAD)
        directory=self.state/('repair-dialyzer-'+HEAD[:12])
        self.assertEqual((directory/'failed-main/worker.log').read_bytes(),self.log)
        self.assertEqual(json.loads((directory/'policy-before.json').read_bytes()),policy)
        self.assertEqual(fake.load_policy(),dict(policy,installed_revision=HEAD))
        self.assertEqual(journal.read_bytes(),b'preserved');self.assertFalse(self.root.exists())
        self.assertEqual(len([x for x in calls if x[0]=='/usr/bin/tmux']),1)
        with self.assertRaises(Hold):self.repair.apply(HEAD)
        self.assertEqual(len([x for x in calls if x[0]=='/usr/bin/tmux']),1)

    def test_staging_drift_refuses_archive_or_launch(self):
        fake,source,api,calls,policy,defs=self.fixture();self.apply_patches(fake,source,api)
        blob=source.blob
        def drift(entry):(self.root/'source/f000').write_bytes(b'concurrent');return blob(entry)
        source.blob=drift
        with self.assertRaises(Hold):self.repair.apply(HEAD)
        self.assertTrue(self.root.exists());self.assertEqual(fake.load_policy(),policy)
        self.assertFalse(any(c[0]=='/usr/bin/tmux' for c in calls))

    def prepare(self,warm=True):
        fake,source,api,calls,policy,defs=self.fixture()
        directory=self.state/('repair-dialyzer-'+HEAD[:12]);directory.mkdir()
        self.root.rename(directory/'failed-main')
        inputs=dict(head=HEAD,image=IMAGE,seed=self.seed,profiles=defs,
                    cache_before=[dict(path='dev/a.plt',size=5,sha256=sha256(b'cache'))] if warm else [])
        (directory/'input.json').write_bytes(canonical(inputs));(directory/'main-entries.json').write_bytes(canonical(self.entries))
        policy['installed_revision']=HEAD;fake.replace_policy(policy)
        for p in [patch.dict('sys.modules',{'owner':fake}),patch.object(self.repair,'GitHub',return_value=api),
                  patch.object(self.repair,'Source',return_value=source),patch.object(self.repair,'get_review_identity',return_value=(10001,10001)),
                  patch.object(self.repair,'inspect_plt',return_value=inputs['cache_before'] or [dict(path='dev/new.plt',size=1,sha256='d'*64)])]:
            p.start();self.addCleanup(p.stop)
        return fake,calls,directory

    def quality(self,tests=305):
        return dict(stages=dict.fromkeys(('build','format','lint','coverage','dialyzer'),0),source_before=True,
                    source_after=True,cleanup=0,tests=tests,failures=0,skipped=6,coverage=100.0,dialyzer_errors=0)

    def test_warm_image_reuse_runs_full_quality_once_and_keeps_disabled(self):
        fake,calls,directory=self.prepare();keys=[]
        def run(root,key,entries,profile):keys.append(key);return self.quality()
        with patch.object(runner,'run',side_effect=run),redirect_stdout(io.StringIO()):
            self.repair.prepare_profile('main',HEAD,directory)
        self.assertEqual(len(keys),1);self.assertNotIn(['dependency-build'],calls)
        self.assertEqual(json.loads((self.root/'acceptance.json').read_bytes())['quality'],self.quality())
        self.assertFalse(fake.load_policy()['enabled'])
        with self.assertRaises(Hold):self.repair.prepare_profile('main',HEAD,directory)
        self.assertEqual(len(keys),1)

    def test_missing_cache_builds_once_and_still_requires_full_quality(self):
        fake,calls,directory=self.prepare(warm=False)
        with patch.object(runner,'run',return_value=self.quality()),redirect_stdout(io.StringIO()):
            self.repair.prepare_profile('main',HEAD,directory)
        self.assertEqual(calls.count(['dependency-build']),1)
        self.assertFalse(json.loads((self.root/'acceptance.json').read_bytes())['reused_image'])

    def test_bad_quality_never_updates_policy_or_writes_acceptance(self):
        fake,calls,directory=self.prepare()
        with patch.object(runner,'run',return_value=self.quality(tests=1)),self.assertRaises(Hold):
            self.repair.prepare_profile('main',HEAD,directory)
        self.assertFalse((self.root/'acceptance.json').exists());self.assertEqual(fake.load_policy()['profiles'],[])

    def test_profile_drift_or_missing_built_cache_stops_before_worker(self):
        fake,calls,directory=self.prepare(warm=False)
        with patch.object(self.repair,'inspect_plt',return_value=[]),patch.object(runner,'run') as quality,self.assertRaises(Hold):
            self.repair.prepare_profile('main',HEAD,directory)
        quality.assert_not_called();self.assertEqual(fake.load_policy()['profiles'],[])

    def test_definition_or_binary_drift_stops_before_profile_directory(self):
        fake,calls,directory=self.prepare()
        definitions=json.loads((self.install/'profiles.json').read_bytes())
        (self.install/'profiles.json').write_bytes(canonical(dict(definitions,main=dict(definitions['main'],minimum_tests=1))))
        with self.assertRaises(Hold):self.repair.prepare_profile('main',HEAD,directory)
        self.assertFalse(self.root.exists())
        (self.install/'profiles.json').write_bytes(canonical(definitions));Path(fake.BINARY).write_bytes(b'changed')
        with self.assertRaises(Hold):self.repair.prepare_profile('main',HEAD,directory)
        self.assertFalse(self.root.exists())

    def test_both_profiles_run_once_in_order_with_distinct_keys_and_full_thresholds(self):
        fake,calls,directory=self.prepare();keys=[]
        def quality(root,key,entries,profile):
            keys.append(key);return self.quality(profile['minimum_tests'])
        with patch.object(runner,'run',side_effect=quality),redirect_stdout(io.StringIO()):
            self.repair.prepare_profile('main',HEAD,directory)
            self.repair.prepare_profile('sn004',HEAD,directory)
        self.assertEqual(len(keys),2);self.assertNotEqual(keys[0],keys[1])
        self.assertEqual([p['name'] for p in fake.load_policy()['profiles']],['main','sn004'])
        self.assertFalse(fake.load_policy()['enabled']);self.assertEqual(calls.count(['dependency-build']),1)
        receipt=json.loads((self.state/'prepare-sn004/acceptance.json').read_bytes())
        self.assertEqual(receipt['quality']['tests'],328)

    def test_active_units_refuse_apply_before_claim_or_archive(self):
        fake,source,api,calls,policy,defs=self.fixture();self.apply_patches(fake,source,api)
        with patch.object(self.repair,'stopped',side_effect=Hold('repair_service_active')),self.assertRaises(Hold):
            self.repair.apply(HEAD)
        self.assertTrue(self.root.exists());self.assertEqual(fake.load_policy(),policy)
        self.assertFalse((self.state/('repair-dialyzer-'+HEAD[:12])).exists())

    def test_driver_main_failure_stops_before_sn004_without_exception_text_export(self):
        directory=self.path/'driver';directory.mkdir();names=[];states=[]
        def fail(name,*args):names.append(name);raise RuntimeError('PRIVATE_FIXTURE_SECRET')
        with patch.object(self.repair.os,'dup2'),patch.object(self.repair,'prepare_profile',side_effect=fail),\
             patch.object(self.repair,'emit_status',side_effect=lambda s:states.append(copy.deepcopy(s))),\
             redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.repair.preparation_driver(HEAD,directory)
        self.assertEqual(names,['main']);self.assertEqual(states[-1]['phase'],'hold')
        self.assertNotIn('PRIVATE_FIXTURE_SECRET',json.dumps(states))


if __name__=='__main__':unittest.main()
