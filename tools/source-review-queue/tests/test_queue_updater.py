"""Static update/rollback on real temporary files; systemd is a test double."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_queue_context import q

UPDATER = Path(__file__).resolve().parents[1] / 'update_queue.py'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


class DeliveryApi:
    """Only local delivery fixtures; production notify/deliver write the bytes."""
    def get(self, path):
        return {'labels': []}

    def request(self, method, path, body=None):
        if method != 'POST' or not path.endswith('/comments'):
            raise AssertionError((method, path))
        return {'id': 12345, 'body': body['body']}


def complete_source(job, result=None):
    number = int(job.name[3:])
    result = result or dict(issue=number, head='a' * 40, status='SOURCE_REVIEW_INCOMPLETE',
                            at=q.utc(), protocol={}, tests_by_reviewer='NOT_RUN', release_approval=False)
    save(job / 'final.json', result)
    with patch.object(q, 'QROOT', job.parent.parent):
        q._finish_task(number, DeliveryApi())
    return result


def complete_notice(attempt, result):
    q.execution_adapter().notify(int(attempt.parent.parent.name[3:]), attempt, DeliveryApi(), result)


class Controller:
    def __init__(self):
        self.events = []
        self.running = True
        self.busy = False
        self.fail_next_health = False

    def admission_identity(self, jobs):
        return jobs.stat().st_uid

    def admission_probe(self, jobs):
        if jobs.stat().st_mode & 0o222:
            raise AssertionError('admission was not paused')

    def identity(self):
        return dict(User='symphony-next', Group='symphony-next',
                    WorkingDirectory='/var/lib/symphony-next-bootstrap/queue-v1',
                    ProtectSystem='strict', KillMode='control-group', Restart='no')

    def idle(self):
        return not self.busy

    def stopped(self):
        return not self.running

    def stop(self):
        self.events.append('stop')
        self.running = False

    def start(self):
        self.events.append('start')
        self.running = True

    def healthy(self):
        if self.fail_next_health:
            self.fail_next_health = False
            return False
        return self.running


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(UPDATER.is_file(), 'reviewable existing-service updater is missing')
        spec = importlib.util.spec_from_file_location('sn102_update_under_test', UPDATER)
        self.u = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.u)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / 'install'
        self.package = self.root / 'package'
        self.state = self.root / 'state'
        for p in (self.install, self.package, self.state):
            p.mkdir(mode=0o700)
        self.original = {'queue.py': b'# predecessor\n', 'WORKFLOW.md': b'unchanged workflow\n',
                         'tmux.conf': b'unchanged tmux\n',
                         'installed.json': json.dumps({'script_sha256': sha(b'# predecessor\n'),
                            'mode': 'source-review-only', 'daily_turns': 100}).encode()}
        for name, raw in self.original.items():
            (self.install / name).write_bytes(raw)
        self.predecessor = {name: sha(raw) for name, raw in self.original.items()}
        payload = {'queue.py': b'# reviewed queue\n', 'execution.py': b'# reviewed execution\n',
                   'executor-policy.json': json.dumps(dict(schema='snq-executor-policy/v1', enabled=False,
                                         revision='not-admitted', tasks={})).encode()}
        metadata = json.loads(self.original['installed.json'])
        metadata.update(script_sha256=sha(payload['queue.py']), execution_schema='snq-execution-install/v1',
                        execution_sha256=sha(payload['execution.py']))
        payload['installed.json'] = json.dumps(metadata).encode()
        (self.package / 'payload').mkdir()
        for name, raw in payload.items():
            (self.package / 'payload' / name).write_bytes(raw)
        (self.package / 'update_queue.py').write_bytes(UPDATER.read_bytes())
        self.manifest = dict(schema='snq-update-package/v1', head='a' * 40, tree='b' * 40,
            predecessor=self.predecessor, payload={name: sha(raw) for name, raw in payload.items()},
            updater_sha256=sha(UPDATER.read_bytes()), review=dict(head='a' * 40, tree='b' * 40,
                independent=True, state='completed', result='no_major_findings',
                url='https://github.com/pupkinson/SymphonyNext/pull/103#issuecomment-123456789'))
        save(self.package / 'manifest.json', self.manifest)
        job = self.state / 'jobs/GH-77'
        job.mkdir(parents=True)
        job.parent.chmod(0o700)
        complete_source(job)
        save(job / 'claim.json', {'historical': True})
        (self.state / 'reservations/2026-10-15').mkdir(parents=True)
        (self.state / 'reservations/2026-10-15/GH-77').write_bytes(b'reserved-once\n')
        self.before = self.state_bytes()
        self.ctl = Controller()
        self.update = self.u.Updater(self.package, self.install, self.state, self.ctl,
                                     predecessor=self.predecessor, owner_uid=os.geteuid(), drain_seconds=0)

    def state_bytes(self):
        return {p.relative_to(self.state).as_posix(): p.read_bytes()
                for p in self.state.rglob('*') if p.is_file()}

    def test_check_is_read_only_and_apply_keeps_workflow_state_and_execution_disabled(self):
        self.update.check()
        self.assertEqual(self.ctl.events, [])
        result = self.update.apply()
        self.assertEqual(result['status'], 'APPLIED_EXECUTOR_DISABLED')
        self.assertEqual(self.ctl.events, ['stop', 'start'])
        self.assertEqual(self.state_bytes(), self.before)
        self.assertEqual((self.install / 'WORKFLOW.md').read_bytes(), self.original['WORKFLOW.md'])
        self.assertEqual((self.install / 'tmux.conf').read_bytes(), self.original['tmux.conf'])
        self.assertFalse(json.loads((self.install / 'executor-policy.json').read_bytes())['enabled'])

    def test_explicit_rollback_restores_exact_predecessor_without_restoring_state(self):
        self.update.apply()
        # New terminal history must survive rollback; never restore old state.
        job = self.state / 'jobs/GH-88'
        job.mkdir()
        complete_source(job)
        preserved = self.state_bytes()
        result = self.update.rollback()
        self.assertEqual(result['status'], 'ROLLED_BACK')
        for name, raw in self.original.items():
            self.assertEqual((self.install / name).read_bytes(), raw)
        self.assertFalse((self.install / 'execution.py').exists())
        self.assertFalse((self.install / 'executor-policy.json').exists())
        self.assertEqual(self.state_bytes(), preserved)

    def test_start_failure_automatically_restores_static_predecessor(self):
        self.ctl.fail_next_health = True
        with self.assertRaisesRegex(self.u.Hold, 'START_FAILED_ROLLED_BACK'):
            self.update.apply()
        self.assertEqual((self.install / 'queue.py').read_bytes(), self.original['queue.py'])
        self.assertEqual(self.state_bytes(), self.before)
        self.assertTrue(self.ctl.running)

    def test_corrupt_payload_or_predecessor_refuses_before_service_stop(self):
        for where, name in [(self.package / 'payload', 'queue.py'), (self.install, 'WORKFLOW.md')]:
            with self.subTest(name=name):
                old = (where / name).read_bytes()
                (where / name).write_bytes(b'changed\n')
                with self.assertRaises(self.u.Hold):
                    self.update.apply()
                self.assertEqual(self.ctl.events, [])
                (where / name).write_bytes(old)

    def test_stale_or_author_review_cannot_admit_update(self):
        for field, value in [('head', 'c' * 40), ('independent', False), ('state', 'running')]:
            with self.subTest(field=field):
                bad = copy.deepcopy(self.manifest)
                bad['review'][field] = value
                save(self.package / 'manifest.json', bad)
                with self.assertRaises(self.u.Hold):
                    self.update.apply()
                self.assertEqual(self.ctl.events, [])

    def test_running_or_unreconciled_job_cannot_be_stopped_for_update(self):
        self.ctl.busy = True
        with self.assertRaises(self.u.Hold):
            self.update.apply()
        self.assertEqual(self.ctl.events, [])
        self.ctl.busy = False
        (self.state / 'jobs/GH-77/label-removed.json').unlink()
        with self.assertRaises(self.u.Hold):
            self.update.apply()
        self.assertEqual(self.ctl.events, [])

    def test_repeat_apply_or_rollback_does_not_restart_or_replay(self):
        self.update.apply()
        events = list(self.ctl.events)
        self.assertEqual(self.update.apply()['status'], 'APPLIED_EXECUTOR_DISABLED')
        self.assertEqual(self.ctl.events, events)
        self.update.rollback()
        events = list(self.ctl.events)
        self.assertEqual(self.update.rollback()['status'], 'ROLLED_BACK')
        self.assertEqual(self.ctl.events, events)

    def test_enabled_policy_blocks_rollback(self):
        self.update.apply()
        policy = self.install / 'executor-policy.json'
        data = json.loads(policy.read_bytes())
        data['enabled'] = True
        save(policy, data)
        events = list(self.ctl.events)
        with self.assertRaises(self.u.Hold):
            self.update.rollback()
        self.assertEqual(self.ctl.events, events)

    def test_unknown_outbox_blocks_update_before_service_stop(self):
        outbox = self.state / 'jobs/GH-77/attempts/1/outbox'
        outbox.mkdir(parents=True)
        save(outbox / 'pr-intent.json', {'payload': {'draft': True}})
        with self.assertRaisesRegex(self.u.Hold, 'UNKNOWN_OUTBOX'):
            self.update.apply()
        self.assertEqual(self.ctl.events, [])

    def test_crash_during_static_replacement_has_explicit_rollback_without_replay(self):
        self.update.check()
        self.update.make_backup()
        self.ctl.stop()
        (self.install / 'queue.py').write_bytes((self.package / 'payload/queue.py').read_bytes())
        result = self.update.rollback()
        self.assertEqual(result['status'], 'ROLLED_BACK')
        self.assertEqual(self.state_bytes(), self.before)
        for name, raw in self.original.items():
            self.assertEqual((self.install / name).read_bytes(), raw)

    def test_journal_parent_symlink_cannot_expand_state_read_access(self):
        outside = self.root / 'outside'
        (self.state / 'jobs').rename(outside)
        (self.state / 'jobs').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(self.u.Hold):
            self.update.check()
        self.assertEqual(self.ctl.events, [])

    def test_symlink_payload_and_mutable_updater_are_refused(self):
        p = self.package / 'payload/queue.py'
        raw = p.read_bytes()
        p.unlink()
        p.symlink_to(self.install / 'queue.py')
        with self.assertRaises(self.u.Hold):
            self.update.check()
        p.unlink()
        p.write_bytes(raw)
        (self.package / 'update_queue.py').chmod(0o666)
        with self.assertRaises(self.u.Hold):
            self.update.check()


if __name__ == '__main__':
    unittest.main()
