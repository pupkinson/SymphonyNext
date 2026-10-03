"""Recovery changes real immutable policy/package/history, not mocked writes."""
import copy
import importlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import unittest
import types
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, canonical, sha256
from snci import refresh, runner
from snci.source import Source
import owner as owner_code
import test_review_install as install_fixture

HEAD='a'*40


class RetentionRecoveryTests(unittest.TestCase):
    def setUp(self):
        try:self.n=importlib.import_module('snci.recover_retention')
        except ImportError:self.fail('Fresh quality recovery with running image retention is absent')
        h=install_fixture.ReviewInstallTests('test_install_changes_only_revision_and_preserves_history_and_backups')
        h.setUp();self.addCleanup(h.doCleanups);self.h=h
        self.root=h.root;self.events=[];self.containers={};self.images={}
        self.patches=[]
        for name in ['INSTALL','STATE','ETC']:self.swap(self.n,name,getattr(h.r,name))
        self.swap(self.n,'trusted',lambda p,**kw:Path(p))
        oldkey=h.key
        self.app={}
        for p in h.policy['profiles']:
            raw=('LOCKED_'+p['name']).encode();digest=blob_hash(raw);h.blobs[digest]=raw
            p['locked']={'elixir/mix.exs':digest}
            self.app[p['name']]={'elixir/mix.exs':{'sha':digest,'size':len(raw),'mode':'100644'}}
        h.before=canonical(h.policy);h.old_digest=sha256(h.before)
        (h.etc/'policy.json').write_bytes(h.before)
        h.key=sha256(canonical([h.r.TARGET,h.old_digest]));h.attempt.rename(h.attempt.with_name(h.key));h.attempt=h.attempt.with_name(h.key)
        inputs=json.loads((h.attempt/'inputs.json').read_bytes());inputs['policy_sha256']=h.old_digest
        (h.attempt/'inputs.json').write_bytes(canonical(inputs))
        with sqlite3.connect(h.state/'journal.sqlite3') as db:
            db.execute('UPDATE attempts SET key=?,policy=? WHERE key=?',(h.key,h.old_digest,oldkey))
        self.swap(h.r,'OLD_POLICY_SHA',h.old_digest)
        self.swap(h.r,'DISABLED_POLICY_SHA',sha256(canonical(dict(h.policy,enabled=False))))
        parent=copy.deepcopy(h.new);new=copy.deepcopy(parent)
        for name in self.n.DELTA:
            raw=('RETENTION:'+name).encode();digest=blob_hash(raw);h.blobs[digest]=raw
            new[name]={'sha':digest,'size':len(raw),'mode':'100644'}
        h.trees[self.n.SOURCE_BASE]=(self.n.SOURCE_TREE,parent);h.trees[HEAD]=('c'*40,new)
        for p in h.policy['profiles']:h.trees[p['head']]=(p['tree'],self.app[p['name']])
        real=Source.__new__(Source);real.tree=h.source.tree;real.blob=h.source.blob;h.source.materialize=real.materialize
        seed={'Id':self.n.SEED,'RootFS':{'Type':'layers','Layers':['sha256:'+'e'*64]}}
        self.images[self.n.SEED]=seed;h.owner.SEED=self.n.SEED
        self.images['localhost/symphony-next-ci-seed:'+self.n.SEED.split(':')[1]]=seed
        h.owner.image_layers=lambda info:info['RootFS']['Layers']
        def inspect(ref,missing_ok=False):
            value=self.images.get(ref)
            if value is None and not missing_ok:raise Hold('local_image_inspect_failed')
            return copy.deepcopy(value)
        h.owner.inspect_image=inspect
        self.daemon={'root':'/mnt/sdb1/production-runtime/docker-data','driver':'overlay2','id':self.n.DAEMON_ID}
        self.swap(self.n,'validate_rules',lambda *args:None)
        self.swap(self.n,'eligible_target',lambda api:copy.deepcopy(h.r.TARGET))
        self.swap(self.n,'native_probe',lambda stage,owner,policy,path:self.probe(path))
        def build(root):
            name=root.name;image='sha256:'+('3' if name=='main' else '4')*64
            self.events.append(('build',name));self.images[image]={'Id':image,'RootFS':seed['RootFS']}
            (root/'image.id').write_text(image);(root/'build.log').write_bytes(b'BUILT')
            return image
        h.owner.build_dependency_image=build
        h.owner.verify_seed_build=types.FunctionType(owner_code.verify_seed_build.__code__,
            dict(owner_code.__dict__,inspect_image=inspect))
        original=h.owner.run
        def run(args,**kw):
            if args[:2]==['systemctl','show']:return original(args,**kw)
            self.assertEqual(args[:2],['/usr/bin/docker','--host=unix:///var/run/docker.sock'])
            a=args[2:];out=b''
            if a[0]=='info':out=canonical(self.daemon)
            elif a[:2]==['ps','-a']:
                name=next(x for x in a if x.startswith('name=')).removeprefix('name=^/').removesuffix('$')
                out=(name+'\n').encode() if name in self.containers else b''
            elif a[0]=='create':
                def option(name):return next((x.split('=',1)[1] for x in a if x.startswith(name+'=')),None)
                name=option('--name');image=a[a.index('--entrypoint=/usr/bin/env')+1]
                label=option('--label');k,v=label.split('=',1)
                self.containers[name]={'Id':'b'*64,'Name':'/'+name,'Image':image,
                    'Config':{'User':option('--user'),'WorkingDir':option('--workdir'),
                              'Entrypoint':['/usr/bin/env'],'Cmd':a[a.index(image)+1:],
                              'Labels':{k:v},'Volumes':None,'OpenStdin':False,'Tty':False,
                              'Healthcheck':{'Test':['NONE']} if '--no-healthcheck' in a else {'Test':['CMD','unexpected-healthcheck']}},
                    'HostConfig':{'NetworkMode':option('--network') or 'bridge','ReadonlyRootfs':'--read-only' in a,
                        'Privileged':False,'CapDrop':[option('--cap-drop')] if option('--cap-drop') else [],
                        'CapAdd':None,'SecurityOpt':[option('--security-opt')],
                        'RestartPolicy':{'Name':option('--restart')},'Memory':int(option('--memory').removesuffix('m'))*1048576,
                        'MemorySwap':int(option('--memory-swap').removesuffix('m'))*1048576,
                        'NanoCpus':int(float(option('--cpus'))*1000000000),'PidsLimit':int(option('--pids-limit')),
                        'PidMode':'','IpcMode':'private','UTSMode':'','UsernsMode':''},
                    'Mounts':[],'State':{'Running':False,'Paused':False,'Restarting':False,'Dead':False,'OOMKilled':False,'Error':''}}
                out=b'b'*64
            elif a[0]=='start':self.containers[a[1]]['State']['Running']=True
            elif a[0]=='inspect':out=canonical([self.containers[a[1]]])
            elif a[:2]==['image','tag']:self.images[a[3]]=copy.deepcopy(self.images[a[2]])
            else:raise AssertionError('Unexpected mutation '+str(a))
            self.events.append(tuple(a[:2]));return type('Result',(),{'stdout':out})()
        h.owner.run=run
        h.api.request=lambda method,path:{}
        def quality(root,key,entries,profile):
            self.events.append(('quality',profile['name']))
            (root/'worker.log').write_bytes(b'REAL_BOUNDARY_FIXTURE')
            return {'tests':305 if profile['name']=='main' else 331,'failures':0,'skipped':6,'coverage':100.,
                    'dialyzer_errors':0,'cleanup':0,'source_before':True,'source_after':True,
                    'stages':{x:0 for x in ('build','format','lint','coverage','dialyzer')}}
        self.swap(runner,'run',quality)

    def swap(self,module,name,value):
        p=patch.object(module,name,value);p.start();self.addCleanup(p.stop)

    def probe(self,path):path.write_bytes(b'NATIVE_9_PASS');return sha256(path.read_bytes())

    def perform(self):return self.n.perform(self.h.owner,HEAD,self.h.api,self.h.source)

    def test_new_images_require_fresh_receipts_and_old_history_is_preserved(self):
        h=self.h;journal=(h.state/'journal.sqlite3').read_bytes()
        old={p['preparation']:(h.state/p['preparation']).read_bytes() for p in h.policy['profiles']}
        self.perform();actual=h.owner.load_policy()
        self.assertTrue(actual['enabled']);self.assertEqual(actual['installed_revision'],HEAD)
        expected=copy.deepcopy(h.policy);expected['installed_revision']=HEAD
        for p in expected['profiles']:
            p['image']='sha256:'+('3' if p['name']=='main' else '4')*64
            p['preparation']='refresh-'+HEAD+'/'+p['name']+'/acceptance.json'
            p['preparation_sha256']=sha256((h.state/p['preparation']).read_bytes())
        self.assertEqual(actual,expected);self.assertEqual((h.state/'journal.sqlite3').read_bytes(),journal)
        for p,raw in old.items():self.assertEqual((h.state/p).read_bytes(),raw)
        self.assertEqual([x for x in self.events if x[0]=='quality'],[('quality','main'),('quality','sn004')])
        self.assertTrue(all(c['State']['Running'] for c in self.containers.values()))
        self.n.completed(h.state,actual,(h.etc/'policy.json').read_bytes(),h.owner)

    def test_bad_quality_holds_before_policy_swap_and_blocks_replay(self):
        self.swap(runner,'run',lambda *a:{})
        with self.assertRaisesRegex(Hold,'quality_stages'):self.perform()
        self.h.retained()
        with self.assertRaisesRegex(Hold,'retention_already_claimed'):self.perform()

    def test_failed_native_probe_preserves_old_package_and_policy(self):
        def fail(*a):raise Hold('fixture_native_failed')
        self.swap(self.n,'native_probe',fail)
        with self.assertRaisesRegex(Hold,'fixture_native_failed'):self.perform()
        self.h.retained();self.assertFalse(self.images.get('sha256:'+'3'*64))

    def test_daemon_drift_after_build_holds_before_swap(self):
        old=self.h.owner.build_dependency_image
        def build(root):
            image=old(root);self.daemon={'id':'CHANGED'}
            return image
        self.h.owner.build_dependency_image=build
        with self.assertRaisesRegex(Hold,'retention_daemon'):self.perform()
        self.h.retained()

    def test_old_receipt_drift_holds_before_swap(self):
        old=self.h.owner.build_dependency_image
        def build(root):
            image=old(root);path=self.h.state/self.h.policy['profiles'][0]['preparation']
            if root.name=='sn004':path.write_bytes(path.read_bytes()+b' ')
            return image
        self.h.owner.build_dependency_image=build
        with self.assertRaisesRegex(Hold,'receipt_digest'):self.perform()
        self.h.retained()

    def test_stopped_or_relaxed_keeper_cannot_complete(self):
        self.perform();h=self.h;actual=h.owner.load_policy()
        c=next(iter(self.containers.values()));before=copy.deepcopy(c)
        for mutation in [lambda d:d['State'].update(Running=False),lambda d:d['HostConfig'].update(NetworkMode='bridge'),
                         lambda d:d['HostConfig'].update(Privileged=True),lambda d:d.update(Mounts=[{'Source':'/var/run/docker.sock'}])]:
            c.clear();c.update(copy.deepcopy(before));mutation(c)
            with self.assertRaisesRegex(Hold,'retention_keeper'):
                self.n.completed(h.state,actual,(h.etc/'policy.json').read_bytes(),h.owner)

    def test_inherited_image_healthcheck_cannot_execute_in_keeper(self):
        self.perform();h=self.h;p=h.owner.load_policy()
        next(iter(self.containers.values()))['Config']['Healthcheck']={'Test':['CMD','unexpected-command']}
        with self.assertRaisesRegex(Hold,'retention_keeper'):
            self.n.completed(h.state,p,(h.etc/'policy.json').read_bytes(),h.owner)

    def test_keeper_collision_is_refused_before_claim(self):
        self.containers['snci-retain-'+HEAD+'-main']={'foreign':True}
        with self.assertRaisesRegex(Hold,'retention_keeper_exists'):self.perform()
        self.h.retained();self.assertFalse((self.h.state/('refresh-'+HEAD)).exists())

    def test_unknown_create_outcome_keeps_claim_and_never_repeats(self):
        original=self.h.owner.run
        def unknown(args,**kw):
            result=original(args,**kw)
            if args[2]=='create':raise subprocess.TimeoutExpired(args,30)
            return result
        self.h.owner.run=unknown
        with self.assertRaises(subprocess.TimeoutExpired):self.perform()
        self.h.retained();self.assertTrue(self.containers)
        with self.assertRaisesRegex(Hold,'retention_already_claimed'):self.perform()

    def test_failed_completion_is_removed_before_owner_service_gate(self):
        original=self.n.write_new
        def partial(path,data,*args):
            original(path,data,*args)
            if path.name=='COMPLETE.json':raise OSError('fixture fsync failure after write')
        self.swap(self.n,'write_new',partial)
        with self.assertRaises(OSError):self.perform()
        self.assertFalse((self.h.state/('refresh-'+HEAD)/'COMPLETE.json').exists())

    def test_expired_new_receipts_do_not_authorize_service(self):
        self.perform();h=self.h;p=h.owner.load_policy();now=time.time()
        with patch('time.time',return_value=now+86401),self.assertRaisesRegex(Hold,'native_acceptance_stale'):
            self.n.completed(h.state,p,(h.etc/'policy.json').read_bytes(),h.owner)

    def test_staged_code_drift_refuses_before_policy_swap(self):
        def drift(stage,owner,policy,path):
            (stage/'owner.py').write_bytes(b'DRIFT');return self.probe(path)
        self.swap(self.n,'native_probe',drift)
        with self.assertRaisesRegex(Hold,'review_install_stage_bytes'):self.perform()
        self.h.retained()

    def test_held_attempt_and_pending_guard_remain_immutable(self):
        with sqlite3.connect(self.h.state/'journal.sqlite3') as db:db.execute("UPDATE attempts SET state='running'")
        with self.assertRaisesRegex(Hold,'review_install_pending'):self.perform()
        self.h.retained();self.assertFalse((self.h.state/('refresh-'+HEAD)).exists())

    def test_source_delta_cannot_change_worker(self):
        tree,entries=self.h.trees[HEAD];entries['ci/continuous/snci/worker.py']=entries['ci/continuous/snci/recover_retention.py']
        with self.assertRaisesRegex(Hold,'retention_package_scope'):self.perform()
        self.h.retained()

    def test_partial_policy_failure_has_no_completion_and_retains_backup(self):
        def fail(p):raise OSError('fixture atomic policy failure')
        self.h.owner.replace_policy=fail
        with self.assertRaises(OSError):self.perform()
        self.assertEqual((self.h.etc/'policy.json').read_bytes(),self.h.before)
        self.assertEqual((self.h.install/'revision').read_text(),HEAD)
        self.assertFalse((self.h.state/('refresh-'+HEAD)/'COMPLETE.json').exists())
        backup=self.h.install.with_name('install-before-retention-'+HEAD)
        self.assertEqual((backup/'revision').read_text(),self.h.r.BASE)

    def test_completion_hash_is_bound_to_native_log(self):
        self.perform();h=self.h;p=h.owner.load_policy()
        (h.state/('refresh-'+HEAD)/'native-codex.log').write_bytes(b'DRIFT')
        with self.assertRaisesRegex(Hold,'retention_completion_native'):
            self.n.completed(h.state,p,(h.etc/'policy.json').read_bytes(),h.owner)


if __name__=='__main__':unittest.main()
