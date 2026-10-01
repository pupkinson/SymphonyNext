"""One additional owner-authorized setup cycle; preserve evidence, never activate."""
import argparse
import os
from pathlib import Path, PurePosixPath
import re
import resource
import subprocess
import sys
import tarfile
import time
sys.dont_write_bytecode=True
sys.path.insert(0,'/opt/symphony-next-ci')
from snci.common import API,Hold,blob_hash,canonical,decode,require,sha256,trusted,write_new
from snci.github import GitHub
from snci.source import Source,changed_paths
from snci.repair_seed import emit_status,stopped
from snci.repair_caps import get_review_identity,sync_directory
from snci import runner

BASE='8fd4edc25a4e3ddd5b690a4e269919cc88c73760'
WORKER_LOG_SHA='6bef832ab53da8eba2d30fb88d31d5d380646bb8be2110fe2965e816cab0a65b'
INSTALL=Path('/opt/symphony-next-ci')
STATE=Path('/var/lib/symphony-next-ci')
ETC=Path('/etc/symphony-next-ci')
PREFIX='ci/continuous/'
DELTA={PREFIX+x for x in ('worker.py','snci/runner.py','Dependency.Dockerfile','snci/repair_dialyzer.py',
                         'tests/test_worker_diagnostics.py','tests/test_dialyzer_repair.py','README.md')} | {
    'docs/superpowers/plans/2026-10-01-continuous-dialyzer-repair.md'}
TAR_LIMIT=512*1024*1024


def package_delta(base,head):
    require(set(changed_paths(head,base))==DELTA and DELTA<=set(head),'dialyzer_repair_scope')
    package={p[len(PREFIX):]:e for p,e in head.items() if p.startswith(PREFIX)}
    require(all(e.get('mode')=='100644' for e in package.values()),'dialyzer_package_mode')
    return package


def plt_files(path):
    """Inspect an inert docker-cp tar, without extracting any member to the host."""
    require(trusted(path,private=True).stat().st_size<=TAR_LIMIT,'plt_archive_size')
    files=[];seen=set()
    try:
        with tarfile.open(path,mode='r|') as tar:
            for count,member in enumerate(tar):
                require(count<100000,'plt_archive_members')
                name=member.name
                while name.startswith('./'):name=name[2:]
                if name in ('.',''):
                    require(member.isdir(),'plt_archive_path');continue
                parts=PurePosixPath(name).parts
                require(parts and not name.startswith('/') and '..' not in parts,'plt_archive_path')
                require(name not in seen,'plt_archive_duplicate');seen.add(name)
                require(0<=member.size<=TAR_LIMIT,'plt_archive_member_size')
                # Copying dev/. may retain the dev directory or use relative names.
                project=(len(parts)==1 or len(parts)==2 and parts[0]=='dev') and name.endswith('.plt')
                if not project:continue
                require(member.isreg() and member.size>0,'plt_archive_file')
                inp=tar.extractfile(member)
                require(inp is not None,'plt_archive_file')
                import hashlib
                digest=hashlib.sha256();size=0
                with inp:
                    for block in iter(lambda:inp.read(1024*1024),b''):
                        size+=len(block);require(size<=member.size,'plt_archive_file_size');digest.update(block)
                require(size==member.size and len(files)<16,'plt_archive_file_size')
                files.append(dict(path=name,size=size,sha256=digest.hexdigest()))
    except (tarfile.TarError,OSError,EOFError):raise Hold('plt_archive_invalid') from None
    return sorted(files,key=lambda x:x['path'])


def inspect_plt(image,directory,key):
    """Never start this container. Only copy an immutable image's dev cache."""
    require(re.fullmatch(r'sha256:[0-9a-f]{64}',image) and re.fullmatch(r'[0-9a-f]{64}',key),'plt_probe_identity')
    name='snci-plt-'+key;label='snci.plt='+key;directory=Path(directory)
    claim=directory/('plt-'+key+'.json');archive=directory/('plt-'+key+'.tar')
    require(not claim.exists() and not archive.exists(),'plt_probe_claimed')
    require(not runner.command(['ps','-a','--filter','name=^/'+name+'$','--format','{{.Names}}']).strip(),'plt_probe_existing')
    write_new(claim,canonical(dict(image=image,key=key,started=False)))
    try:
        runner.command(['create','--pull=never','--name='+name,'--label='+label,'--network=none',
                        '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
                        '--user=10001:10001','--restart=no','--entrypoint=/usr/bin/true',image])
        data=decode(runner.command(['inspect',name]));require(isinstance(data,list) and len(data)==1,'plt_probe_shape')
        d=data[0];config=d['Config'];h=d['HostConfig'];state=d['State']
        require(d['Name']=='/'+name and d['Image']==image and config.get('Labels',{}).get('snci.plt')==key
                and config['User']=='10001:10001' and config['Entrypoint']==['/usr/bin/true']
                and not config.get('Cmd') and not config.get('Volumes') and not d.get('Mounts')
                and h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and h['Privileged'] is False
                and h['CapDrop']==['ALL'] and not h.get('CapAdd')
                and h['SecurityOpt']==['no-new-privileges:true'] and h['RestartPolicy']['Name']=='no'
                and state['Status']=='created' and state['Running'] is False,'plt_probe_isolation')
        def limits():resource.setrlimit(resource.RLIMIT_FSIZE,(TAR_LIMIT,TAR_LIMIT))
        with os.fdopen(os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as out:
            r=subprocess.run(runner.DOCKER+['cp',name+':/seed/source/elixir/_build/dev/.','-'],
                             stdout=out,stderr=subprocess.PIPE,timeout=60,preexec_fn=limits,
                             env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
            out.flush();os.fsync(out.fileno())
        require(r.returncode==0,'plt_probe_copy')
        return plt_files(archive)
    finally:
        names=runner.command(['ps','-a','--filter','name=^/'+name+'$','--format','{{.Names}}']).decode().splitlines()
        if names:
            require(names==[name],'plt_cleanup_name')
            d=decode(runner.command(['inspect',name]))[0]
            require(d.get('Config',{}).get('Labels',{}).get('snci.plt')==key
                    and d.get('Image')==image and d.get('State',{}).get('Running') is False,'plt_cleanup_owner')
            runner.command(['rm',name])


def verify_sources(source,entries):
    source=trusted(source,directory=True);actual=set()
    for path in source.rglob('*'):
        require(not path.is_symlink(),'dialyzer_source_symlink')
        if path.is_dir():trusted(path,directory=True);continue
        name=path.relative_to(source).as_posix();require(name in entries and path.is_file(),'dialyzer_source_extra')
        e=entries[name];raw=trusted(path).read_bytes()
        require(blob_hash(raw)==e['sha'] and len(raw)==e['size']
                and path.stat().st_mode&0o777==(0o755 if e['mode']=='100755' else 0o644),'dialyzer_source_changed')
        actual.add(name)
    require(actual==set(entries) and len(actual)==180,'dialyzer_source_incomplete')


def failed_main(root,entries,dockerfile,trace):
    trusted(root,directory=True)
    require({p.name for p in root.iterdir()}=={'source','Dependency.Dockerfile','.dockerignore','build.log','image.id',
                 'seed.json','source.json','native-codex.log','reused-image.json','worker.log'},'dialyzer_failure_files')
    log=trusted(root/'worker.log',private=True).read_bytes()
    require(sha256(log)==WORKER_LOG_SHA and b'SNCI_RESULT ' not in log and log.count(b'SNCI_WORKER_FAILED')==1,
            'dialyzer_failure_log')
    stages=re.findall(rb'^SNCI_STAGE ([a-z-]+) (-?\d+)$',log,re.M)
    require(stages==[(s.encode(),b'0') for s in ('isolation','pg-init','pg-start','pg-create','deps','build','format','lint','coverage')]
            and b'snci.common.Hold: worker_failed' in trace,'dialyzer_failure_stages')
    require(trusted(root/'Dependency.Dockerfile').read_bytes()==dockerfile,'dialyzer_recipe_changed')
    require(trusted(root/'.dockerignore').read_bytes()==b'*\n!Dependency.Dockerfile\n!source\n!source/**\n','dialyzer_context_changed')
    require(decode(trusted(root/'source.json').read_bytes())==entries,'dialyzer_source_manifest')
    verify_sources(root/'source',entries)
    image=trusted(root/'image.id').read_text().strip()
    require(re.fullmatch(r'sha256:[0-9a-f]{64}',image),'dialyzer_image_id')
    seed=decode(trusted(root/'seed.json',private=True).read_bytes())
    import owner
    require(set(seed)=={'id','reference','layers'} and seed['id']==owner.SEED
            and seed['reference']=='localhost/symphony-next-ci-seed:'+owner.SEED.split(':')[1]
            and isinstance(seed['layers'],list) and seed['layers']
            and all(isinstance(x,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',x) for x in seed['layers']),'dialyzer_seed_receipt')
    build=trusted(root/'build.log',private=True).read_bytes()
    reused=decode(trusted(root/'reused-image.json',private=True).read_bytes())
    require(set(reused)=={'image','origin','build_log_sha256'} and reused['image']==image
            and reused['build_log_sha256']==sha256(build),'dialyzer_reused_image_receipt')
    return dict(image=image,seed=seed,source_count=180,worker_log_sha256=sha256(log),trace_sha256=sha256(trace),
                source_manifest_sha256=sha256(trusted(root/'source.json').read_bytes()),
                build_log_sha256=sha256(build),native_probe_sha256=sha256(trusted(root/'native-codex.log',private=True).read_bytes()),
                reused_receipt_sha256=sha256(trusted(root/'reused-image.json',private=True).read_bytes()))


def prepare_profile(name,head,directory):
    import owner
    directory=Path(directory);inputs=decode(trusted(directory/'input.json',private=True).read_bytes())
    policy=owner.load_policy()
    expected=[] if name=='main' else ['main']
    require(name in ('main','sn004') and inputs['head']==head and policy['installed_revision']==head
            and policy['enabled'] is False and [x['name'] for x in policy['profiles']]==expected,'dialyzer_prepare_policy')
    definitions=decode(trusted(INSTALL/'profiles.json').read_bytes())
    require(definitions==inputs['profiles'],'dialyzer_prepare_definitions');definition=definitions[name]
    require(policy['codex_binary']==owner.BINARY and policy['codex_sha256']==owner.BINARY_SHA
            and sha256(trusted(owner.BINARY).read_bytes())==owner.BINARY_SHA,'dialyzer_native_binary')
    api=GitHub(policy['github'],policy['github_key']);source=Source(api,STATE/'blobs')
    owner.validate_rules(api.request('GET',API+'/rulesets/23980199'),policy['ruleset'])
    tree,entries=source.tree(definition['head']);require(tree==definition['tree'],'dialyzer_profile_tree')
    if name=='main':require(entries==decode(trusted(directory/'main-entries.json',private=True).read_bytes()),'dialyzer_prepare_entries')
    root=STATE/('prepare-'+name);require(not root.exists(),'dialyzer_profile_claimed');root.mkdir(mode=0o700)
    source.materialize(entries,root/'source')
    # Source.tree/materialize enforce hashes and paths for both locked profiles.
    if name=='main':verify_sources(root/'source',entries)
    write_new(root/'Dependency.Dockerfile',trusted(INSTALL/'Dependency.Dockerfile').read_bytes())
    write_new(root/'.dockerignore',b'*\n!Dependency.Dockerfile\n!source\n!source/**\n')
    reused=name=='main' and bool(inputs['cache_before'])
    if reused:
        image=inputs['image'];owner.verify_seed_build(inputs['seed'],image)
        write_new(root/'seed.json',canonical(inputs['seed']));write_new(root/'image.id',image.encode())
        write_new(root/'build.log',trusted(directory/'failed-main/build.log',private=True).read_bytes())
        write_new(root/'reused-image.json',canonical(dict(image=image,origin=str(directory/'failed-main'),
                                                      build_log_sha256=sha256((root/'build.log').read_bytes()))))
    else:image=owner.build_dependency_image(root)
    probe_key=sha256(canonical(dict(plt='prepared',profile=name,head=head,image=image)))
    cache=inspect_plt(image,root,probe_key);require(cache,'dialyzer_prepared_cache_missing')
    if reused:require(cache==inputs['cache_before'],'dialyzer_cache_changed')
    write_new(root/'plt.json',canonical(dict(image=image,head=definition['head'],tree=tree,files=cache)))
    profile=dict(definition,image=image);policy['profiles'].append(profile);owner.validate_policy(policy)
    uid,gid=get_review_identity()
    with (root/'native-codex.log').open('xb') as log:
        owner.run(['/usr/bin/python3','-I',str(INSTALL/'tests/native_codex_probe.py'),policy['codex_binary']],
                  user=uid,group=gid,extra_groups=[],cwd=INSTALL/'review-empty',stdout=log,stderr=subprocess.STDOUT,timeout=180)
    key=sha256(canonical(dict(setup=name,head=definition['head'],image=image,repair=head)))
    quality=runner.validate_result(runner.run(root,key,entries,profile),profile)
    receipt=dict(profile=name,head=definition['head'],tree=tree,image=image,codex_sha256=policy['codex_sha256'],
                 quality=quality,time=int(time.time()),native_probe_sha256=sha256((root/'native-codex.log').read_bytes()),
                 reused_image=reused,repair_revision=head,plt_sha256=sha256((root/'plt.json').read_bytes()))
    write_new(root/'acceptance.json',canonical(receipt));owner.replace_policy(policy)
    print('PROFILE_PREPARED_DISABLED '+name,flush=True)


def preparation_driver(head,directory):
    import owner
    os.umask(0o077)
    with (Path(directory)/'prepare.log').open('xb',buffering=0) as log:
        os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
        state=dict(schema='snci-prepare-status/v1',installed_revision=head,phase='preparing',profile=None,
                   pid=os.getpid(),started=int(time.time()),prepared=[])
        try:
            for name in ('main','sn004'):
                state.update(profile=name,updated=int(time.time()));emit_status(state)
                print('PREPARE_START '+name,flush=True);prepare_profile(name,head,directory)
                receipt=decode(trusted(STATE/('prepare-'+name)/'acceptance.json',private=True).read_bytes())
                state['prepared'].append({k:receipt[k] for k in ('profile','head','tree','image')} |
                    {k:receipt['quality'][k] for k in ('tests','skipped','coverage','dialyzer_errors')})
            require(owner.load_policy()['enabled'] is False,'unexpected_activation')
            state.update(phase='all_profiles_prepared_disabled',profile=None,updated=int(time.time()),exit_code=0)
            emit_status(state);print('ALL_PROFILES_PREPARED_DISABLED',flush=True)
        except Exception as error:
            state.update(phase='hold',updated=int(time.time()),error_type=type(error).__name__,exit_code=1)
            if isinstance(error,Hold) and re.fullmatch(r'[a-z][a-z0-9_]{0,80}',str(error)):state['hold_code']=str(error)
            emit_status(state)
            import traceback
            traceback.print_exc();print('PREPARATION_HOLD',flush=True);raise SystemExit(1)


def apply(head):
    require(os.geteuid()==0 and os.uname().nodename.split('.')[0]=='1c-db','owner_identity')
    require(isinstance(head,str) and re.fullmatch(r'[0-9a-f]{40}',head) and head!=BASE,'dialyzer_reviewed_head')
    os.umask(0o077);require(trusted(INSTALL/'revision').read_text()==BASE,'dialyzer_base_revision')
    manifest=decode(trusted(INSTALL/'installed.json').read_bytes())
    for name,digest in manifest.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'dialyzer_manifest_path')
        require(sha256(trusted(INSTALL/name).read_bytes())==digest,'dialyzer_installed_changed')
    import owner
    policy=owner.load_policy()
    require(policy['enabled'] is False and policy['profiles']==[] and policy['installed_revision']==BASE,'dialyzer_policy_state')
    stopped(owner)
    status_raw=trusted(INSTALL/'preparation-status.json').read_bytes();status=decode(status_raw)
    require(status['installed_revision']==BASE and status['phase']=='hold' and status['profile']=='main'
            and status.get('hold_code')=='worker_failed' and status['prepared']==[] and type(status['pid']) is int
            and not Path('/proc',str(status['pid'])).exists(),'dialyzer_failure_status')
    directory=STATE/('repair-dialyzer-'+head[:12]);staging=INSTALL.parent/('symphony-next-ci-after-dialyzer-'+head[:12])
    backup=INSTALL.parent/('symphony-next-ci-before-dialyzer-'+head[:12])
    require(not any(p.exists() or p.is_symlink() for p in (directory,staging,backup,STATE/'prepare-sn004')),'dialyzer_already_claimed')
    api=GitHub(policy['github'],policy['github_key']);source=Source(api,STATE/'blobs');revision=head
    for _ in range(2):
        commit=api.request('GET',API+'/git/commits/'+revision);parents=commit.get('parents',[])
        require(commit.get('sha')==revision and len(parents)==1,'dialyzer_commit_history');revision=parents[0]['sha']
        if revision==BASE:break
    require(revision==BASE,'dialyzer_commit_history')
    _,base=source.tree(BASE);tree,current=source.tree(head);package=package_delta(base,current)
    old={p[len(PREFIX):]:e for p,e in base.items() if p.startswith(PREFIX)}
    require(set(manifest)==set(old),'dialyzer_manifest_scope')
    for name,entry in old.items():require(blob_hash(trusted(INSTALL/name).read_bytes())==entry['sha'],'dialyzer_base_blob')
    definitions=decode(trusted(INSTALL/'profiles.json').read_bytes());definition=definitions['main']
    profile_tree,entries=source.tree(definition['head']);require(profile_tree==definition['tree'],'dialyzer_profile_tree')
    trace_path=STATE/('repair-cap-names-'+BASE[:12])/'prepare.log'
    evidence=failed_main(STATE/'prepare-main',entries,trusted(INSTALL/'Dependency.Dockerfile').read_bytes(),
                         trusted(trace_path,private=True).read_bytes())
    owner.verify_seed_build(evidence['seed'],evidence['image'])
    previous=sha256(canonical(dict(setup='main',head=definition['head'],image=evidence['image'],repair=BASE)))
    require(not runner.command(['ps','-a','--filter','name=^/snci-'+previous+'$','--format','{{.Names}}']).strip(),
            'dialyzer_previous_container_present')
    directory.mkdir(mode=0o700);sync_directory(STATE)
    write_new(directory/'policy-before.json',trusted(ETC/'policy.json',private=True).read_bytes())
    write_new(directory/'status-before.json',status_raw);write_new(directory/'main-entries.json',canonical(entries))
    cache=inspect_plt(evidence['image'],directory,sha256(canonical(dict(plt='before',head=head,image=evidence['image']))))
    write_new(directory/'input.json',canonical(dict(evidence,head=head,tree=tree,base=BASE,profiles=definitions,
                                                  cache_before=cache,native_setup_repair=3)))
    staging.mkdir(mode=0o755);sync_directory(INSTALL.parent);new_manifest={}
    for name,entry in package.items():
        raw=trusted(INSTALL/name).read_bytes() if old.get(name)==entry else source.blob(entry)
        dest=staging/name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        write_new(dest,raw,0o644);new_manifest[name]=sha256(raw)
    write_new(staging/'installed.json',canonical(new_manifest),0o644);write_new(staging/'revision',head.encode(),0o644)
    (staging/'review-empty').mkdir(mode=0o755)
    for path in [staging]+[p for p in staging.rglob('*') if p.is_dir()]:path.chmod(0o755)
    stopped(owner)
    require(owner.load_policy()==policy and trusted(INSTALL/'revision').read_text()==BASE
            and trusted(INSTALL/'preparation-status.json').read_bytes()==status_raw,'dialyzer_inputs_changed')
    require(failed_main(STATE/'prepare-main',entries,trusted(INSTALL/'Dependency.Dockerfile').read_bytes(),
                       trusted(trace_path,private=True).read_bytes())==evidence,'dialyzer_evidence_changed')
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
               '-s','snci-dialyzer-repair','-c',str(INSTALL),'/usr/bin/python3','-I','-u',str(directory/'driver.py')],timeout=30)
    print('DIALYZER_REPAIR_PREPARATION_STARTED_DISABLED '+head)
    print('STATUS '+str(INSTALL/'preparation-status.json'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reviewed-head',required=True)
    apply(parser.parse_args().reviewed_head)


if __name__=='__main__':main()
