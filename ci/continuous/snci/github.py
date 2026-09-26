"""Repository-scoped App transport. GET retries only; POST outcomes never retried."""
import base64
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from .common import API, APP_ID, REPO_ID, Hold, canonical, decode, require, trusted

PERMISSIONS={'contents':'read','pull_requests':'read','checks':'write'}

def wire(method,path,token,body=None):
    require(method in ('GET','POST') and re.fullmatch(r'/[A-Za-z0-9_/?=&.%-]+',path)
            and '..' not in path and not path.startswith('//'),'github_path')
    require(re.fullmatch(r'[A-Za-z0-9_.-]+',token or '') is not None,'github_token')
    request=urllib.request.Request('https://api.github.com'+path,method=method,
        data=canonical(body) if body is not None else None,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                 'Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'symphony-next-ci/1'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    delays=(0,10,60) if method=='GET' else (0,)
    for i,delay in enumerate(delays):
        if delay:time.sleep(delay)
        try:
            with opener.open(request,timeout=30) as response:
                require(200<=response.status<300,'github_http')
                return decode(response.read(2*1024*1024+1))
        except urllib.error.HTTPError as e:
            retry=e.code in (429,500,502,503,504)
            if e.code==429:
                retry_after=e.headers.get('Retry-After','0')
                require(retry_after.isdigit() and int(retry_after)<=60,'github_rate_hold')
                if method=='GET' and i+1<len(delays):time.sleep(int(retry_after))
            if not retry or i+1==len(delays):raise Hold('github_http_'+str(e.code)) from None
        except (urllib.error.URLError,TimeoutError,OSError):
            if i+1==len(delays):raise Hold('github_transport') from None
    raise Hold('github_transport')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise Hold('github_redirect')

class GitHub:
    def __init__(self,config,key):
        require(config.get('app_id')==APP_ID and type(config.get('installation_id')) is int,'app_config')
        self.config=config;self.key=trusted(key,private=True);self.token=None;self.expires=0
    def authenticate(self):
        now=int(time.time())
        def b64(v):return base64.urlsafe_b64encode(v).rstrip(b'=')
        raw=b64(canonical({'alg':'RS256','typ':'JWT'}))+b'.'+b64(canonical({'iat':now-60,'exp':now+540,'iss':str(APP_ID)}))
        result=subprocess.run(['/usr/bin/openssl','dgst','-sha256','-sign',str(self.key)],
                              input=raw,capture_output=True,timeout=10,env={'PATH':'/usr/bin:/bin'})
        require(result.returncode==0,'app_signing')
        jwt=(raw+b'.'+b64(result.stdout)).decode()
        require(wire('GET','/app',jwt).get('id')==APP_ID,'app_identity')
        ident=self.config['installation_id']
        installation=wire('GET','/app/installations/'+str(ident),jwt)
        require(installation.get('id')==ident and installation.get('account',{}).get('login')=='pupkinson'
                and installation.get('repository_selection')=='selected'
                and installation.get('permissions')==dict(PERMISSIONS,metadata='read'),'app_scope')
        token=wire('POST','/app/installations/'+str(ident)+'/access_tokens',jwt,
                   {'repository_ids':[REPO_ID],'permissions':PERMISSIONS})
        require(token.get('permissions')==dict(PERMISSIONS,metadata='read'),'token_scope')
        self.token=token['token'];self.expires=time.monotonic()+2700
        repos=wire('GET','/installation/repositories?per_page=100',self.token)
        require(repos.get('total_count')==1 and [x.get('id') for x in repos.get('repositories',[])]==[REPO_ID],'token_repository')
    def request(self,method,path,body=None):
        require(path.startswith(API+'/'),'repository_scope')
        require(method=='GET' or (method=='POST' and path==API+'/check-runs'),'write_scope')
        if not self.token or time.monotonic()>=self.expires:self.authenticate()
        return wire(method,path,self.token,body)
    def pages(self,path,field=None):
        require('page=' not in path,'pagination_input')
        out=[]
        for page in range(1,101):
            url=path+('&' if '?' in path else '?')+'per_page=100&page='+str(page)
            result=self.request('GET',url)
            rows=result[field] if field else result
            require(isinstance(rows,list),'pagination_shape')
            out.extend(rows)
            if len(rows)<100:return out
        raise Hold('pagination_limit')
