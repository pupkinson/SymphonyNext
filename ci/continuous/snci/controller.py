"""A single protected polling controller; deliberately no merge/deploy methods."""
import fcntl
import json
import os
import re
from pathlib import Path
import signal
from .common import API, APP_ID, CHECK, RULESET, Hold, canonical, decode, require, sha256, trusted, write_new
from .github import GitHub
from .source import OMITTED_BLOBS, Source, changed_paths, protected_change, select_profile, validate_rules, validate_target
from .state import Journal
from . import reviewer, runner

STATE=Path('/var/lib/symphony-next-ci')
POLICY=Path('/etc/symphony-next-ci/policy.json')

def check_matches(actual,body):
    return (type(actual.get('id')) is int and actual['id']>0 and actual.get('app',{}).get('id')==APP_ID
            and all(actual.get(k)==body[k] for k in ('head_sha','external_id','name','status','conclusion'))
            and all(actual.get('output',{}).get(k)==body['output'][k] for k in ('title','summary')))

def reconcile(api,journal,key,guard):
    row=journal.get(key);require(row['state']=='publishing','not_publishing')
    body=row['data']['check_body'];guard()
    checks=api.pages(API+'/commits/'+body['head_sha']+'/check-runs?filter=all','check_runs')
    matches=[x for x in checks if x.get('external_id')==body['external_id']]
    if not matches:return False
    require(len(matches)==1 and check_matches(matches[0],body),'publication_conflict')
    actual=api.request('GET',API+'/check-runs/'+str(matches[0]['id']))
    require(check_matches(actual,body),'publication_readback')
    guard();journal.set(key,'success',dict(row['data'],check_id=actual['id']))
    return True

def publish(api,journal,key,body,guard):
    guard()
    existing=api.pages(API+'/commits/'+body['head_sha']+'/check-runs?filter=all','check_runs')
    require(not any(x.get('external_id')==body['external_id'] for x in existing),'publication_already_exists')
    journal.set(key,'publishing',dict(journal.get(key)['data'],check_body=body))
    # Unknown response leaves the durable intent intact. Never replay POST.
    actual=api.request('POST',API+'/check-runs',body)
    require(check_matches(actual,body),'publication_response')
    require(reconcile(api,journal,key,guard),'publication_not_visible')

def guard(api,target,policy,policy_digest):
    require(sha256(trusted(POLICY,private=True).read_bytes())==policy_digest,'policy_changed')
    validate_target(api.request('GET',API+'/pulls/'+str(target['pr'])),target)
    validate_rules(api.request('GET',API+'/rulesets/'+str(RULESET)),policy['ruleset'])

def process(api,journal,source,target,policy,digest,review_fn=reviewer.review,run_fn=runner.run):
    key=journal.claim(target,digest,policy['daily_attempts'])
    if not key:return False
    root=STATE/'attempts'/key
    try:
        root.mkdir(mode=0o755)
        tree,head=source.tree(target['head']);base_tree,base=source.tree(target['base'])
        target=dict(target,tree=tree)
        paths=changed_paths(head,base);require(paths,'empty_change')
        protected_change(paths,target,policy)
        profile=select_profile(head,policy)
        write_new(root/'inputs.json',canonical({'target':target,'base_tree':base_tree,'profile':profile['name'],
                                               'policy_sha256':digest,'changed':paths,'omitted_unchanged_blobs':OMITTED_BLOBS}))
        fresh=lambda:guard(api,target,policy,digest)
        fresh()
        review=review_fn(target,source,head,base,paths,policy)
        write_new(root/'review.json',canonical(review))
        require(review['verdict']['verdict']=='READY','review_not_ready')
        fresh();source.materialize(head,root/'source')
        quality=run_fn(root,key,head,profile)
        evidence={'target':target,'policy_sha256':digest,'profile':profile['name'],'quality':quality,
                  'review_sha256':sha256(canonical(review)),'source_tree':tree,'omitted_unchanged_blobs':OMITTED_BLOBS}
        write_new(root/'result.json',canonical(evidence))
        journal.set(key,'running',{'evidence_sha256':sha256(canonical(evidence))})
        summary='Independent review READY; protected stages passed. Evidence SHA256: '+sha256(canonical(evidence))
        body={'name':CHECK,'head_sha':target['head'],'external_id':'snci-v1-'+key,'status':'completed','conclusion':'success',
              'output':{'title':'SymphonyNext protected verification','summary':summary}}
        publish(api,journal,key,body,fresh)
        return True
    except Exception as e:
        # Publication intent survives EVERY exception for read-only reconciliation.
        row=journal.get(key)
        if row['state']=='running':journal.set(key,'hold',{'reason':str(e) if isinstance(e,Hold) else 'internal_error'})
        raise

def validate_policy(p):
    require(p.get('schema')=='snci-policy/v1' and p.get('repository')=='pupkinson/SymphonyNext','policy_identity')
    require(type(p.get('enabled')) is bool and type(p.get('daily_attempts')) is int and 1<=p['daily_attempts']<=4,'policy_limits')
    require(1<=len(p.get('profiles',[]))<=4 and p.get('review_seconds')==900,'policy_profile_limits')
    require(isinstance(p.get('codex_binary'),str) and p['codex_binary'].startswith('/usr/')
            and re.fullmatch(r'[0-9a-f]{64}',p.get('codex_sha256','')),'policy_codex')
    require(len({x.get('name') for x in p['profiles']})==len(p['profiles']),'profile_names')
    for profile in p['profiles']:
        require(profile.get('locked') and profile.get('minimum_tests',0)>=305 and profile.get('maximum_skips')==6,'profile_assertions')
        require(all(path in profile['locked'] for path in ('elixir/mix.exs','elixir/mix.lock','elixir/test/test_helper.exs')),'profile_required_locks')
        require(any(path.startswith('elixir/test/') and path.endswith('_test.exs') for path in profile['locked']),'profile_locked_suite')
        require(isinstance(profile.get('image'),str) and re.fullmatch(r'sha256:[0-9a-f]{64}',profile['image']),'profile_image')
    validate_rules(p['ruleset'],p['ruleset'])

def tick():
    require(os.geteuid()==0,'controller_identity')
    trusted(STATE,private=True,directory=True)
    # Installed code is independent of candidate branches and immutable to workers.
    install=trusted('/opt/symphony-next-ci',directory=True)
    manifest=decode(trusted(install/'installed.json').read_bytes())
    for name,expected in manifest.items():
        require(not name.startswith('/') and '..' not in name.split('/'),'installed_path')
        require(sha256(trusted(install/name).read_bytes())==expected,'installed_code_changed')
    raw=trusted(POLICY,private=True).read_bytes();policy=decode(raw);validate_policy(policy);digest=sha256(raw)
    lock=open(STATE/'controller.lock','a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:lock.close();return 'ALREADY_RUNNING'
    journal=Journal(STATE/'journal.sqlite3')
    try:
        api=GitHub(policy['github'],policy['github_key'])
        for row in journal.pending():
            if row['state']=='publishing':
                if row['policy']!=digest:continue # old policy needs explicit investigation; never repost
                try:reconcile(api,journal,row['key'],lambda:guard(api,row['target'],policy,digest))
                except Hold as e:
                    if str(e)=='stale_target':journal.set(row['key'],'stale',row['data'])
                    else:raise
            else:
                runner.stop_owned(row['key'])
                journal.set(row['key'],'hold',{'reason':'interrupted_attempt_no_retry'})
        if not policy['enabled']:return 'DISABLED'
        source=Source(api,STATE/'blobs')
        prs=api.pages(API+'/pulls?state=open&sort=created&direction=asc')
        for pr in prs:
            try:target=validate_target(pr)
            except Hold:continue
            if process(api,journal,source,target,policy,digest):return 'TRUSTED_CHECK_READBACK_PASS'
        return 'NO_NEW_WORK'
    finally:journal.close();lock.close()

def main():
    def stop(*_):raise Hold('controller_stopped')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:print(json.dumps({'status':tick()}))
    except Hold as e:print(json.dumps({'status':'HOLD','reason':str(e)}));raise SystemExit(1)
    except Exception:print(json.dumps({'status':'HOLD','reason':'internal_error'}));raise SystemExit(1)

if __name__=='__main__':main()
