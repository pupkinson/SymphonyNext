"""One owner-approved cache-transfer cycle; keep every attempt and stay disabled."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
sys.dont_write_bytecode=True
sys.path.insert(0,'/opt/symphony-next-ci')
from snci.common import API,blob_hash,canonical,decode,require,sha256,trusted,write_new
from snci.github import GitHub
from snci.source import Source,changed_paths
from snci.repair_seed import emit_status,stopped
from snci.repair_caps import sync_directory
from snci.repair_dialyzer import plt_files,verify_sources
from snci import runner

BASE='4662fbb392f531c59cb3ac07b4753ad353423a9f'
INSTALL=Path('/opt/symphony-next-ci')
STATE=Path('/var/lib/symphony-next-ci')
ETC=Path('/etc/symphony-next-ci')
PREFIX='ci/continuous/'
DELTA={PREFIX+x for x in ('worker.py','snci/runner.py','snci/repair_cache.py','tests/test_worker_cache.py',
                         'tests/test_worker_diagnostics.py','tests/test_cache_repair.py','README.md')} | {
    'docs/superpowers/plans/2026-10-01-continuous-cache-transfer-repair.md'}


def package_delta(base,head):
    require(set(changed_paths(head,base))==DELTA and DELTA<=set(head),'cache_repair_scope')
    package={p[len(PREFIX):]:e for p,e in head.items() if p.startswith(PREFIX)}
    require(all(e.get('mode')=='100644' for e in package.values()),'cache_package_mode')
    return package


def verify_install(manifest,old=None):
    require(isinstance(manifest,dict) and manifest,'cache_manifest')
    if old is not None:require(set(manifest)==set(old),'cache_manifest_scope')
    for name,digest in manifest.items():
        require(isinstance(name,str) and name and not Path(name).is_absolute() and '..' not in Path(name).parts
                and isinstance(digest,str) and re.fullmatch(r'[0-9a-f]{64}',digest),'cache_manifest_path')
        raw=trusted(INSTALL/name).read_bytes()
        require(sha256(raw)==digest,'cache_installed_changed')
        if old is not None:require(blob_hash(raw)==old[name]['sha'],'cache_base_blob')


def failed_main(root,entries,recipe,definition):
    """Match the closed setup failure and retain private hashes of every artifact."""
    import owner
    root=trusted(root,directory=True)
    image=trusted(root/'image.id').read_text().strip()
    require(re.fullmatch(r'sha256:[0-9a-f]{64}',image),'cache_image_id')
    key=sha256(canonical(dict(plt='prepared',profile='main',head=BASE,image=image)))
    claim='plt-'+key+'.json';archive='plt-'+key+'.tar'
    expected={'source','Dependency.Dockerfile','.dockerignore','build.log','image.id','seed.json',
              'source.json','native-codex.log','worker.log','plt.json',claim,archive}
    require({p.name for p in root.iterdir()}==expected,'cache_failure_files')
    failure=dict(stage='setup',kind='worker_error',exit_code=None,timeout_seconds=0,duration_seconds=0,
                 log_bytes=0,log_truncated=False,cleanup_exit_code=None)
    log=b'SNCI_FAILURE '+json.dumps(failure,sort_keys=True).encode()+b'\nSNCI_WORKER_FAILED\n'
    require(trusted(root/'worker.log',private=True).read_bytes()==log,'cache_failure_log')
    require(trusted(root/'Dependency.Dockerfile').read_bytes()==recipe,'cache_recipe_changed')
    require(trusted(root/'.dockerignore').read_bytes()==b'*\n!Dependency.Dockerfile\n!source\n!source/**\n','cache_context_changed')
    require(decode(trusted(root/'source.json').read_bytes())==entries,'cache_source_manifest')
    verify_sources(root/'source',entries)
    seed=decode(trusted(root/'seed.json',private=True).read_bytes())
    require(set(seed)=={'id','reference','layers'} and seed['id']==owner.SEED
            and seed['reference']=='localhost/symphony-next-ci-seed:'+owner.SEED.split(':')[1]
            and isinstance(seed['layers'],list) and seed['layers']
            and all(isinstance(x,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',x) for x in seed['layers']),'cache_seed_receipt')
    require(decode(trusted(root/claim,private=True).read_bytes())==dict(image=image,key=key,started=False),'cache_probe_claim')
    cache=plt_files(root/archive);require(cache,'cache_prepared_plt_missing')
    receipt=decode(trusted(root/'plt.json',private=True).read_bytes())
    require(receipt==dict(image=image,head=definition['head'],tree=definition['tree'],files=cache),'cache_plt_receipt')
    hashes={name:sha256(trusted(root/name,private=name not in {'Dependency.Dockerfile','.dockerignore','source.json'}).read_bytes())
            for name in sorted(expected-{'source'})}
    return dict(image=image,seed=seed,cache_before=cache,artifact_sha256=hashes,source_count=180)


def apply(head):
    require(os.geteuid()==0 and os.uname().nodename.split('.')[0]=='1c-db','owner_identity')
    require(isinstance(head,str) and re.fullmatch(r'[0-9a-f]{40}',head) and head!=BASE,'cache_reviewed_head')
    os.umask(0o077)
    require(trusted(INSTALL/'revision').read_text()==BASE,'cache_base_revision')
    manifest_raw=trusted(INSTALL/'installed.json').read_bytes();manifest=decode(manifest_raw);verify_install(manifest)
    import owner
    policy=owner.load_policy();policy_raw=trusted(ETC/'policy.json',private=True).read_bytes()
    require(policy['enabled'] is False and policy['profiles']==[] and policy['installed_revision']==BASE,'cache_policy_state')
    stopped(owner)
    status_raw=trusted(INSTALL/'preparation-status.json').read_bytes();status=decode(status_raw)
    require(status['installed_revision']==BASE and status['phase']=='hold' and status['profile']=='main'
            and status.get('hold_code')=='worker_worker_error_setup' and status['prepared']==[]
            and status.get('exit_code')==1 and status.get('error_type')=='Hold'
            and type(status['pid']) is int and status['pid']>0 and not Path('/proc',str(status['pid'])).exists(),
            'cache_failure_status')
    directory=STATE/('repair-cache-'+head[:12]);staging=INSTALL.parent/('symphony-next-ci-after-cache-'+head[:12])
    backup=INSTALL.parent/('symphony-next-ci-before-cache-'+head[:12])
    require(not any(p.exists() or p.is_symlink() for p in (directory,staging,backup,STATE/'prepare-sn004')),'cache_already_claimed')
    api=GitHub(policy['github'],policy['github_key']);source=Source(api,STATE/'blobs');revision=head
    for _ in range(2):
        commit=api.request('GET',API+'/git/commits/'+revision);parents=commit.get('parents',[])
        require(commit.get('sha')==revision and len(parents)==1,'cache_commit_history');revision=parents[0]['sha']
        if revision==BASE:break
    require(revision==BASE,'cache_commit_history')
    _,base=source.tree(BASE);tree,current=source.tree(head);package=package_delta(base,current)
    old={p[len(PREFIX):]:e for p,e in base.items() if p.startswith(PREFIX)};verify_install(manifest,old)
    definitions=decode(trusted(INSTALL/'profiles.json').read_bytes());definition=definitions['main']
    profile_tree,entries=source.tree(definition['head']);require(profile_tree==definition['tree'],'cache_profile_tree')
    recipe=trusted(INSTALL/'Dependency.Dockerfile').read_bytes()
    evidence=failed_main(STATE/'prepare-main',entries,recipe,definition)
    owner.verify_seed_build(evidence['seed'],evidence['image'])
    previous=sha256(canonical(dict(setup='main',head=definition['head'],image=evidence['image'],repair=BASE)))
    require(not runner.command(['ps','-a','--filter','name=^/snci-'+previous+'$','--format','{{.Names}}']).strip(),
            'cache_previous_container_present')
    directory.mkdir(mode=0o700);sync_directory(STATE)
    write_new(directory/'policy-before.json',policy_raw);write_new(directory/'status-before.json',status_raw)
    write_new(directory/'main-entries.json',canonical(entries))
    write_new(directory/'input.json',canonical(dict(evidence,head=head,tree=tree,base=BASE,profiles=definitions)))
    staging.mkdir(mode=0o755);sync_directory(INSTALL.parent);new_manifest={}
    for name,entry in package.items():
        raw=trusted(INSTALL/name).read_bytes() if old.get(name)==entry else source.blob(entry)
        require(blob_hash(raw)==entry['sha'] and len(raw)==entry['size'],'cache_incoming_blob')
        dest=staging/name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        write_new(dest,raw,0o644);new_manifest[name]=sha256(raw)
    write_new(staging/'installed.json',canonical(new_manifest),0o644);write_new(staging/'revision',head.encode(),0o644)
    (staging/'review-empty').mkdir(mode=0o755)
    for path in [staging]+[p for p in staging.rglob('*') if p.is_dir()]:path.chmod(0o755)
    stopped(owner);verify_install(manifest,old)
    require(owner.load_policy()==policy and trusted(ETC/'policy.json',private=True).read_bytes()==policy_raw
            and trusted(INSTALL/'revision').read_text()==BASE and trusted(INSTALL/'installed.json').read_bytes()==manifest_raw
            and trusted(INSTALL/'preparation-status.json').read_bytes()==status_raw,'cache_inputs_changed')
    require(failed_main(STATE/'prepare-main',entries,recipe,definition)==evidence,'cache_evidence_changed')
    owner.verify_seed_build(evidence['seed'],evidence['image'])
    (STATE/'prepare-main').rename(directory/'failed-main');sync_directory(STATE);sync_directory(directory)
    INSTALL.rename(backup);sync_directory(INSTALL.parent)
    try:staging.rename(INSTALL);sync_directory(INSTALL.parent)
    except Exception:backup.rename(INSTALL);sync_directory(INSTALL.parent);raise
    policy['installed_revision']=head;owner.replace_policy(policy)
    driver=('import sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,"/opt/symphony-next-ci")\n'
            'from snci.repair_dialyzer import preparation_driver\n'
            'preparation_driver('+repr(head)+','+repr(str(directory))+')\n').encode()
    write_new(directory/'driver.py',driver)
    emit_status(dict(schema='snci-prepare-status/v1',installed_revision=head,phase='installed_disabled',profile=None,
                     pid=None,started=int(time.time()),updated=int(time.time()),prepared=[]))
    owner.run(['/usr/bin/tmux','-S',str(directory/'tmux.sock'),'-f','/dev/null','new-session','-d',
               '-s','snci-cache-repair','-c',str(INSTALL),'/usr/bin/python3','-I','-u',str(directory/'driver.py')],timeout=30)
    print('CACHE_REPAIR_PREPARATION_STARTED_DISABLED '+head)
    print('STATUS '+str(INSTALL/'preparation-status.json'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reviewed-head',required=True)
    apply(parser.parse_args().reviewed_head)


if __name__=='__main__':main()
