"""Offline regressions. No GitHub, model, systemd or server calls."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'bootstrap/pilot_observer.py'
BASE = '30b29e7970d64ecadf0e5c1d8d5e3b1230952ba8'
INVOCATION = 'a' * 32
START = 1790109600.0


def module():
    if not MODULE.exists():
        raise AssertionError('observer repair is not implemented')
    name = 'observer_under_test'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, MODULE)
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[name] = loaded
        spec.loader.exec_module(loaded)
    return sys.modules[name]


class Clock:
    def __init__(self): self.n = 0.0
    def mono(self): return self.n
    def wall(self): return START + self.n
    def advance(self, n=3): self.n += n


def runtime(clock, running=True, **extra):
    stamp = dt.datetime.fromtimestamp(clock.wall(), dt.timezone.utc).isoformat()
    rows = [dict(issue_id='2', issue_identifier='GH-2', session_id='session-one',
                 turn_count=1, last_event_at=stamp, last_event='notification')] if running else []
    data = dict(generated_at=stamp, counts=dict(running=len(rows), blocked=0, retrying=0),
                running=rows, blocked=[], retrying=[],
                codex_totals=dict(input_tokens=100, output_tokens=20, total_tokens=120))
    data.update(extra)
    return data


def service(active=True, invocation=INVOCATION):
    return dict(MainPID='42' if active else '0', InvocationID=invocation if active else '',
                ActiveState='active' if active else 'inactive', SubState='running' if active else 'dead')


def artifact(**extra):
    data = dict(admission_label_present=False, artifact_scope='ONE_REPORT_ONE_COMMIT',
                draft_pr=True, pr_open=True, pr_merged=False, issue_open=True,
                pr_number=6, head='b'*40, base=BASE, tree='c'*40,
                parent=BASE, source_verified=True)
    data.update(extra)
    return data


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = Clock()
        self.progress = []
        self.path = Path(self.tmp.name) / 'observer-state.json'
        self.o = self.m.PilotObserver(self.path, operation='fixture-one', source=BASE,
            clock=self.clock.mono, wall=self.clock.wall, emit=self.progress.append,
            idle_grace=6, startup_limit=12, wall_limit=120, progress_interval=3)
        self.addCleanup(self.o.close)
        self.o.start_requested()
        self.o.service_started(INVOCATION)

    def sample(self, running=True, hook=False, alive=None, data='default', st=None):
        if data == 'default': data = runtime(self.clock, running)
        if alive is None: alive = running
        return self.o.sample(st or service(), data, agent_started=True,
                             hook_finished=hook, worker_alive=alive)

    def idle(self, hook=False):
        self.sample()
        for _ in range(3):
            self.clock.advance()
            reason = self.sample(False, hook=hook, alive=False)
        return reason

    def test_invalid_session_keeps_last_good_snapshot_time(self):
        self.sample()
        previous = self.o.snapshot()['last_valid_api_at']
        self.clock.advance()
        data = runtime(self.clock)
        data['running'][0]['session_id'] = None
        self.assertEqual(self.sample(data=data), 'observation_unavailable')
        self.assertEqual(self.o.snapshot()['last_valid_api_at'], previous)

    def test_late_preparation_does_not_consume_startup_budget(self):
        self.o.close()
        self.clock.advance(110)
        target = self.path.parent/'other-state.json'
        other = self.m.PilotObserver(target, operation='late', source=BASE,
                clock=self.clock.mono,wall=self.clock.wall,startup_limit=12,wall_limit=120)
        try:
            self.clock.advance(20)
            other.start_requested(); other.service_started(INVOCATION)
            self.assertIsNone(other.sample(service(),runtime(self.clock,False),
                agent_started=False,hook_finished=False,worker_alive=False))
        finally: other.close()

    def test_repeated_start_cannot_reset_budget(self):
        with self.assertRaises(self.m.ObserverError): self.o.start_requested()

    def test_running_checkpoint_is_saved_before_next_poll(self):
        self.sample()
        saved = json.loads(self.path.read_text())
        self.assertTrue(saved['session_observed'])
        self.assertEqual(saved['last_counts']['running'], 1)
        self.assertEqual(saved['observed_token_counts']['total_tokens'], 120)

    def test_interrupt_preserves_observed_start(self):
        self.sample()
        self.o.finish('operator_interrupted')
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['termination_reason'], 'operator_interrupted')
        self.assertTrue(saved['session_observed'])
        self.assertNotEqual(saved['phase'], 'not_started')
        self.assertEqual(saved['observed_token_counts']['total_tokens'], 120)

    def test_idle_without_hook_is_bounded_not_success(self):
        self.assertEqual(self.idle(), 'idle_requires_reconciliation')
        self.o.reconcile(artifact())
        saved = self.o.snapshot()
        self.assertEqual(saved['termination_reason'], 'worker_exited_without_hook')
        self.assertEqual(saved['normal_turn_completion'], 'UNKNOWN')
        self.assertFalse(saved['accepted'])
        self.assertLess(self.clock.n, 120)

    def test_hook_with_running_agent_does_not_finish(self):
        self.assertIsNone(self.sample(hook=True))
        self.assertIsNone(self.o.snapshot()['termination_reason'])

    def test_hook_and_verified_artifact_is_only_candidate(self):
        self.assertEqual(self.idle(hook=True), 'idle_requires_reconciliation')
        self.o.reconcile(artifact())
        self.assertEqual(self.o.snapshot()['termination_reason'], 'worker_finished_awaiting_acceptance')
        self.assertFalse(self.o.snapshot()['accepted'])

    def test_missing_artifact_is_not_success(self):
        self.idle()
        self.o.reconcile(artifact(artifact_scope='NOT_VERIFIED', draft_pr='NOT_FOUND'))
        self.assertEqual(self.o.snapshot()['termination_reason'], 'worker_exit_artifact_unverified')

    def test_wrong_base_is_not_success(self):
        self.idle(hook=True)
        self.o.reconcile(artifact(base='d'*40))
        self.assertEqual(self.o.snapshot()['termination_reason'], 'worker_exit_artifact_unverified')

    def test_remaining_admission_does_not_relaunch(self):
        self.idle()
        self.o.reconcile(artifact(admission_label_present=True))
        self.assertEqual(self.o.snapshot()['termination_reason'], 'worker_exit_admission_remaining')

    def test_zero_before_any_start_is_not_completion(self):
        self.o.state['agent_launch_observed'] = False
        for _ in range(4):
            self.clock.advance()
            reason = self.o.sample(service(), runtime(self.clock, False),
                agent_started=False, hook_finished=False, worker_alive=False)
        self.assertEqual(reason, 'no_dispatch_within_startup_limit')
        self.assertFalse(self.o.snapshot()['session_observed'])

    def test_agent_marker_without_session_is_unattested_exit(self):
        for _ in range(3):
            self.clock.advance()
            reason = self.sample(False, alive=False)
        self.assertEqual(reason, 'idle_requires_reconciliation')
        self.o.reconcile(artifact())
        self.assertEqual(self.o.snapshot()['termination_reason'], 'worker_exit_session_unattested')

    def test_changed_invocation_stops_without_acceptance(self):
        self.sample()
        reason = self.sample(st=service(invocation='d'*32))
        self.assertEqual(reason, 'service_identity_changed')
        self.assertTrue(self.o.snapshot()['session_observed'])

    def test_stale_snapshot_does_not_count_as_idle(self):
        self.sample()
        stale = runtime(self.clock, False)
        self.clock.advance(40)
        reason = self.sample(False, alive=False, data=stale)
        self.assertEqual(reason, 'observation_unavailable')
        self.assertEqual(self.o.snapshot()['last_counts']['running'], 1)

    def test_duplicate_snapshot_does_not_advance_idle(self):
        self.sample()
        self.clock.advance()
        old = runtime(self.clock, False)
        self.sample(False, alive=False, data=old)
        self.clock.advance(10)
        self.assertEqual(self.sample(False, alive=False, data=old), 'observation_unavailable')

    def test_incomplete_counts_not_treated_as_zero(self):
        self.sample()
        self.clock.advance()
        d = runtime(self.clock, False)
        del d['counts']['retrying']
        self.assertEqual(self.sample(False, data=d), 'observation_unavailable')
        self.assertEqual(self.o.snapshot()['last_counts']['running'], 1)

    def test_unexpected_issue_stops(self):
        d = runtime(self.clock)
        d['running'][0]['issue_id'] = '9'
        self.assertEqual(self.sample(data=d), 'unexpected_worker')

    def test_second_session_stops(self):
        self.sample()
        self.clock.advance()
        d = runtime(self.clock)
        d['running'][0]['session_id'] = 'second-session'
        self.assertEqual(self.sample(data=d), 'unexpected_session')

    def test_blocked_stops(self):
        d=runtime(self.clock, False)
        d['counts']['blocked']=1; d['blocked']=[dict(issue_id='2')]
        self.assertEqual(self.sample(False, data=d), 'worker_blocked')

    def test_retry_stops_no_relaunch(self):
        d=runtime(self.clock, False)
        d['counts']['retrying']=1; d['retrying']=[dict(issue_id='2')]
        self.assertEqual(self.sample(False, data=d), 'worker_retry_requested_no_relaunch')

    def test_wall_deadline_stops(self):
        self.sample()
        self.clock.advance(121)
        self.assertEqual(self.sample(), 'wall_deadline_reached')

    def test_worker_process_still_alive_prevents_idle_finish(self):
        self.sample()
        for _ in range(4):
            self.clock.advance()
            reason = self.sample(False, alive=True)
        self.assertIsNone(reason)

    def test_unknown_process_state_never_counts_as_gone(self):
        self.sample()
        self.clock.advance(10)
        reason = self.o.sample(service(), runtime(self.clock, False),
                agent_started=True, hook_finished=False, worker_alive=None)
        self.assertEqual(reason, 'observation_unavailable')

    def test_network_failure_preserves_usage(self):
        self.sample()
        self.clock.advance()
        self.assertEqual(self.sample(data=None), 'observation_unavailable')
        self.assertEqual(self.o.snapshot()['observed_token_counts']['total_tokens'], 120)

    def test_no_raw_api_message_or_credentials_persisted(self):
        d=runtime(self.clock)
        d['raw_message']='secret-value-never-save'
        d['running'][0]['message']='secret-value-never-save'
        self.sample(data=d)
        self.assertNotIn('secret-value', self.path.read_text())

    def test_token_counts_do_not_regress(self):
        self.sample()
        self.clock.advance()
        d=runtime(self.clock); d['codex_totals']['total_tokens']=10
        self.sample(data=d)
        self.assertEqual(self.o.snapshot()['observed_token_counts']['total_tokens'], 120)

    def test_progress_is_periodic_and_sanitized(self):
        for _ in range(4): self.sample(); self.clock.advance()
        self.assertGreaterEqual(len(self.progress), 4)
        self.assertTrue(all(p['status']=='PILOT_PROGRESS' for p in self.progress))
        self.assertIn('seconds_remaining',self.progress[-1])

    def test_existing_checkpoint_is_never_reinitialized(self):
        self.o.close()
        with self.assertRaises(self.m.ObserverError):
            self.m.PilotObserver(self.path,operation='another',source=BASE)

    def test_second_writer_is_rejected(self):
        with self.assertRaises(self.m.ObserverError):
            self.m.PilotObserver(self.path,operation='fixture-one',source=BASE)

    def test_old_result_and_markers_are_untouched(self):
        result=self.path.parent/'result.json'; marker=self.path.parent/'agent-started'
        result.write_text('old-result'); marker.write_text('old-marker')
        self.sample(); self.o.finish('operator_interrupted')
        self.assertEqual(result.read_text(),'old-result')
        self.assertEqual(marker.read_text(),'old-marker')

    def test_checkpoint_symlink_rejected(self):
        self.o.close()
        self.path.unlink()
        outside=self.path.parent/'untouched'; outside.write_text('intact')
        self.path.symlink_to(outside)
        with self.assertRaises(self.m.ObserverError):
            self.m.PilotObserver(self.path,operation='fixture-one',source=BASE)
        self.assertEqual(outside.read_text(),'intact')

    def test_checkpoint_mode_is_private(self):
        self.sample()
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_failed_replace_leaves_valid_previous_snapshot(self):
        self.sample(); before=self.path.read_bytes()
        with patch.object(self.m.os,'replace',side_effect=OSError('fixture')):
            with self.assertRaises(OSError): self.o.finish('operator_interrupted')
        self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(json.loads(before)['session_observed'])

    def test_stopped_service_preserves_seen_session(self):
        self.sample(); self.clock.advance()
        self.assertEqual(self.sample(False, st=service(False)), 'service_ended')
        self.assertTrue(self.o.snapshot()['session_observed'])

    def test_reconciliation_error_does_not_erase_exit(self):
        self.idle()
        self.o.finish('artifact_readback_unavailable')
        self.assertTrue(self.o.snapshot()['worker_exit_observed'])
        self.assertFalse(self.o.snapshot()['accepted'])


if __name__ == '__main__': unittest.main()
