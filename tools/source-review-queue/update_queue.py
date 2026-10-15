#!/usr/bin/env python3
"""Owner-run exact-predecessor update; no admission, credentials or state restore.

CLI paths/unit are fixed. The injectable paths/controller are for offline
qualification only. Copy the reviewed package to a private root-owned directory
and verify its outer SHA256 before running this file as root on 1c-db.
"""
import ast
import datetime
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import pwd
import re
import signal
import socket
import stat
import subprocess
import sys
import time

UNIT = 'symphony-next-queue.service'
INSTALL = Path('/opt/symphony-next-queue-v1')
STATE = Path('/var/lib/symphony-next-bootstrap/queue-v1')
PREDECESSOR = {
    'queue.py': '7fa0ee5624132253e487cf8093af5b1bd90fe5680c682d9672114cdbeccd33d1',
    'WORKFLOW.md': '863dcc07d8120597786370f7d43a8df7645b91940cf5ffc03fd08e674a4bc3e5',
    'tmux.conf': 'efbb1c10814140d8b2be96cc9e02cab29d15814f5e00b36ddb2821c46a1864ee',
    'installed.json': 'b96964a5a184d6670628f9cf925a87dfbccedffcf219d870aa5662c5c1ce8b57'}
PAYLOAD = {'queue.py', 'execution.py', 'installed.json', 'executor-policy.json'}
IDENTITY = dict(User='symphony-next', Group='symphony-next',
                WorkingDirectory=str(STATE), ProtectSystem='strict',
                KillMode='control-group', Restart='no')
SUCCESS = 'SOURCE_REVIEW_COMPLETED_NOT_RELEASE_APPROVAL'


def wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


class Hold(Exception):
    pass


def require(value, code):
    if not value:
        raise Hold(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, maximum=1000000, *, observed=False):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'PATH_SYMLINK')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as f:
        s = os.fstat(f.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_size <= maximum, 'FILE_LIMIT')
        raw = f.read(maximum + 1)
    require(len(raw) <= maximum, 'FILE_LIMIT')
    return (raw, s) if observed else raw


def trusted(path, uid):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'PATH_SYMLINK')
    for p in (path, *path.parents):
        s = p.stat()
        require(s.st_uid in (0, uid) and (not s.st_mode & 0o022 or p != path
                and stat.S_ISDIR(s.st_mode) and s.st_mode & stat.S_ISVTX), 'UNTRUSTED_PACKAGE_PATH')


def atomic(path, raw, mode=0o644, uid=None, gid=None):
    path = Path(path)
    require(not path.is_symlink(), 'PATH_SYMLINK')
    tmp = path.with_name('.' + path.name + '.sn102-' + str(os.getpid()))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            os.fchmod(f.fileno(), mode)
            if uid is not None:
                os.fchown(f.fileno(), uid, gid)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if tmp.exists():
            tmp.unlink()


def save(path, value):
    atomic(path, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode(), 0o600)


def journal_json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'NOTIFICATION_JOURNAL_DUPLICATE_KEY')
            value[key] = item
        return value
    def nonfinite(_value):
        raise Hold('NOTIFICATION_JOURNAL_NONFINITE')
    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, TypeError):
        raise Hold('NOTIFICATION_JOURNAL_MISSING_OR_INVALID') from None
    require(isinstance(value, dict), 'NOTIFICATION_JOURNAL_SCHEMA')
    return value


def journal(path, maximum=1000000, *, observed=False):
    try:
        data = read(path, maximum, observed=observed)
        return (journal_json(data[0]), data[1]) if observed else journal_json(data)
    except (OSError, ValueError, TypeError):
        raise Hold('NOTIFICATION_JOURNAL_MISSING_OR_INVALID') from None


def timestamp(value):
    require(isinstance(value, str), 'NOTIFICATION_TIMESTAMP')
    try:
        date = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(date.tzinfo is not None, 'NOTIFICATION_TIMESTAMP')
        return date
    except ValueError:
        raise Hold('NOTIFICATION_TIMESTAMP') from None


def source_body(number, result):
    """The identical formatter in pinned7fa0ee and candidate _finish_task.

    Do not import/execute either service module with root's authority.
    """
    text = str(result.get('review_text', 'No complete source verdict. This is not release approval.'))
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    text = re.sub(r'(?i)Bearer\s+\S+', 'Bearer [REDACTED]', text)
    text = re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]{15,}|github_pat_[A-Za-z0-9_]{15,}|sk-[A-Za-z0-9_-]{12,})',
                  '[REDACTED]', text)
    text = ''.join(c for c in text if c in '\n\t' or ord(c) >= 32 and ord(c) != 127)[:65536]
    if len(text.encode()) > 43000:
        text = text.encode()[:43000].decode('utf-8', 'ignore') + '\n[Full report retained in the service journal.]'
    return (f'snq-v1 GH-{number}\n## Symphony source-review result\n\n'
            f'HEAD `{result["head"]}`\n\n**{result["status"]}**\n\n' + text
            + '\n\nTests by this reviewer: NOT_RUN. No trusted CI, merge or deploy.')


class Controller:
    def admission_identity(self, jobs):
        """The pinned predecessor admits by mkdir, before auth/model/reserve.

        Check the real service's credentials, not root's os.access result.
        This reads only credential metadata, never process arguments/env.
        """
        account = pwd.getpwnam(IDENTITY['User'])
        require(account.pw_uid == 995 and account.pw_gid == 995, 'ADMISSION_CREDENTIALS_CHANGED')
        s = jobs.stat()
        require(s.st_uid == account.pw_uid and s.st_gid == account.pw_gid,
                'ADMISSION_DIRECTORY_OWNER')
        data = self.properties()
        if data.get('ActiveState') == 'inactive' and data.get('MainPID') == '0':
            require(data.get('ControlGroup') in ('', '/system.slice/' + UNIT), 'SERVICE_CGROUP_CHANGED')
            return account
        require(data.get('ControlGroup') == '/system.slice/' + UNIT, 'SERVICE_CGROUP_CHANGED')
        pids = read(Path('/sys/fs/cgroup/system.slice') / UNIT / 'cgroup.procs', 65536).split()
        require(pids and data.get('MainPID', '').encode() in pids, 'SERVICE_PROCESS_UNKNOWN')
        for pid in pids:
            require(pid.isdigit(), 'SERVICE_PROCESS_UNKNOWN')
            status = dict(line.split(':', 1) for line in
                          read(Path('/proc') / pid.decode() / 'status', 65536).decode().splitlines()
                          if ':' in line)
            require(status.get('Uid', '').split() == [str(account.pw_uid)] * 4
                    and int(status.get('CapEff', '-1'), 16) == 0, 'ADMISSION_CREDENTIALS_CHANGED')
        return account

    def admission_probe(self, jobs):
        account = self.admission_identity(jobs)
        def demote():
            os.setgroups([])
            os.setgid(account.pw_gid)
            os.setuid(account.pw_uid)
        # An actual mkdir denial is the pause acknowledgement. No issue is
        # claimed, no model is called, and no service capability is added.
        script = ("import errno,os,sys\n"
                  "p=sys.argv[1]+'/.update-admission-probe-'+str(os.getpid())\n"
                  "try: os.mkdir(p,0o700)\n"
                  "except OSError as e: sys.exit(0 if e.errno==errno.EACCES else 3)\n"
                  "else: os.rmdir(p); sys.exit(4)\n")
        result = subprocess.run(['/usr/bin/python3', '-I', '-B', '-c', script, str(jobs)],
                                preexec_fn=demote, capture_output=True, timeout=5,
                                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        require(result.returncode == 0, 'ADMISSION_PAUSE_UNCONFIRMED')

    def command(self, *args):
        p = subprocess.run(['/usr/bin/systemctl', *args, UNIT], capture_output=True, text=True,
                           timeout=55, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'SYSTEMD_PAGER': ''})
        require(p.returncode == 0, 'SYSTEMCTL_FAILED')
        return p.stdout

    def properties(self):
        fields = ','.join((*IDENTITY, 'ExecStart', 'MainPID', 'ActiveState', 'SubState', 'ControlGroup'))
        return dict(line.split('=', 1) for line in self.command('show', '--property=' + fields).splitlines() if '=' in line)

    def identity(self):
        data = self.properties()
        command = '/usr/bin/python3 -I -B /opt/symphony-next-queue-v1/queue.py --serve'
        require('argv[]=' + command + ' ;' in data.get('ExecStart', ''), 'SERVICE_COMMAND_CHANGED')
        return {key: data.get(key) for key in IDENTITY}

    def idle(self):
        c = http.client.HTTPConnection('127.0.0.1', 4327, timeout=3)
        try:
            c.request('GET', '/api/v1/state')
            r = c.getresponse()
            raw = r.read(1000001)
            require(r.status == 200 and len(raw) <= 1000000, 'DASHBOARD_UNAVAILABLE')
            data = json.loads(raw)
            return isinstance(data, dict) and all(isinstance(data.get(k), list) and not data[k]
                                                for k in ('running', 'blocked', 'retrying'))
        except (OSError, ValueError, http.client.HTTPException):
            raise Hold('DASHBOARD_UNAVAILABLE') from None
        finally:
            c.close()

    def stopped(self):
        data = self.properties()
        require(data.get('ControlGroup') in ('', '/system.slice/' + UNIT), 'SERVICE_CGROUP_CHANGED')
        group = Path('/sys/fs/cgroup/system.slice') / UNIT / 'cgroup.procs'
        return data.get('ActiveState') == 'inactive' and data.get('MainPID') == '0' and (
            not group.exists() or not read(group, 65536).strip())

    def stop(self):
        self.command('stop')
        require(self.stopped(), 'SERVICE_NOT_STOPPED')

    def start(self):
        self.command('start')

    def healthy(self):
        for _ in range(45):
            data = self.properties()
            if data.get('ActiveState') == 'failed':
                return False
            if data.get('ActiveState') == 'active' and data.get('MainPID') not in ('', '0', None):
                try:
                    if self.idle():
                        return True
                except Hold:
                    pass
            time.sleep(1)
        return False


class Updater:
    def __init__(self, package, install, state, controller, *, predecessor=None, owner_uid=0,
                 drain_seconds=30):
        self.package, self.install, self.state = map(Path, (package, install, state))
        self.ctl, self.uid = controller, owner_uid
        self.predecessor = PREDECESSOR if predecessor is None else predecessor
        self.drain_seconds = drain_seconds

    def package_check(self):
        trusted(self.package, self.uid)
        trusted(self.install, self.uid)
        self.m = json.loads(read(self.package / 'manifest.json'))
        m = self.m
        require(set(m) == {'schema', 'head', 'tree', 'predecessor', 'payload', 'updater_sha256', 'review'}
                and m['schema'] == 'snq-update-package/v1'
                and all(isinstance(m[k], str) and re.fullmatch('[a-f0-9]{40}', m[k]) for k in ('head', 'tree')),
                'PACKAGE_MANIFEST')
        require(m['predecessor'] == self.predecessor and set(m['payload']) == PAYLOAD, 'PACKAGE_SCOPE')
        trusted(self.package / 'manifest.json', self.uid)
        trusted(self.package / 'update_queue.py', self.uid)
        require(sha(read(self.package / 'update_queue.py')) == m['updater_sha256'], 'UPDATER_CHANGED')
        review = m['review']
        require(isinstance(review, dict) and review.get('head') == m['head'] and review.get('tree') == m['tree']
                and review.get('independent') is True and review.get('state') == 'completed'
                and review.get('result') == 'no_major_findings'
                and re.fullmatch(r'https://github\.com/pupkinson/SymphonyNext/pull/103#issuecomment-[0-9]+',
                                 str(review.get('url'))), 'INDEPENDENT_EXACT_HEAD_REVIEW_REQUIRED')
        self.payload = {}
        for name, expected in m['payload'].items():
            p = self.package / 'payload' / name
            trusted(p, self.uid)
            raw = read(p)
            require(sha(raw) == expected, 'PAYLOAD_CHANGED')
            self.payload[name] = raw
            if name.endswith('.py'):
                ast.parse(raw.decode(), feature_version=(3, 10))
        policy = json.loads(self.payload['executor-policy.json'])
        require(policy == dict(schema='snq-executor-policy/v1', enabled=False, revision='not-admitted', tasks={}),
                'EXECUTOR_MUST_BE_DISABLED')
        new = json.loads(self.payload['installed.json'])
        require(new.get('script_sha256') == m['payload']['queue.py']
                and new.get('execution_schema') == 'snq-execution-install/v1'
                and new.get('execution_sha256') == m['payload']['execution.py'], 'INSTALLATION_PINS')
        require(self.ctl.identity() == IDENTITY, 'SERVICE_IDENTITY_CHANGED')
        self.backup = self.install / '.rollback' / m['head']
        return m

    def matches(self, hashes):
        return all((self.install / n).is_file() and sha(read(self.install / n)) == h for n, h in hashes.items())

    def check(self, *, idle=True):
        self.package_check()
        for name, expected in self.predecessor.items():
            trusted(self.install / name, self.uid)
            require(sha(read(self.install / name)) == expected, 'INSTALLED_PREDECESSOR_CHANGED')
        require(not any((self.install / n).exists() or (self.install / n).is_symlink()
                        for n in ('execution.py', 'executor-policy.json')), 'EXECUTOR_ALREADY_INSTALLED')
        old = json.loads(read(self.install / 'installed.json'))
        new = json.loads(self.payload['installed.json'])
        require({k: v for k, v in new.items() if k not in ('execution_schema', 'execution_sha256')}
                == dict(old, script_sha256=self.m['payload']['queue.py']), 'LEGACY_METADATA_CHANGED')
        if idle:
            self.quiet()
            require(self.ctl.idle(), 'QUEUE_NOT_IDLE')
        return {'status': 'UPDATE_CHECK_PASS', 'head': self.m['head'], 'executor_enabled': False}

    def quiet(self):
        require(self.state.is_dir() and not any(p.is_symlink() for p in (self.state, *self.state.parents)),
                'STATE_SYMLINK')
        for name in ('jobs', 'reservations', 'accepted', 'review-links'):
            root = self.state / name
            require(not root.is_symlink() and (not root.exists() or root.is_dir()), 'STATE_SYMLINK')
        for job in sorted((self.state / 'jobs').glob('GH-*')):
            require(job.is_dir() and not job.is_symlink(),
                    'JOURNAL_NEEDS_RECONCILIATION')
            attempts = job / 'attempts'
            if attempts.exists() or attempts.is_symlink():
                require(attempts.is_dir() and not attempts.is_symlink(), 'STATE_SYMLINK')
                for attempt in attempts.iterdir():
                    require(attempt.is_dir() and not attempt.is_symlink(), 'STATE_SYMLINK')
                    for name in ('outbox', 'notifications'):
                        path = attempt / name
                        require(not path.is_symlink() and (not path.exists() or path.is_dir()),
                                'STATE_SYMLINK')
            if (job / 'execution.json').exists():
                generation = json.loads(read(job / 'execution.json'))['generation']
                require(type(generation) is int and 1 <= generation <= 3, 'EXECUTION_JOURNAL')
                final = job / 'attempts' / str(generation) / 'final.json'
                require(final.is_file() and json.loads(read(final)).get('state') in
                        ('AcceptedSource', 'Blocked', 'Stopped', 'Rework'), 'DEVELOPER_NOT_TERMINAL')
            for intent in job.glob('attempts/*/outbox/*-intent.json'):
                receipt = intent.with_name(intent.name.replace('-intent.json', '-receipt.json'))
                require(receipt.is_file(),
                        'UNKNOWN_OUTBOX_REQUIRES_RECONCILIATION')
                try:
                    outcome = json.loads(read(receipt))
                    payload = json.loads(read(intent))['payload']
                    key = intent.name[:-len('-intent.json')]
                    require(isinstance(outcome, dict) and isinstance(payload, dict),
                            'UNKNOWN_OUTBOX_REQUIRES_RECONCILIATION')
                    if key in ('branch', 'tree', 'commit', 'publish-ref') or re.fullmatch('blob-[0-9]+', key):
                        require(set(outcome) == {'sha'} and re.fullmatch('[a-f0-9]{40}', str(outcome['sha']))
                                and (key != 'branch' or outcome['sha'] == payload.get('sha'))
                                and (key != 'publish-ref' or outcome['sha'] == payload.get('head')),
                                'UNKNOWN_OUTBOX_REQUIRES_RECONCILIATION')
                    elif key in ('pr', 'review'):
                        require(set(outcome) == {'number'} and type(outcome['number']) is int
                                and 0 < outcome['number'] < 2147483647, 'UNKNOWN_OUTBOX_REQUIRES_RECONCILIATION')
                    else:
                        require(key == 'review-label' and set(outcome) == {'admitted'}
                                and outcome['admitted'] is True,
                                'UNKNOWN_OUTBOX_REQUIRES_RECONCILIATION')
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    raise Hold('UNKNOWN_OUTBOX_REQUIRES_RECONCILIATION') from None
            self.notifications(job)
        try:
            self.reviews_applied()
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise Hold('REVIEW_APPLICATION_INCOMPLETE:' + type(exc).__name__) from None

    def delivery(self, directory, *, legacy=False):
        """Inspect the existing delivery contract, never replay/repair it.

        All four records apply to both root source and nested developer
        delivery; only the DELETE intent is optional (label already absent).
        A root developer compatibility marker never enters this method.
        """
        require(directory.is_dir() and not directory.is_symlink(), 'NOTIFICATION_DIRECTORY')
        names = {'comment-intent.json', 'comment-readback.json', 'label-remove-intent.json',
                 'label-removed.json'}
        if not legacy:
            # save()'s pre-replace files cannot trigger POST/DELETE. A crash
            # can retain partial bytes; they never replace canonical proof.
            temporary = r'\.(?:comment-intent|comment-readback|label-remove-intent|label-removed)\.json\.[0-9]+'
            require(all((p.name in names or re.fullmatch(temporary, p.name))
                        and p.is_file() and not p.is_symlink()
                        for p in directory.iterdir()), 'NOTIFICATION_DIRECTORY')
        records = [journal(directory / n, 100000, observed=True) for n in
                   ('comment-intent.json', 'comment-readback.json', 'label-removed.json')]
        (intent, intended), (receipt, received), (removed, retired) = records
        require(set(intent) == {'body'} and isinstance(intent['body'], str)
                and 0 < len(intent['body'].encode()) <= 100000, 'NOTIFICATION_COMMENT_INTENT')
        require(set(receipt) == {'id'} and type(receipt['id']) is int
                and 0 < receipt['id'] < 2 ** 63, 'NOTIFICATION_COMMENT_OUTCOME_UNKNOWN')
        require(set(removed) == {'confirmed', 'at'} and removed['confirmed'] is True,
                'NOTIFICATION_LABEL_OUTCOME_UNKNOWN')
        confirmed_at = timestamp(removed['at'])
        # This is evidence from the existing trusted queue's canonical live
        # files, not permission to infer receipt content from file presence.
        # save()/once() create a fresh inode, fsync, then atomically replace;
        # a retained hold requires the COMMENT receipt's later replacement.
        # Copied/retimed proofs are outside that provenance. Coarse/equal
        # post-hold times or clock/order anomalies remain HOLD, never success.
        now = time.time_ns()

        def coherent(metadata):
            require(metadata.st_dev == intended.st_dev and metadata.st_nlink == 1
                    and 0 < metadata.st_mtime_ns <= metadata.st_ctime_ns <= now,
                    'NOTIFICATION_FILE_CHRONOLOGY')

        for _value, metadata in records:
            coherent(metadata)
        require(intended.st_mtime_ns <= received.st_mtime_ns <= retired.st_mtime_ns
                and intended.st_ctime_ns <= received.st_ctime_ns <= retired.st_ctime_ns
                and confirmed_at.timestamp() <= retired.st_mtime_ns / 10 ** 9,
                'NOTIFICATION_FILE_CHRONOLOGY')
        label_intent = directory / 'label-remove-intent.json'
        if label_intent.exists() or label_intent.is_symlink():
            deletion, deleting = journal(label_intent, observed=True)
            coherent(deleting)
            require(set(deletion) == {'at'} and timestamp(deletion['at']) <= confirmed_at,
                    'NOTIFICATION_LABEL_OUTCOME_UNKNOWN')
            require(deleting.st_mtime_ns <= retired.st_mtime_ns
                    and deleting.st_ctime_ns <= retired.st_ctime_ns
                    and timestamp(deletion['at']).timestamp() <= deleting.st_mtime_ns / 10 ** 9,
                    'NOTIFICATION_FILE_CHRONOLOGY')
        hold = directory / 'delivery-hold.json'
        if legacy and (hold.exists() or hold.is_symlink()):
            value, held = journal(hold, observed=True)
            coherent(held)
            require(set(value) == {'reason', 'at'} and isinstance(value['reason'], str)
                    and value['reason'] and timestamp(value['at']) <= confirmed_at,
                    'NOTIFICATION_DELIVERY_UNRESOLVED')
            require(held.st_mtime_ns < received.st_mtime_ns
                    and held.st_ctime_ns < received.st_ctime_ns
                    and timestamp(value['at']).timestamp() <= held.st_mtime_ns / 10 ** 9,
                    'NOTIFICATION_COMMENT_RECONCILIATION_UNCONFIRMED')
        return intent['body']

    def notification_result(self, result, number, generation):
        require(type(result.get('issue')) is int and result['issue'] == number
                and result.get('release_approval') is False, 'NOTIFICATION_RESULT_BINDING')
        if 'generation' in result:
            require(type(result['generation']) is int and result['generation'] == generation,
                    'NOTIFICATION_RESULT_GENERATION')
        for key in ('head', 'base'):
            if key in result:
                require(isinstance(result[key], str) and re.fullmatch('[a-f0-9]{40}', result[key]),
                        'NOTIFICATION_RESULT_REVISION')

    def notifications(self, job):
        """Every generation/final and every extant state, including history.

        Legacy compatibility is explicit: pinned predecessor uses ROOT
        delivery; developer uses nested delivery and an inert ROOT marker.
        Neither role can substitute the other's retirement proof.
        """
        require(re.fullmatch(r'GH-[1-9][0-9]*', job.name), 'NOTIFICATION_ISSUE')
        number = int(job.name[3:])
        marker = job / 'execution.json'
        if not (marker.exists() or marker.is_symlink()):
            result = journal(job / 'final.json')
            require(type(result.get('issue')) is int and result['issue'] == number
                    and isinstance(result.get('head'), str)
                    and (result['head'] == 'UNKNOWN' or re.fullmatch('[a-f0-9]{40}', result['head']))
                    and isinstance(result.get('status'), str) and result['status']
                    and result.get('release_approval') is False
                    and result.get('tests_by_reviewer') == 'NOT_RUN'
                    and isinstance(result.get('protocol'), dict), 'NOTIFICATION_SOURCE_RESULT')
            timestamp(result.get('at'))
            require(not (job / 'notifications').exists()
                    and not any((job / 'attempts').glob('*/notifications')),
                    'NOTIFICATION_ROLE_LAYOUT')
            require(self.delivery(job, legacy=True) == source_body(number, result),
                    'NOTIFICATION_SOURCE_BODY_CHANGED')
            return
        execution = journal(marker)
        generation = execution.get('generation')
        require(set(execution) == {'role', 'generation'} and execution['role'] == 'developer'
                and type(generation) is int and 1 <= generation <= 3, 'EXECUTION_JOURNAL')
        require(wire(journal(job / 'label-removed.json')) == wire(dict(confirmed=False,
                scope='developer-journal-skip-for-legacy-recovery')), 'DEVELOPER_COMPATIBILITY_MARKER')
        # These root delivery records are never created for developer jobs.
        require(not any((job / n).exists() or (job / n).is_symlink() for n in
                        ('comment-intent.json', 'comment-readback.json', 'label-remove-intent.json',
                         'delivery-hold.json', 'notifications')), 'NOTIFICATION_ROLE_LAYOUT')
        attempts = job / 'attempts'
        require(attempts.is_dir() and not attempts.is_symlink(), 'NOTIFICATION_GENERATIONS')
        require({p.name for p in attempts.iterdir()} == {str(g) for g in range(1, generation + 1)},
                'NOTIFICATION_GENERATIONS')
        for g in range(1, generation + 1):
            attempt = attempts / str(g)
            require(attempt.is_dir() and not attempt.is_symlink(), 'NOTIFICATION_GENERATIONS')
            final = journal(attempt / 'final.json')
            self.notification_result(final, number, g)
            require(final.get('state') in ('AcceptedSource', 'Blocked', 'Stopped', 'Rework'),
                    'DEVELOPER_NOT_TERMINAL')
            notices = attempt / 'notifications'
            require(notices.is_dir() and not notices.is_symlink(), 'NOTIFICATION_REQUIRED')
            states = {p.name for p in notices.iterdir()}
            require(final['state'] in states and states <= {'Review', 'AcceptedSource', 'Blocked', 'Stopped', 'Rework'},
                    'NOTIFICATION_REQUIRED')
            for state in sorted(states):
                body = self.delivery(notices / state)
                prefix = f'snq-v1 GH-{number}\n## Symphony developer result\n\n'
                require(body.startswith(prefix) and len(body.encode()) <= 50000, 'NOTIFICATION_DEVELOPER_BODY')
                result = journal_json(body[len(prefix):])
                self.notification_result(result, number, g)
                require(result.get('state') == state
                        and body == prefix + json.dumps(result, ensure_ascii=False, sort_keys=True),
                        'NOTIFICATION_DEVELOPER_BODY')
                if state == final['state']:
                    expected = final
                else:
                    require(state == 'Review', 'NOTIFICATION_HISTORICAL_RESULT')
                    candidate = journal(attempt / 'candidate.json')
                    require(type(candidate.get('issue')) is int and candidate['issue'] == number
                            and type(candidate.get('generation')) is int and candidate['generation'] == g,
                            'NOTIFICATION_HISTORICAL_RESULT')
                    expected = dict(state='Review', issue=number, release_approval=False,
                                    **{k: candidate[k] for k in ('head', 'base', 'artifact', 'tests')})
                require(wire(result) == wire(expected), 'NOTIFICATION_RESULT_CHANGED')

    def rollback_quiet(self):
        try:
            self.quiet()
        except BaseException:
            # A previous interrupted operator may own a closed gate while the
            # queue is still running. A notification HOLD must let that queue
            # recover; never reopen an unowned pause or a stopped service.
            receipt = self.backup / 'intake.json'
            if receipt.exists() and not self.ctl.stopped():
                trusted(receipt, self.uid)
                if json.loads(read(receipt)).get('phase') in ('intent', 'paused'):
                    self.intake(release=True)
            raise

    def reviews_applied(self):
        """Read-only verification of every historical linked disposition.

        Retirement of the source label precedes downstream application. A
        marker alone is also insufficient: its exact inputs and every sink
        must agree. Reconciliation remains the queue's job, never root's.
        """
        accepted, linked, applications = {}, set(), set()
        for path in sorted((self.state / 'review-links').glob('*')):
            link_raw = read(path)
            link = json.loads(link_raw)
            require(isinstance(link, dict) and set(link) ==
                    {'issue', 'generation', 'review_issue', 'head', 'base'}, 'REVIEW_LINK')
            issue, generation, review = (link[k] for k in ('issue', 'generation', 'review_issue'))
            require(type(issue) is int and 0 < issue < 2147483647 and type(review) is int
                    and 0 < review < 2147483647 and issue != review and type(generation) is int
                    and 1 <= generation <= 3 and path.name == f'GH-{review}.json'
                    and all(re.fullmatch('[a-f0-9]{40}', str(link[k])) for k in ('head', 'base')),
                    'REVIEW_LINK')
            linked.add(review)
            require((issue, generation) not in applications, 'DUPLICATE_REVIEW_APPLICATION')
            applications.add((issue, generation))
            source = self.state / 'jobs' / f'GH-{review}'
            result = json.loads(read(source / 'final.json'))
            marker = json.loads(read(source / 'linked-review-applied.json'))
            require(type(result.get('issue')) is int and result['issue'] == review
                    and result.get('head') == link['head'] and result.get('release_approval') is False
                    and marker == dict(source_result_sha256=sha(wire(result)), link_sha256=sha(link_raw)),
                    'LINKED_REVIEW_NOT_APPLIED')
            job = self.state / 'jobs' / f'GH-{issue}'
            execution = json.loads(read(job / 'execution.json'))
            require(execution.get('role') == 'developer' and type(execution.get('generation')) is int
                    and generation <= execution['generation'] <= 3, 'REVIEW_GENERATION')
            attempt = job / 'attempts' / str(generation)
            candidate = json.loads(read(attempt / 'candidate.json'))
            require(type(candidate.get('issue')) is int and candidate['issue'] == issue
                    and type(candidate.get('generation')) is int and candidate['generation'] == generation
                    and isinstance(candidate.get('author_thread'), str) and candidate['author_thread']
                    and all(candidate.get(k) == link[k] for k in ('head', 'base')), 'REVIEW_CANDIDATE')
            disposition = json.loads(read(attempt / 'acceptance.json'))
            final = json.loads(read(attempt / 'final.json'))
            require(wire(disposition) == wire(final) and type(disposition.get('issue')) is int
                    and disposition['issue'] == issue and type(disposition.get('generation')) is int
                    and disposition['generation'] == generation
                    and all(disposition.get(k) == link[k] for k in ('head', 'base'))
                    and disposition.get('release_approval') is False, 'ACCEPTANCE_NOT_CONVERGED')
            expected = self.disposition(candidate, result, review)
            require(wire(disposition) == wire(dict(expected, issue=issue, generation=generation)),
                    'ACCEPTANCE_NOT_CONVERGED')
            if disposition['state'] == 'AcceptedSource':
                accepted.setdefault(issue, {})[generation] = disposition
        # Every acceptance needs the originating applied review; every current
        # artifact must be exactly the newest *accepted* generation. A later
        # Rework legitimately retains an earlier accepted artifact.
        for job in sorted((self.state / 'jobs').glob('GH-*')):
            if (job / 'linked-review-applied.json').exists():
                require(int(job.name[3:]) in linked, 'ORPHAN_REVIEW_APPLICATION')
            for attempt in job.glob('attempts/*'):
                if (attempt / 'acceptance.json').exists():
                    require((int(job.name[3:]), int(attempt.name)) in applications, 'ORPHAN_ACCEPTANCE')
                elif (attempt / 'final.json').exists():
                    require(json.loads(read(attempt / 'final.json')).get('state') != 'AcceptedSource',
                            'ACCEPTANCE_NOT_CONVERGED')
        expected_pointers = {f'GH-{issue}.json': values[max(values)] for issue, values in accepted.items()}
        actual_pointers = {p.name: json.loads(read(p)) for p in (self.state / 'accepted').glob('*')}
        require(wire(actual_pointers) == wire(expected_pointers), 'ACCEPTED_ARTIFACT_NOT_CONVERGED')

    def disposition(self, candidate, source, number):
        head, base = candidate['head'], candidate['base']
        if source.get('status') != SUCCESS:
            return dict(state='Blocked', head=head, base=base, release_approval=False,
                        reason='INDEPENDENT_REVIEW_INCOMPLETE')
        matches = re.findall(r'^```snq-verdict\s*\n(.*?)\n```\s*$', source.get('review_text', ''), re.M | re.S)
        verdict = json.loads(matches[0]) if len(matches) == 1 else {}
        if verdict:
            require(isinstance(verdict, dict) and set(verdict) == {'head_sha', 'base_sha', 'verdict'},
                    'REVIEW_VERDICT')
        review = dict(issue=number, head=verdict.get('head_sha', head if not verdict else None),
                      base=verdict.get('base_sha', base if not verdict else None),
                      verdict=verdict.get('verdict', 'blocked'),
                      reviewer_thread=source.get('protocol', {}).get('thread_id'), source_status=source['status'])
        require(review['head'] == head and review['base'] == base
                and isinstance(review['reviewer_thread'], str) and review['reviewer_thread']
                and review['reviewer_thread'] != candidate.get('author_thread'), 'REVIEW_STALE_OR_SELF')
        state = 'Rework' if review['verdict'] == 'rework' else 'Blocked'
        artifact, tests, required = (candidate.get(k, {}) for k in ('artifact', 'tests', 'required_tests'))
        if (review['verdict'] == 'accepted' and required
                and all(tests.get(t, {}).get('exit_code') == 0 for t in required)
                and artifact.get('repo') == 'pupkinson/SymphonyNext' and artifact.get('head') == head
                and re.fullmatch('[a-f0-9]{40}', str(artifact.get('tree')))
                and type(artifact.get('pr')) is int and 0 < artifact['pr'] < 2147483647):
            state = 'AcceptedSource'
        value = dict(state=state, head=head, base=base, release_approval=False, review=review)
        if state == 'AcceptedSource':
            value['artifact'] = artifact
        return value

    def seal(self):
        # Hash durable control records only; never auth/config/cache/model files.
        items = {}
        for top in ('jobs', 'reservations', 'accepted', 'review-links'):
            for p in sorted((self.state / top).rglob('*')):
                require(not p.is_symlink(), 'STATE_SYMLINK')
                rel = p.relative_to(self.state)
                if p.is_file() and not set(rel.parts) & {'run', 'cache', 'config', 'data'}:
                    require(p.name not in ('auth.json', 'credentials.json', 'runtime.env'), 'SECRET_IN_JOURNAL')
                    items[rel.as_posix()] = sha(read(p, 8388608))
        return sha(json.dumps(items, sort_keys=True).encode())

    def record(self, value):
        save(self.backup / 'record.json', value)

    def intake(self, release=False):
        """Revoke only new mkdir admission; existing job directories drain.

        The actual 7fa0ee predecessor and candidate both claim a new source
        job with mkdir under jobs, before any auth/model/budget. Rollback
        separately pins the disabled developer policy (including generations).
        No dispatcher-specific pause API or ignored lock is assumed.
        """
        jobs = self.state / 'jobs'
        require(not any(p.is_symlink() for p in (jobs, *jobs.parents)), 'STATE_SYMLINK')
        receipt = self.backup / 'intake.json'
        fd = os.open(jobs, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            s = os.fstat(fd)
            identity = dict(device=s.st_dev, inode=s.st_ino, uid=s.st_uid, gid=s.st_gid, mode=0o700)
            mode = stat.S_IMODE(s.st_mode)
            if receipt.exists():
                trusted(receipt, self.uid)
                value = json.loads(read(receipt))
                require(value.get('head') == self.m['head'] and value.get('jobs') == identity
                        and value.get('phase') in ('intent', 'paused', 'released'), 'INTAKE_RECEIPT_CHANGED')
            else:
                require(not release and mode == 0o700, 'INTAKE_PAUSE_UNOWNED')
                value = dict(head=self.m['head'], jobs=identity, phase='released', events=[])
            require(mode in (0o500, 0o700) and jobs.stat().st_ino == s.st_ino, 'INTAKE_DIRECTORY_CHANGED')
            if release:
                require(value['phase'] != 'released' or mode == 0o700, 'INTAKE_PAUSE_UNOWNED')
                os.fchmod(fd, 0o700)
                os.fsync(fd)
                value['phase'] = 'released'
            else:
                self.ctl.admission_identity(jobs)
                value['phase'] = 'intent'
                value['events'].append(dict(phase='intent', at=time.time()))
                save(receipt, value)  # Recovery owns the gate even if killed next.
                os.fchmod(fd, 0o500)  # No permissions added; children stay writable.
                os.fsync(fd)
                self.ctl.admission_probe(jobs)
                require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o500
                        and jobs.stat().st_ino == s.st_ino, 'ADMISSION_PAUSE_UNCONFIRMED')
                value['phase'] = 'paused'
            value['events'].append(dict(phase=value['phase'], at=time.time()))
            save(receipt, value)
        finally:
            os.close(fd)

    def drain(self):
        deadline = time.monotonic() + self.drain_seconds
        while True:
            try:
                self.quiet()
                require(self.ctl.idle(), 'QUEUE_NOT_DRAINED')
                self.ctl.admission_probe(self.state / 'jobs')
                require(stat.S_IMODE((self.state / 'jobs').stat().st_mode) == 0o500,
                        'ADMISSION_PAUSE_UNCONFIRMED')
                return
            except (Hold, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                if time.monotonic() >= deadline:
                    reason = str(exc) if isinstance(exc, Hold) else type(exc).__name__
                    raise Hold('INTAKE_PAUSED_WORK_NOT_DRAINED:' + reason) from None
                time.sleep(0.2)

    def prior(self):
        trusted(self.backup, self.uid)
        value = json.loads(read(self.backup / 'record.json'))
        require(value.get('head') == self.m['head'] and value.get('tree') == self.m['tree']
                and set(value.get('files', {})) == set(self.predecessor), 'ROLLBACK_RECORD')
        for name, expected in self.predecessor.items():
            require(sha(read(self.backup / name)) == expected
                    and value['files'][name]['sha256'] == expected, 'ROLLBACK_BYTES_CHANGED')
        return value

    def make_backup(self):
        self.backup.parent.mkdir(mode=0o700, exist_ok=True)
        trusted(self.backup.parent, self.uid)
        self.backup.mkdir(mode=0o700)
        files = {}
        for name, expected in self.predecessor.items():
            p = self.install / name
            raw = read(p)
            require(sha(raw) == expected, 'INSTALLED_PREDECESSOR_CHANGED')
            s = p.stat()
            files[name] = dict(sha256=expected, mode=stat.S_IMODE(s.st_mode), uid=s.st_uid, gid=s.st_gid)
            atomic(self.backup / name, raw, 0o600)
        value = dict(head=self.m['head'], tree=self.m['tree'], phase='prepared', files=files)
        self.record(value)
        return value

    def restore(self, value):
        require(self.ctl.stopped(), 'SERVICE_NOT_STOPPED')
        self.quiet()
        for name in PAYLOAD | set(self.predecessor):
            p = self.install / name
            if p.exists() or p.is_symlink():
                allowed = {v for v in (self.predecessor.get(name), self.m['payload'].get(name)) if v}
                require(sha(read(p)) in allowed, 'UNKNOWN_INSTALLED_BYTES')
        for name, metadata in value['files'].items():
            atomic(self.install / name, read(self.backup / name), metadata['mode'], metadata['uid'], metadata['gid'])
        for name in ('execution.py', 'executor-policy.json'):
            if (self.install / name).exists():
                (self.install / name).unlink()
        require(self.matches(self.predecessor), 'ROLLBACK_READBACK_FAILED')
        self.ctl.start()
        require(self.ctl.healthy(), 'ROLLBACK_START_FAILED')
        value.update(phase='rolled_back', status='ROLLED_BACK', state_sha256=self.seal())
        self.record(value)
        if (self.backup / 'intake.json').exists():
            self.intake(release=True)
        return dict(status='ROLLED_BACK', head=self.m['head'], state_sha256=value['state_sha256'])

    def apply(self):
        self.package_check()
        if self.backup.exists():
            value = self.prior()
            require(value.get('phase') == 'applied' and self.matches(self.m['payload'])
                    and self.matches({n: self.predecessor[n] for n in ('WORKFLOW.md', 'tmux.conf')})
                    and self.ctl.healthy(), 'UPDATE_ALREADY_ATTEMPTED_USE_ROLLBACK')
            self.quiet()
            if (self.backup / 'intake.json').exists():
                self.intake(release=True)
            return dict(status='APPLIED_EXECUTOR_DISABLED', head=self.m['head'])
        self.check(idle=False)
        value = self.make_backup()  # Durable predecessor before the first stop.
        try:
            self.intake()
            self.drain()
        except BaseException:
            if (self.backup / 'intake.json').exists() and not self.ctl.stopped():
                self.intake(release=True)
            raise
        try:
            self.ctl.stop()  # The real predecessor's mkdir gate is still closed.
            require(self.ctl.stopped(), 'SERVICE_NOT_STOPPED')
            self.quiet()
            before = self.seal()
            value.update(phase='replacing', state_sha256=before)
            self.record(value)
            for name, raw in self.payload.items():
                atomic(self.install / name, raw)
            require(self.matches(self.m['payload']) and self.matches({n: self.predecessor[n]
                    for n in ('WORKFLOW.md', 'tmux.conf')}), 'INSTALLED_READBACK_FAILED')
            require(self.seal() == before, 'STATE_CHANGED_DURING_UPDATE')
            self.ctl.start()
            require(self.ctl.healthy(), 'CANDIDATE_START_FAILED')
            require(self.seal() == before, 'STATE_CHANGED_AT_STARTUP')
            value.update(phase='applied', status='APPLIED_EXECUTOR_DISABLED')
            self.record(value)
            self.intake(release=True)
            return dict(status='APPLIED_EXECUTOR_DISABLED', head=self.m['head'], state_sha256=before)
        except BaseException:
            # Candidate startup/recovery is allowed to finish, never killed
            # because a preceding dashboard read happened to be idle.
            if not self.ctl.stopped():
                self.intake()
                self.drain()
                self.ctl.stop()
            self.restore(value)
            raise Hold('START_FAILED_ROLLED_BACK') from None

    def rollback(self):
        self.package_check()
        value = self.prior()
        if value.get('phase') == 'rolled_back':
            require(self.matches(self.predecessor) and self.ctl.healthy(), 'ROLLBACK_READBACK_FAILED')
            self.rollback_quiet()
            if (self.backup / 'intake.json').exists():
                self.intake(release=True)
            return dict(status='ROLLED_BACK', head=self.m['head'])
        self.rollback_quiet()
        # Refuse changed policy/static files before stopping a healthy service.
        for name in PAYLOAD | set(self.predecessor):
            p = self.install / name
            if p.exists() or p.is_symlink():
                require(sha(read(p)) in {self.m['payload'].get(name), self.predecessor.get(name)},
                        'UNKNOWN_INSTALLED_BYTES')
        was_stopped = self.ctl.stopped()
        try:
            self.intake()
            if not was_stopped:
                self.drain()
                self.ctl.stop()
        except BaseException:
            if not self.ctl.stopped() and (self.backup / 'intake.json').exists():
                self.intake(release=True)
            raise
        return self.restore(value)


def main():
    os.umask(0o077)
    require(os.geteuid() == 0 and socket.gethostname() == '1c-db', 'ROOT_ON_1C_DB_REQUIRED')
    require(len(sys.argv) == 2 and sys.argv[1] in ('check', 'apply', 'rollback'), 'MODE_REQUIRED')
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt('UPDATE_INTERRUPTED')
    signal.signal(signal.SIGTERM, interrupted)
    package = Path(__file__).resolve().parent
    trusted(INSTALL, 0)
    lock = os.open(INSTALL / '.update.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        update = Updater(package, INSTALL, STATE, Controller())
        result = getattr(update, sys.argv[1])()
        print(json.dumps(result, sort_keys=True))
    finally:
        os.close(lock)


if __name__ == '__main__':
    try:
        main()
    except (Hold, OSError, ValueError, KeyError, TypeError, AttributeError, SyntaxError,
            subprocess.SubprocessError, KeyboardInterrupt) as exc:
        print(json.dumps({'status': 'HOLD', 'reason': str(exc) if isinstance(exc, Hold) else type(exc).__name__}), file=sys.stderr)
        raise SystemExit(2)
