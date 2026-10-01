"""Second bounded native setup repair; reuse main's verified image, never activate."""
import argparse
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time
sys.dont_write_bytecode = True
sys.path.insert(0, "/opt/symphony-next-ci")
from snci.common import API, Hold, blob_hash, canonical, decode, require, sha256, trusted, write_new
from snci.github import GitHub
from snci.source import Source, changed_paths
from snci.repair_seed import emit_status, stopped
from snci import runner

BASE = "151fc2eb53189bca42b0775e26a231fb837e7899"
INSTALL = Path("/opt/symphony-next-ci")
STATE = Path("/var/lib/symphony-next-ci")
ETC = Path("/etc/symphony-next-ci")
PREFIX = "ci/continuous/"
DELTA = {PREFIX+"snci/runner.py", PREFIX+"snci/repair_caps.py", PREFIX+"README.md",
         PREFIX+"tests/test_runner_isolation.py", PREFIX+"tests/test_caps_repair.py"}


def package_delta(base, head):
    require(set(changed_paths(head, base)) == DELTA and DELTA <= set(head), "caps_repair_scope")
    package = {p[len(PREFIX):]: e for p, e in head.items() if p.startswith(PREFIX)}
    require(all(e.get("mode") == "100644" for e in package.values()), "caps_repair_package_mode")
    return package


def diagnostic_evidence(image):
    directory = STATE / ("diagnose-isolation-" + BASE[:12])
    claim = decode(trusted(directory/"claim.json", private=True).read_bytes())
    raw = trusted(directory/"result.json", private=True).read_bytes(); report = decode(raw)
    key = sha256(canonical({"diagnostic":"isolation-v1", "head":BASE, "image":image}))
    require(claim == {"head":BASE, "image":image, "key":key}, "caps_diagnostic_identity")
    require(set(report) == {"head","cleanup","seed_build_verified","worker_started","mismatches","fields"}
            and report["head"] == BASE and type(report["cleanup"]) is int and report["cleanup"] == 0
            and report["seed_build_verified"] is True and report["worker_started"] is False
            and report["mismatches"] == ["CapAdd"], "caps_diagnostic_outcome")
    expected = {"NetworkMode":"none", "ReadonlyRootfs":True, "Privileged":False, "RestartPolicy":"no",
                "Memory":4294967296, "MemorySwap":4294967296, "NanoCpus":2000000000, "PidsLimit":256,
                "CapDrop":["ALL"], "CapAdd":["CAP_CHOWN","CAP_KILL","CAP_SETGID","CAP_SETUID"],
                "SecurityOpt":["no-new-privileges:true"],
                "Tmpfs":{"/work":"rw,exec,nosuid,nodev,size=3g,uid=0,gid=0,mode=755",
                         "/tmp":"rw,exec,nosuid,nodev,size=256m,uid=0,gid=0,mode=1777"}}
    require(report["fields"] == expected and
            all(type(report["fields"][k]) is type(v) for k,v in expected.items()), "caps_diagnostic_fields")
    return {"sha256":sha256(raw), "image":image}


def verify_sources(source, entries):
    source = trusted(source, directory=True); actual = set()
    for path in source.rglob("*"):
        require(not path.is_symlink(), "caps_source_symlink")
        if path.is_dir():
            trusted(path, directory=True); continue
        name = path.relative_to(source).as_posix()
        require(name in entries and path.is_file(), "caps_source_extra")
        entry = entries[name]; raw = trusted(path).read_bytes()
        require(blob_hash(raw) == entry["sha"] and len(raw) == entry["size"]
                and path.stat().st_mode & 0o777 == (0o755 if entry["mode"] == "100755" else 0o644),
                "caps_source_changed")
        actual.add(name)
    require(actual == set(entries) and len(actual) == 180, "caps_source_incomplete")


def failed_main(root, entries, dockerfile, trace):
    trusted(root, directory=True)
    names = {"source","Dependency.Dockerfile",".dockerignore","build.log","image.id","seed.json",
             "source.json","native-codex.log"}
    require({p.name for p in root.iterdir()} == names, "caps_requires_unstarted_worker")
    require(b"command(args);inspect_container(key,image,root)" in trace
            and b"snci.common.Hold: container_isolation" in trace, "caps_requires_initial_inspect")
    require(trusted(root/"Dependency.Dockerfile").read_bytes() == dockerfile, "caps_recipe_changed")
    require(trusted(root/".dockerignore").read_bytes() == b"*\n!Dependency.Dockerfile\n!source\n!source/**\n",
            "caps_context_changed")
    require(decode(trusted(root/"source.json").read_bytes()) == entries, "caps_source_manifest")
    verify_sources(root/"source", entries)
    image = trusted(root/"image.id").read_text().strip()
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", image) is not None, "caps_image_id")
    seed = decode(trusted(root/"seed.json", private=True).read_bytes())
    import owner
    require(set(seed) == {"id","reference","layers"} and seed["id"] == owner.SEED
            and seed["reference"] == "localhost/symphony-next-ci-seed:" + owner.SEED.split(":")[1]
            and isinstance(seed["layers"], list) and seed["layers"]
            and all(isinstance(x,str) and re.fullmatch(r"sha256:[0-9a-f]{64}", x) for x in seed["layers"]),
            "caps_seed_receipt")
    return {"image":image,"seed":seed,"source_count":180,"trace_sha256":sha256(trace),
            "source_manifest_sha256":sha256(trusted(root/"source.json").read_bytes()),
            "build_log_sha256":sha256(trusted(root/"build.log", private=True).read_bytes()),
            "native_probe_sha256":sha256(trusted(root/"native-codex.log", private=True).read_bytes())}


def get_review_identity():
    user = pwd.getpwnam("snci-review")
    return user.pw_uid, user.pw_gid


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def resume_main(head, directory):
    import owner
    inputs = decode(trusted(Path(directory)/"input.json", private=True).read_bytes())
    require(inputs["head"] == head, "caps_resume_head")
    policy = owner.load_policy()
    require(policy["installed_revision"] == head and policy["enabled"] is False and policy["profiles"] == [],
            "caps_resume_policy")
    definition = decode(trusted(INSTALL/"profiles.json").read_bytes())["main"]
    require(definition == inputs["profile"], "caps_resume_definition")
    entries = decode(trusted(Path(directory)/"main-entries.json", private=True).read_bytes())
    require(len(entries) == 180, "caps_resume_entries")
    image = inputs["image"]; seed = inputs["seed"]
    owner.verify_seed_build(seed, image)
    require(policy["codex_binary"] == owner.BINARY and policy["codex_sha256"] == owner.BINARY_SHA
            and sha256(trusted(owner.BINARY).read_bytes()) == policy["codex_sha256"], "caps_native_binary")
    api = GitHub(policy["github"], policy["github_key"])
    owner.validate_rules(api.request("GET", API+"/rulesets/23980199"), policy["ruleset"])
    root = STATE/"prepare-main"; root.mkdir(mode=0o700)
    Source(api, STATE/"blobs").materialize(entries, root/"source")
    verify_sources(root/"source", entries)
    write_new(root/"Dependency.Dockerfile", trusted(INSTALL/"Dependency.Dockerfile").read_bytes())
    write_new(root/".dockerignore", b"*\n!Dependency.Dockerfile\n!source\n!source/**\n")
    write_new(root/"seed.json", canonical(seed)); write_new(root/"image.id", image.encode())
    write_new(root/"build.log", trusted(Path(directory)/"failed-main/build.log", private=True).read_bytes())
    write_new(root/"reused-image.json", canonical({"image":image,"origin":str(Path(directory)/"failed-main"),
                                                  "build_log_sha256":sha256((root/"build.log").read_bytes())}))
    profile = dict(definition, image=image)
    policy["profiles"] = [profile]; owner.validate_policy(policy)
    uid,gid = get_review_identity()
    with (root/"native-codex.log").open("xb") as log:
        owner.run(["/usr/bin/python3","-I",str(INSTALL/"tests/native_codex_probe.py"),policy["codex_binary"]],
                  user=uid,group=gid,extra_groups=[],cwd=INSTALL/"review-empty",
                  stdout=log,stderr=subprocess.STDOUT,timeout=180)
    key = sha256(canonical({"setup":"main","head":definition["head"],"image":image,"repair":head}))
    quality = runner.validate_result(runner.run(root,key,entries,profile), profile)
    receipt = {"profile":"main","head":definition["head"],"tree":definition["tree"],"image":image,
               "codex_sha256":policy["codex_sha256"],"quality":quality,"time":int(time.time()),
               "native_probe_sha256":sha256((root/"native-codex.log").read_bytes()),
               "reused_image":True,"repair_revision":head}
    write_new(root/"acceptance.json", canonical(receipt)); owner.replace_policy(policy)
    print("PROFILE_PREPARED_DISABLED main", flush=True)


def preparation_driver(head, directory):
    import owner
    os.umask(0o077)
    with (Path(directory)/"prepare.log").open("xb", buffering=0) as log:
        os.dup2(log.fileno(),1); os.dup2(log.fileno(),2)
        state = {"schema":"snci-prepare-status/v1","installed_revision":head,"phase":"preparing",
                 "profile":None,"pid":os.getpid(),"started":int(time.time()),"prepared":[]}
        try:
            for name in ("main","sn004"):
                state.update(profile=name,updated=int(time.time())); emit_status(state)
                print("PREPARE_START "+name, flush=True)
                if name == "main": resume_main(head, directory)
                else: owner.prepare(name)
                receipt = decode(trusted(STATE/("prepare-"+name)/"acceptance.json", private=True).read_bytes())
                state["prepared"].append({k:receipt[k] for k in ("profile","head","tree","image")} |
                     {k:receipt["quality"][k] for k in ("tests","skipped","coverage","dialyzer_errors")})
            require(owner.load_policy()["enabled"] is False, "unexpected_activation")
            state.update(phase="all_profiles_prepared_disabled",profile=None,updated=int(time.time()),exit_code=0)
            emit_status(state); print("ALL_PROFILES_PREPARED_DISABLED", flush=True)
        except Exception as error:
            state.update(phase="hold",updated=int(time.time()),error_type=type(error).__name__,exit_code=1)
            if isinstance(error,Hold) and re.fullmatch(r"[a-z][a-z0-9_]{0,80}", str(error)):
                state["hold_code"] = str(error)
            emit_status(state)
            import traceback
            traceback.print_exc(); print("PREPARATION_HOLD", flush=True)
            raise SystemExit(1)


def apply(head):
    require(os.geteuid() == 0 and os.uname().nodename.split(".")[0] == "1c-db", "owner_identity")
    require(isinstance(head,str) and re.fullmatch(r"[0-9a-f]{40}",head) and head != BASE, "caps_reviewed_head")
    os.umask(0o077)
    require(trusted(INSTALL/"revision").read_text() == BASE, "caps_base_revision")
    manifest = decode(trusted(INSTALL/"installed.json").read_bytes())
    for name,digest in manifest.items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "caps_manifest_path")
        require(sha256(trusted(INSTALL/name).read_bytes()) == digest, "caps_installed_changed")
    import owner
    policy = owner.load_policy()
    require(policy["enabled"] is False and policy["profiles"] == [] and policy["installed_revision"] == BASE,
            "caps_policy_state")
    stopped(owner)
    status_raw = trusted(INSTALL/"preparation-status.json").read_bytes(); status = decode(status_raw)
    require(status["installed_revision"] == BASE and status["phase"] == "hold" and status["profile"] == "main"
            and status.get("hold_code") == "container_isolation" and status["prepared"] == []
            and type(status["pid"]) is int and not Path("/proc",str(status["pid"])).exists(), "caps_failure_status")
    directory = STATE/("repair-cap-names-"+head[:12])
    staging = INSTALL.parent/("symphony-next-ci-after-caps-"+head[:12])
    backup = INSTALL.parent/("symphony-next-ci-before-caps-"+head[:12])
    require(not any(p.exists() for p in (directory,staging,backup,STATE/"prepare-sn004")), "caps_already_claimed")
    api = GitHub(policy["github"], policy["github_key"]); source = Source(api, STATE/"blobs")
    revision = head
    for _ in range(2):
        commit = api.request("GET",API+"/git/commits/"+revision)
        parents = commit.get("parents",[])
        require(commit.get("sha") == revision and len(parents) == 1, "caps_commit_history")
        revision = parents[0]["sha"]
        if revision == BASE: break
    require(revision == BASE, "caps_commit_history")
    _,base = source.tree(BASE); tree,current = source.tree(head); package = package_delta(base,current)
    old = {p[len(PREFIX):]:e for p,e in base.items() if p.startswith(PREFIX)}
    require(set(manifest) == set(old), "caps_manifest_scope")
    for name,entry in old.items():
        require(blob_hash(trusted(INSTALL/name).read_bytes()) == entry["sha"], "caps_base_blob")
    definition = decode(trusted(INSTALL/"profiles.json").read_bytes())["main"]
    profile_tree,entries = source.tree(definition["head"])
    require(profile_tree == definition["tree"], "caps_profile_tree")
    trace_path = STATE/("repair-local-seed-"+BASE[:12])/"prepare.log"
    trace = trusted(trace_path, private=True).read_bytes()
    evidence = failed_main(STATE/"prepare-main",entries,trusted(INSTALL/"Dependency.Dockerfile").read_bytes(),trace)
    diagnosis = diagnostic_evidence(evidence["image"]); owner.verify_seed_build(evidence["seed"],evidence["image"])
    previous_key = sha256(canonical({"setup":"main","head":definition["head"],"image":evidence["image"]}))
    require(not runner.command(["ps","-a","--filter","name=^/snci-"+previous_key+"$","--format","{{.Names}}"]).strip(),
            "caps_previous_container_present")
    directory.mkdir(mode=0o700); sync_directory(STATE)
    staging.mkdir(mode=0o755); sync_directory(INSTALL.parent); new_manifest = {}
    for name,entry in package.items():
        raw = trusted(INSTALL/name).read_bytes() if old.get(name) == entry else source.blob(entry)
        dest = staging/name; dest.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        write_new(dest,raw,0o644); new_manifest[name] = sha256(raw)
    write_new(staging/"installed.json",canonical(new_manifest),0o644); write_new(staging/"revision",head.encode(),0o644)
    (staging/"review-empty").mkdir(mode=0o755)
    for p in [staging]+[p for p in staging.rglob("*") if p.is_dir()]: p.chmod(0o755)
    write_new(directory/"policy-before.json",trusted(ETC/"policy.json",private=True).read_bytes())
    write_new(directory/"status-before.json",status_raw)
    write_new(directory/"main-entries.json",canonical(entries))
    write_new(directory/"input.json",canonical(dict(evidence,head=head,tree=tree,base=BASE,profile=definition,
                                                   diagnostic=diagnosis,native_setup_repair=2)))
    stopped(owner)
    require(owner.load_policy() == policy and trusted(INSTALL/"revision").read_text() == BASE
            and trusted(INSTALL/"preparation-status.json").read_bytes() == status_raw, "caps_inputs_changed")
    require(failed_main(STATE/"prepare-main",entries,trusted(INSTALL/"Dependency.Dockerfile").read_bytes(),
                       trusted(trace_path,private=True).read_bytes()) == evidence
            and diagnostic_evidence(evidence["image"]) == diagnosis, "caps_evidence_changed")
    (STATE/"prepare-main").rename(directory/"failed-main"); sync_directory(STATE); sync_directory(directory)
    INSTALL.rename(backup); sync_directory(INSTALL.parent)
    try: staging.rename(INSTALL); sync_directory(INSTALL.parent)
    except Exception: backup.rename(INSTALL); sync_directory(INSTALL.parent); raise
    policy["installed_revision"] = head; owner.replace_policy(policy)
    driver = ('import sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,"/opt/symphony-next-ci")\n'
              'from snci.repair_caps import preparation_driver\n'
              'preparation_driver('+repr(head)+','+repr(str(directory))+')\n').encode()
    write_new(directory/"driver.py",driver)
    emit_status({"schema":"snci-prepare-status/v1","installed_revision":head,"phase":"installed_disabled",
                 "profile":None,"pid":None,"started":int(time.time()),"updated":int(time.time()),"prepared":[]})
    owner.run(["/usr/bin/tmux","-S",str(directory/"tmux.sock"),"-f","/dev/null","new-session","-d",
               "-s","snci-cap-repair","-c",str(INSTALL),"/usr/bin/python3","-I","-u",str(directory/"driver.py")],timeout=30)
    print("CAPABILITY_REPAIR_PREPARATION_STARTED_DISABLED "+head)
    print("STATUS "+str(INSTALL/"preparation-status.json"))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--reviewed-head", required=True)
    apply(parser.parse_args().reviewed_head)


if __name__ == "__main__": main()
