"""Owner resume preserves the diagnosed attempt and reuses only its pinned image."""
import copy
from contextlib import redirect_stdout, redirect_stderr
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, canonical, sha256
from snci import runner
import owner

BASE = "151fc2eb53189bca42b0775e26a231fb837e7899"
HEAD = "a" * 40
IMAGE = "sha256:" + "b" * 64
FIELDS = {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
          "RestartPolicy": "no", "Memory": 4294967296, "MemorySwap": 4294967296,
          "NanoCpus": 2000000000, "PidsLimit": 256, "CapDrop": ["ALL"],
          "CapAdd": ["CAP_CHOWN", "CAP_KILL", "CAP_SETGID", "CAP_SETUID"],
          "SecurityOpt": ["no-new-privileges:true"],
          "Tmpfs": {"/work": "rw,exec,nosuid,nodev,size=3g,uid=0,gid=0,mode=755",
                    "/tmp": "rw,exec,nosuid,nodev,size=256m,uid=0,gid=0,mode=1777"}}


class CapabilityRepairTests(unittest.TestCase):
    def setUp(self):
        try:
            self.repair = importlib.import_module("snci.repair_caps")
        except ImportError:
            self.fail("Owner resumption for the diagnosed capability failure is not implemented")
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name); self.install = self.path / "install"; self.install.mkdir()
        self.state = self.path / "state"; self.state.mkdir(); self.etc = self.path / "etc"; self.etc.mkdir()
        self.root = self.state / "prepare-main"; self.root.mkdir(); (self.root / "source").mkdir()
        self.entries = {}; self.raw_source = {}
        for i in range(180):
            name = f"f{i:03}"; raw = b"fixture source"
            (self.root / "source" / name).write_bytes(raw); (self.root / "source" / name).chmod(0o644)
            self.entries[name] = {"sha": blob_hash(raw), "size": len(raw), "mode": "100644"}
            self.raw_source[self.entries[name]["sha"]] = raw
        self.seed = {"id": owner.SEED, "reference": "localhost/symphony-next-ci-seed:" + owner.SEED.split(":")[1],
                     "layers": ["sha256:" + "c" * 64]}
        self.recipe = b"ARG BASE_IMAGE\nFROM "+self.seed["reference"].encode()+b"\n"
        self.trace = b"command(args);inspect_container(key,image,root)\nsnci.common.Hold: container_isolation\n"
        contents = {"Dependency.Dockerfile": self.recipe, ".dockerignore": b"*\n!Dependency.Dockerfile\n!source\n!source/**\n",
                    "image.id": (IMAGE+"\n").encode(), "seed.json": canonical(self.seed),
                    "source.json": canonical(self.entries), "build.log": b"successful image build\n",
                    "native-codex.log": b"previous probe passed\n"}
        for name, raw in contents.items(): (self.root/name).write_bytes(raw)
        self.diagnosis = self.state / ("diagnose-isolation-" + BASE[:12]); self.diagnosis.mkdir()
        key = sha256(canonical({"diagnostic":"isolation-v1","head":BASE,"image":IMAGE}))
        self.claim = {"head":BASE,"image":IMAGE,"key":key}
        self.report = {"head":BASE,"cleanup":0,"seed_build_verified":True,"worker_started":False,
                       "mismatches":["CapAdd"],"fields":copy.deepcopy(FIELDS)}
        self.write_diagnosis()
        for name, value in (("INSTALL",self.install),("STATE",self.state),("ETC",self.etc)):
            p = patch.object(self.repair,name,value); p.start(); self.addCleanup(p.stop)
        p = patch.object(self.repair,"trusted",lambda path,**kw:Path(path)); p.start(); self.addCleanup(p.stop)

    def write_diagnosis(self):
        (self.diagnosis/"claim.json").write_bytes(canonical(self.claim))
        (self.diagnosis/"result.json").write_bytes(canonical(self.report))

    def test_diagnostic_proves_only_capability_spelling_difference(self):
        self.assertEqual(self.repair.diagnostic_evidence(IMAGE)["sha256"],sha256(canonical(self.report)))

    def test_diagnostic_refuses_worker_start_other_mismatch_or_failed_cleanup(self):
        for name,value in (("worker_started",True),("cleanup",1),("mismatches",["Memory"])):
            old=copy.deepcopy(self.report);self.report[name]=value;self.write_diagnosis()
            with self.subTest(name=name),self.assertRaises(Hold):self.repair.diagnostic_evidence(IMAGE)
            self.report=old
        self.write_diagnosis()

    def test_diagnostic_refuses_extra_right_or_other_isolation_change(self):
        for name,value in (("CapAdd",FIELDS["CapAdd"]+["CAP_SYS_ADMIN"]),("ReadonlyRootfs",False),
                           ("SecurityOpt",[]),("Memory",0)):
            self.report["fields"]=copy.deepcopy(FIELDS);self.report["fields"][name]=value;self.write_diagnosis()
            with self.subTest(name=name),self.assertRaises(Hold):self.repair.diagnostic_evidence(IMAGE)

    def test_diagnostic_refuses_wrong_image_or_revision(self):
        for name,value in (("image","sha256:"+"d"*64),("head","e"*40)):
            old=dict(self.claim);self.claim[name]=value;self.write_diagnosis()
            with self.subTest(name=name),self.assertRaises(Hold):self.repair.diagnostic_evidence(IMAGE)
            self.claim=old

    def test_failed_main_requires_full_unchanged_source_and_initial_inspect_failure(self):
        result=self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)
        self.assertEqual(result["image"],IMAGE);self.assertEqual(result["source_count"],180)
        self.assertEqual(result["build_log_sha256"],sha256(b"successful image build\n"))

    def test_started_or_accepted_worker_evidence_cannot_be_resumed(self):
        for name in ("worker.log","acceptance.json"):
            p=self.root/name;p.write_bytes(b"evidence")
            with self.subTest(name=name),self.assertRaises(Hold):
                self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)
            p.unlink()
        with self.assertRaises(Hold):
            self.repair.failed_main(self.root,self.entries,self.recipe,b"final=inspect_container(key,image,root)\ncontainer_isolation")

    def test_failed_main_refuses_changed_missing_or_symlink_source(self):
        p=self.root/"source/f000";p.write_bytes(b"changed")
        with self.assertRaises(Hold):self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)
        p.unlink()
        with self.assertRaises(Hold):self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)
        p.symlink_to("f001")
        with self.assertRaises(Hold):self.repair.failed_main(self.root,self.entries,self.recipe,self.trace)

    def test_package_delta_refuses_application_changes_deletion_or_modes(self):
        base={p:{"sha":"c"*40,"mode":"100644"} for p in self.repair.DELTA}
        head={p:{"sha":"d"*40,"mode":"100644"} for p in self.repair.DELTA}
        self.repair.package_delta(base,head)
        with self.assertRaises(Hold):self.repair.package_delta(base,dict(head,**{"elixir/mix.exs":{"sha":"e"*40}}))
        with self.assertRaises(Hold):self.repair.package_delta(base,{k:v for k,v in head.items() if not k.endswith("README.md")})
        changed=copy.deepcopy(head);changed[next(iter(changed))]["mode"]="100755"
        with self.assertRaises(Hold):self.repair.package_delta(base,changed)

    def owner_fixture(self):
        definition={"name":"main","head":"e"*40,"tree":"f"*40,"minimum_tests":305,"maximum_skips":6,"locked":{}}
        binary=self.path/"codex";binary.write_bytes(b"fixture binary")
        policy={"enabled":False,"profiles":[],"installed_revision":BASE,"github":{},"github_key":"fixture-key-path",
                "codex_binary":str(binary),"codex_sha256":sha256(binary.read_bytes()),"ruleset":{},"unchanged_setting":123}
        (self.etc/"policy.json").write_bytes(canonical(policy))
        raw_files={"README.md":b"old README","snci/runner.py":b"old runner","Dependency.Dockerfile":self.recipe,
                   "profiles.json":canonical({"main":definition})}
        manifest={}
        for name,raw in raw_files.items():
            p=self.install/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);manifest[name]=sha256(raw)
        (self.install/"installed.json").write_bytes(canonical(manifest));(self.install/"revision").write_text(BASE)
        status={"schema":"snci-prepare-status/v1","installed_revision":BASE,"phase":"hold","profile":"main",
                "pid":2147483647,"started":1,"updated":2,"prepared":[],"hold_code":"container_isolation","error_type":"Hold","exit_code":1}
        (self.install/"preparation-status.json").write_bytes(canonical(status))
        trace=self.state/("repair-local-seed-"+BASE[:12]);trace.mkdir();(trace/"prepare.log").write_bytes(self.trace)
        base={self.repair.PREFIX+n:{"sha":blob_hash(raw),"size":len(raw),"mode":"100644"} for n,raw in raw_files.items()}
        head=dict(base);blobs={}
        for name in self.repair.DELTA:
            raw=(name+" reviewed child\n").encode();entry={"sha":blob_hash(raw),"size":len(raw),"mode":"100644"}
            head[name]=entry;blobs[entry["sha"]]=raw
        entries=self.entries;source_raw=self.raw_source
        class Source:
            def tree(self,revision):
                if revision==BASE:return "1"*40,base
                if revision==HEAD:return "2"*40,head
                return definition["tree"],entries
            def blob(self,entry):return blobs[entry["sha"]]
            def materialize(self,values,directory):
                directory=Path(directory);directory.mkdir()
                for name,e in values.items():
                    p=directory/name;p.write_bytes(source_raw[e["sha"]]);p.chmod(0o644)
        calls=[]
        def run(args,**kwargs):
            calls.append(args)
            if args[0]=="/usr/bin/systemctl":
                return types.SimpleNamespace(stdout=b"disabled\n" if "UnitFileState" in args else b"inactive\n")
            if args[0]=="/usr/bin/tmux":return types.SimpleNamespace(stdout=b"")
            if args[:2]==["/usr/bin/python3","-I"]:
                kwargs["stdout"].write(b"fresh offline probe passed\n");return types.SimpleNamespace(stdout=b"")
            raise AssertionError(args)
        def replace_policy(value):(self.etc/"policy.json").write_bytes(canonical(value))
        fake=types.SimpleNamespace(SEED=owner.SEED,BINARY=str(binary),BINARY_SHA=policy["codex_sha256"],
                runner=runner,load_policy=lambda:json.loads((self.etc/"policy.json").read_text()),run=run,
                replace_policy=replace_policy,verify_seed_build=lambda seed,image:None,
                validate_policy=lambda value:None,validate_rules=lambda *args:None)
        api=types.SimpleNamespace(request=lambda method,path:{"sha":HEAD,"parents":[{"sha":BASE}]})
        return fake,Source(),api,calls,policy,definition

    def test_apply_preserves_failed_attempt_policy_and_journal_and_starts_once(self):
        fake,source,api,calls,policy,definition=self.owner_fixture()
        attempts=self.state/"attempts";attempts.mkdir();journal=attempts/"journal";journal.write_bytes(b"immutable history")
        with patch.dict("sys.modules",{"owner":fake}),patch.object(self.repair,"GitHub",return_value=api),patch.object(self.repair,"Source",return_value=source),patch.object(self.repair,"stopped"),patch.object(self.repair.os,"geteuid",return_value=0),patch.object(self.repair.os,"uname",return_value=types.SimpleNamespace(nodename="1c-db")),patch.object(self.repair,"emit_status"),patch.object(runner,"command",return_value=b""),redirect_stdout(io.StringIO()):
            self.repair.apply(HEAD)
            self.assertEqual((self.install/"revision").read_text(),HEAD)
            self.assertEqual(json.loads((self.etc/"policy.json").read_bytes()),dict(policy,installed_revision=HEAD))
            archive=self.state/("repair-cap-names-"+HEAD[:12])/"failed-main"
            self.assertEqual((archive/"image.id").read_text().strip(),IMAGE)
            self.assertEqual((archive/"build.log").read_bytes(),b"successful image build\n")
            self.assertEqual(journal.read_bytes(),b"immutable history")
            self.assertEqual(len([x for x in calls if x[0]=="/usr/bin/tmux"]),1)
            with self.assertRaises(Hold):self.repair.apply(HEAD)
            self.assertEqual(len([x for x in calls if x[0]=="/usr/bin/tmux"]),1)
            self.assertFalse(self.root.exists())

    def prepare_resume(self,fake,definition):
        directory=self.state/("repair-cap-names-"+HEAD[:12]);directory.mkdir()
        self.root.rename(directory/"failed-main")
        (directory/"main-entries.json").write_bytes(canonical(self.entries))
        (directory/"input.json").write_bytes(canonical({"head":HEAD,"image":IMAGE,"seed":self.seed,"profile":definition}))
        policy=fake.load_policy();policy["installed_revision"]=HEAD;fake.replace_policy(policy)
        return directory

    def test_resume_reuses_image_without_build_and_writes_fresh_acceptance(self):
        fake,source,api,calls,policy,definition=self.owner_fixture();directory=self.prepare_resume(fake,definition)
        quality={"stages":dict.fromkeys(("build","format","lint","coverage","dialyzer"),0),"source_before":True,
                 "source_after":True,"cleanup":0,"tests":305,"failures":0,"skipped":6,"coverage":100.0,"dialyzer_errors":0}
        def run_quality(root,key,entries,profile):
            self.assertEqual(profile["image"],IMAGE);self.assertEqual(len(entries),180)
            self.assertEqual((Path(root)/"source/f000").read_bytes(),b"fixture source")
            return quality
        with patch.dict("sys.modules",{"owner":fake}),patch.object(self.repair,"GitHub",return_value=api),patch.object(self.repair,"Source",return_value=source),patch.object(self.repair,"get_review_identity",return_value=(10001,10001)),patch.object(runner,"run",side_effect=run_quality):
            self.repair.resume_main(HEAD,directory)
        receipt=json.loads((self.root/"acceptance.json").read_bytes())
        self.assertEqual(receipt["image"],IMAGE);self.assertEqual(receipt["quality"],quality)
        self.assertFalse(fake.load_policy()["enabled"]);self.assertEqual(len(fake.load_policy()["profiles"]),1)
        self.assertEqual((directory/"failed-main/build.log").read_bytes(),b"successful image build\n")
        self.assertEqual((self.root/"native-codex.log").read_bytes(),b"fresh offline probe passed\n")
        self.assertFalse(any("build" in args for args in calls))
        with patch.dict("sys.modules",{"owner":fake}),self.assertRaises(Hold):self.repair.resume_main(HEAD,directory)

    def test_resume_cannot_accept_bad_quality(self):
        fake,source,api,calls,policy,definition=self.owner_fixture();directory=self.prepare_resume(fake,definition)
        bad={"stages":{},"tests":0}
        with patch.dict("sys.modules",{"owner":fake}),patch.object(self.repair,"GitHub",return_value=api),patch.object(self.repair,"Source",return_value=source),patch.object(self.repair,"get_review_identity",return_value=(10001,10001)),patch.object(runner,"run",return_value=bad),self.assertRaises(Hold):
            self.repair.resume_main(HEAD,directory)
        self.assertFalse((self.root/"acceptance.json").exists());self.assertEqual(fake.load_policy()["profiles"],[])

    def test_resume_refuses_definition_drift_before_creating_worktree(self):
        fake,source,api,calls,policy,definition=self.owner_fixture();directory=self.prepare_resume(fake,definition)
        changed=dict(definition,minimum_tests=1)
        (self.install/"profiles.json").write_bytes(canonical({"main":changed}))
        with patch.dict("sys.modules",{"owner":fake}),self.assertRaises(Hold):
            self.repair.resume_main(HEAD,directory)
        self.assertFalse(self.root.exists());self.assertEqual(fake.load_policy()["profiles"],[])

    def test_apply_rechecks_source_after_staging_before_archiving(self):
        fake,source,api,calls,policy,definition=self.owner_fixture()
        blob=source.blob
        def changed(entry):
            (self.root/"source/f000").write_bytes(b"concurrent change")
            return blob(entry)
        source.blob=changed
        with patch.dict("sys.modules",{"owner":fake}),patch.object(self.repair,"GitHub",return_value=api),patch.object(self.repair,"Source",return_value=source),patch.object(self.repair,"stopped"),patch.object(self.repair.os,"geteuid",return_value=0),patch.object(self.repair.os,"uname",return_value=types.SimpleNamespace(nodename="1c-db")),patch.object(self.repair,"emit_status"),patch.object(runner,"command",return_value=b""),self.assertRaises(Hold):
            self.repair.apply(HEAD)
        self.assertTrue(self.root.exists());self.assertEqual((self.install/"revision").read_text(),BASE)
        self.assertFalse(any(x[0]=="/usr/bin/tmux" for x in calls))

    def test_driver_failure_stops_before_sn004_and_does_not_export_exception_text(self):
        fake=types.SimpleNamespace(prepare=lambda name:self.fail("sn004 started after main failed"))
        status=[];directory=self.path/"driver";directory.mkdir()
        with patch.dict("sys.modules",{"owner":fake}),patch.object(self.repair.os,"dup2"),patch.object(self.repair,"resume_main",side_effect=RuntimeError("PRIVATE_FIXTURE_SECRET")),patch.object(self.repair,"emit_status",side_effect=lambda value:status.append(copy.deepcopy(value))),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.repair.preparation_driver(HEAD,directory)
        self.assertEqual(status[-1]["phase"],"hold");self.assertEqual(status[-1]["profile"],"main")
        self.assertEqual(status[-1]["prepared"],[]);self.assertNotIn("PRIVATE_FIXTURE_SECRET",json.dumps(status))

    def test_apply_refuses_active_service_before_archiving(self):
        fake,source,api,calls,policy,definition=self.owner_fixture()
        with patch.dict("sys.modules",{"owner":fake}),patch.object(self.repair,"stopped",side_effect=Hold("repair_service_active")),patch.object(self.repair.os,"geteuid",return_value=0),patch.object(self.repair.os,"uname",return_value=types.SimpleNamespace(nodename="1c-db")),self.assertRaises(Hold):
            self.repair.apply(HEAD)
        self.assertTrue(self.root.exists());self.assertEqual((self.install/"revision").read_text(),BASE)
        self.assertFalse(any(x[0]=="/usr/bin/tmux" for x in calls))


if __name__ == "__main__": unittest.main()
