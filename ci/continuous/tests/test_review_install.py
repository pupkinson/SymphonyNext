"""Real temporary policy/package/journal state across an owner-only transition."""
import copy
import importlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, canonical, sha256
from snci import refresh

HEAD='a'*40


class ReviewInstallTests(unittest.TestCase):
    def setUp(self):
        try:self.r=importlib.import_module('snci.repair_review')
        except ImportError:self.fail('Bounded owner transition for accepted source transport is absent')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.install=self.root/'install';self.install.mkdir()
        self.state=self.root/'state';self.state.mkdir();self.etc=self.root/'etc';self.etc.mkdir()
        self.blobs={}
        def entry(raw):
            sha=blob_hash(raw);self.blobs[sha]=raw
            return {'sha':sha,'size':len(raw),'mode':'100644'}
        self.old={'ci/continuous/owner.py':entry(b'OWNER_FIXED'),
                  'ci/continuous/snci/worker.py':entry(b'WORKER_FIXED'),
                  'ci/continuous/Dependency.Dockerfile':entry(b'RECIPE_FIXED')}
        for name in self.r.SOURCE_DELTA:
            if not name.endswith('test_native_probe.py') and not name.startswith('docs/'):
                self.old[name]=entry(('old:'+name).encode())
        self.accepted=copy.deepcopy(self.old)
        for name in self.r.SOURCE_DELTA:self.accepted[name]=entry(('accepted:'+name).encode())
        self.new=copy.deepcopy(self.accepted)
        for name in self.r.DELTA:self.new[name]=entry(('candidate:'+name).encode())
        self.trees={self.r.BASE:(self.r.BASE_TREE,self.old),
                    self.r.SOURCE_BASE:(self.r.SOURCE_TREE,self.accepted),HEAD:('c'*40,self.new)}
        self.source=types.SimpleNamespace(tree=lambda h:copy.deepcopy(self.trees[h]),blob=lambda e:self.blobs[e['sha']])
        self.manifest={}
        for name,e in self.old.items():
            if name.startswith('ci/continuous/'):
                relative=name[len('ci/continuous/'):];p=self.install/relative;p.parent.mkdir(parents=True,exist_ok=True)
                raw=self.blobs[e['sha']];p.write_bytes(raw);self.manifest[relative]=sha256(raw)
        (self.install/'installed.json').write_bytes(canonical(self.manifest))
        (self.install/'revision').write_text(self.r.BASE);(self.install/'review-empty').mkdir()
        self.binary=self.root/'codex';self.binary.write_bytes(b'PINNED_NATIVE_FIXTURE')
        self.policy={'schema':'snci-policy/v1','repository':'pupkinson/SymphonyNext','enabled':True,
                     'installed_revision':self.r.BASE,'codex_binary':str(self.binary),'codex_sha256':sha256(self.binary.read_bytes()),
                     'daily_attempts':4,'review_model':None,'ruleset':{},'profiles':[],'exceptions':[],
                     'github':{'app_id':5069157},'github_key':'PRIVATE_KEY_PATH_FIXTURE'}
        bindings={}
        for name,minimum in [('main',305),('sn004',331)]:
            image='sha256:'+('1' if name=='main' else '2')*64
            profile={'name':name,'head':self.r.TARGET['base'] if name=='main' else self.r.TARGET['head'],
                     'tree':'b'*40 if name=='main' else self.r.TREE,'image':image,
                     'minimum_tests':minimum,'maximum_skips':6,'locked':{'elixir/mix.exs':'d'*40}}
            quality={'tests':minimum,'failures':0,'skipped':6,'coverage':100.,'dialyzer_errors':0,
                     'stages':{x:0 for x in ('build','format','lint','coverage','dialyzer')},'cleanup':0,
                     'source_before':True,'source_after':True}
            receipt={'profile':name,'head':profile['head'],'tree':profile['tree'],'image':image,
                     'codex_sha256':self.policy['codex_sha256'],'time':int(time.time()),'quality':quality,
                     'native_probe_sha256':'e'*64,'refresh_revision':self.r.BASE}
            relative='refresh-'+self.r.BASE+'/'+name+'/acceptance.json'
            path=self.state/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(receipt))
            profile.update(preparation=relative,preparation_sha256=sha256(path.read_bytes()))
            bindings[name]={'image':image,'preparation_sha256':profile['preparation_sha256']}
            self.policy['profiles'].append(profile)
        self.before=canonical(self.policy);(self.etc/'policy.json').write_bytes(self.before)
        self.review=copy.deepcopy(self.r.EXPECTED_REVIEW);self.review_raw=canonical(self.review)
        self.old_digest=sha256(self.before);self.key=sha256(canonical([self.r.TARGET,self.old_digest]))
        self.attempt=self.state/'attempts'/self.key;self.attempt.mkdir(parents=True)
        inputs={'target':dict(self.r.TARGET,tree=self.r.TREE),'policy_sha256':self.old_digest,'profile':'sn004'}
        (self.attempt/'inputs.json').write_bytes(canonical(inputs));(self.attempt/'review.json').write_bytes(self.review_raw)
        with sqlite3.connect(self.state/'journal.sqlite3') as db:
            db.execute('CREATE TABLE attempts(key TEXT,target TEXT,policy TEXT,day TEXT,state TEXT,data TEXT)')
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?)',(self.key,canonical(self.r.TARGET).decode(),
                       self.old_digest,'2026-10-02','hold',canonical({'reason':'review_not_ready'}).decode()))
        self.images={x['image']:{'Id':x['image']} for x in self.policy['profiles']};self.events=[]
        def run(args,**kw):
            self.events.append(args)
            if args[:2]==['systemctl','show']:
                unit=args[2];data=f'Id={unit}\nActiveState=inactive\nSubState=dead\nUnitFileState=disabled\nMainPID=0\n'
                return types.SimpleNamespace(stdout=data.encode())
            raise AssertionError('Unexpected native action: '+str(args))
        def replace(p):
            pending=self.etc/'policy.new';pending.write_bytes(canonical(p));pending.replace(self.etc/'policy.json')
        self.owner=types.SimpleNamespace(BINARY=str(self.binary),BINARY_SHA=self.policy['codex_sha256'],run=run,
            validate_policy=lambda p:None,inspect_image=lambda x:self.images[x],replace_policy=replace,
            load_policy=lambda:__import__('json').loads((self.etc/'policy.json').read_bytes()))
        self.api=types.SimpleNamespace(request=lambda method,path:{},pages=lambda path:[])
        values={'INSTALL':self.install,'STATE':self.state,'ETC':self.etc,'OLD_POLICY_SHA':self.old_digest,
                'OLD_REVIEW_SHA':sha256(self.review_raw),'DISABLED_POLICY_SHA':sha256(canonical(dict(self.policy,enabled=False))),
                'BINDINGS':bindings,'trusted':lambda p,**kw:Path(p)}
        for name,value in values.items():self.patched(self.r,name,value)
        for name,value in [('INSTALL',self.install),('STATE',self.state),('ETC',self.etc),
                           ('trusted',lambda p,**kw:Path(p))]:self.patched(refresh,name,value)
        self.patched(refresh,'completed_refresh',lambda *args:None);self.patched(refresh,'idle_native',lambda:None)
        self.patched(refresh,'reviewed_commit',lambda *args,**kw:{'tree':{'sha':'c'*40}})
        self.patched(self.r,'validate_rules',lambda *args:None)
        self.patched(self.r,'eligible_target',lambda api:copy.deepcopy(self.r.TARGET))
        def native(stage,owner,policy,path):path.write_bytes(b'NATIVE_FIXTURE_PASS');return sha256(path.read_bytes())
        self.patched(self.r,'native_probe',native)

    def patched(self,module,name,value):
        p=patch.object(module,name,value);p.start();self.addCleanup(p.stop)

    def retained(self):
        self.assertEqual((self.etc/'policy.json').read_bytes(),self.before)
        self.assertEqual((self.install/'revision').read_text(),self.r.BASE)

    def test_install_changes_only_revision_and_preserves_history_and_backups(self):
        journal=(self.state/'journal.sqlite3').read_bytes()
        receipts={p['preparation']:(self.state/p['preparation']).read_bytes() for p in self.policy['profiles']}
        self.r.perform(self.owner,HEAD,self.api,self.source)
        self.assertEqual(self.owner.load_policy(),dict(self.policy,installed_revision=HEAD))
        self.assertEqual((self.state/'journal.sqlite3').read_bytes(),journal)
        for relative,raw in receipts.items():self.assertEqual((self.state/relative).read_bytes(),raw)
        directory=self.state/('review-transport-'+HEAD)
        self.assertEqual((directory/'policy-before.json').read_bytes(),self.before)
        backup=self.install.with_name(self.install.name+'-before-review-transport-'+HEAD)
        self.assertEqual((backup/'revision').read_text(),self.r.BASE)
        self.r.completed(self.state,self.owner.load_policy(),(self.etc/'policy.json').read_bytes())
        self.assertFalse(any(x[:2] in (['systemctl','start'],['systemctl','enable']) for x in self.events))

    def test_failed_probe_preserves_old_package_policy_and_blocks_replay(self):
        def fail(*args):raise Hold('native_failed')
        self.patched(self.r,'native_probe',fail)
        with self.assertRaisesRegex(Hold,'native_failed'):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.retained()
        with self.assertRaisesRegex(Hold,'already_claimed'):self.r.perform(self.owner,HEAD,self.api,self.source)

    def test_source_and_worker_delta_are_bounded(self):
        changed=copy.deepcopy(self.new);changed['ci/continuous/snci/worker.py']=self.new['ci/continuous/snci/repair_review.py']
        with self.assertRaisesRegex(Hold,'review_install_package_scope'):self.r.package(self.old,self.accepted,changed)
        changed=copy.deepcopy(self.new);changed['outside.py']=next(iter(self.new.values()))
        with self.assertRaisesRegex(Hold,'review_install_package_scope'):self.r.package(self.old,self.accepted,changed)

    def test_wrong_policy_or_review_hash_refuses_before_claim(self):
        for name,reason in [('OLD_POLICY_SHA','review_install_policy'),('OLD_REVIEW_SHA','review_install_review')]:
            with self.subTest(name=name),patch.object(self.r,name,'f'*64),self.assertRaisesRegex(Hold,reason):
                self.r.perform(self.owner,HEAD,self.api,self.source)
        self.retained();self.assertFalse((self.state/('review-transport-'+HEAD)).exists())

    def test_claim_requires_review_only_terminal_hold(self):
        with sqlite3.connect(self.state/'journal.sqlite3') as db:db.execute("UPDATE attempts SET state='publishing'")
        with self.assertRaisesRegex(Hold,'review_install_pending'):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.retained()

    def test_existing_quality_or_source_output_refuses(self):
        (self.attempt/'result.json').write_bytes(b'{}')
        with self.assertRaisesRegex(Hold,'review_install_review_only'):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.retained()

    def test_installed_source_drift_refuses_before_claim(self):
        (self.install/'owner.py').write_bytes(b'DRIFT')
        with self.assertRaisesRegex(Hold,'refresh_installed_changed'):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.retained()

    def test_receipt_digest_and_image_drift_refuse(self):
        profile=self.policy['profiles'][0];path=self.state/profile['preparation'];raw=path.read_bytes()
        path.write_bytes(raw+b' ')
        with self.assertRaisesRegex(Hold,'receipt_digest'):self.r.perform(self.owner,HEAD,self.api,self.source)
        path.write_bytes(raw);self.images[profile['image']]={'Id':'sha256:'+'f'*64}
        with self.assertRaisesRegex(Hold,'review_install_image'):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.retained()

    def test_recheck_catches_policy_drift_during_probe(self):
        def drift(stage,owner,policy,path):
            self.owner.replace_policy(dict(self.policy,daily_attempts=3));path.write_bytes(b'PASS');return sha256(path.read_bytes())
        self.patched(self.r,'native_probe',drift)
        with self.assertRaisesRegex(Hold,'review_install_policy'):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.assertEqual((self.install/'revision').read_text(),self.r.BASE)

    def test_policy_commit_failure_preserves_backup_without_completion(self):
        def fail(p):raise OSError('fixture policy failure')
        self.owner.replace_policy=fail
        with self.assertRaises(OSError):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.assertEqual((self.etc/'policy.json').read_bytes(),self.before)
        self.assertEqual((self.install/'revision').read_text(),HEAD)
        self.assertFalse((self.state/('review-transport-'+HEAD)/'COMPLETE.json').exists())
        with self.assertRaisesRegex(Hold,'already_claimed'):self.r.perform(self.owner,HEAD,self.api,self.source)

    def test_completion_is_bound_to_policy_and_preserved_receipts(self):
        self.r.perform(self.owner,HEAD,self.api,self.source)
        wrong=dict(self.owner.load_policy(),enabled=False)
        with self.assertRaisesRegex(Hold,'completion_revision'):self.r.completed(self.state,wrong,canonical(wrong))
        path=self.state/self.policy['profiles'][0]['preparation'];path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(Hold,'receipt_digest'):self.r.completed(self.state,self.owner.load_policy(),(self.etc/'policy.json').read_bytes())

    def test_expired_receipt_cannot_be_refreshed_by_installation(self):
        profile=self.policy['profiles'][0];path=self.state/profile['preparation']
        receipt=__import__('json').loads(path.read_bytes());receipt['time']=int(time.time())-86401
        path.write_bytes(canonical(receipt));digest=sha256(path.read_bytes())
        profile['preparation_sha256']=digest;self.r.BINDINGS[profile['name']]['preparation_sha256']=digest
        with self.assertRaisesRegex(Hold,'native_acceptance_stale'):self.r.receipts(self.state,self.policy)

    def test_failed_completion_is_removed_and_cannot_authorize_service_run(self):
        original=self.r.write_new
        def fail(path,data,*args):
            if path.name=='COMPLETE.json':path.write_bytes(b'{"partial":true}');raise OSError('fixture completion failure')
            return original(path,data,*args)
        self.patched(self.r,'write_new',fail)
        with self.assertRaises(OSError):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.assertFalse((self.state/('review-transport-'+HEAD)/'COMPLETE.json').exists())
        with self.assertRaises(OSError):self.r.completed(self.state,self.owner.load_policy(),(self.etc/'policy.json').read_bytes())

    def test_staged_byte_drift_is_rejected_before_replacement(self):
        def drift(stage,owner,policy,path):
            (stage/'owner.py').write_bytes(b'DRIFT');path.write_bytes(b'PASS');return sha256(path.read_bytes())
        self.patched(self.r,'native_probe',drift)
        with self.assertRaisesRegex(Hold,'review_install_stage_bytes'):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.retained()

    def test_active_timer_prevents_claim(self):
        original=self.owner.run
        def active(args,**kw):
            result=original(args,**kw)
            if args[2].endswith('.timer'):result.stdout=result.stdout.replace(b'ActiveState=inactive',b'ActiveState=active')
            return result
        self.owner.run=active
        with self.assertRaisesRegex(Hold,'refresh_service_active'):self.r.perform(self.owner,HEAD,self.api,self.source)
        self.retained();self.assertFalse((self.state/('review-transport-'+HEAD)).exists())


if __name__=='__main__':unittest.main()
