"""Single-use owner source-contract repair; preserve retained quality and pause."""
import argparse
import copy
import datetime
import fcntl
import os
from pathlib import Path
import re
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import API, RULESET, Hold, canonical, decode, require, sha256, trusted, write_new
from snci.github import GitHub
from snci.source import OMITTED_BLOBS, Source, changed_paths, select_profile, validate_rules
from snci import refresh, repair_review as prior, recover_retention as recovery
from snci.repair_review import eligible_target, native_probe

BASE='06f2bb716af887b4f1cc52b1f850b0608bf81076'
BASE_TREE='97890dad460556c9ec0c8a95d309fa370df07c7d'
POLICY_SHA='c9f9b7c2297639ec8201703f5449d6f9684bae2eb266d4cab1f468358e6f36d1'
INSTALL=refresh.INSTALL;STATE=refresh.STATE;ETC=refresh.ETC
PREFIX='ci/continuous/'
DELTA={PREFIX+p for p in ('snci/reviewer.py','snci/controller.py','snci/repair_source.py',
    'tests/test_source_contract.py','tests/test_controller_flow.py','tests/native_codex_probe.py',
    'tests/test_source_repair.py','README.md')}|{'docs/superpowers/plans/2026-10-03-ci-source-contract.md'}
BINDINGS={
    'main':{'image':'sha256:12e54646c896886029addbfc72f36848c633a7588abf4b72d6d21bf7fd1512fc',
            'preparation_sha256':'1bd4d6bcaa9ad97611b983972ae903fdfeb7882ca8110a2a7a99b670627e6622'},
    'sn004':{'image':'sha256:e29492434b19b7015e518193feeb789eb7b889341a660793e1db880aa6ded46c',
             'preparation_sha256':'12ba9000be8c6dcd59cb795f2a7a0b6699002536e63984cb76404a5dd868b35a'}}


def budget(rows,limit):
    day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    used=sum(row[3]==day for row in rows)
    require(type(limit) is int and 1<=limit<=4 and used<limit,'source_repair_daily_budget')
    return {'day':day,'used':used,'limit':limit,'remaining':limit-used}


def history(state,expected_inputs=None):
    rows=prior.journal_rows(state);key=sha256(canonical([prior.TARGET,POLICY_SHA]))
    matches=[row for row in rows if row[0]==key]
    require(len(matches)==1 and decode(matches[0][1])==prior.TARGET and matches[0][2]==POLICY_SHA
            and matches[0][4]=='hold' and decode(matches[0][5])=={'reason':'review_source_only'},
            'source_repair_attempt')
    root=trusted(Path(state)/'attempts'/key,directory=True)
    require({p.name for p in root.iterdir()}=={'inputs.json'},'source_repair_attempt_files')
    raw=trusted(root/'inputs.json',private=True).read_bytes();value=decode(raw)
    require(value.get('target')==dict(prior.TARGET,tree=prior.TREE)
            and value.get('profile')=='sn004' and value.get('policy_sha256')==POLICY_SHA
            and (expected_inputs is None or raw==expected_inputs),'source_repair_attempt_inputs')
    hold=prior.saved_hold(state)
    hold['journal_sha256']=sha256(canonical([row for row in rows if row[0]!=key]))
    return {'parent_hold':hold,'journal_sha256':sha256(canonical(rows)),
            'attempt_key':key,'attempt_inputs_sha256':sha256(raw)},rows


def verify_manifest(path,expected_sha,revision):
    raw=trusted(Path(path)/'installed.json').read_bytes();manifest=decode(raw)
    require(sha256(raw)==expected_sha and trusted(Path(path)/'revision').read_text()==revision,
            'source_repair_manifest')
    for name,digest in manifest.items():
        require(not name.startswith('/') and '..' not in name.split('/')
                and sha256(trusted(Path(path)/name).read_bytes())==digest,'source_repair_package_bytes')


def parent(state,policy,owner,old_install,current_history):
    directory=trusted(Path(state)/('refresh-'+BASE),private=True,directory=True)
    raw=trusted(directory/'COMPLETE.json',private=True).read_bytes();proof=decode(raw)
    intent=decode(trusted(directory/'commit-intent.json',private=True).read_bytes())
    require(intent=={'head':BASE,'policy_sha256':POLICY_SHA} and proof.get('head')==BASE
            and proof.get('policy_sha256')==POLICY_SHA
            and proof.get('status')=='RECOVERED_REVIEW_TRANSPORT_PAUSED','source_repair_parent_proof')
    oldraw=trusted(directory/'policy-before.json',private=True).read_bytes();old=decode(oldraw)
    require(sha256(oldraw)==prior.OLD_POLICY_SHA and proof.get('hold')==current_history['parent_hold']
            and proof.get('history')==recovery.historical_receipts(old),'source_repair_parent_history')
    expected=copy.deepcopy(old);expected['installed_revision']=BASE
    require({p['name'] for p in policy['profiles']}==set(BINDINGS),'source_repair_profiles')
    for p in expected['profiles']:
        current=next(x for x in policy['profiles'] if x['name']==p['name'])
        require(all(current.get(k)==v for k,v in BINDINGS[p['name']].items())
                and current.get('preparation')=='refresh-'+BASE+'/'+p['name']+'/acceptance.json',
                'source_repair_receipt_binding')
        for k in ('image','preparation','preparation_sha256'):p[k]=current[k]
    require(policy==expected,'source_repair_parent_delta')
    profiles=recovery.verify_new(owner,BASE,policy,proof['seed'])
    require(proof.get('profiles')==profiles,'source_repair_parent_profiles')
    require(proof.get('native_probe_sha256')==sha256(trusted(directory/'native-codex.log',private=True).read_bytes()),
            'source_repair_parent_native')
    require(proof.get('daemon')==recovery.daemon_identity(owner) and proof.get('seed')==recovery.seed_identity(owner),
            'source_repair_parent_daemon')
    verify_manifest(old_install,proof['manifest_sha256'],BASE)
    return {'proof_sha256':sha256(raw),'profiles':profiles,'daemon':proof['daemon'],'seed':proof['seed']}


def preflight(owner,head,api,source):
    refresh.stopped(owner);refresh.idle_native()
    raw=trusted(ETC/'policy.json',private=True).read_bytes();policy=decode(raw)
    require(sha256(raw)==POLICY_SHA and policy.get('installed_revision')==BASE
            and policy.get('enabled') is True,'source_repair_policy')
    owner.validate_policy(policy)
    require(policy['codex_binary']==owner.BINARY and policy['codex_sha256']==owner.BINARY_SHA
            and sha256(trusted(owner.BINARY).read_bytes())==owner.BINARY_SHA,'source_repair_native')
    require(eligible_target(api)==prior.TARGET,'source_repair_target')
    validate_rules(api.request('GET',API+'/rulesets/'+str(RULESET)),policy['ruleset'])
    commit=refresh.reviewed_commit(api,head,base=BASE)
    base_tree,base=source.tree(BASE);tree,new=source.tree(head)
    require(base_tree==BASE_TREE and tree==commit['tree']['sha'],'source_repair_tree')
    require(set(changed_paths(new,base))==DELTA and DELTA<=set(new),'source_repair_scope')
    package={p[len(PREFIX):]:entry for p,entry in new.items() if p.startswith(PREFIX)}
    require(all(entry.get('mode')=='100644' for entry in package.values()),'source_repair_mode')
    refresh.verify_package(base)
    target_tree,target_head=source.tree(prior.TARGET['head']);target_base_tree,target_base=source.tree(prior.TARGET['base'])
    require(target_tree==prior.TREE and select_profile(target_head,policy)['name']=='sn004','source_repair_target_source')
    inputs=canonical({'target':dict(prior.TARGET,tree=target_tree),'base_tree':target_base_tree,'profile':'sn004',
        'policy_sha256':POLICY_SHA,'changed':changed_paths(target_head,target_base),'omitted_unchanged_blobs':OMITTED_BLOBS})
    current_history,rows=history(STATE,inputs)
    retained=parent(STATE,policy,owner,INSTALL,current_history)
    return {'policy':policy,'policy_raw':raw,'package':package,'new':new,'tree':tree,
            'history':current_history,'parent':retained,'budget':budget(rows,policy['daily_attempts'])}


def completed(state,policy,raw,owner):
    head=policy.get('installed_revision')
    require(isinstance(head,str) and re.fullmatch(r'[0-9a-f]{40}',head) and head!=BASE,'source_repair_completion_head')
    directory=trusted(Path(state)/('source-contract-'+head),private=True,directory=True)
    before=trusted(directory/'policy-before.json',private=True).read_bytes();old=decode(before)
    require(sha256(before)==POLICY_SHA and policy==dict(old,installed_revision=head)
            and raw==canonical(policy),'source_repair_completion_delta')
    intent=decode(trusted(directory/'commit-intent.json',private=True).read_bytes())
    proof=decode(trusted(directory/'COMPLETE.json',private=True).read_bytes())
    require(intent=={'head':head,'policy_sha256':sha256(raw)} and proof.get('head')==head
            and proof.get('policy_sha256')==sha256(raw)
            and proof.get('status')=='SOURCE_CONTRACT_INSTALLED_PAUSED','source_repair_completion_proof')
    current_history,rows=history(state)
    backup=INSTALL.with_name(INSTALL.name+'-before-source-contract-'+head)
    require(proof.get('history')==current_history and proof.get('parent')==parent(state,old,owner,backup,current_history),
            'source_repair_completion_history')
    require(proof.get('native_probe_sha256')==sha256(trusted(directory/'native-codex.log',private=True).read_bytes()),
            'source_repair_completion_native')
    verify_manifest(INSTALL,proof['manifest_sha256'],head)
    refresh.stopped(owner);refresh.idle_native()
    require(proof.get('budget')==budget(rows,policy['daily_attempts']),'source_repair_completion_budget')


def perform(owner,head,api,source):
    require(isinstance(head,str) and re.fullmatch(r'[0-9a-f]{40}',head) and head!=BASE,'source_repair_head')
    directory=STATE/('source-contract-'+head);backup=INSTALL.with_name(INSTALL.name+'-before-source-contract-'+head)
    stage=INSTALL.with_name(INSTALL.name+'-refresh-'+head)
    require(not any(p.exists() or p.is_symlink() for p in (directory,backup,stage)),'source_repair_already_claimed')
    snapshot=preflight(owner,head,api,source)
    directory.mkdir(mode=0o700);refresh.sync(STATE)
    write_new(directory/'policy-before.json',snapshot['policy_raw'])
    write_new(directory/'inputs.json',canonical({k:snapshot[k] for k in ('tree','history','parent','budget')}))
    stage=refresh.stage_package(head,snapshot,source)
    probe=native_probe(stage,owner,snapshot['policy'],directory/'native-codex.log')
    require(preflight(owner,head,api,source)==snapshot,'source_repair_inputs_changed')
    prior.verify_stage(stage,snapshot['package'])
    future=dict(snapshot['policy'],installed_revision=head);owner.validate_policy(future)
    intent={'head':head,'policy_sha256':sha256(canonical(future))}
    write_new(directory/'commit-intent.json',canonical(intent))
    INSTALL.rename(backup);refresh.sync(INSTALL.parent)
    try:stage.rename(INSTALL)
    except Exception:backup.rename(INSTALL);refresh.sync(INSTALL.parent);raise
    refresh.sync(INSTALL.parent);owner.replace_policy(future)
    require(trusted(ETC/'policy.json',private=True).read_bytes()==canonical(future),'source_repair_policy_readback')
    refresh.verify_package(snapshot['new']);refresh.stopped(owner)
    proof=dict(intent,status='SOURCE_CONTRACT_INSTALLED_PAUSED',history=snapshot['history'],parent=snapshot['parent'],
               budget=snapshot['budget'],native_probe_sha256=probe,
               manifest_sha256=sha256(trusted(INSTALL/'installed.json').read_bytes()))
    try:
        write_new(directory/'COMPLETE.json',canonical(proof));completed(STATE,future,canonical(future),owner)
    except Exception:
        (directory/'COMPLETE.json').unlink(missing_ok=True);refresh.sync(directory);raise
    print('SOURCE_CONTRACT_INSTALLED_PAUSED '+head,flush=True)
    return proof


def apply(head):
    require(os.geteuid()==0 and os.uname().nodename.split('.')[0]=='1c-db','source_repair_owner_identity')
    import owner
    checkout=trusted(Path(__file__).resolve().parents[3],directory=True)
    require(owner.run(['git','rev-parse','HEAD'],cwd=checkout,capture_output=True).stdout.decode().strip()==head
            and not owner.run(['git','status','--porcelain','--untracked-files=all'],cwd=checkout,
                              capture_output=True).stdout,'source_repair_clean_checkout')
    trusted(STATE,private=True,directory=True);trusted(ETC,private=True,directory=True)
    path=STATE/'controller.lock';fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a') as lock:
        trusted(path,private=True)
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Hold('source_repair_controller_busy') from None
        policy=owner.load_policy();api=GitHub(policy['github'],policy['github_key'])
        perform(owner,head,api,Source(api,STATE/'blobs'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reviewed-head',required=True);args=parser.parse_args()
    os.umask(0o077)
    try:apply(args.reviewed_head)
    except Hold as error:print('HOLD '+str(error));raise SystemExit(1)
    except Exception:print('HOLD source_repair_internal_error');raise SystemExit(1)


if __name__=='__main__':main()
