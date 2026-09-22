"""Durable, fail-closed observation only. No start, restart, network or model API.

The operator-owned adapter supplies current service/runtime/exit/readback evidence.
An idle slot, a hook marker and a published PR are NOT normal-turn attestation.
Python 3.10+, Linux/POSIX filesystem. Construct once in a NEW private operation dir.
"""
import copy
import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import tempfile
import time


class ObserverError(Exception):
    """A bounded diagnostic code, never a raw provider response."""


def observer_timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('timestamp')
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp_timezone')
    return parsed.timestamp()


class PilotObserver:
    """One observer; durable snapshots survive signals, never resume model work.

    Every successful transition fsyncs both the new file and its parent directory.
    A read/parse failure retains the last GOOD observation, clearly marked stale.
    Only fresh, internally consistent snapshots can advance idle reconciliation.
    """
    def __init__(self, checkpoint, *, operation, source, issue_id='2',
                 clock=time.monotonic, wall=time.time, emit=None,
                 idle_grace=15, startup_limit=120, wall_limit=1800,
                 progress_interval=15, stale_after=30):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', operation):
            raise ObserverError('invalid_operation')
        if not re.fullmatch(r'[0-9a-f]{40}', source) or not re.fullmatch(r'[1-9][0-9]{0,10}', issue_id):
            raise ObserverError('invalid_source_or_issue')
        limits = (idle_grace, startup_limit, wall_limit, progress_interval, stale_after)
        if any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0 for n in limits):
            raise ObserverError('invalid_limit')
        self.path = Path(checkpoint)
        for p in (self.path, *self.path.parents):
            if p.is_symlink():
                raise ObserverError('checkpoint_symlink')
        parent = self.path.parent.stat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
                or stat.S_IMODE(parent.st_mode) & 0o077):
            raise ObserverError('checkpoint_parent_not_private')
        self.lock = None
        self.clock, self.wall, self.emit = clock, wall, emit
        self.idle_grace, self.startup_limit = idle_grace, startup_limit
        self.wall_limit, self.progress_interval, self.stale_after = wall_limit, progress_interval, stale_after
        self.begun = clock()
        self.last_progress = -math.inf
        self.last_generated = None
        self.idle_since = None
        self.state = dict(schema='symphony-next-observer/v1', operation=operation,
            source_head=source, issue_id=issue_id, sequence=0, phase='prepared',
            start_intent=False, service_start_confirmed=False, invocation_id=None,
            service_started_wall=None, agent_launch_observed=False, session_observed=False,
            worker_session_started=False, session_fingerprint=None,
            worker_exit_observed=False, hook_observed=False, normal_turn_completion='UNKNOWN',
            last_counts=None, last_event_at=None, last_valid_api_at=None,
            observed_token_counts={}, idle_samples=0, observation_failures=0,
            artifact_verification='NOT_RUN', termination_reason=None, accepted=False,
            persistence_error=False, progress_output_error=False)
        try:
            fd = os.open(str(self.path)+'.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            self.lock = fd
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.geteuid():
                raise ObserverError('checkpoint_lock_invalid')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ObserverError('observer_already_owned') from None
            if self.path.exists() or self.path.is_symlink():
                raise ObserverError('checkpoint_exists_no_reinitialization')
            self._save()
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None

    def snapshot(self):
        return copy.deepcopy(self.state)

    def _save(self):
        if self.lock is None:
            raise ObserverError('observer_closed')
        # Keep a signal from interrupting atomic replacement halfway through.
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM, signal.SIGHUP})
        name = None
        try:
            self.state['sequence'] += 1
            self.state['captured_at'] = datetime.datetime.fromtimestamp(self.wall(), datetime.timezone.utc).isoformat()
            self.state['elapsed_seconds'] = max(0, self.clock() - self.begun)
            self.state['seconds_remaining'] = max(0, self.wall_limit - self.state['elapsed_seconds'])
            if self.path.is_symlink():
                raise ObserverError('checkpoint_symlink')
            fd, name = tempfile.mkstemp(prefix='.observer-', dir=self.path.parent)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(self.state, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
                stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(name, self.path)
            name = None
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            self.state['persistence_error'] = True
            raise
        finally:
            if name is not None:
                try: os.unlink(name)
                except FileNotFoundError: pass
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)

    def _commit(self):
        self._save()
        now = self.clock()
        if self.emit is not None and now - self.last_progress >= self.progress_interval:
            event_age = None
            if self.state['last_event_at']:
                event_age = max(0, self.wall() - observer_timestamp(self.state['last_event_at']))
            event = dict(status='PILOT_PROGRESS', issue_id=self.state['issue_id'],
                phase=self.state['phase'], counts=self.state['last_counts'],
                last_event_age_seconds=event_age, elapsed_seconds=self.state['elapsed_seconds'],
                seconds_remaining=self.state['seconds_remaining'],
                observation_failures=self.state['observation_failures'])
            try:
                self.emit(event)
            except (BrokenPipeError, OSError):
                self.state['progress_output_error'] = True
                self._save()
            self.last_progress = now

    def start_requested(self):
        if self.state['start_intent']:
            raise ObserverError('start_already_requested')
        self.begun = self.clock()
        self.state['start_intent'] = True
        self.state['phase'] = 'service_start_requested'
        self._commit()

    def service_started(self, invocation):
        if not isinstance(invocation, str) or not re.fullmatch(r'[0-9a-f]{32}', invocation):
            raise ObserverError('service_invocation_unconfirmed')
        if self.state['invocation_id'] not in (None, invocation):
            raise ObserverError('service_identity_changed')
        self.state.update(service_start_confirmed=True, invocation_id=invocation,
                          service_started_wall=self.wall(), phase='awaiting_dispatch')
        self._commit()

    def finish(self, reason):
        if not isinstance(reason, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,99}', reason):
            reason = 'observer_error'
        # A later Ctrl+C during finalization cannot erase an observed terminal event.
        if self.state['termination_reason'] is None:
            self.state['termination_reason'] = reason
        self.state['phase'] = 'observation_ended'
        self._commit()
        return self.state['termination_reason']

    def _unavailable(self):
        self.state['observation_failures'] += 1
        self.state['idle_samples'] = 0
        self.idle_since = None
        self.state['phase'] = 'observation_degraded'
        self._commit()
        return 'observation_unavailable'

    def sample(self, service, runtime, *, agent_started, hook_finished, worker_alive):
        if self.state['termination_reason']:
            return self.state['termination_reason']
        now = self.clock()
        if now - self.begun >= self.wall_limit:
            return self.finish('wall_deadline_reached')
        if type(agent_started) is not bool or type(hook_finished) is not bool:
            return self._unavailable()
        self.state['agent_launch_observed'] |= agent_started
        self.state['hook_observed'] |= hook_finished
        if not isinstance(service, dict) or service.get('ActiveState') not in ('active', 'activating', 'inactive', 'failed', 'deactivating'):
            return self._unavailable()
        if service['ActiveState'] in ('inactive', 'failed') and service.get('MainPID') == '0':
            return self.finish('service_ended')
        if not self.state['service_start_confirmed']:
            return self._unavailable()
        if service.get('InvocationID') != self.state['invocation_id']:
            return self.finish('service_identity_changed')
        if not self.state['agent_launch_observed'] and now - self.begun >= self.startup_limit:
            return self.finish('no_dispatch_within_startup_limit')
        try:
            if not isinstance(runtime, dict): raise ValueError('runtime')
            generated = observer_timestamp(runtime.get('generated_at'))
            if (generated < self.state['service_started_wall'] or generated > self.wall()+5
                    or self.wall()-generated > self.stale_after
                    or (self.last_generated is not None and generated <= self.last_generated)):
                raise ValueError('stale_snapshot')
            counts = runtime['counts']
            for name in ('running', 'blocked', 'retrying'):
                count = counts[name]
                if type(count) is not int or not 0 <= count <= 1000:
                    raise ValueError('counts')
                rows = runtime[name]
                if not isinstance(rows, list) or len(rows) != count:
                    raise ValueError('count_rows_mismatch')
            running = runtime['running']
        except (KeyError, TypeError, ValueError, OverflowError):
            return self._unavailable()
        if len(running) > 1 or any(not isinstance(row, dict) or row.get('issue_id') != self.state['issue_id'] for row in running):
            return self.finish('unexpected_worker')
        if worker_alive is not True and worker_alive is not False:
            return self._unavailable()
        if running:
            session = running[0].get('session_id')
            if not isinstance(session, str) or not 1 <= len(session) <= 256:
                return self._unavailable()
        self.state['last_counts'] = {n: counts[n] for n in ('running', 'blocked', 'retrying')}
        self.state['last_valid_api_at'] = runtime['generated_at']
        self.state['observation_failures'] = 0
        self.last_generated = generated
        if running:
            session = running[0].get('session_id')
            if not isinstance(session, str) or not 1 <= len(session) <= 256:
                return self._unavailable()
            fingerprint = hashlib.sha256(session.encode()).hexdigest()
            if self.state['session_fingerprint'] not in (None, fingerprint):
                return self.finish('unexpected_session')
            self.state.update(session_fingerprint=fingerprint, session_observed=True,
                              worker_session_started=True)
            event = running[0].get('last_event_at')
            try:
                when = observer_timestamp(event)
                old = observer_timestamp(self.state['last_event_at']) if self.state['last_event_at'] else -math.inf
                if old <= when <= self.wall()+5 and when >= self.state['service_started_wall']:
                    self.state['last_event_at'] = event
            except (TypeError, ValueError, OverflowError):
                pass
        # These are runtime counters, not a monetary cost or model-identity proof.
        totals = runtime.get('codex_totals')
        if isinstance(totals, dict) and self.state['session_observed']:
            for name in ('input_tokens', 'output_tokens', 'total_tokens'):
                value = totals.get(name)
                if type(value) is int and 0 <= value < 2**63:
                    self.state['observed_token_counts'][name] = max(value, self.state['observed_token_counts'].get(name, 0))
        if counts['blocked']:
            return self.finish('worker_blocked')
        if counts['retrying']:
            return self.finish('worker_retry_requested_no_relaunch')
        if not running and not worker_alive and (self.state['agent_launch_observed'] or self.state['session_observed']):
            if self.idle_since is None: self.idle_since = now
            self.state['idle_samples'] += 1
            self.state['phase'] = 'confirming_worker_exit'
            if self.state['idle_samples'] >= 2 and now-self.idle_since >= self.idle_grace:
                self.state['worker_exit_observed'] = True
                self.state['phase'] = 'reconciling_artifact'
                self._commit()
                return 'idle_requires_reconciliation'
        else:
            self.idle_since = None
            self.state['idle_samples'] = 0
            self.state['phase'] = 'worker_active' if running or worker_alive else 'awaiting_dispatch'
        self._commit()
        return None

    def reconcile(self, artifact):
        if not self.state['worker_exit_observed']:
            raise ObserverError('exit_not_observed')
        if not isinstance(artifact, dict):
            return self.finish('artifact_readback_unavailable')
        if artifact.get('admission_label_present') is not False:
            return self.finish('worker_exit_admission_remaining')
        required = dict(artifact_scope='ONE_REPORT_ONE_COMMIT', draft_pr=True,
            pr_open=True, pr_merged=False, issue_open=True, base=self.state['source_head'],
            parent=self.state['source_head'], source_verified=True)
        matches = all(type(artifact.get(k)) is type(v) and artifact.get(k) == v for k,v in required.items())
        matches &= type(artifact.get('pr_number')) is int and artifact['pr_number'] > 0
        matches &= all(isinstance(artifact.get(k), str) and re.fullmatch(r'[0-9a-f]{40}', artifact[k]) for k in ('head','tree'))
        if not matches:
            self.state['artifact_verification'] = 'UNVERIFIED'
            return self.finish('worker_exit_artifact_unverified')
        self.state['artifact_verification'] = 'ONE_REPORT_ONE_COMMIT'
        self.state['artifact'] = {k: artifact[k] for k in ('head','tree','base','parent','pr_number')}
        if not self.state['session_observed']:
            return self.finish('worker_exit_session_unattested')
        return self.finish('worker_finished_awaiting_acceptance' if self.state['hook_observed'] else 'worker_exited_without_hook')
