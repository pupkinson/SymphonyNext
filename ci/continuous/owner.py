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
    with (root/'build.log').open('xb') as log:
        run(runner.DOCKER+['build','--network=default','--build-arg','BASE_IMAGE='+SEED,
            '--iidfile',str(root/'image.id'),'-f',str(root/'Dependency.Dockerfile'),str(root)],
            stdout=log,stderr=subprocess.STDOUT,timeout=1800)
    image=(root/'image.id').read_text().strip()
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
    p=load_policy();require(p['enabled'] is False,'already_enabled')
    validate_policy(p)
    manifest=decode(trusted(INSTALL/'installed.json').read_bytes())
    for name,digest in manifest.items():
        require(sha256(trusted(INSTALL/name).read_bytes())==digest,'installed_code_changed')
    require(sha256(trusted(p['codex_binary']).read_bytes())==p['codex_sha256'],'native_binary_changed')
    for profile in p['profiles']:
        evidence=decode(trusted(STATE/('prepare-'+profile['name'])/'acceptance.json',private=True).read_bytes())
        require(evidence['image']==profile['image'] and evidence['head']==profile['head']
                and evidence['codex_sha256']==p['codex_sha256']
                and 0<=time.time()-evidence['time']<86400,'native_acceptance_stale')
        runner.validate_result(evidence['quality'],profile)
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
