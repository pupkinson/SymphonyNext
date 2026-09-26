"""Start only the installed worker in a pinned, credential-free container."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
from .common import Hold, canonical, decode, require, write_new

INSTALL=Path('/opt/symphony-next-ci')
DOCKER=['/usr/bin/docker','--host=unix:///var/run/docker.sock']
WORKER_ENV=['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    'LANG=C.UTF-8','HOME=/work/home','MIX_HOME=/work/home/.mix','HEX_HOME=/work/home/.hex',
    'HEX_OFFLINE=1','MIX_REBAR3=/usr/local/bin/rebar3','ERL_FLAGS=+S 2:2',
    'CODEX_HOME=/work/empty-codex','PYTHONDONTWRITEBYTECODE=1']
TMPFS={'/work':'rw,exec,nosuid,nodev,size=3g,uid=0,gid=0,mode=755',
       '/tmp':'rw,exec,nosuid,nodev,size=256m,uid=0,gid=0,mode=1777'}

def create_args(root,image,key):
    require(re.fullmatch(r'[0-9a-f]{64}',key) is not None and re.fullmatch(r'sha256:[0-9a-f]{64}',image),'runner_identity')
    args=['create','--pull=never','--name=snci-'+key,'--label=snci.attempt='+key,
          '--restart=no','--read-only','--network=none','--cap-drop=ALL','--security-opt=no-new-privileges:true',
          '--user=0:0','--cap-add=CHOWN','--cap-add=SETUID','--cap-add=SETGID','--cap-add=KILL','--cpus=2','--memory=4g','--memory-swap=4g','--pids-limit=256',
          '--workdir=/','--log-driver=json-file','--log-opt=max-size=32m','--log-opt=max-file=1',
          '--stop-timeout=15']
    for target,options in TMPFS.items():args+=['--tmpfs='+target+':'+options]
    for source,target in [(Path(root)/'source','/input'),(INSTALL/'worker.py','/worker.py'),(Path(root)/'source.json','/source.json')]:
        args+=['--mount','type=bind,source='+str(source)+',target='+target+',readonly,bind-propagation=rprivate']
    return args+['--entrypoint=/usr/bin/env',image,'-i']+WORKER_ENV+['/usr/bin/python3','-I','/worker.py']

def command(args,timeout=30):
    try:r=subprocess.run(DOCKER+args,capture_output=True,timeout=timeout,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    except (subprocess.TimeoutExpired,OSError):raise Hold('docker_transport') from None
    require(r.returncode==0,'docker_command')
    require(len(r.stdout)<=34*1024*1024,'docker_output')
    return r.stdout

def inspect_container(key,image,root):
    data=decode(command(['inspect','snci-'+key]))
    require(isinstance(data,list) and len(data)==1,'container_inspect')
    d=data[0];h=d['HostConfig'];c=d['Config']
    require(d['Name']=='/snci-'+key and d['Image']==image and c['User']=='0:0'
            and c.get('Labels',{}).get('snci.attempt')==key,'container_identity')
    require(h['NetworkMode']=='none' and h['ReadonlyRootfs'] and not h['Privileged']
            and h['RestartPolicy']['Name']=='no' and h['Memory']==4294967296 and h['MemorySwap']==4294967296
            and h['NanoCpus']==2000000000 and h['PidsLimit']==256 and h['CapDrop']==['ALL']
            and sorted(h['CapAdd'])==['CHOWN','KILL','SETGID','SETUID']
            and h['SecurityOpt']==['no-new-privileges:true'] and h['Tmpfs']==TMPFS,'container_isolation')
    require(c['Entrypoint']==['/usr/bin/env'] and c['Cmd']==['-i']+WORKER_ENV+['/usr/bin/python3','-I','/worker.py']
            and not c.get('Volumes') and not c.get('OpenStdin') and not c.get('Tty'),'container_command')
    for field in ('Binds','PortBindings','Devices','DeviceRequests','DeviceCgroupRules','VolumesFrom','Links','ExtraHosts','GroupAdd','PublishAllPorts','AutoRemove'):
        require(not h.get(field),'container_extra')
    require(h.get('PidMode')=='' and h.get('IpcMode')=='private' and h.get('UTSMode')=='' and h.get('UsernsMode')=='','container_namespaces')
    mounts=d.get('Mounts',[])
    expected={(str(Path(root)/'source'),'/input'),(str(INSTALL/'worker.py'),'/worker.py'),(str(Path(root)/'source.json'),'/source.json')}
    require(len(mounts)==3 and {(m.get('Source'),m.get('Destination')) for m in mounts}==expected
            and all(m.get('Type')=='bind' and m.get('RW') is False and m.get('Propagation')=='rprivate' for m in mounts),'container_mounts')
    return d

def stop_owned(key):
    require(re.fullmatch(r'[0-9a-f]{64}',key) is not None,'cleanup_key')
    # Removing by deterministic owned name works after an unknown create/start.
    names=command(['ps','-a','--filter','name=^/snci-'+key+'$','--format','{{.Names}}']).decode().splitlines()
    if not names:return
    require(names==['snci-'+key],'cleanup_name')
    d=decode(command(['inspect','snci-'+key]))[0]
    require(d.get('Config',{}).get('Labels',{}).get('snci.attempt')==key,'cleanup_owner')
    command(['rm','--force','snci-'+key])

def validate_result(result,profile):
    require(result.get('stages')==dict.fromkeys(('build','format','lint','coverage','dialyzer'),0),'quality_stages')
    require(result.get('source_before') is True and result.get('source_after') is True and result.get('cleanup')==0,'quality_cleanup_source')
    require(type(result.get('tests')) is int and result['tests']>=profile['minimum_tests'] and result.get('failures')==0
            and type(result.get('skipped')) is int and 0<=result['skipped']<=profile['maximum_skips']
            and result.get('coverage')==100.0 and result.get('dialyzer_errors')==0,'quality_assertions')
    return result

def run(root,key,entries,profile):
    root=Path(root);write_new(root/'source.json',canonical(entries),0o644)
    image=profile['image'];args=create_args(root,image,key)
    try:
        command(args);inspect_container(key,image,root)
        command(['start','snci-'+key])
        status=command(['wait','snci-'+key],timeout=1500).decode().strip()
        final=inspect_container(key,image,root)
        logs=command(['logs','snci-'+key])
        write_new(root/'worker.log',logs)
        require(status=='0' and final['State'].get('Running') is False and final['State'].get('ExitCode')==0
                and not final['State'].get('OOMKilled') and not final['State'].get('Error'),'worker_failed')
        matches=[line[len(b'SNCI_RESULT '):] for line in logs.splitlines() if line.startswith(b'SNCI_RESULT ')]
        require(len(matches)==1,'worker_receipt')
        return validate_result(decode(matches[0]),profile)
    finally:stop_owned(key)
