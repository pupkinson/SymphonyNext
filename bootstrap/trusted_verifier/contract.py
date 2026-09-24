"""Locked acceptance and root-owned artifact boundaries (Python 3.10+)."""
import hashlib
import json
import os
from pathlib import Path
import stat

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def decode_json(raw):
    require(len(raw) <= 1024 * 1024, 'json_too_large')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def trusted_file(path, owner=0, check_parents=True, private=False):
    path = Path(path).absolute()
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid == owner and not s.st_mode & 0o022,
            'untrusted_file')
    if private:
        require(not s.st_mode & 0o077, 'private_file_permissions')
    if check_parents:
        for parent in path.parents:
            p = parent.lstat()
            require(stat.S_ISDIR(p.st_mode) and p.st_uid == owner and not p.st_mode & 0o022,
                    'untrusted_parent')
    return path

def write_new_json(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)

def validate_report(target, report):
    require(type(report) is dict and report.get('schema') == 'symphony-next-test-report/v1',
            'report_schema')
    require(report.get('head') == target['head'] and report.get('tree') == target['tree'],
            'report_source_mismatch')
    expected = target['test_ids']
    require(type(expected) is list and expected and len(set(expected)) == len(expected),
            'target_tests_invalid')
    for field in ('test_ids', 'passed'):
        actual = report.get(field)
        require(type(actual) is list and all(type(x) is str for x in actual)
                and len(actual) == len(expected) and sorted(actual) == sorted(expected),
                'report_test_ids_mismatch')
    require(type(report.get('tests_run')) is int and report['tests_run'] == len(expected),
            'report_test_count')
    require(report.get('successful') is True, 'report_not_successful')
    for field in ('failures', 'errors', 'skipped', 'expected_failures', 'unexpected_successes'):
        require(report.get(field) == [], 'report_nonpass')
    isolation = report.get('isolation', {})
    uid = isolation.get('uid')
    require(type(uid) is int and uid > 0, 'worker_identity')
    for field in ('mount_namespace_separate', 'network_namespace_separate',
                  'source_readonly', 'venv_readonly', 'scratch_bounded', 'host_tmp_inaccessible'):
        require(isolation.get(field) is True, 'worker_isolation')

def validate_check(expected, actual):
    require(type(actual.get('id')) is int and actual['id'] > 0, 'check_id')
    require(actual.get('head_sha') == expected['head']
            and actual.get('app', {}).get('id') == expected['app_id']
            and actual.get('external_id') == expected['external_id']
            and actual.get('name') == expected['name']
            and actual.get('status') == 'completed'
            and actual.get('conclusion') == 'success', 'check_readback_mismatch')
