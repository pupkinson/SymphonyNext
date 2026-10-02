#!/usr/bin/python3
"""Owner-operated setup. Never invoked by a candidate PR or polling controller.

Installation and preparation leave the timer disabled. Activation is a separate
explicit owner action after inspecting acceptance evidence. No merge/deploy API.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from snci.common import canonical, decode, require, sha256, trusted, write_new
from snci.controller import validate_policy
from snci.github import GitHub
from snci.source import Source, validate_rules
from snci import runner

INSTALL=Path('/opt/symphony-next-ci')
STATE=Path('/var/lib/symphony-next-ci')
ETC=Path('/etc/symphony-next-ci')
HOME=Path('/var/lib/symphony-next-ci-review')
BINARY='/usr/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex'
BINARY_SHA='0753dfe1d8b87a52436deb13eb1c549661ef4c84fee2c5aa688385eebeccb761'
SEED='sha256:a93a7c8e7a2d292c924f461d06a27986b1a95818c1be1fbb5b68b290b409256c'
UNIT='symphony-next-ci'

def run(args,**kwargs):
    return subprocess.run(args,check=True,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8'},**kwargs)

def inspect_image(reference,missing_ok=False):
    try:
        result=run(runner.DOCKER+['image','inspect','--format','{{json .}}',reference],
                   capture_output=True,timeout=30)
    except subprocess.CalledProcessError as error:
        message=(error.stderr or b'').decode(errors='replace').strip()
        missing=message in ('Error response from daemon: No such image: '+reference,
                            'Error: No such object: '+reference)
        if missing_ok and error.returncode==1 and not (error.stdout or b'').strip() and missing:
            return None
        require(False,'local_image_inspect_failed')
    info=decode(result.stdout)
    require(isinstance(info,dict),'local_image_inspect_shape')
    return info

def image_layers(info):
    rootfs=info.get('RootFS',{})
    layers=rootfs.get('Layers')
    require(rootfs.get('Type')=='layers' and isinstance(layers,list) and layers
            and all(isinstance(x,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',x) for x in layers),
            'local_image_layers')
    return layers

def prepare_seed():
    # The docker driver uses this daemon's local store; other drivers must hold.
    builder=run(runner.DOCKER+['buildx','inspect','default','--timeout','20s'],
                capture_output=True,timeout=30).stdout.decode()
    require([line.partition(':')[2].strip() for line in builder.splitlines()
             if line.startswith('Driver:')]==['docker'],'local_seed_requires_docker_driver')
    info=inspect_image(SEED)
    require(info is not None and info.get('Id')==SEED,'local_seed_identity')
    layers=image_layers(info)
    reference='localhost/symphony-next-ci-seed:'+SEED.split(':')[1]
    existing=inspect_image(reference,missing_ok=True)
    require(existing is None or existing.get('Id')==SEED,'local_seed_tag_conflict')
    if existing is None:
        run(runner.DOCKER+['image','tag',SEED,reference],timeout=30)
    require(inspect_image(reference).get('Id')==SEED,'local_seed_tag_identity')
    return {'reference':reference,'id':SEED,'layers':layers}

def verify_seed_build(seed,image):
    require(inspect_image(seed['reference']).get('Id')==SEED,'local_seed_tag_changed')
    built=inspect_image(image)
    require(built.get('Id')==image,'built_image_identity')
    layers=image_layers(built)
    require(layers[:len(seed['layers'])]==seed['layers'],'built_image_seed_layers')

def build_dependency_image(root):
    seed=prepare_seed()
    write_new(root/'seed.json',canonical(seed))
    with (root/'build.log').open('xb') as log:
        run(runner.DOCKER+['build','--builder=default','--pull=false','--progress=plain',
            '--network=default','--build-arg','BASE_IMAGE='+seed['reference'],
            '--iidfile',str(root/'image.id'),'-f',str(root/'Dependency.Dockerfile'),str(root)],
            stdout=log,stderr=subprocess.STDOUT,timeout=1800)
    image=(root/'image.id').read_text().strip()
    require(re.fullmatch(r'sha256:[0-9a-f]{64}',image) is not None,'built_image_id')
    verify_seed_build(seed,image)
    return image

def load_policy():return decode(trusted(ETC/'policy.json',private=True).read_bytes())

def replace_policy(p):
    tmp=ETC/('policy.'+str(os.getpid())+'.tmp')
    write_new(tmp,canonical(p));os.replace(tmp,ETC/'policy.json')
    fd=os.open(ETC,os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def install(head):
    source=Path(__file__).resolve().parent
    repo=source.parents[1]
    actual=run(['git','rev-parse','HEAD'],cwd=repo,capture_output=True).stdout.decode().strip()
    require(actual==head and len(head)==40,'reviewed_revision_required')
    require(not run(['git','status','--porcelain','--untracked-files=all'],cwd=repo,capture_output=True).stdout,'dirty_checkout')
    require(not any(p.exists() for p in (INSTALL,STATE,ETC,HOME)), 'existing_installation_no_overwrite')
    try:pwd.getpwnam('snci-review')
    except KeyError:pass
    else:raise RuntimeError('existing_account_no_reuse')
    require(sha256(trusted(BINARY).read_bytes())==BINARY_SHA,'native_binary_revision')
    old=Path('/var/lib/symphony-next-verifier/private')
    config=decode(trusted(old/'config.json',private=True).read_bytes())
    trusted(old/'app.pem',private=True)
    # Validate inputs before creating any persistent service state.
    require(config.get('app_id')==5069157 and type(config.get('installation_id')) is int,'app_config')
    for p in (INSTALL,STATE,ETC):p.mkdir(mode=0o755 if p==INSTALL else 0o700)
    (STATE/'attempts').mkdir(mode=0o700)
    manifest={}
    for p in sorted(source.rglob('*')):
        if p.is_dir() or '__pycache__' in p.parts:continue
        require(not p.is_symlink() and p.is_file(),'package_regular_files')
        name=p.relative_to(source);dest=INSTALL/name
        dest.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        write_new(dest,p.read_bytes(),0o644);manifest[str(name)]=sha256(p.read_bytes())
    write_new(INSTALL/'installed.json',canonical(manifest),0o644)
    write_new(INSTALL/'revision',head.encode(),0o644)
    (INSTALL/'review-empty').mkdir(mode=0o755)
    for d in [INSTALL]+[d for d in INSTALL.rglob('*') if d.is_dir()]:d.chmod(0o755)
    run(['/usr/sbin/useradd','--system','--user-group','--home-dir',str(HOME),'--shell','/usr/sbin/nologin','snci-review'])
    user=pwd.getpwnam('snci-review');HOME.mkdir(mode=0o700);os.chown(HOME,user.pw_uid,user.pw_gid)
    write_new(HOME/'config.toml',b'cli_auth_credentials_store = "file"\n',0o644)
    p={'schema':'snci-policy/v1','repository':'pupkinson/SymphonyNext','enabled':False,
       'daily_attempts':4,'review_seconds':900,'review_model':None,
       'codex_binary':BINARY,'codex_sha256':BINARY_SHA,'github':{
           'app_id':config['app_id'],'installation_id':config['installation_id']},
       'github_key':str(old/'app.pem'),'ruleset':decode((INSTALL/'ruleset.json').read_bytes()),
       'profiles':[],'exceptions':[],'installed_revision':head}
    write_new(ETC/'policy.json',canonical(p))
    for suffix in ('service','timer'):
        dest=Path('/etc/systemd/system')/(UNIT+'.'+suffix)
        require(not dest.exists(),'existing_unit_no_overwrite')
        write_new(dest,(INSTALL/dest.name).read_bytes(),0o644)
    run(['systemctl','daemon-reload'])
    print('INSTALLED_DISABLED. Login with the dedicated account, then prepare a reviewed profile.')

def prepare(name):
    p=load_policy();require(p['enabled'] is False,'disable_before_prepare')
    definition=decode(trusted(INSTALL/'profiles.json').read_bytes())[name]
    api=GitHub(p['github'],p['github_key'])
    validate_rules(api.request('GET','/repos/pupkinson/SymphonyNext/rulesets/23980199'),p['ruleset'])
    root=STATE/('prepare-'+name);root.mkdir(mode=0o700)
    source=Source(api,STATE/'blobs');tree,entries=source.tree(definition['head'])
    require(tree==definition['tree'],'profile_tree')
    source.materialize(entries,root/'source')
    write_new(root/'Dependency.Dockerfile',trusted(INSTALL/'Dependency.Dockerfile').read_bytes())
    write_new(root/'.dockerignore',b'*\n!Dependency.Dockerfile\n!source\n!source/**\n')
    # Build log may include dependency diagnostics, and remains root-private.
    image=build_dependency_image(root)
    profile=dict(definition,image=image)
    p['profiles']=[x for x in p['profiles'] if x['name']!=name]+[profile]
    validate_policy(p)
    # Native offline Codex probe, executed as dedicated reviewer with fake auth-free provider.
    u=pwd.getpwnam('snci-review')
    with (root/'native-codex.log').open('xb') as log:
        run(['/usr/bin/python3','-I',str(INSTALL/'tests/native_codex_probe.py'),p['codex_binary']],
            user=u.pw_uid,group=u.pw_gid,extra_groups=[],cwd=INSTALL/'review-empty',
            stdout=log,stderr=subprocess.STDOUT,timeout=180)
    key=sha256(canonical({'setup':name,'head':definition['head'],'image':image}))
    quality=runner.run(root,key,entries,profile)
    receipt={'profile':name,'head':definition['head'],'tree':tree,'image':image,
             'codex_sha256':p['codex_sha256'],'quality':quality,'time':int(time.time()),
             'native_probe_sha256':sha256((root/'native-codex.log').read_bytes())}
    write_new(root/'acceptance.json',canonical(receipt))
    replace_policy(p)
    print('PROFILE_PREPARED_DISABLED '+name)

def activate():
    policy_raw=trusted(ETC/'policy.json',private=True).read_bytes()
    p=decode(policy_raw);require(p['enabled'] is False,'already_enabled')
    validate_policy(p)
    require(trusted(INSTALL/'revision').read_text()==p['installed_revision'],'installed_revision_mismatch')
    from snci.refresh import completed_refresh, read_acceptance
    completed_refresh(STATE,p,policy_raw)
    manifest=decode(trusted(INSTALL/'installed.json').read_bytes())
    for name,digest in manifest.items():
        require(sha256(trusted(INSTALL/name).read_bytes())==digest,'installed_code_changed')
    require(sha256(trusted(p['codex_binary']).read_bytes())==p['codex_sha256'],'native_binary_changed')
    for profile in p['profiles']:
        read_acceptance(STATE,profile,p['codex_sha256'],time.time())
    api=GitHub(p['github'],p['github_key'])
    validate_rules(api.request('GET','/repos/pupkinson/SymphonyNext/rulesets/23980199'),p['ruleset'])
    u=pwd.getpwnam('snci-review')
    subprocess.run([p['codex_binary'],'login','status'],user=u.pw_uid,group=u.pw_gid,extra_groups=[],
        env={'PATH':'/usr/bin:/bin','HOME':str(HOME),'CODEX_HOME':str(HOME)},
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=30)
    p['enabled']=True;replace_policy(p)
    run(['systemctl','enable','--now',UNIT+'.timer'])
    print('ENABLED. First successful exact-HEAD run is still required before claiming a trusted check.')

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('install');p.add_argument('--reviewed-head',required=True)
    p=sub.add_parser('prepare');p.add_argument('profile',choices=['main','sn004'])
    sub.add_parser('activate')
    args=parser.parse_args();require(os.geteuid()==0,'owner_identity')
    if args.command=='install':install(args.reviewed_head)
    elif args.command=='prepare':prepare(args.profile)
    else:activate()

if __name__=='__main__':main()
