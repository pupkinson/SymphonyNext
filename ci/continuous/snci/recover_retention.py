"""Owner-only fresh-quality recovery, running image references, paused install."""
import argparse
import copy
import fcntl
import os
from pathlib import Path
import re
import sys
import time
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import API, RULESET, Hold, canonical, decode, require, sha256, trusted, write_new
from snci.github import GitHub
from snci.source import Source, changed_paths, select_profile, validate_rules
from snci import refresh, repair_review as prior, runner
from snci.repair_review import eligible_target, native_probe
from snci.rebuild_missing import seed_identity

SOURCE_BASE='10fc787a2b03c0dbd602f35991dd9aacd36718ab'
SOURCE_TREE='812fe91fc7fe9154229f2e4ecad475b98da5250e'
SEED='sha256:a93a7c8e7a2d292c924f461d06a27986b1a95818c1be1fbb5b68b290b409256c'
DAEMON_ID='f3c7201a-409f-4cde-871d-6e727a298cf7'
INSTALL=refresh.INSTALL;STATE=refresh.STATE;ETC=refresh.ETC
DELTA={'ci/continuous/snci/recover_retention.py','ci/continuous/tests/test_retention_recovery.py',
       'ci/continuous/README.md','docs/superpowers/plans/2026-10-03-ci-recover-retain.md'}
KEEP_CMD=['-i','PATH=/usr/bin:/bin','HOME=/nonexistent','LANG=C.UTF-8',
          '/usr/bin/python3','-I','-S','-c','import signal; signal.pause()']


def daemon_identity(owner):
    raw=owner.run(runner.DOCKER+['info','--format',
        '{"root":{{json .DockerRootDir}},"driver":{{json .Driver}},"id":{{json .ID}}}'],
        capture_output=True,timeout=30).stdout
    value=decode(raw)
    require(value=={'root':'/mnt/sdb1/production-runtime/docker-data','driver':'overlay2','id':DAEMON_ID},
            'retention_daemon')
    return value


def keeper_name(head,name):
    require(isinstance(head,str) and re.fullmatch(r'[0-9a-f]{40}',head) and name in ('main','sn004'),
            'retention_identity')
    return 'snci-retain-'+head+'-'+name


def keeper_absent(owner,head,name):
    label=keeper_name(head,name)
    raw=owner.run(runner.DOCKER+['ps','-a','--filter','name=^/'+label+'$','--format','{{.Names}}'],
                  capture_output=True,timeout=30).stdout
    require(not raw.strip(),'retention_keeper_exists')


def keeper_verify(owner,head,profile):
    name=keeper_name(head,profile['name'])
    value=decode(owner.run(runner.DOCKER+['inspect',name],capture_output=True,timeout=30).stdout)
    require(isinstance(value,list) and len(value)==1,'retention_keeper_shape')
    d=value[0];c=d.get('Config',{});h=d.get('HostConfig',{});s=d.get('State',{})
    require(d.get('Name')=='/'+name and d.get('Image')==profile['image']
            and c.get('Labels',{}).get('snci.retention')==head+'-'+profile['name']
            and c.get('User')=='10001:10001' and c.get('WorkingDir')=='/'
            and c.get('Entrypoint')==['/usr/bin/env'] and c.get('Cmd')==KEEP_CMD
            and c.get('Healthcheck',{}).get('Test')==['NONE']
            and not c.get('Volumes') and not c.get('OpenStdin') and not c.get('Tty'),'retention_keeper_identity')
    require(h.get('NetworkMode')=='none' and h.get('ReadonlyRootfs') is True and not h.get('Privileged')
            and h.get('CapDrop')==['ALL'] and not h.get('CapAdd')
            and h.get('SecurityOpt')==['no-new-privileges:true']
            and h.get('RestartPolicy',{}).get('Name')=='unless-stopped'
            and h.get('Memory')==33554432 and h.get('MemorySwap')==33554432
            and h.get('NanoCpus')==50000000 and h.get('PidsLimit')==16
            and h.get('PidMode')=='' and h.get('IpcMode')=='private'
            and h.get('UTSMode')=='' and h.get('UsernsMode')==''
            and not d.get('Mounts') and not any(h.get(k) for k in
            ('Binds','Tmpfs','PortBindings','Devices','DeviceRequests','DeviceCgroupRules','VolumesFrom','Links',
             'ExtraHosts','GroupAdd','PublishAllPorts','AutoRemove')),'retention_keeper_isolation')
    require(s.get('Running') is True and not any(s.get(k) for k in
            ('Paused','Restarting','Dead','OOMKilled','Error')),'retention_keeper_running')
    return d['Id']


def retain(owner,head,profile):
    name=profile['name'];keeper_absent(owner,head,name)
    tag='localhost/symphony-next-ci-prepared:'+head+'-'+name
    require(owner.inspect_image(tag,missing_ok=True) is None,'retention_tag_exists')
    owner.run(runner.DOCKER+['create','--pull=never','--name='+keeper_name(head,name),
        '--label=snci.retention='+head+'-'+name,'--restart=unless-stopped','--read-only','--network=none','--no-healthcheck',
        '--cap-drop=ALL','--security-opt=no-new-privileges:true','--user=10001:10001','--cpus=0.05',
        '--memory=32m','--memory-swap=32m','--pids-limit=16','--workdir=/',
        '--log-driver=json-file','--log-opt=max-size=1m','--log-opt=max-file=1',
        '--entrypoint=/usr/bin/env',profile['image']]+KEEP_CMD,capture_output=True,timeout=30)
    owner.run(runner.DOCKER+['start',keeper_name(head,name)],capture_output=True,timeout=30)
    identity=keeper_verify(owner,head,profile)
    require(owner.inspect_image(profile['image']).get('Id')==profile['image'],'retention_image')
    require(owner.inspect_image(tag,missing_ok=True) is None,'retention_tag_exists')
    owner.run(runner.DOCKER+['image','tag',profile['image'],tag],timeout=30)
    require(owner.inspect_image(tag).get('Id')==profile['image'],'retention_tag')
    return {'container':identity,'tag':tag,'image':profile['image']}


def historical_receipts(policy):
    profiles=policy.get('profiles',[])
    require(len(profiles)==2 and {p['name'] for p in profiles}==set(prior.BINDINGS),'retention_profiles')
    result={}
    for p in profiles:
        require(all(p.get(k)==v for k,v in prior.BINDINGS[p['name']].items())
                and p.get('preparation')=='refresh-'+prior.BASE+'/'+p['name']+'/acceptance.json',
                'retention_history_binding')
        refresh.read_acceptance(STATE,p,policy['codex_sha256'],time.time(),fresh=False)
        result[p['name']]=sha256(trusted(STATE/p['preparation'],private=True).read_bytes())
    return result


def profile_sources(source,policy):
    result={}
    for p in policy['profiles']:
        tree,entries=source.tree(p['head'])
        require(tree==p['tree'] and select_profile(entries,policy)['name']==p['name'],'retention_profile_source')
        result[p['name']]=entries
    return result


def preflight(owner,head,api,source,initial=False):
    refresh.stopped(owner);refresh.idle_native()
    raw=trusted(ETC/'policy.json',private=True).read_bytes();policy=decode(raw)
    require(sha256(raw)==prior.OLD_POLICY_SHA and policy.get('enabled') is True
            and policy.get('installed_revision')==prior.BASE,'retention_policy')
    owner.validate_policy(policy)
    require(trusted(INSTALL/'revision').read_text()==prior.BASE,'retention_revision')
    disabled=canonical(dict(policy,enabled=False))
    require(sha256(disabled)==prior.DISABLED_POLICY_SHA,'retention_activation')
    refresh.completed_refresh(STATE,dict(policy,enabled=False),disabled)
    require(policy['codex_binary']==owner.BINARY and policy['codex_sha256']==owner.BINARY_SHA
            and sha256(trusted(owner.BINARY).read_bytes())==owner.BINARY_SHA,'retention_native')
    commit=refresh.reviewed_commit(api,head,base=SOURCE_BASE)
    ot,old=source.tree(prior.BASE);at,accepted=source.tree(prior.SOURCE_BASE)
    pt,parent=source.tree(SOURCE_BASE);tree,new=source.tree(head)
    require(ot==prior.BASE_TREE and at==prior.SOURCE_TREE and pt==SOURCE_TREE
            and tree==commit['tree']['sha'],'retention_tree')
    prior.package(old,accepted,parent)
    require(set(changed_paths(new,parent))==DELTA and DELTA<=set(new),'retention_package_scope')
    package={p[len(refresh.PREFIX):]:e for p,e in new.items() if p.startswith(refresh.PREFIX)}
    require(all(e.get('mode')=='100644' for e in package.values()),'retention_package_mode')
    manifest=refresh.verify_package(old)
    require(eligible_target(api)==prior.TARGET,'retention_target')
    validate_rules(api.request('GET',API+'/rulesets/'+str(RULESET)),policy['ruleset'])
    hold=prior.saved_hold(STATE);receipts=historical_receipts(policy);entries=profile_sources(source,policy)
    seed=seed_identity(owner);daemon=daemon_identity(owner)
    if initial:
        for p in policy['profiles']:
            require(owner.inspect_image(p['image'],missing_ok=True) is None,'retention_image_not_missing')
            oldtag='localhost/symphony-next-ci-prepared:'+prior.BASE+'-'+p['name']
            require(owner.inspect_image(oldtag,missing_ok=True) is None,'retention_old_tag_exists')
            keeper_absent(owner,head,p['name'])
            tag='localhost/symphony-next-ci-prepared:'+head+'-'+p['name']
            require(owner.inspect_image(tag,missing_ok=True) is None,'retention_tag_exists')
    return dict(policy=policy,policy_raw=raw,package=package,new=new,old_manifest=manifest,tree=tree,
                target=prior.TARGET,hold=hold,receipts=receipts,entries=entries,seed=seed,daemon=daemon,
                recipe=trusted(INSTALL/'Dependency.Dockerfile').read_bytes())


def verify_new(owner,head,policy,seed):
    result={}
    for p in policy['profiles']:
        refresh.read_acceptance(STATE,p,policy['codex_sha256'],time.time())
        owner.verify_seed_build(seed,p['image'])
        keeper=keeper_verify(owner,head,p)
        tag='localhost/symphony-next-ci-prepared:'+head+'-'+p['name']
        require(owner.inspect_image(tag).get('Id')==p['image'],'retention_tag')
        result[p['name']]={'image':p['image'],'receipt':p['preparation_sha256'],'keeper':keeper}
    return result


def completed(state,policy,raw,owner):
    head=policy['installed_revision'];keeper_name(head,'main')
    directory=trusted(Path(state)/('refresh-'+head),private=True,directory=True)
    intent=decode(trusted(directory/'commit-intent.json',private=True).read_bytes())
    proof=decode(trusted(directory/'COMPLETE.json',private=True).read_bytes())
    require(intent=={'head':head,'policy_sha256':sha256(raw)} and proof.get('head')==head
            and proof.get('policy_sha256')==sha256(raw) and policy.get('enabled') is True
            and proof.get('status')=='RECOVERED_REVIEW_TRANSPORT_PAUSED','retention_completion_policy')
    oldraw=trusted(directory/'policy-before.json',private=True).read_bytes();old=decode(oldraw)
    require(sha256(oldraw)==prior.OLD_POLICY_SHA and proof.get('hold')==prior.saved_hold(state)
            and proof.get('history')==historical_receipts(old),'retention_completion_history')
    expected=copy.deepcopy(old);expected['installed_revision']=head
    for p in expected['profiles']:
        fresh=next(x for x in policy['profiles'] if x['name']==p['name'])
        for k in ('image','preparation','preparation_sha256'):p[k]=fresh[k]
        require(p['preparation']=='refresh-'+head+'/'+p['name']+'/acceptance.json','retention_completion_pointer')
    require(policy==expected,'retention_completion_delta')
    require(proof.get('profiles')==verify_new(owner,head,policy,proof['seed']),'retention_completion_profiles')
    manifest=decode(trusted(INSTALL/'installed.json').read_bytes())
    require(proof.get('manifest_sha256')==sha256(canonical(manifest))
            and trusted(INSTALL/'revision').read_text()==head,'retention_completion_package')
    for name,digest in manifest.items():
        require(not name.startswith('/') and '..' not in name.split('/')
                and sha256(trusted(INSTALL/name).read_bytes())==digest,'retention_completion_bytes')
    require(proof.get('native_probe_sha256')==sha256(trusted(directory/'native-codex.log',private=True).read_bytes()),
            'retention_completion_native')
    require(proof.get('daemon')==daemon_identity(owner) and proof.get('seed')==seed_identity(owner),
            'retention_completion_daemon')
    refresh.stopped(owner)


def perform(owner,head,api,source):
    keeper_name(head,'main')
    directory=STATE/('refresh-'+head);backup=INSTALL.with_name(INSTALL.name+'-before-retention-'+head)
    stage=INSTALL.with_name(INSTALL.name+'-refresh-'+head)
    prior_paths=[STATE/('review-transport-'+SOURCE_BASE),INSTALL.with_name(INSTALL.name+'-refresh-'+SOURCE_BASE),
                 INSTALL.with_name(INSTALL.name+'-before-review-transport-'+SOURCE_BASE)]
    require(not any(p.exists() or p.is_symlink() for p in [directory,backup,stage]+prior_paths),
            'retention_already_claimed')
    snapshot=preflight(owner,head,api,source,initial=True)
    directory.mkdir(mode=0o700);refresh.sync(STATE)
    write_new(directory/'policy-before.json',snapshot['policy_raw'])
    write_new(directory/'inputs.json',canonical({k:snapshot[k] for k in ('hold','receipts','tree','seed','daemon')}))
    stage=refresh.stage_package(head,snapshot,source)
    native=native_probe(stage,owner,snapshot['policy'],directory/'native-codex.log')
    future=copy.deepcopy(snapshot['policy']);future['profiles']=[]
    for old in snapshot['policy']['profiles']:
        name=old['name'];root=directory/name;root.mkdir(mode=0o700)
        source.materialize(snapshot['entries'][name],root/'source')
        write_new(root/'Dependency.Dockerfile',snapshot['recipe'])
        write_new(root/'.dockerignore',b'*\n!Dependency.Dockerfile\n!source\n!source/**\n')
        print('RECOVERY_BUILD_START '+name,flush=True)
        image=owner.build_dependency_image(root)
        require(isinstance(image,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',image),'retention_built_id')
        owner.verify_seed_build(snapshot['seed'],image)
        profile=dict(old,image=image);binding=retain(owner,head,profile)
        write_new(root/'retention.json',canonical(binding))
        print('RECOVERY_QUALITY_START '+name,flush=True)
        key=sha256(canonical({'retention':head,'profile':name,'head':profile['head'],'image':image}))
        quality=runner.validate_result(runner.run(root,key,snapshot['entries'][name],profile),profile)
        receipt={'profile':name,'head':profile['head'],'tree':profile['tree'],'image':image,
                 'codex_sha256':future['codex_sha256'],'time':int(time.time()),'quality':quality,
                 'native_probe_sha256':native,'refresh_revision':head}
        raw=canonical(receipt);write_new(root/'acceptance.json',raw)
        profile.update(preparation='refresh-'+head+'/'+name+'/acceptance.json',preparation_sha256=sha256(raw))
        future['profiles'].append(profile)
    require(preflight(owner,head,api,source)==snapshot,'retention_inputs_changed')
    prior.verify_stage(stage,snapshot['package'])
    future['installed_revision']=head;owner.validate_policy(future)
    profiles=verify_new(owner,head,future,snapshot['seed'])
    intent={'head':head,'policy_sha256':sha256(canonical(future))}
    write_new(directory/'commit-intent.json',canonical(intent))
    INSTALL.rename(backup);refresh.sync(INSTALL.parent)
    try:stage.rename(INSTALL)
    except Exception:backup.rename(INSTALL);refresh.sync(INSTALL.parent);raise
    refresh.sync(INSTALL.parent);owner.replace_policy(future)
    require(trusted(ETC/'policy.json',private=True).read_bytes()==canonical(future),'retention_policy_readback')
    refresh.verify_package(snapshot['new']);refresh.stopped(owner)
    proof=dict(intent,status='RECOVERED_REVIEW_TRANSPORT_PAUSED',hold=snapshot['hold'],history=snapshot['receipts'],
               profiles=profiles,seed=snapshot['seed'],daemon=snapshot['daemon'],native_probe_sha256=native,
               manifest_sha256=sha256(trusted(INSTALL/'installed.json').read_bytes()))
    try:
        write_new(directory/'COMPLETE.json',canonical(proof));completed(STATE,future,canonical(future),owner)
    except Exception:
        (directory/'COMPLETE.json').unlink(missing_ok=True);refresh.sync(directory);raise
    print('RECOVERED_REVIEW_TRANSPORT_PAUSED '+head,flush=True)
    return proof


def apply(head):
    require(os.geteuid()==0 and os.uname().nodename.split('.')[0]=='1c-db','retention_owner_identity')
    import owner
    checkout=trusted(Path(__file__).resolve().parents[3],directory=True)
    require(owner.run(['git','rev-parse','HEAD'],cwd=checkout,capture_output=True).stdout.decode().strip()==head
            and not owner.run(['git','status','--porcelain','--untracked-files=all'],cwd=checkout,
                              capture_output=True).stdout,'retention_clean_checkout')
    trusted(STATE,private=True,directory=True);trusted(ETC,private=True,directory=True)
    path=STATE/'controller.lock';fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a') as lock:
        trusted(path,private=True)
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Hold('retention_controller_busy') from None
        policy=owner.load_policy();api=GitHub(policy['github'],policy['github_key'])
        perform(owner,head,api,Source(api,STATE/'blobs'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reviewed-head',required=True);args=parser.parse_args()
    os.umask(0o077)
    try:apply(args.reviewed_head)
    except Hold as error:print('HOLD '+str(error));raise SystemExit(1)
    except Exception:print('HOLD retention_internal_error');raise SystemExit(1)


if __name__=='__main__':main()
