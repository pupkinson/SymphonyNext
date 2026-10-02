#!/usr/bin/env python3
"""Owner-run CI metadata snapshot. No installation, network, models or CI execution.

This independent reader never imports the installed verifier or follows paths from
its configuration. Output is a whitelist, not a dump of policy or credentials.
A collected snapshot is NOT acceptance, package-integrity or runtime attestation.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import socket
import stat
import subprocess

HEAD = '21ce4282e7ef8330cc1155bcb7b94fbf132032a8'
TREE = '29fe41a2873a3db13ac2c0dc74b7f149391c9eeb'
LOCK = 'elixir/test/symphony_control/runtime_config_test.exs'
BLOB = '5ca85121e627a8e085083fc2ea25b404c2fcd9c7'
FILES = {
    'revision': '/opt/symphony-next-ci/revision',
    'definitions': '/opt/symphony-next-ci/profiles.json',
    'manifest': '/opt/symphony-next-ci/installed.json',
    'policy': '/etc/symphony-next-ci/policy.json',
    'prepare_main': '/var/lib/symphony-next-ci/prepare-main/acceptance.json',
    'prepare_sn004': '/var/lib/symphony-next-ci/prepare-sn004/acceptance.json',
}
STAGES = ('build', 'format', 'lint', 'coverage', 'dialyzer')
UNITS = ('symphony-next-ci.service', 'symphony-next-ci.timer')


def read_fixed(path, limit=2_000_000, owner=0):
    """Read a bounded regular file; reject links, unsafe file mode and read races."""
    parts = PurePosixPath(path).parts
    if not parts or parts[0] != '/' or any(x in ('.', '..') for x in parts):
        raise ValueError('path')
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    fd = None
    try:
        for name in parts[1:-1]:
            new = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = new
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOATIME, dir_fd=directory)
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != owner
                or before.st_mode & 0o022 or before.st_size > limit):
            raise ValueError('file_contract')
        chunks, remaining = [], limit + 1
        while remaining:
            block = os.read(fd, min(65536, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        after = os.fstat(fd)
        raw = b''.join(chunks)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if len(raw) > limit or any(getattr(before, f) != getattr(after, f) for f in fields):
            raise ValueError('file_changed')
        return raw
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory)


def digest(value, length=40):
    return value if isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value) else None


def number(value):
    return value if type(value) in (int, float) and 0 <= value <= 10**12 else None


def boolean(value):
    return value if type(value) is bool else None


def object_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate_key')
        out[key] = value
    return out


def reject_constant(value):
    raise ValueError('nonfinite')


def profile(value, name):
    if not isinstance(value, dict):
        raise ValueError('profile')
    locked = value.get('locked', {})
    if not isinstance(locked, dict):
        raise ValueError('locked')
    row = {'name': name, 'head': digest(value.get('head')), 'tree': digest(value.get('tree')),
           'minimum_tests': number(value.get('minimum_tests')), 'maximum_skips': number(value.get('maximum_skips')),
           'locked_count': len(locked), 'runtime_test_blob': digest(locked.get(LOCK))}
    image = value.get('image')
    row['image'] = image if isinstance(image, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', image) else None
    row['reviewed_target_matches'] = (row['head'] == HEAD and row['tree'] == TREE
                                      and row['runtime_test_blob'] == BLOB)
    return row


def summarize(kind, raw):
    result = {'state': 'read', 'sha256': hashlib.sha256(raw).hexdigest()}
    if kind == 'revision':
        revision = digest(raw.decode('ascii').strip())
        if revision is None:
            raise ValueError('revision')
        return dict(result, revision=revision)
    value = json.loads(raw, object_pairs_hook=object_pairs, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError('object')
    if kind == 'manifest':
        return dict(result, entry_count=len(value), package_integrity='NOT_CHECKED')
    if kind in ('policy', 'definitions'):
        if kind == 'definitions':
            rows = [profile(value[name], name) for name in ('main', 'sn004') if name in value]
        else:
            profiles = value.get('profiles', [])
            if not isinstance(profiles, list) or len(profiles) > 4:
                raise ValueError('profiles')
            if not all(isinstance(p, dict) for p in profiles):
                raise ValueError('profile_type')
            rows = [profile(p, p['name']) for p in profiles if p.get('name') in ('main', 'sn004')]
            result.update(enabled=boolean(value.get('enabled')), installed_revision=digest(value.get('installed_revision')),
                          daily_attempts=number(value.get('daily_attempts')), review_seconds=number(value.get('review_seconds')))
        result['profiles'] = rows
        return result
    if kind not in ('prepare_main', 'prepare_sn004'):
        raise ValueError('kind')
    quality = value.get('quality', {})
    if not isinstance(quality, dict) or not isinstance(quality.get('stages', {}), dict):
        raise ValueError('quality')
    result.update(head=digest(value.get('head')), tree=digest(value.get('tree')), time=number(value.get('time')),
                  image=profile({'image': value.get('image')}, 'receipt')['image'],
                  codex_sha256=digest(value.get('codex_sha256'), 64),
                  native_probe_sha256=digest(value.get('native_probe_sha256'), 64))
    result['quality'] = {k: number(quality.get(k)) for k in ('tests','failures','skipped','coverage','dialyzer_errors','cleanup')}
    result['quality'].update({k: boolean(quality.get(k)) for k in ('source_before','source_after')})
    result['quality']['stages'] = {k: number(quality.get('stages', {}).get(k)) for k in STAGES}
    return result


def unit_metadata():
    result = {}
    properties = ('Id', 'ActiveState', 'SubState', 'MainPID', 'UnitFileState', 'Result', 'ExecMainStatus')
    words = {'active','inactive','failed','running','dead','waiting','exited','activating','deactivating',
             'disabled','enabled','static','masked','not-found','success','exit-code','timeout','signal'} | set(UNITS)
    for unit in UNITS:
        try:
            p = subprocess.run(['/usr/bin/systemctl', 'show', unit, '--property='+','.join(properties), '--no-pager'],
                               env={'PATH':'/usr/bin:/bin','LANG':'C','SYSTEMD_PAGER':''}, cwd='/',
                               capture_output=True, text=True, timeout=10)
            if p.returncode or len(p.stdout) > 20000:
                result[unit] = {'state':'unavailable'}
                continue
            fields = {}
            for line in p.stdout.splitlines():
                key, sep, val = line.partition('=')
                if sep and key in properties:
                    fields[key] = val if val in words or re.fullmatch(r'[0-9]{1,12}',val) else 'OTHER'
            result[unit] = fields
        except (OSError, subprocess.SubprocessError):
            result[unit] = {'state':'unavailable'}
    return result


def snapshot(reader=read_fixed, get_units=unit_metadata):
    files = {}
    for key, path in FILES.items():
        try:
            files[key] = summarize(key, reader(path))
        except FileNotFoundError:
            files[key] = {'state':'missing'}
        except OSError:
            files[key] = {'state':'unreadable'}
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            files[key] = {'state':'invalid'}
    units = get_units()
    complete = all(v['state'] == 'read' for v in files.values()) and not any(v.get('state')=='unavailable' for v in units.values() if isinstance(v,dict))
    return {'operation':'SNCI_OWNER_METADATA_READBACK',
            'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'status':'SNCI_SNAPSHOT_COLLECTED' if complete else 'SNCI_SNAPSHOT_PARTIAL',
            'readiness':'NOT_ATTESTED', 'tests_executed':False, 'service_changed':False,
            'policy_changed':False, 'model_turn':False, 'files':files, 'units':units}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read', action='store_true', required=True, help='read fixed CI metadata, no changes')
    parser.parse_args(argv)
    if os.geteuid() != 0 or socket.gethostname().split('.')[0] != '1c-db':
        print(json.dumps({'status':'OWNER_TERMINAL_ON_1C_DB_REQUIRED','service_changed':False}))
        return 2
    result = snapshot()
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'SNCI_SNAPSHOT_COLLECTED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
