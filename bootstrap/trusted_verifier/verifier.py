#!/usr/bin/python3
"""Fixed owner-operated bootstrap for the reviewed PR #11 target; no model launch."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
from datetime import datetime, timezone

# -I does not add the script directory. Installed directory must be root-owned.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from contract import decode_json, digest, require, trusted_file, validate_check, validate_report, write_new_json
from github_api import CLEAN_ENV, GitHub, REPO, REPO_ID

INSTALL = Path('/opt/symphony-next-verifier')
STATE = Path('/var/lib/symphony-next-verifier')
HEAD = '78d60bd77a5c9667e1241ca64f3429a3123d86df'
TARGET_HASH = '1c587fcf6ac9855c9952283f395f4aa89c5c7fd0c0c2e643cd2b2142f451abbb'
CHECK = 'symphony-next/verified-tests'
FILES = {'verifier.py', 'contract.py', 'worker.py', 'github_api.py', 'askpass.py', 'controller.service',
         'target.json', 'requirements.lock', 'README.md'}

def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def root_host():
    require(os.geteuid() == 0 and platform.node() == '1c-db', 'owner_root_on_1c_db_required')
    require(sys.version_info[:2] == (3, 10) and platform.machine() == 'x86_64',
            'requires_cpython310_linux_x86_64')
    os.umask(0o077)

def checked_package(path, installed=False):
    path = Path(path)
    if installed:
        trusted_file(path / 'package-manifest.json')
    manifest = decode_json((path / 'package-manifest.json').read_bytes())
    require(type(manifest) is dict and set(manifest) == FILES, 'package_manifest_scope')
    for name, sha in manifest.items():
        item = path / name
        require(item.is_file() and not item.is_symlink() and digest(item) == sha,
                'package_checksum_mismatch')
        if installed: trusted_file(item)
    require(manifest['target.json'] == TARGET_HASH, 'target_checksum_mismatch')
    return manifest

def run_checked(argv, *, cwd=None, env=None, timeout=60):
    p = subprocess.run(argv, cwd=cwd, env=env or CLEAN_ENV, capture_output=True, timeout=timeout)
    require(p.returncode == 0, 'command_failed_' + Path(argv[0]).name)
    return p.stdout

def install(wheelhouse):
    root_host()
    manifest = checked_package(HERE)
    unit_file = Path('/etc/systemd/system/symphony-next-verifier-controller.service')
    require(not unit_file.exists() and not unit_file.is_symlink(), 'controller_unit_already_exists')
    require(not INSTALL.exists() and not INSTALL.is_symlink()
            and not STATE.exists() and not STATE.is_symlink(), 'installation_already_exists')
    for tool in ('python3','git','curl','openssl','systemd-run','systemctl'):
        require(Path('/usr/bin', tool).is_file(), 'missing_prerequisite_' + tool)
    for parent in (INSTALL.parent, STATE.parent):
        s = parent.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
                'installation_parent_untrusted')
    wheelhouse = Path(wheelhouse)
    require(wheelhouse.is_dir() and not wheelhouse.is_symlink(), 'wheelhouse_directory')
    wanted = {line.split('--hash=sha256:')[1].strip()
              for line in (HERE / 'requirements.lock').read_text().splitlines()
              if '--hash=sha256:' in line}
    wheels = list(wheelhouse.iterdir())
    require(len(wheels) == 6 and all(p.is_file() and not p.is_symlink()
            and p.name.endswith('.whl') and p.stat().st_size <= 5*1024*1024 for p in wheels),
            'wheelhouse_files')
    require({digest(p) for p in wheels} == wanted, 'wheelhouse_checksums')
    INSTALL.mkdir(mode=0o755)
    STATE.mkdir(mode=0o700)
    (STATE/'private').mkdir(mode=0o700)
    (STATE/'jobs').mkdir(mode=0o700)
    write_new_json(STATE/'installation-intent.json', {'at':now(),'manifest':manifest})
    for name in FILES | {'package-manifest.json'}:
        data = (HERE/name).read_bytes()
        with (INSTALL/name).open('xb') as out: out.write(data)
        (INSTALL/name).chmod(0o755 if name == 'askpass.py' else 0o644)
    checked_package(INSTALL, installed=True)
    staged = STATE/'private'/'wheels'
    staged.mkdir(mode=0o700)
    for wheel in wheels:
        data = wheel.read_bytes()
        require(hashlib.sha256(data).hexdigest() in wanted, 'wheel_changed_during_copy')
        with (staged/wheel.name).open('xb') as out: out.write(data)
    run_checked(['/usr/bin/python3','-I','-B','-m','venv',str(INSTALL/'venv')], timeout=120)
    python = str(INSTALL/'venv/bin/python3')
    run_checked([python,'-I','-B','-m','pip','--isolated','install','--no-index',
                 '--only-binary=:all:','--require-hashes','--find-links',str(staged),
                 '-r',str(INSTALL/'requirements.lock')], timeout=120)
    run_checked([python,'-I','-B','-m','pip','--isolated','check'])
    # venv includes symlinks created by Python to the known system interpreter.
    for directory, dirs, names in os.walk(INSTALL/'venv', followlinks=False):
        Path(directory).chmod(0o755)
        for name in names:
            p=Path(directory)/name
            if not p.is_symlink():
                p.chmod(0o755 if p.stat().st_mode & 0o111 else 0o644)
    freeze = run_checked([python,'-I','-B','-m','pip','--isolated','freeze']).decode()
    with unit_file.open('xb') as out: out.write((INSTALL/'controller.service').read_bytes())
    unit_file.chmod(0o644)
    run_checked(['/usr/bin/systemctl','daemon-reload'])
    write_new_json(STATE/'installed.json', {'status':'INSTALLED_NO_TEST_RUN','at':now(),
        'target':HEAD,'package_manifest_sha256':digest(INSTALL/'package-manifest.json'),
        'dependencies':freeze,'native_systemd_verified':False})
    print(json.dumps({'status':'INSTALLED_NO_TEST_RUN','model_turn':'NOT_RUN'}))

def configure(app_id, installation_id, key_file):
    root_host()
    checked_package(INSTALL, installed=True)
    trusted_file(STATE/'installed.json', private=True)
    require(type(app_id) is int and app_id > 0 and type(installation_id) is int
            and installation_id > 0, 'invalid_app_ids')
    key = trusted_file(key_file, private=True)
    data = key.read_bytes()
    require(len(data) <= 32768, 'key_size')
    require(data.startswith((b'-----BEGIN PRIVATE KEY-----', b'-----BEGIN RSA PRIVATE KEY-----'))
            and b'ENCRYPTED' not in data, 'unencrypted_app_key_required')
    run_checked(['/usr/bin/openssl','pkey','-in',str(key),'-check','-noout'])
    private = STATE/'private'
    require(not (private/'config.json').exists() and not (private/'app.pem').exists(),
            'configuration_already_exists')
    with (private/'app.pem').open('xb') as out:
        out.write(data);out.flush();os.fsync(out.fileno())
    (private/'app.pem').chmod(0o600)
    write_new_json(private/'config.json', {'app_id':app_id,'installation_id':installation_id})
    print(json.dumps({'status':'CONFIGURED_NO_TEST_RUN','app_id':app_id,
                      'installation_id':installation_id,'private_key_printed':False}))

def claim_attempt(jobs, head):
    require(re.fullmatch('[a-f0-9]{40}',head) is not None, 'invalid_target')
    job = Path(jobs)/head
    job.mkdir(mode=0o700)  # Existing/partial attempts are never silently reused.
    write_new_json(job/'intent.json', {'at':now(),'head':head,'status':'ATTEMPT_CLAIMED'})
    return job

def verify_pr(api, target):
    pr = api.request('GET', '/repos/'+REPO+'/pulls/11')
    require(pr.get('state') == 'open' and pr.get('merged') is False
            and pr.get('head',{}).get('sha') == target['head']
            and pr.get('head',{}).get('ref') == target['branch']
            and pr.get('head',{}).get('repo',{}).get('id') == REPO_ID
            and pr.get('base',{}).get('sha') == target['base']
            and pr.get('base',{}).get('repo',{}).get('id') == REPO_ID, 'pr_source_changed')
    return {'number':11,'head':pr['head']['sha'],'base':pr['base']['sha'],'at':now()}

def source_identity(source, target):
    def git(*args):
        return run_checked(['/usr/bin/git','-c','core.hooksPath=/dev/null',
                            '-c','core.fsmonitor=false',*args],cwd=source).decode().strip()
    require(git('rev-parse','HEAD') == target['head']
            and git('rev-parse','HEAD^{tree}') == target['tree']
            and git('show','-s','--format=%P','HEAD') == target['parent'],
            'checkout_identity')
    require(not git('status','--porcelain','--untracked-files=all'), 'checkout_dirty')
    require(git('merge-base',target['base'],'HEAD') == target['base'], 'checkout_base')
    tracked = run_checked(['/usr/bin/git','ls-tree','-rz','--full-tree','HEAD'],cwd=source)
    for entry in tracked.split(b'\0'):
        if entry:
            metadata, raw_path = entry.split(b'\t',1)
            require(metadata.split()[0] in (b'100644',b'100755'), 'source_nonregular_entry')
            p=source/os.fsdecode(raw_path)
            require(p.is_file() and not p.is_symlink(), 'source_file_type')
    for name, sha in target['test_files'].items():
        require(digest(source/name) == sha, 'locked_test_checksum')

def fetch_source(api, job, target):
    source=job/'source';source.mkdir(mode=0o755)
    token_file=STATE/'private'/'checkout-token'
    fd=os.open(token_file,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as out:out.write(api.token)
    env=dict(CLEAN_ENV,GIT_ASKPASS=str(INSTALL/'askpass.py'),SNV_TOKEN_FILE=str(token_file))
    try:
        run_checked(['/usr/bin/git','-c','core.hooksPath=/dev/null','init','--template=','--quiet'],cwd=source)
        run_checked(['/usr/bin/git','-c','credential.helper=','-c','core.hooksPath=/dev/null',
                     'fetch','--quiet','--no-tags','--depth=4',
                     'https://github.com/'+REPO+'.git',target['head']],cwd=source,env=env,timeout=180)
        run_checked(['/usr/bin/git','-c','core.hooksPath=/dev/null','checkout','--quiet','--detach',
                     target['head']],cwd=source)
    finally:
        token_file.unlink()  # Only the just-created root-private token file.
    source_identity(source,target)
    for directory, dirs, names in os.walk(source):
        Path(directory).chmod(0o755)
        for name in names:
            p = Path(directory)/name
            require(not p.is_symlink(), 'checkout_symlink')
            p.chmod(0o555 if p.stat().st_mode & 0o111 else 0o444)
    return source

def unit_command(job, unit):
    require(re.fullmatch(r'symphony-next-verify-[a-f0-9]{12}',unit) is not None,'unit_name')
    bindings=['/usr:/usr',str(job/'source')+':/source',
              str(INSTALL/'venv')+':/venv',str(job/'worker')+':/verifier']
    props = ['DynamicUser=yes','RootDirectory='+str(job/'root'),'WorkingDirectory=/source',
             'MountAPIVFS=yes',
             'BindReadOnlyPaths='+' '.join(bindings),'PrivateNetwork=yes','PrivateDevices=yes',
             'ProtectSystem=strict','ProtectHome=yes','ProtectProc=invisible',
             'NoNewPrivileges=yes','CapabilityBoundingSet=','RestrictSUIDSGID=yes',
             'InaccessiblePaths=/tmp /var/tmp','PrivateIPC=yes',
             'RestrictNamespaces=yes','LockPersonality=yes','ProtectKernelTunables=yes',
             'ProtectKernelModules=yes','ProtectKernelLogs=yes','ProtectControlGroups=yes',
             'RestrictAddressFamilies=AF_UNIX','MemoryMax=2147483648','CPUQuota=200%',
             'TasksMax=128','RuntimeMaxSec=600','TimeoutStopSec=5','KillMode=control-group',
             'KillSignal=SIGKILL','SendSIGKILL=yes','Restart=no','UMask=0077',
             'LimitFSIZE=16777216','LimitCORE=0',
             'TemporaryFileSystem=/worktmp:rw,nosuid,nodev,size=512M,mode=1777 /run:rw,nosuid,nodev,size=16M,mode=755',
             'Environment=HOME=/worktmp XDG_CACHE_HOME=/worktmp/cache TMPDIR=/worktmp PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_OPTIONAL_LOCKS=0 GIT_TERMINAL_PROMPT=0']
    return ['/usr/bin/systemd-run','--unit='+unit,'--service-type=exec','--wait','--pipe','--quiet',
            *['--property='+p for p in props],'/venv/bin/python3','-I','-B','/verifier/worker.py']

def read_worker_report(raw):
    reports=[x[len(b'SNV_REPORT='):] for x in raw.splitlines() if x.startswith(b'SNV_REPORT=')]
    require(len(reports) == 1, 'worker_report_count')
    return decode_json(reports[0])

def execute_unit(job, target):
    root=job/'root';root.mkdir(mode=0o755);root.chmod(0o755)
    for name in ('usr','proc','dev','source','venv','verifier','tmp','run','etc','worktmp','var','var/tmp'):
        (root/name).mkdir(mode=0o755)
        (root/name).chmod(0o755)
    for name in ('bin','sbin','lib','lib64'):
        (root/name).symlink_to('usr/'+name)
    worker=job/'worker';worker.mkdir(mode=0o755);worker.chmod(0o755)
    for name in ('worker.py','target.json'):
        shutil.copyfile(INSTALL/name,worker/name);(worker/name).chmod(0o444)
    host={'mnt':os.readlink('/proc/self/ns/mnt'),'net':os.readlink('/proc/self/ns/net')}
    (worker/'host.json').write_text(json.dumps(host));(worker/'host.json').chmod(0o444)
    unit='symphony-next-verify-'+target['head'][:12]
    stdout=job/'worker.stdout';stderr=job/'worker.stderr'
    timed_out=False
    try:
        with stdout.open('xb') as out,stderr.open('xb') as err:
            try:
                result=subprocess.run(unit_command(job,unit),stdin=subprocess.DEVNULL,
                                      stdout=out,stderr=err,env=CLEAN_ENV,timeout=630)
                code=result.returncode
            except subprocess.TimeoutExpired:
                timed_out=True;code=124
    finally:
        # Fixed owned unit only. This is never the Symphony WORK-01 unit.
        stopped=subprocess.run(['/usr/bin/systemctl','stop',unit],env=CLEAN_ENV,
                               capture_output=True,timeout=20)
        state=subprocess.run(['/usr/bin/systemctl','show',unit,'--property=LoadState',
                              '--property=ActiveState','--property=SubState','--property=MainPID'],
                             env=CLEAN_ENV,capture_output=True,timeout=10)
        parsed=dict(line.split('=',1) for line in state.stdout.decode().splitlines() if '=' in line)
        write_new_json(job/'unit-state.json',{'state':parsed,'stop_exit':stopped.returncode,
                                            'show_exit':state.returncode,'at':now()})
    require(parsed.get('ActiveState') == 'inactive' and parsed.get('MainPID') == '0',
            'worker_not_confirmed_inactive')
    write_new_json(job/'worker-exit.json',{'exit_code':code,'timed_out':timed_out})
    require(code == 0,'test_process_failed')
    require(stdout.stat().st_size <= 1024*1024 and stderr.stat().st_size <= 16*1024*1024,
            'worker_output_limit')
    return read_worker_report(stdout.read_bytes())

def publish_once(api, job, expected, body):
    write_new_json(job/'publication-intent.json',{'expected':expected,'body':body,'at':now()})
    created=api.request('POST','/repos/'+REPO+'/check-runs',body)
    require(type(created.get('id')) is int and created['id'] > 0,'check_create_response')
    write_new_json(job/'check-created.json',{'id':created['id']})
    actual=api.request('GET','/repos/'+REPO+'/check-runs/'+str(created['id']))
    validate_check(expected,actual)
    receipt={'id':created['id'],'app_id':expected['app_id'],'head':expected['head'],
             'external_id':expected['external_id'],'name':expected['name'],'conclusion':'success',
             'html_url':actual.get('html_url'),'at':now()}
    write_new_json(job/'check-verified.json',receipt)
    return receipt

def runtime_manifest():
    binaries = {}
    for name in ('python3','git','curl','openssl','systemd-run','systemctl'):
        path = Path('/usr/bin',name).resolve()
        trusted_file(path)
        binaries[str(path)] = digest(path)
    packages = {}
    for path in sorted((INSTALL/'venv').rglob('*')):
        if path.is_file():
            trusted_file(path.resolve())
            packages[str(path.relative_to(INSTALL/'venv'))] = digest(path)
    return {'binaries':binaries,'venv_files':packages,
            'python':sys.version,'kernel':platform.release(),
            'systemd':run_checked(['/usr/bin/systemd-run','--version']).decode().splitlines()[0]}

def verify():
    root_host();checked_package(INSTALL,installed=True)
    require(os.environ.get('SNV_CONTROLLER_SERVICE') == '1'
            and os.environ.get('INVOCATION_ID'), 'use_installed_controller_service')
    trusted_file(STATE/'installed.json',private=True)
    config=decode_json(trusted_file(STATE/'private/config.json',private=True).read_bytes())
    key=trusted_file(STATE/'private/app.pem',private=True)
    target=decode_json((INSTALL/'target.json').read_bytes())
    require(target['head'] == HEAD,'target_mismatch')
    lock=os.open(STATE/'private/controller.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        job=claim_attempt(STATE/'jobs',target['head'])
        try:
            api=GitHub(config,key,STATE/'private')
            write_new_json(job/'pr-before.json',verify_pr(api,target))
            runtime = runtime_manifest()
            write_new_json(job/'runtime-before.json',runtime)
            source=fetch_source(api,job,target)
            report=execute_unit(job,target)
            source_identity(source,target)
            require(runtime_manifest() == runtime,'runtime_changed')
            validate_report(target,report)
            write_new_json(job/'test-report.json',report)
            write_new_json(job/'pr-after.json',verify_pr(api,target))
            expected={'head':HEAD,'app_id':config['app_id'],'external_id':'snv-'+HEAD,'name':CHECK}
            body={'name':CHECK,'head_sha':HEAD,'external_id':expected['external_id'],
                  'status':'completed','conclusion':'success','completed_at':now(),
                  'output':{'title':'Frozen Python suite passed',
                            'summary':'126/126 tests; no skips/errors. Source '+HEAD+
                            '; evidence SHA256 '+digest(job/'test-report.json')}}
            receipt=publish_once(api,job,expected,body)
            verify_pr(api,target)
            write_new_json(job/'result.json',{'status':'CHECK_PUBLISHED_EXACT_HEAD','head':HEAD,
                'check':receipt,'protected_branch_binding':'OWNER_CONFIGURATION_REQUIRED',
                'server_functional_acceptance':'NOT_RUN','model_turn':'NOT_RUN','at':now()})
        except BaseException as exc:
            if not (job/'result.json').exists():
                write_new_json(job/'result.json',{'status':'STOP','exception_type':type(exc).__name__,
                    'reason':str(exc) if type(exc) is ValueError and re.fullmatch('[a-z0-9_]+',str(exc)) else 'verifier_failed',
                    'publication_intent':(job/'publication-intent.json').exists(),
                    'instruction':'Preserve this attempt. Do not rerun tests or publication blindly.',
                    'model_turn':'NOT_RUN','at':now()})
            raise
        print((job/'result.json').read_text())
    finally:
        os.close(lock)

def status():
    root_host()
    job=STATE/'jobs'/HEAD
    for name in ('result.json','check-verified.json','publication-intent.json','intent.json'):
        p=job/name
        if p.exists():
            print(trusted_file(p,private=True).read_text());return
    print(json.dumps({'status':'NO_VERIFICATION_ATTEMPT','model_turn':'NOT_RUN'}))

def main():
    def stop(signum, frame):
        raise KeyboardInterrupt('owner_stop')
    signal.signal(signal.SIGTERM, stop)
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('install');p.add_argument('--wheelhouse',required=True)
    p=sub.add_parser('configure');p.add_argument('--app-id',type=int,required=True)
    p.add_argument('--installation-id',type=int,required=True);p.add_argument('--key-file',required=True)
    sub.add_parser('verify');sub.add_parser('status')
    args=parser.parse_args()
    try:
        if args.command=='install':install(args.wheelhouse)
        elif args.command=='configure':configure(args.app_id,args.installation_id,args.key_file)
        elif args.command=='verify':verify()
        else:status()
        return 0
    except BaseException as exc:
        print(json.dumps({'status':'STOP','exception_type':type(exc).__name__,
            'reason':str(exc) if type(exc) is ValueError and re.fullmatch('[a-z0-9_]+',str(exc)) else 'verifier_failed',
            'instruction':'Preserve artifacts; use status. Do not blindly repeat verification.'}),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
