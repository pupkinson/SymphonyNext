"""Validate immutable source and owner-installed quality policy."""
import base64
from pathlib import Path
import re
from .common import API, APP_ID, CHECK, REPO, REPO_ID, RULESET, SHA, Hold, blob_hash, canonical, require, write_new

# One pre-existing inert video is metadata-pinned, never downloaded/executed.
# A change, deletion, mode change or another large asset requires owner policy work.
OMITTED_BLOBS={'.github/media/symphony-demo.mp4':{
    'sha':'32b1f857f45eb901905ea24355b599fb417f53c5','mode':'100644','size':30446771}}

# A separately owner-reviewed request, not a generic non-main/draft exception.
PR75_REQUEST = {'pr': 75, 'head': 'be5371e71db363d5a07c7109d6dd010a6ceca7ef',
    'base': '233dda1878533a425574074b8d34344b50d41cf7',
    'tree': 'b0f828141ca90851f6e037d6f1741aaaa28496de',
    'head_ref': 'feat/sn005-oidc-protocol-20261004',
    'base_ref': 'docs/sn005-authentik-project-access-20261004',
    'repository_id': REPO_ID, 'draft': True}

PR75_SUCCESSOR_REQUEST = dict(PR75_REQUEST,
    head="8c5828b1a5c4a2261fb2cd0a021235109a8e07a3",
    tree="496889153378c3e22bd58c96cf0f6855364117e5")

def validate_owner_request(request):
    require(isinstance(request,dict) and any(canonical(request)==canonical(pinned)
                for pinned in (PR75_REQUEST, PR75_SUCCESSOR_REQUEST)),
            'owner_request_scope')

def safe_path(path):
    return (isinstance(path,str) and len(path)<240 and
            re.fullmatch(r'[A-Za-z0-9_./@+\-]+',path) is not None and
            all(p not in ('','.','..','.git') for p in path.split('/')))

def parse_tree(data, expected, omissions=None):
    omissions=omissions or {}
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
        if path in omissions:
            require(all(e.get(k)==v for k,v in omissions[path].items()),'omitted_asset_changed')
            continue
        n=e.get('size');require(type(n) is int and 0<=n<=700000,'blob_size')
        size+=n;require(size<=16*1024*1024,'source_size')
        out[path]={'sha':e['sha'],'mode':e['mode'],'size':n}
    require(set(omissions)<=seen,'omitted_asset_missing')
    return out

def verify_blob(data, expected):
    require(data.get('sha')==expected and data.get('encoding')=='base64','blob_identity')
    try: raw=base64.b64decode(''.join(data['content'].split()),validate=True)
    except (ValueError,KeyError):raise Hold('blob_encoding') from None
    require(len(raw)==data.get('size') and len(raw)<=700000 and blob_hash(raw)==expected,'blob_hash')
    return raw

def validate_target(pr, expected=None, owner_request=None):
    require(pr.get('state')=='open' and pr.get('merged') is not True,'pr_closed')
    require(type(pr.get('number')) is int and pr['number']>0,'pr_number')
    if owner_request is not None:
        validate_owner_request(owner_request)
        require(pr['number']==owner_request['pr'] and pr.get('draft') is owner_request['draft'],
                'owner_request_target')
    else:
        require(not pr.get('draft') or 'snv:verify' in [l.get('name') for l in pr.get('labels',[])],'draft_not_requested')
    for side in ('head','base'):
        value=pr.get(side,{})
        require(value.get('repo',{}).get('id')==REPO_ID,'foreign_repository')
        require(SHA.fullmatch(value.get('sha','')) is not None,'target_sha')
    target={'pr':pr['number'],'head':pr['head']['sha'],'base':pr['base']['sha']}
    if owner_request is not None:
        require(all(target[k]==owner_request[k] for k in target)
                and all(pr[side].get('ref')==owner_request[side+'_ref'] for side in ('head','base')),
                'owner_request_target')
    else:
        require(pr['base'].get('ref')=='main','base_branch')
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

def quality_control(path):
    return (path in ('elixir/mix.exs','elixir/mix.lock') or
            path.rsplit('/',1)[-1] in ('.credo.exs','.formatter.exs') or
            path.startswith(('elixir/config/','elixir/lib/mix/')))

def select_profile(entries, policy):
    matches=[p for p in policy['profiles'] if p['locked'] and
             all(entries.get(path,{}).get('sha')==sha for path,sha in p['locked'].items()) and
             all(path in p['locked'] for path in entries if quality_control(path))]
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
        return tree,parse_tree(self.api.request('GET',API+'/git/trees/'+tree+'?recursive=1'),tree,OMITTED_BLOBS)
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
        # Normalize after materialization: service UMask=0077 must not change
        # candidate file contracts or supervisor traversal after UID transfer.
        for p in [directory]+[p for p in directory.rglob('*') if p.is_dir()]:p.chmod(0o755)
