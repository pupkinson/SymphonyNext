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
import time

ROOT=Path('/work/source')
LOG_BYTES=0
LOG_LIMIT=16*1024*1024
CLEANUP_EXIT_CODE=None
SETUP_STEP=None
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

class StageFailure(RuntimeError):
    def __init__(self,details):
        self.details=details
        super().__init__('stage_failed')

def failure_details(error):
    original=error
    seen=set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error,StageFailure):
            return dict(error.details,cleanup_exit_code=CLEANUP_EXIT_CODE)
        error=error.__context__
    detail=dict(stage='setup',kind='worker_error',exit_code=None,timeout_seconds=0,
                duration_seconds=0,log_bytes=0,log_truncated=False,cleanup_exit_code=CLEANUP_EXIT_CODE)
    if SETUP_STEP in {'supervisor','manifest','source_copy','source_verify','lock','home_cache',
                      'empty_codex','deps_cache','build_cache','ownership','postgres_toolchain','postgres_dirs'}:
        detail['setup_step']=SETUP_STEP
        if isinstance(original,(OSError,shutil.Error)):detail['kind']='io_error'
    return detail

def copy_build_cache(source,destination):
    source=Path(source)
    excluded={source/env/directory for env in ('dev','test') for directory in ('lib','phoenix-colocated')}
    def ignore(directory,names):
        return {'symphony_elixir'} if Path(directory) in excluded else set()
    # Exclude own compiled output before dereferencing links. Dependency links
    # remain strict: a missing dependency target must still fail preparation.
    shutil.copytree(source,destination,ignore=ignore)

def stage(name,args,timeout=300):
    require(name in set(STAGES)|{'isolation','pg-init','pg-start','pg-create','deps'},'stage_name')
    log=Path('/work')/(name+'.log')
    def limits():resource.setrlimit(resource.RLIMIT_FSIZE,(256*1024*1024,256*1024*1024))
    started=time.monotonic();code=None;kind=None;p=None
    try:
        fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as out:
            try:
                p=subprocess.Popen(args,cwd=ROOT/'elixir',stdout=out,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits,user=10001,group=10001,extra_groups=[])
            except (OSError,subprocess.SubprocessError):kind='spawn_error'
            if p is not None:
                try:code=p.wait(timeout=timeout)
                except subprocess.TimeoutExpired:kind='timeout'
                finally:
                    if p.poll() is None:
                        try:os.killpg(p.pid,signal.SIGTERM)
                        except ProcessLookupError:pass
                        try:p.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            try:os.killpg(p.pid,signal.SIGKILL)
                            except ProcessLookupError:pass
                            p.wait(timeout=5)
                    code=p.returncode
    except OSError:kind=kind or 'io_error'
    global LOG_BYTES
    size=0;raw=b'';remaining=max(0,LOG_LIMIT-LOG_BYTES)
    # Read only our newly created regular log, never an existing/symlink path.
    if p is not None or kind=='spawn_error':
        try:
            size=log.stat().st_size
            with log.open('rb') as inp:raw=inp.read(remaining)
        except OSError:kind=kind or 'io_error'
    text=raw.decode(errors='replace')
    encoded=text.encode()
    truncated=len(raw)<size or len(encoded)>remaining
    if len(encoded)>remaining:text=encoded[:remaining].decode(errors='ignore')
    LOG_BYTES+=len(text.encode())
    print('SNCI_STAGE '+name+' '+str(code),flush=True)
    print(text,flush=True)
    kind=kind or ('log_budget' if truncated else 'stage_exit' if code!=0 else None)
    if kind:
        raise StageFailure(dict(stage=name,kind=kind,exit_code=code,timeout_seconds=timeout,
                                duration_seconds=round(time.monotonic()-started,3),
                                log_bytes=size,log_truncated=truncated,cleanup_exit_code=None))
    return text

def parse_quality(coverage,dialyzer):
    coverage=re.sub(r'\x1b\[[0-9;]*m','',coverage)
    count=re.findall(r'^\s*(\d+) tests?, (\d+) failures?, (\d+) skipped\s*$',coverage,re.M)
    total=re.findall(r'^\|\s*([0-9.]+)%\s*\|\s*Total\s*\|\s*$',coverage,re.M)
    dial=re.findall(r'^Total errors: (\d+), Skipped: (\d+), Unnecessary Skips: (\d+)\s*$',dialyzer,re.M)
    require(len(count)==1 and total==['100.00'] and dial==[('0','0','0')],'quality_output')
    return dict(zip(('tests','failures','skipped'),map(int,count[0])),coverage=100.0,dialyzer_errors=0)

def main():
    global CLEANUP_EXIT_CODE,SETUP_STEP
    SETUP_STEP='supervisor'
    require(os.getuid()==0,'worker_supervisor_user')
    SETUP_STEP='manifest'
    entries=json.loads(Path('/source.json').read_text())
    SETUP_STEP='source_copy'
    shutil.copytree('/input',ROOT)
    SETUP_STEP='source_verify'
    verify_source(entries)
    SETUP_STEP='lock'
    require(hashlib.sha256((ROOT/'elixir/mix.lock').read_bytes()).hexdigest()==Path('/seed/lock.sha256').read_text().strip(),'dependency_image_lock')
    SETUP_STEP='home_cache'
    shutil.copytree('/seed/home','/work/home')
    SETUP_STEP='empty_codex'
    Path('/work/empty-codex').mkdir()
    SETUP_STEP='deps_cache'
    shutil.copytree('/seed/source/elixir/deps',ROOT/'elixir/deps')
    # Dependency cache only; the candidate application must be rebuilt.
    SETUP_STEP='build_cache'
    if Path('/seed/source/elixir/_build').exists():
        copy_build_cache('/seed/source/elixir/_build',ROOT/'elixir/_build')
    # Candidate processes cannot signal the root supervisor or rewrite its logs.
    # Only disposable source/cache directories belong to the candidate identity.
    SETUP_STEP='ownership'
    for parent in (ROOT,Path('/work/home'),Path('/work/empty-codex')):
        os.chown(parent,10001,10001)
        for p in parent.rglob('*'):
            if not p.is_symlink():os.chown(p,10001,10001)
    SETUP_STEP='postgres_toolchain'
    pg_bins=sorted(Path('/usr/lib/postgresql').glob('*/bin/initdb'))
    require(len(pg_bins)==1,'postgres_toolchain')
    SETUP_STEP='postgres_dirs'
    bindir=pg_bins[0].parent;data=Path('/work/pg');sock=Path('/work/pg-socket');sock.mkdir(mode=0o700);data.mkdir(mode=0o700)
    os.chown(sock,10001,10001);os.chown(data,10001,10001)
    pg_log=Path('/work/pg/postgres.log')
    result={'stages':{},'source_before':True,'source_after':False,'cleanup':1}
    started=False
    isolation='import os,signal; assert os.getuid()==10001; caps=next(x.split()[1] for x in open("/proc/self/status") if x.startswith("CapEff:")); assert int(caps,16)==0\ntry: os.kill(os.getppid(),signal.SIGCONT)\nexcept PermissionError: pass\nelse: raise RuntimeError("candidate_can_signal_supervisor")'
    SETUP_STEP=None
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
            CLEANUP_EXIT_CODE=r.returncode
        require(result['cleanup']==0,'postgres_cleanup')
    print('SNCI_RESULT '+json.dumps(result,sort_keys=True),flush=True)

def run_main():
    global SETUP_STEP
    SETUP_STEP=None
    try:main();return 0
    except Exception as error:
        print('SNCI_FAILURE '+json.dumps(failure_details(error),sort_keys=True),flush=True)
        print('SNCI_WORKER_FAILED',flush=True);return 1

if __name__=='__main__':raise SystemExit(run_main())
