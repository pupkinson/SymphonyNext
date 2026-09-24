"""Runs only the frozen unittest suite; no network or publication credentials."""
import json
import os
from pathlib import Path
import signal
import sys
import unittest

def flatten(suite):
    for entry in suite:
        if isinstance(entry, unittest.TestSuite):
            yield from flatten(entry)
        else:
            yield entry.id()

def run_suite(source):
    source = Path(source)
    suite = unittest.TestLoader().discover(str(source / 'tests'))
    ids = list(flatten(suite))
    class Result(unittest.TextTestResult):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.passed_ids = []
        def addSuccess(self, test):
            self.passed_ids.append(test.id())
            super().addSuccess(test)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, resultclass=Result).run(suite)
    return {'test_ids': sorted(ids), 'passed': sorted(result.passed_ids),
            'failures': sorted(t.id() for t, _ in result.failures),
            'errors': sorted(t.id() for t, _ in result.errors),
            'skipped': sorted(t.id() for t, _ in result.skipped),
            'expected_failures': sorted(t.id() for t, _ in result.expectedFailures),
            'unexpected_successes': sorted(t.id() for t in result.unexpectedSuccesses),
            'tests_run': result.testsRun, 'successful': result.wasSuccessful()}

def main():
    target = json.loads(Path('/verifier/target.json').read_text())
    host = json.loads(Path('/verifier/host.json').read_text())
    scratch = os.statvfs('/worktmp')
    mounts = Path('/proc/self/mountinfo').read_text().splitlines()
    scratch_mount = [line for line in mounts if line.split()[4] == '/worktmp']
    isolation = {
        'uid': os.getuid(),
        'mount_namespace_separate': os.readlink('/proc/self/ns/mnt') != host['mnt'],
        'network_namespace_separate': os.readlink('/proc/self/ns/net') != host['net'],
        'source_readonly': bool(os.statvfs('/source').f_flag & os.ST_RDONLY),
        'venv_readonly': bool(os.statvfs('/venv').f_flag & os.ST_RDONLY),
        'scratch_bounded': bool(len(scratch_mount) == 1 and ' - tmpfs ' in scratch_mount[0]
            and 0 < scratch.f_blocks * scratch.f_frsize <= 512*1024*1024
            and os.access('/worktmp', os.W_OK) and not scratch.f_flag & os.ST_RDONLY),
        'host_tmp_inaccessible': all(not os.access(p, os.W_OK | os.X_OK)
                                     for p in ('/tmp','/var/tmp'))}
    if isolation['uid'] == 0 or not all(v is True for k, v in isolation.items() if k != 'uid'):
        raise SystemExit('worker_isolation_failed')
    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL or not hasattr(os, 'pidfd_open'):
        raise SystemExit('unsupported_process_runtime')
    from jsonschema import Draft202012Validator
    Draft202012Validator.check_schema({'type': 'object'})
    result = run_suite('/source')
    result.update(schema='symphony-next-test-report/v1', head=target['head'],
                  tree=target['tree'], isolation=isolation)
    print('SNV_REPORT=' + json.dumps(result, sort_keys=True), flush=True)
    return 0 if result['successful'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
