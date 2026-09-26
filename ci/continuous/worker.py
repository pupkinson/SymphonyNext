#!/usr/bin/python3
"""Installed test driver. Candidate files never control stage selection."""
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess

ROOT=Path('/work/source')
LOG_BYTES=0
STAGES={'build':['mix','build'],'format':['mix','format','--check-formatted'],
        'lint':['mix','lint'],'coverage':['mix','test','--cover'],
        'dialyzer':['mix','dialyzer','--format','short']}

def require(ok,code):
    if not ok:raise RuntimeError(code)

def git_hash(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def verify_source(entries):
    for name,e in entries.items():
        p=ROOT/name
        require(not p.is_symlink() and p.is_file() and git_hash(p.read_bytes())==e['sha'],'source_changed')
        require(p.stat().st_mode&0o777==(0o755 if e['mode']=='100755' else 0o644),'source_mode')

def stage(name,args,timeout=300):
    log=Path('/work')/(name+'.log')
    def limits():resource.setrlimit(resource.RLIMIT_FSIZE,(256*1024*1024,256*1024*1024))
    with log.open('wb') as out:
        p=subprocess.Popen(args,cwd=ROOT/'elixir',stdout=out,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits,user=10001,group=10001,extra_groups=[])
        try:code=p.wait(timeout=timeout)
        finally:
            if p.poll() is None:
                os.killpg(p.pid,signal.SIGTERM)
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
    global LOG_BYTES
    LOG_BYTES+=log.stat().st_size
    require(LOG_BYTES<=16*1024*1024,'log_budget')
    text=log.read_text(errors='replace')
    print('SNCI_STAGE '+name+' '+str(code),flush=True)
    print(text,flush=True)
    require(code==0,'stage_'+name)
    return text

def parse_quality(coverage,dialyzer):
    coverage=re.sub(r'\x1b\[[0-9;]*m','',coverage)
    count=re.findall(r'^\s*(\d+) tests?, (\d+) failures?, (\d+) skipped\s*$',coverage,re.M)
    total=re.findall(r'^\|\s*([0-9.]+)%\s*\|\s*Total\s*\|\s*$',coverage,re.M)
    dial=re.findall(r'^Total errors: (\d+), Skipped: (\d+), Unnecessary Skips: (\d+)\s*$',dialyzer,re.M)
    require(len(count)==1 and total==['100.00'] and dial==[('0','0','0')],'quality_output')
    return dict(zip(('tests','failures','skipped'),map(int,count[0])),coverage=100.0,dialyzer_errors=0)

def main():
    require(os.getuid()==0,'worker_supervisor_user')
    entries=json.loads(Path('/source.json').read_text())
    shutil.copytree('/input',ROOT)
    verify_source(entries)
    require(hashlib.sha256((ROOT/'elixir/mix.lock').read_bytes()).hexdigest()==Path('/seed/lock.sha256').read_text().strip(),'dependency_image_lock')
    shutil.copytree('/seed/home','/work/home')
    Path('/work/empty-codex').mkdir()
    shutil.copytree('/seed/source/elixir/deps',ROOT/'elixir/deps')
    # Dependency cache only; the candidate application must be rebuilt.
    if Path('/seed/source/elixir/_build').exists():
        shutil.copytree('/seed/source/elixir/_build',ROOT/'elixir/_build')
        for env in ('dev','test'):
            shutil.rmtree(ROOT/'elixir/_build'/env/'lib/symphony_elixir',ignore_errors=True)
    # Candidate processes cannot signal the root supervisor or rewrite its logs.
    # Only disposable source/cache directories belong to the candidate identity.
    for parent in (ROOT,Path('/work/home'),Path('/work/empty-codex')):
        os.chown(parent,10001,10001)
        for p in parent.rglob('*'):
            if not p.is_symlink():os.chown(p,10001,10001)
    pg_bins=sorted(Path('/usr/lib/postgresql').glob('*/bin/initdb'))
    require(len(pg_bins)==1,'postgres_toolchain')
    bindir=pg_bins[0].parent;data=Path('/work/pg');sock=Path('/work/pg-socket');sock.mkdir(mode=0o700);data.mkdir(mode=0o700)
    os.chown(sock,10001,10001);os.chown(data,10001,10001)
    pg_log=Path('/work/pg/postgres.log')
    result={'stages':{},'source_before':True,'source_after':False,'cleanup':1}
    started=False
    isolation='import os,signal; assert os.getuid()==10001; caps=next(x.split()[1] for x in open("/proc/self/status") if x.startswith("CapEff:")); assert int(caps,16)==0\ntry: os.kill(os.getppid(),signal.SIGCONT)\nexcept PermissionError: pass\nelse: raise RuntimeError("candidate_can_signal_supervisor")'
    stage('isolation',['/usr/bin/python3','-I','-c',isolation])
    try:
        stage('pg-init',[str(bindir/'initdb'),'-D',str(data),'-U','sn004_fixture','--auth=trust','--no-locale'])
        # pg_ctl can succeed then lose its response: stop by the owned data directory regardless.
        started=True
        stage('pg-start',[str(bindir/'pg_ctl'),'-D',str(data),'-l',str(pg_log),'-o',
              '-c listen_addresses= -c unix_socket_directories='+str(sock)+' -p 55474','-w','start'])
        stage('pg-create',[str(bindir/'createdb'),'-h',str(sock),'-p','55474','-U','sn004_fixture','sn004_test'])
        os.environ['SN004_TEST_PG_SOCKET']=str(sock)
        # Offline dependency state must agree before candidate compilation.
        stage('deps',['mix','deps.get','--check-locked'])
        logs={}
        for name,args in STAGES.items():
            logs[name]=stage(name,args,600 if name=='dialyzer' else 300);result['stages'][name]=0
        result.update(parse_quality(logs['coverage'],logs['dialyzer']))
        verify_source(entries);result['source_after']=True
    finally:
        if started:
            r=subprocess.run([str(bindir/'pg_ctl'),'-D',str(data),'-m','immediate','-w','stop'],capture_output=True,timeout=30,user=10001,group=10001,extra_groups=[])
            result['cleanup']=r.returncode
        require(result['cleanup']==0,'postgres_cleanup')
    print('SNCI_RESULT '+json.dumps(result,sort_keys=True),flush=True)

if __name__=='__main__':
    try:main()
    except Exception:print('SNCI_WORKER_FAILED',flush=True);raise SystemExit(1)
