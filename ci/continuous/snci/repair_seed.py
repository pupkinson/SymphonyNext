"""Owner-only repair of the diagnosed, pre-RUN local-seed build failure.

Updates a stopped installation from an independently reviewed child revision.
Preserves the failed attempt and package; starts preparation once, never CI.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time
sys.dont_write_bytecode=True
sys.path.insert(0,'/opt/symphony-next-ci')
from snci.common import Hold, canonical, decode, require, sha256, trusted, write_new, blob_hash
from snci.github import GitHub
from snci.source import Source, changed_paths

BASE='8794bfd42e29580c00978015a46969c7642f56dc'
INSTALL=Path('/opt/symphony-next-ci')
STATE=Path('/var/lib/symphony-next-ci')
ETC=Path('/etc/symphony-next-ci')
PREFIX='ci/continuous/'
DELTA={PREFIX+'owner.py',PREFIX+'README.md',PREFIX+'snci/repair_seed.py',
       PREFIX+'tests/test_owner_seed.py',PREFIX+'tests/test_seed_repair.py'}

def package_delta(base,head):
    require(set(changed_paths(head,base))==DELTA,'repair_source_scope')
    require(DELTA<=set(head),'repair_source_files_missing')
    package={p[len(PREFIX):]:e for p,e in head.items() if p.startswith(PREFIX)}
    require(all(e.get('mode')=='100644' for e in package.values()),'repair_package_mode')
    return package

def failed_build(root,entries,dockerfile):
    trusted(root,directory=True)
    require({p.name for p in root.iterdir()}=={'source','Dependency.Dockerfile','.dockerignore','build.log'},
            'repair_requires_pre_run_failure')
    require(trusted(root/'Dependency.Dockerfile').read_bytes()==dockerfile,'failed_build_recipe_changed')
    require(trusted(root/'.dockerignore').read_bytes()==b'*\n!Dependency.Dockerfile\n!source\n!source/**\n',
            'failed_build_context_changed')
    log=trusted(root/'build.log',private=True).read_bytes()
    import owner
    require(b'docker.io/library/'+owner.SEED.encode() in log and b'pull access denied' in log
            and b'failed to solve' in log,'different_build_failure')
    source=trusted(root/'source',directory=True)
    actual=set()
    for p in source.rglob('*'):
        require(not p.is_symlink(),'repair_source_symlink')
        if p.is_dir():continue
        name=p.relative_to(source).as_posix()
        require(name in entries and p.is_file(),'repair_source_extra')
        e=entries[name];raw=trusted(p).read_bytes()
        require(blob_hash(raw)==e['sha'] and len(raw)==e['size']
                and p.stat().st_mode&0o777==(0o755 if e['mode']=='100755' else 0o644),'repair_source_changed')
        actual.add(name)
    require(actual==set(entries) and len(actual)==180,'repair_source_incomplete')
    return {'build_log_sha256':sha256(log),'source_count':len(actual)}

def emit_status(status):
    # Closed schema: never publish exception text, source, credentials or logs.
    allowed={'schema','installed_revision','phase','profile','pid','started','updated','prepared',
             'error_type','hold_code','exit_code'}
    require(set(status)<=allowed and status.get('schema')=='snci-prepare-status/v1','status_schema')
    required={'schema','installed_revision','phase','profile','pid','started','updated','prepared'}
    require(required<=set(status),'status_fields')
    require(isinstance(status['installed_revision'],str) and
            re.fullmatch(r'[0-9a-f]{40}',status['installed_revision']) is not None,'status_revision')
    require(status['phase'] in ('preparing','installed_disabled','all_profiles_prepared_disabled','hold')
            and status['profile'] in (None,'main','sn004'),'status_phase_profile')
    require(status['pid'] is None or (type(status['pid']) is int and status['pid']>0),'status_pid')
    require(all(type(status[k]) is int and status[k]>=0 for k in ('started','updated')),'status_time')
    require(isinstance(status['prepared'],list) and len(status['prepared'])<=2,'status_prepared')
    for field in ('error_type','hold_code'):
        if field in status:
            require(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,80}',status[field]) is not None,'status_error_text')
    for receipt in status.get('prepared',[]):
        require(set(receipt)=={'profile','head','tree','image','tests','skipped','coverage','dialyzer_errors'},
                'status_receipt_schema')
        require(receipt['profile'] in ('main','sn004') and
                all(isinstance(receipt[k],str) and re.fullmatch(r'[0-9a-f]{40}',receipt[k]) for k in ('head','tree'))
                and isinstance(receipt['image'],str) and re.fullmatch(r'sha256:[0-9a-f]{64}',receipt['image']),
                'status_receipt_identity')
        require(type(receipt['tests']) is int and receipt['tests']>={'main':305,'sn004':328}[receipt['profile']]
                and type(receipt['skipped']) is int and 0<=receipt['skipped']<=6
                and receipt['coverage']==100.0 and receipt['dialyzer_errors']==0,'status_receipt_quality')
    if status['phase']=='all_profiles_prepared_disabled':
        require([r['profile'] for r in status['prepared']]==['main','sn004'] and status.get('exit_code')==0,
                'status_incomplete_success')
    trusted(INSTALL,directory=True)
    path=INSTALL/'preparation-status.json'
    tmp=path.with_name('preparation-status.'+str(os.getpid())+'.tmp')
    write_new(tmp,canonical(status),0o644)
    os.replace(tmp,path)
    fd=os.open(INSTALL,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def preparation_driver(head,directory):
    import owner
    os.umask(0o077)
    with (Path(directory)/'prepare.log').open('xb',buffering=0) as log:
        os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
        state={'schema':'snci-prepare-status/v1','installed_revision':head,'phase':'preparing',
               'profile':None,'pid':os.getpid(),'started':int(time.time()),'prepared':[]}
        try:
            for name in ('main','sn004'):
                state.update(profile=name,updated=int(time.time()));emit_status(state)
                print('PREPARE_START '+name,flush=True)
                owner.prepare(name)
                receipt=decode(trusted(STATE/('prepare-'+name)/'acceptance.json',private=True).read_bytes())
                quality=receipt['quality']
                state['prepared'].append({k:receipt[k] for k in ('profile','head','tree','image')}
                    |{k:quality[k] for k in ('tests','skipped','coverage','dialyzer_errors')})
            require(owner.load_policy()['enabled'] is False,'unexpected_activation')
            state.update(phase='all_profiles_prepared_disabled',profile=None,updated=int(time.time()),exit_code=0)
            emit_status(state);print('ALL_PROFILES_PREPARED_DISABLED',flush=True)
        except Exception as error:
            state.update(phase='hold',updated=int(time.time()),error_type=type(error).__name__,exit_code=1)
            if isinstance(error,Hold) and re.fullmatch(r'[a-z][a-z0-9_]{0,80}',str(error)):
                state['hold_code']=str(error)
            emit_status(state)
            import traceback
            traceback.print_exc();print('PREPARATION_HOLD',flush=True)
            raise SystemExit(1)

def stopped(owner):
    for unit in ('symphony-next-ci.timer','symphony-next-ci.service'):
        require(owner.run(['/usr/bin/systemctl','show',unit,'-p','ActiveState','--value'],
                          capture_output=True,timeout=30).stdout.strip()==b'inactive','repair_service_active')
    require(owner.run(['/usr/bin/systemctl','show','symphony-next-ci.timer','-p','UnitFileState','--value'],
                      capture_output=True,timeout=30).stdout.strip()==b'disabled','repair_timer_enabled')
    for p in Path('/proc').glob('[0-9]*/cmdline'):
        try:args=p.read_bytes().split(b'\0')
        except (FileNotFoundError,ProcessLookupError):continue
        require(not (b'/opt/symphony-next-ci/owner.py' in args and b'prepare' in args)
                and not any(a.startswith(b'/var/lib/symphony-next-ci/') and a.endswith(b'/driver.py') for a in args)
                and b'/opt/symphony-next-ci/entry.py' not in args,'repair_process_active')

def apply(head):
    require(os.geteuid()==0 and os.uname().nodename.split('.')[0]=='1c-db','owner_identity')
    require(re.fullmatch(r'[0-9a-f]{40}',head) is not None and head!=BASE,'reviewed_head_required')
    os.umask(0o077)
    require(trusted(INSTALL/'revision').read_text()==BASE,'repair_base_revision')
    manifest=decode(trusted(INSTALL/'installed.json').read_bytes())
    for name,digest in manifest.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'repair_manifest_path')
        require(sha256(trusted(INSTALL/name).read_bytes())==digest,'repair_installed_code_changed')
    sys.path.insert(0,str(INSTALL))
    import owner
    policy=owner.load_policy()
    require(policy['enabled'] is False and policy['profiles']==[] and policy['installed_revision']==BASE,
            'repair_policy_state')
    stopped(owner)
    directory=STATE/('repair-local-seed-'+head[:12])
    staging=INSTALL.parent/('symphony-next-ci-after-seed-'+head[:12])
    backup=INSTALL.parent/('symphony-next-ci-before-seed-'+head[:12])
    require(not any(p.exists() for p in (directory,staging,backup,STATE/'prepare-sn004',INSTALL/'preparation-status.json')),
            'repair_already_claimed')
    # Inspect only the exact seed. No pull, image run, or old one-shot retry.
    identity=owner.run(owner.runner.DOCKER+['image','inspect','--format','{{.Id}}',owner.SEED],
                       capture_output=True,timeout=30).stdout.decode().strip()
    require(identity==owner.SEED,'repair_seed_missing_or_changed')
    api=GitHub(policy['github'],policy['github_key'])
    source=Source(api,STATE/'blobs')
    _,base=source.tree(BASE);tree,current=source.tree(head)
    package=package_delta(base,current)
    old_package={p[len(PREFIX):]:e for p,e in base.items() if p.startswith(PREFIX)}
    require(set(manifest)==set(old_package),'repair_package_manifest')
    for name,e in old_package.items():
        require(blob_hash(trusted(INSTALL/name).read_bytes())==e['sha'],'repair_base_package_hash')
    definition=decode(trusted(INSTALL/'profiles.json').read_bytes())['main']
    profile_tree,entries=source.tree(definition['head'])
    require(profile_tree==definition['tree'],'repair_profile_tree')
    evidence=failed_build(STATE/'prepare-main',entries,trusted(INSTALL/'Dependency.Dockerfile').read_bytes())
    directory.mkdir(mode=0o700);staging.mkdir(mode=0o755)
    new_manifest={}
    for name,e in package.items():
        require(e['mode']=='100644','repair_package_mode')
        if old_package.get(name)==e:raw=trusted(INSTALL/name).read_bytes()
        else:raw=source.blob(e)
        dest=staging/name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        write_new(dest,raw,0o644);new_manifest[name]=sha256(raw)
    write_new(staging/'installed.json',canonical(new_manifest),0o644)
    write_new(staging/'revision',head.encode(),0o644)
    (staging/'review-empty').mkdir(mode=0o755)
    for p in [staging]+[p for p in staging.rglob('*') if p.is_dir()]:p.chmod(0o755)
    write_new(directory/'policy-before.json',trusted(ETC/'policy.json',private=True).read_bytes())
    write_new(directory/'input.json',canonical(dict(evidence,base=BASE,head=head,tree=tree,backup=str(backup))))
    stopped(owner)
    require(owner.load_policy()==policy and trusted(INSTALL/'revision').read_text()==BASE,
            'repair_inputs_changed')
    (STATE/'prepare-main').rename(directory/'failed-build')
    INSTALL.rename(backup)
    try:staging.rename(INSTALL)
    except Exception:
        backup.rename(INSTALL);raise
    policy['installed_revision']=head;owner.replace_policy(policy)
    driver=('import sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,"/opt/symphony-next-ci")\n'
            'from snci.repair_seed import preparation_driver\n'
            'preparation_driver('+repr(head)+','+repr(str(directory))+')\n').encode()
    write_new(directory/'driver.py',driver)
    emit_status({'schema':'snci-prepare-status/v1','installed_revision':head,'phase':'installed_disabled',
                 'profile':None,'pid':None,'started':int(time.time()),'updated':int(time.time()),'prepared':[]})
    owner.run(['/usr/bin/tmux','-S',str(directory/'tmux.sock'),'-f','/dev/null','new-session','-d',
               '-s','snci-seed-repair','-c',str(INSTALL),'/usr/bin/python3','-I','-u',str(directory/'driver.py')],
              timeout=30)
    print('REPAIRED_PREPARATION_STARTED_DISABLED '+head)
    print('STATUS '+str(INSTALL/'preparation-status.json'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reviewed-head',required=True)
    apply(parser.parse_args().reviewed_head)

if __name__=='__main__':main()
