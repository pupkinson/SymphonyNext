"""Validate immutable source and owner-installed quality policy."""
import base64
from pathlib import Path
import re
from .common import API, APP_ID, CHECK, REPO, REPO_ID, RULESET, SHA, Hold, blob_hash, require, write_new

def safe_path(path):
    return (isinstance(path,str) and len(path)<240 and
            re.fullmatch(r'[A-Za-z0-9_./@+\-]+',path) is not None and
            all(p not in ('','.','..','.git') for p in path.split('/')))

def parse_tree(data, expected):
    require(data.get('sha')==expected and data.get('truncated') is False,'tree_identity_or_truncated')
    entries=data.get('tree',[])
    require(0<len(entries)<=4000,'tree_count')
    out={};seen=set();size=0
    for e in entries:
        path=e.get('path');require(safe_path(path) and path not in seen,'tree_path')
        seen.add(path)
        require(SHA.fullmatch(e.get('sha','')) is not None,'tree_sha')
        if e.get('type')=='tree':
            require(e.get('mode')=='040000','tree_mode');continue
        require(e.get('type')=='blob' and e.get('mode') in ('100644','100755'),'tree_type')
        n=e.get('size');require(type(n) is int and 0<=n<=700000,'blob_size')
        size+=n;require(size<=16*1024*1024,'source_size')
        out[path]={'sha':e['sha'],'mode':e['mode'],'size':n}
    return out

def verify_blob(data, expected):
    require(data.get('sha')==expected and data.get('encoding')=='base64','blob_identity')
    try: raw=base64.b64decode(''.join(data['content'].split()),validate=True)
    except (ValueError,KeyError):raise Hold('blob_encoding') from None
    require(len(raw)==data.get('size') and len(raw)<=700000 and blob_hash(raw)==expected,'blob_hash')
    return raw

def validate_target(pr, expected=None):
    require(pr.get('state')=='open' and pr.get('merged') is not True,'pr_closed')
    require(type(pr.get('number')) is int and pr['number']>0,'pr_number')
    require(not pr.get('draft') or 'snv:verify' in [l.get('name') for l in pr.get('labels',[])],'draft_not_requested')
    for side in ('head','base'):
        value=pr.get(side,{})
        require(value.get('repo',{}).get('id')==REPO_ID,'foreign_repository')
        require(SHA.fullmatch(value.get('sha','')) is not None,'target_sha')
    require(pr['base'].get('ref')=='main','base_branch')
    target={'pr':pr['number'],'head':pr['head']['sha'],'base':pr['base']['sha']}
    if expected:
        require(all(target[k]==expected[k] for k in target),'stale_target')
    return target

def validate_rules(live, pinned):
    fields=('id','target','source_type','source','enforcement','conditions','rules','updated_at')
    require(pinned.get('bypass_actors')==[],'pinned_bypass')
    require(all(k in live and k in pinned and live[k]==pinned[k] for k in fields),'rules_revision')
    require(live['id']==RULESET and live['source']==REPO and live['source_type']=='Repository'
            and live['target']=='branch' and live['enforcement']=='active','rules_identity')
    require(live['conditions'].get('ref_name')=={'include':['~DEFAULT_BRANCH'],'exclude':[]},'rules_scope')
    checks=[r for r in live['rules'] if r.get('type')=='required_status_checks']
    require(len(checks)==1 and {'context':CHECK,'integration_id':APP_ID} in
            checks[0].get('parameters',{}).get('required_status_checks',[]),'required_check')
    if 'bypass_actors' in live:
        require(live['bypass_actors']==[],'live_bypass');return 'visible_empty'
    return 'pinned_empty_revision_matched'

def select_profile(entries, policy):
    matches=[p for p in policy['profiles'] if p['locked'] and
             all(entries.get(path,{}).get('sha')==sha for path,sha in p['locked'].items())]
    require(len(matches)==1,'no_unique_quality_profile')
    return matches[0]

def changed_paths(head,base):
    return sorted(p for p in head.keys()|base.keys() if head.get(p)!=base.get(p))

def protected_change(paths, target, policy):
    guarded=[p for p in paths if p.rsplit('/',1)[-1] in ('AGENTS.md','PROJECT_RULES.md','SKILLS_POLICY.md') or
             p.startswith(('ci/','policies/','.github/','bootstrap/'))]
    if guarded:
        require(any(all(x.get(k)==target[k] for k in ('pr','head','base'))
                    and sorted(x.get('paths',[]))==guarded for x in policy.get('exceptions',[])),
                'protected_change_requires_owner')

class Source:
    def __init__(self,api,cache):self.api=api;self.cache=Path(cache);self.cache.mkdir(exist_ok=True,mode=0o700)
    def tree(self,commit):
        d=self.api.request('GET',API+'/git/commits/'+commit)
        require(d.get('sha')==commit,'commit_identity')
        tree=d['tree']['sha'];require(SHA.fullmatch(tree) is not None,'commit_tree')
        return tree,parse_tree(self.api.request('GET',API+'/git/trees/'+tree+'?recursive=1'),tree)
    def blob(self,entry):
        sha=entry['sha'];p=self.cache/sha
        if p.exists():
            require(not p.is_symlink() and p.is_file(),'cache_type');raw=p.read_bytes()
            require(blob_hash(raw)==sha,'cache_hash');return raw
        raw=verify_blob(self.api.request('GET',API+'/git/blobs/'+sha),sha)
        write_new(p,raw)
        return raw
    def materialize(self,entries,directory):
        directory=Path(directory);directory.mkdir(mode=0o755)
        for path,entry in entries.items():
            require(safe_path(path),'source_path')
            p=directory/path;p.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
            raw=self.blob(entry)
            require(len(raw)==entry['size'],'source_size_changed')
            write_new(p,raw,0o755 if entry['mode']=='100755' else 0o644)
