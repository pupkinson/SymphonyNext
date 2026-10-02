"""Single-use owner maintenance for the exact zero-read source-wrapper hold.

Preserve activated policy, quality receipts and immutable attempt history;
install the separately accepted reviewer while units remain paused. No start.
"""
import argparse
import copy
from contextlib import closing
import fcntl
import os
from pathlib import Path
import pwd
import re
import sqlite3
import subprocess
import sys
import time
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import API, Hold, blob_hash, canonical, decode, require, sha256, trusted, write_new
from snci.github import GitHub
from snci.source import Source, changed_paths, validate_rules, validate_target
from snci import refresh

BASE='38ead3172e536e04dbfded60adc3ca0651607f38'
BASE_TREE='c40a32acb18ca3b228aa41a3b6a69af3c4e7ba17'
SOURCE_BASE='0d0f619217a9d4a3469c3207cf87a08837997201'
SOURCE_TREE='288f9659e0d0d36a6bd5bcabb59dacf44c3d955c'
OLD_POLICY_SHA='e1ab900a45de7e13b374b6ed70a3747982d65b7820dbae8c319b4b72461e371c'
DISABLED_POLICY_SHA='622e0a668634a5c397fbaed925664dd989750482b28301573e8786056ecf3620'
OLD_REVIEW_SHA='9ab88b6a29d291c6f9b9b7b11c34bc5787a75ccfb7b6e0b712e1abe60c0af9d4'
TARGET={'pr':14,'head':'21ce4282e7ef8330cc1155bcb7b94fbf132032a8',
        'base':'2bf21950e0725bc9228b262e1495f5af5eeea1d6'}
TREE='29fe41a2873a3db13ac2c0dc74b7f149391c9eeb'
EXPECTED_REVIEW={'verdict':dict(TARGET,tree=TREE,verdict='HOLD',findings=[],limitations=[
    "Source access failed: the read_source tool wrapper returned 'code-mode host is disabled'. Neither revision nor repository requirements could be inspected; an independent source review could not be completed."]),
    'model':'gpt-6-astra','read_count':0,'source_bytes':0,'read_paths':[]}
BINDINGS={
    'main':{'image':'sha256:d9d3eec73005c59b0b2deb1ea91ac8412483d84fd1c171b2605c2bd8a0cc9d0a',
            'preparation_sha256':'549c8d8b0d5429c2e2cba0a113fa091e4080bf94f7b9c697085a55ad7c2d413e'},
    'sn004':{'image':'sha256:dde11d58700607e35e28e49f48984ec9d001136d679d53833c69da50d1ded522',
             'preparation_sha256':'f873cb22a3f86a98f02fcbff20ce15f2c22fa122a8bff61d0d606a390ba5f1c5'}}
INSTALL=refresh.INSTALL;STATE=refresh.STATE;ETC=refresh.ETC
PREFIX='ci/continuous/'
SOURCE_DELTA={PREFIX+p for p in ('snci/reviewer.py','tests/native_codex_probe.py','tests/test_review.py',
    'tests/test_native_probe.py','README.md')}|{'docs/superpowers/plans/2026-10-02-ci-direct-source-review.md'}
DELTA={PREFIX+p for p in ('snci/repair_review.py','tests/test_review_install.py','README.md')}|{
    'docs/superpowers/plans/2026-10-02-ci-review-transport-install.md'}


def package(old,accepted,new):
    require(set(changed_paths(accepted,old))==SOURCE_DELTA,'review_install_source_scope')
    require(set(changed_paths(new,accepted))==DELTA and DELTA<=set(new),'review_install_package_scope')
    result={p[len(PREFIX):]:e for p,e in new.items() if p.startswith(PREFIX)}
    require(all(e.get('mode')=='100644' for e in result.values()),'review_install_package_mode')
    return result


def journal_rows(state):
    path=trusted(Path(state)/'journal.sqlite3',private=True)
    try:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)) as db:
            rows=db.execute('SELECT key,target,policy,day,state,data FROM attempts ORDER BY key').fetchall()
    except sqlite3.Error:raise Hold('review_install_journal') from None
    require(all(r[4] in ('hold','success','stale') for r in rows),'review_install_pending')
    return rows


def saved_hold(state):
    key=sha256(canonical([TARGET,OLD_POLICY_SHA]));root=trusted(Path(state)/'attempts'/key,directory=True)
    rows=journal_rows(state);matches=[r for r in rows if r[0]==key]
    require(len(matches)==1 and decode(matches[0][1])==TARGET and matches[0][2]==OLD_POLICY_SHA
            and matches[0][4]=='hold' and decode(matches[0][5])=={'reason':'review_not_ready'},'review_install_hold')
    require({p.name for p in root.iterdir()}=={'inputs.json','review.json'},'review_install_review_only')
    raw=trusted(root/'review.json',private=True).read_bytes()
    require(sha256(raw)==OLD_REVIEW_SHA and decode(raw)==EXPECTED_REVIEW,'review_install_review')
    inputs=trusted(root/'inputs.json',private=True).read_bytes();value=decode(inputs)
    require(value.get('target')==dict(TARGET,tree=TREE) and value.get('policy_sha256')==OLD_POLICY_SHA
            and value.get('profile')=='sn004','review_install_hold_inputs')
    return {'key':key,'journal_sha256':sha256(canonical(rows)),'review_sha256':sha256(raw),
            'inputs_sha256':sha256(inputs)}


def eligible_target(api):
    targets=[]
    for pr in api.pages(API+'/pulls?state=open&sort=created&direction=asc'):
        try:targets.append(validate_target(pr))
        except Hold:continue
    require(targets==[TARGET],'review_install_target_changed')
    return targets[0]


def receipts(state,policy,owner=None):
    profiles=policy.get('profiles',[])
    require(len(profiles)==2 and {p['name'] for p in profiles}==set(BINDINGS),'review_install_profiles')
    result={}
    for p in profiles:
        name=p['name'];binding=BINDINGS[name]
        require(all(p.get(k)==v for k,v in binding.items()) and
                p.get('preparation')=='refresh-'+BASE+'/'+name+'/acceptance.json','review_install_receipt_binding')
        refresh.read_acceptance(state,p,policy['codex_sha256'],time.time())
        result[name]=sha256(trusted(Path(state)/p['preparation'],private=True).read_bytes())
        if owner:require(owner.inspect_image(p['image']).get('Id')==p['image'],'review_install_image')
    return result


def preflight(owner,head,api,source):
    refresh.stopped(owner);refresh.idle_native()
    raw=trusted(ETC/'policy.json',private=True).read_bytes();policy=decode(raw)
    require(sha256(raw)==OLD_POLICY_SHA and policy.get('enabled') is True
            and policy.get('installed_revision')==BASE,'review_install_policy')
    owner.validate_policy(policy)
    require(trusted(INSTALL/'revision').read_text()==BASE,'review_install_revision')
    disabled=canonical(dict(policy,enabled=False))
    require(sha256(disabled)==DISABLED_POLICY_SHA,'review_install_prior_activation')
    refresh.completed_refresh(STATE,dict(policy,enabled=False),disabled)
    require(policy['codex_binary']==owner.BINARY and policy['codex_sha256']==owner.BINARY_SHA
            and sha256(trusted(owner.BINARY).read_bytes())==owner.BINARY_SHA,'review_install_native')
    commit=refresh.reviewed_commit(api,head,base=SOURCE_BASE)
    old_tree,old=source.tree(BASE);accepted_tree,accepted=source.tree(SOURCE_BASE);tree,new=source.tree(head)
    require(old_tree==BASE_TREE and accepted_tree==SOURCE_TREE and tree==commit['tree']['sha'],'review_install_tree')
    candidate=package(old,accepted,new);manifest_sha=refresh.verify_package(old)
    target=eligible_target(api);hold=saved_hold(STATE);quality=receipts(STATE,policy,owner)
    validate_rules(api.request('GET',API+'/rulesets/23980199'),policy['ruleset'])
    return dict(policy=policy,policy_raw=raw,package=candidate,new=new,old_manifest=manifest_sha,
                target=target,hold=hold,receipts=quality,tree=tree)


def native_probe(stage,owner,policy,path):
    account=pwd.getpwnam('snci-review')
    require(account.pw_uid not in (0,995,997),'review_install_identity')
    with path.open('xb') as log:
        owner.run(['/usr/bin/python3','-I',str(stage/'tests/native_codex_probe.py'),policy['codex_binary']],
                  user=account.pw_uid,group=account.pw_gid,extra_groups=[],cwd=stage/'review-empty',
                  stdout=log,stderr=subprocess.STDOUT,timeout=180)
        log.flush();os.fsync(log.fileno())
    return sha256(trusted(path,private=True).read_bytes())


def verify_stage(stage,entries):
    manifest=decode(trusted(stage/'installed.json').read_bytes())
    require(set(manifest)==set(entries),'review_install_stage_scope')
    for name,entry in entries.items():
        raw=trusted(stage/name).read_bytes()
        require(blob_hash(raw)==entry['sha'] and len(raw)==entry['size'] and sha256(raw)==manifest[name],
                'review_install_stage_bytes')


def completed(state,policy,raw):
    head=policy.get('installed_revision')
    require(isinstance(head,str) and re.fullmatch(r'[0-9a-f]{40}',head) and policy.get('enabled') is True,
            'review_install_completion_revision')
    directory=trusted(Path(state)/('review-transport-'+head),private=True,directory=True)
    intent=decode(trusted(directory/'commit-intent.json',private=True).read_bytes())
    proof=decode(trusted(directory/'COMPLETE.json',private=True).read_bytes())
    expected={'head':head,'policy_sha256':sha256(raw)}
    require(intent==expected and proof.get('head')==head and proof.get('policy_sha256')==expected['policy_sha256']
            and proof.get('status')=='REVIEW_TRANSPORT_INSTALLED_PAUSED','review_install_completion')
    require(proof.get('receipts')==receipts(state,policy) and proof.get('hold')==saved_hold(state),
            'review_install_completion_history')
    require(proof.get('manifest_sha256')==sha256(trusted(INSTALL/'installed.json').read_bytes())
            and trusted(INSTALL/'revision').read_text()==head,'review_install_completion_package')
    manifest=decode(trusted(INSTALL/'installed.json').read_bytes())
    for name,digest in manifest.items():
        require(not name.startswith('/') and '..' not in name.split('/')
                and sha256(trusted(INSTALL/name).read_bytes())==digest,'review_install_completion_bytes')
    require(proof.get('native_probe_sha256')==sha256(trusted(directory/'native-codex.log',private=True).read_bytes()),
            'review_install_completion_probe')


def perform(owner,head,api,source):
    require(isinstance(head,str) and re.fullmatch(r'[0-9a-f]{40}',head),'review_install_head')
    directory=STATE/('review-transport-'+head)
    backup=INSTALL.with_name(INSTALL.name+'-before-review-transport-'+head)
    stage=INSTALL.with_name(INSTALL.name+'-refresh-'+head)
    require(not any(p.exists() or p.is_symlink() for p in (directory,backup,stage)),'review_install_already_claimed')
    snapshot=preflight(owner,head,api,source)
    directory.mkdir(mode=0o700);refresh.sync(STATE)
    write_new(directory/'policy-before.json',snapshot['policy_raw'])
    write_new(directory/'inputs.json',canonical({'head':head,'base':BASE,'source_base':SOURCE_BASE,
                                               'old_policy_sha256':OLD_POLICY_SHA,'hold':snapshot['hold'],
                                               'receipts':snapshot['receipts'],'tree':snapshot['tree']}))
    stage=refresh.stage_package(head,snapshot,source)
    probe_sha=native_probe(stage,owner,snapshot['policy'],directory/'native-codex.log')
    require(preflight(owner,head,api,source)==snapshot,'review_install_inputs_changed')
    verify_stage(stage,snapshot['package'])
    future=copy.deepcopy(snapshot['policy']);future['installed_revision']=head
    owner.validate_policy(future)
    intent={'head':head,'policy_sha256':sha256(canonical(future))}
    write_new(directory/'commit-intent.json',canonical(intent))
    INSTALL.rename(backup);refresh.sync(INSTALL.parent)
    try:stage.rename(INSTALL)
    except Exception:
        backup.rename(INSTALL);refresh.sync(INSTALL.parent);raise
    refresh.sync(INSTALL.parent)
    owner.replace_policy(future)
    require(trusted(ETC/'policy.json',private=True).read_bytes()==canonical(future),'review_install_policy_readback')
    refresh.verify_package(snapshot['new']);refresh.stopped(owner)
    proof=dict(intent,status='REVIEW_TRANSPORT_INSTALLED_PAUSED',receipts=snapshot['receipts'],hold=snapshot['hold'],
               manifest_sha256=sha256(trusted(INSTALL/'installed.json').read_bytes()),native_probe_sha256=probe_sha)
    try:
        write_new(directory/'COMPLETE.json',canonical(proof));completed(STATE,future,canonical(future))
    except Exception:
        (directory/'COMPLETE.json').unlink(missing_ok=True);refresh.sync(directory);raise
    print('REVIEW_TRANSPORT_INSTALLED_PAUSED '+head,flush=True)
    return proof


def apply(head):
    require(os.geteuid()==0 and os.uname().nodename.split('.')[0]=='1c-db','review_install_owner_identity')
    import owner
    checkout=trusted(Path(__file__).resolve().parents[3],directory=True)
    actual=owner.run(['git','rev-parse','HEAD'],cwd=checkout,capture_output=True).stdout.decode().strip()
    require(actual==head and not owner.run(['git','status','--porcelain','--untracked-files=all'],
            cwd=checkout,capture_output=True).stdout,'review_install_clean_checkout')
    trusted(STATE,private=True,directory=True);trusted(ETC,private=True,directory=True)
    path=STATE/'controller.lock';fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a') as lock:
        trusted(path,private=True)
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Hold('review_install_controller_busy') from None
        policy=owner.load_policy();api=GitHub(policy['github'],policy['github_key'])
        perform(owner,head,api,Source(api,STATE/'blobs'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reviewed-head',required=True);args=parser.parse_args()
    os.umask(0o077)
    try:apply(args.reviewed_head)
    except Hold as error:print('HOLD '+str(error));raise SystemExit(1)
    except Exception:print('HOLD review_install_internal_error');raise SystemExit(1)


if __name__=='__main__':main()
