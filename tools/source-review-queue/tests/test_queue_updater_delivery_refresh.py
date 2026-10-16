"""GET receipt refresh preserves independent delivery proofs; no real APIs/agents."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
import test_queue_updater as fixtures
from test_queue_context import q

previous = SOURCE / 'evidence/predecessor/queue.py'
assert hashlib.sha256(previous.read_bytes()).hexdigest() == '7fa0ee5624132253e487cf8093af5b1bd90fe5680c682d9672114cdbeccd33d1'
spec = importlib.util.spec_from_file_location('gh60_pinned_predecessor', previous)
predecessor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(predecessor)


class Api:
    def __init__(self, admitted):
        self.admitted = admitted
        self.posts = self.deletes = 0
        self.comments = []
        self.interrupt_label_get = False
        self.lose_delete = False

    def get(self, path):
        if '/comments?' in path:
            return copy.deepcopy(self.comments)
        if self.interrupt_label_get:
            raise KeyboardInterrupt('fixture interruption after unique-comment GET receipt replacement')
        return dict(labels=[dict(name=q.LABEL)] if self.admitted else [])

    def request(self, method, path, body=None):
        if method == 'POST':
            self.posts += 1
            row = dict(id=12345 + self.posts, body=body['body'])
            self.comments.append(row)
            return row
        assert method == 'DELETE'
        self.deletes += 1
        self.admitted = False
        if self.lose_delete:
            raise q.Hold('FIXTURE_DELETE_ACK_UNKNOWN')


class DeliveryRefreshTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.UpdateTests('test_check_is_read_only_and_apply_keeps_workflow_state_and_execution_disabled')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def exercise(self, role, module, admitted):
        f = self.f
        number = 104 if role == 'developer' else 60
        job = f.state / ('jobs/GH-' + str(number))
        job.mkdir()
        if role == 'developer':
            attempt = job / 'attempts/1'
            attempt.mkdir(parents=True)
            fixtures.save(job / 'execution.json', dict(role='developer', generation=1))
            fixtures.save(job / 'label-removed.json', dict(confirmed=False,
                          scope='developer-journal-skip-for-legacy-recovery'))
            result = dict(state='Blocked', issue=number, release_approval=False)
            fixtures.save(attempt / 'final.json', result)
            directory = attempt / 'notifications/Blocked'
            def deliver(api):
                q.execution_adapter().notify(number, attempt, api, result)
        else:
            result = dict(issue=number, head='a' * 40, status='SOURCE_REVIEW_INCOMPLETE',
                          at=module.utc(), protocol={}, tests_by_reviewer='NOT_RUN', release_approval=False)
            fixtures.save(job / 'final.json', result)
            directory = job
            def deliver(api):
                with patch.object(module, 'QROOT', f.state):
                    module.finish_task(number, api)
        api = Api(admitted)
        deliver(api)
        f.update.quiet()  # Fully completed first delivery passes the full gate.
        old_label = (directory / 'label-removed.json').read_bytes()
        old_label_stat = (directory / 'label-removed.json').stat()
        old_receipt = (directory / 'comment-readback.json').read_bytes()
        old_receipt_inode = (directory / 'comment-readback.json').stat().st_ino
        writes = (api.posts, api.deletes)
        time.sleep(0.02)  # Fixture separation only; no journal retiming/tolerance.
        api.interrupt_label_get = True
        with self.assertRaises(KeyboardInterrupt):
            deliver(api)
        self.assertEqual((api.posts, api.deletes), writes)
        self.assertEqual((directory / 'label-removed.json').read_bytes(), old_label)
        self.assertEqual((directory / 'comment-readback.json').read_bytes(), old_receipt)
        self.assertNotEqual((directory / 'comment-readback.json').stat().st_ino, old_receipt_inode)
        self.assertFalse((directory / 'delivery-hold.json').exists())
        received = (directory / 'comment-readback.json').stat()
        self.assertGreater(received.st_mtime_ns, old_label_stat.st_mtime_ns)
        self.assertGreater(received.st_ctime_ns, old_label_stat.st_ctime_ns)
        before = f.state_bytes()
        try:
            try:
                f.update.quiet()
            except f.u.Hold as exc:
                self.fail('Confirmed delivery rejected after GET receipt refresh: ' + str(exc))
            f.update.check()
            f.update.check()
            self.assertEqual(f.ctl.events, [])
            self.assertEqual(f.update.apply()['status'], 'APPLIED_EXECUTOR_DISABLED')
            self.assertEqual(f.update.apply()['status'], 'APPLIED_EXECUTOR_DISABLED')
            self.assertEqual(f.update.rollback()['status'], 'ROLLED_BACK')
            self.assertEqual(f.update.rollback()['status'], 'ROLLED_BACK')
            self.assertEqual(f.ctl.events, ['stop', 'start', 'stop', 'start'])
            self.assertEqual((api.posts, api.deletes), writes)
        finally:
            self.assertEqual(f.state_bytes(), before)
            self.assertIn(f.ctl.events, ([], ['stop', 'start', 'stop', 'start']))

    def test_owner_metadata_replay_does_not_require_receipt_before_label(self):
        f = self.f
        directory = f.root / 'owner-metadata'
        directory.mkdir()
        values = {
            'comment-intent.json': (3162521,1791010983894980568),
            'comment-readback.json': (3163879,1791012063642196769),
            'label-removed.json': (3163328,1791010988291175811)}
        payload = {'comment-intent.json':dict(body='GH60 local diagnostic fixture'),
                   'comment-readback.json':dict(id=12345),
                   'label-removed.json':dict(confirmed=True,at='2026-10-03T07:03:08.294010+00:00')}
        def journal(path, *args, **kwargs):
            name = Path(path).name
            inode, stamp = values[name]
            s = SimpleNamespace(st_dev=2050,st_ino=inode,st_nlink=1,st_mtime_ns=stamp,st_ctime_ns=stamp)
            return (payload[name],s) if kwargs.get('observed') else payload[name]
        with patch.object(f.u,'journal',side_effect=journal), patch.object(f.u.time,'time_ns',return_value=1792153313853899946):
            try:
                self.assertEqual(f.update.delivery(directory,legacy=True), payload['comment-intent.json']['body'])
            except f.u.Hold as exc:
                self.fail('Owner GH60 individual coherent metadata rejected: ' + str(exc))


    def holds(self):
        before, events = self.f.state_bytes(), self.f.ctl.events[:]
        with self.assertRaises(self.f.u.Hold):
            self.f.update.check()
        self.assertEqual(self.f.state_bytes(), before)
        self.assertEqual(self.f.ctl.events, events)

    def existing_api(self, job, admitted=False):
        api = Api(admitted)
        body = json.loads((job / 'comment-intent.json').read_bytes())['body']
        api.comments = [dict(id=12345, body=body)]
        return api

    def test_new_intent_and_receipt_cannot_borrow_old_label_confirmation(self):
        job = self.f.state / 'jobs/GH-77'
        intent = json.loads((job / 'comment-intent.json').read_bytes())
        receipt = json.loads((job / 'comment-readback.json').read_bytes())
        time.sleep(0.02)
        q.save(job / 'comment-intent.json', intent)
        q.save(job / 'comment-readback.json', receipt)
        self.holds()

    def test_missing_label_is_not_replaced_by_refreshed_comment(self):
        job = self.f.state / 'jobs/GH-77'
        (job / 'label-removed.json').unlink()
        time.sleep(0.02)
        q.save(job / 'comment-readback.json', dict(id=12345))
        self.holds()

    def test_unconfirmed_label_is_not_replaced_by_refreshed_comment(self):
        job = self.f.state / 'jobs/GH-77'
        q.save(job / 'label-removed.json', dict(confirmed=False, at=q.utc()))
        time.sleep(0.02)
        q.save(job / 'comment-readback.json', dict(id=12345))
        self.holds()

    def test_new_DELETE_intent_and_fresh_comment_cannot_reuse_old_label(self):
        job = self.f.state / 'jobs/GH-77'
        time.sleep(0.02)
        q.save(job / 'label-remove-intent.json', dict(at=q.utc()))
        q.save(job / 'comment-readback.json', dict(id=12345))
        self.holds()

    def test_fresh_comment_after_retained_hold_needs_label_reconfirmation(self):
        job = self.f.state / 'jobs/GH-77'
        q.save(job / 'delivery-hold.json', dict(reason='LABEL_REMOVAL_OUTCOME_UNKNOWN', at=q.utc()))
        time.sleep(0.02)
        api = self.existing_api(job)
        api.interrupt_label_get = True
        with patch.object(q, 'QROOT', self.f.state), self.assertRaises(KeyboardInterrupt):
            q.finish_task(77, api)
        self.assertEqual((api.posts, api.deletes), (0, 0))
        self.holds()

    def retained_equal_clock(self, module, recover):
        job = self.f.state / 'jobs/GH-60'
        job.mkdir()
        stamp = module.utc()
        result = dict(issue=60, head='a'*40, status='SOURCE_REVIEW_INCOMPLETE',
                      at=stamp, protocol={}, tests_by_reviewer='NOT_RUN', release_approval=False)
        module.save(job / 'final.json', result)
        api = Api(True)
        with patch.object(module, 'QROOT', self.f.state), patch.object(module, 'utc', return_value=stamp):
            module.finish_task(60, api)
            old = (job / 'label-removed.json').stat()
            comments, api.comments = api.comments, []
            time.sleep(0.02)
            with self.assertRaises(module.Hold):
                module.finish_task(60, api)
            held = (job / 'delivery-hold.json').stat()
            self.assertLess(old.st_ctime_ns, held.st_ctime_ns)
            api.comments = comments
            api.interrupt_label_get = not recover
            time.sleep(0.02)
            if recover:
                module.finish_task(60, api)
            else:
                with self.assertRaises(KeyboardInterrupt):
                    module.finish_task(60, api)
                self.assertEqual((job / 'label-removed.json').stat().st_ino, old.st_ino)
        self.assertEqual((api.posts, api.deletes), (1, 1))
        before = self.f.state_bytes()
        if recover:
            self.f.update.check()
            journal = self.f.u.journal
            def coarse(path, *args, **kwargs):
                value = journal(path, *args, **kwargs)
                if Path(path) == job / 'label-removed.json' and kwargs.get('observed'):
                    return value[0], SimpleNamespace(st_dev=held.st_dev, st_nlink=1,
                        st_mtime_ns=held.st_mtime_ns - reversed_order,
                        st_ctime_ns=(held.st_ctime_ns - reversed_order
                                     if field == 'ctime' else value[1].st_ctime_ns))
                if Path(path) == job / 'delivery-hold.json' and field == 'ctime':
                    return value[0], SimpleNamespace(st_dev=held.st_dev, st_nlink=1,
                        st_mtime_ns=held.st_mtime_ns - 2, st_ctime_ns=held.st_ctime_ns)
                return value
            for field in ('mtime', 'ctime'):
                for reversed_order in (0, 1):
                    with patch.object(self.f.u, 'journal', side_effect=coarse):
                        self.holds()  # Each equal/reversed clock independently blocks.
            self.f.update.check()
        else:
            self.holds()
            self.holds()
        self.assertEqual(self.f.state_bytes(), before)
        self.assertEqual(self.f.ctl.events, [])

    def test_unknown_DELETE_after_prior_confirmation_holds_until_real_recovery(self):
        job = self.f.state / 'jobs/GH-77'
        api = self.existing_api(job, admitted=True)
        api.lose_delete = True
        with patch.object(q, 'QROOT', self.f.state), self.assertRaises(q.Hold):
            q.finish_task(77, api)
        self.assertEqual((api.posts, api.deletes), (0, 1))
        self.holds()
        time.sleep(0.02)
        with patch.object(q, 'QROOT', self.f.state):
            q.finish_task(77, api)
        self.f.update.check()
        self.assertEqual((api.posts, api.deletes), (0, 1))

    def historical(self):
        job = self.f.state / 'jobs/GH-104'
        job.mkdir()
        fixtures.save(job / 'execution.json', dict(role='developer', generation=2))
        fixtures.save(job / 'label-removed.json', dict(confirmed=False,
                      scope='developer-journal-skip-for-legacy-recovery'))
        api = Api(False)
        adapter = q.execution_adapter()
        for g, state in ((1, 'Rework'), (2, 'Blocked')):
            attempt = job / 'attempts' / str(g)
            attempt.mkdir(parents=True)
            result = dict(state=state, issue=104, generation=g, release_approval=False)
            fixtures.save(attempt / 'final.json', result)
            if g == 1:
                candidate = dict(issue=104, generation=1, head='b'*40, base='a'*40,
                                 artifact=dict(repo=q.REPO, head='b'*40, tree='c'*40, pr=12), tests={})
                fixtures.save(attempt / 'candidate.json', candidate)
                review = dict(state='Review', issue=104, release_approval=False,
                              **{k:candidate[k] for k in ('head','base','artifact','tests')})
                adapter.notify(104, attempt, api, review)
            adapter.notify(104, attempt, api, result)
        self.f.update.check()
        return job, job / 'attempts/1', review, api

    def test_previous_generation_Review_receipt_can_refresh_independently(self):
        job, attempt, review, api = self.historical()
        writes = (api.posts, api.deletes)
        time.sleep(0.02)
        api.interrupt_label_get = True
        with self.assertRaises(KeyboardInterrupt):
            q.execution_adapter().notify(104, attempt, api, review)
        before = self.f.state_bytes()
        try:
            self.f.update.check()
            self.f.update.check()
        except self.f.u.Hold as exc:
            self.fail('Historical GET refresh rejected: ' + str(exc))
        self.assertEqual(self.f.state_bytes(), before)
        self.assertEqual((api.posts, api.deletes), writes)
        self.assertEqual(self.f.ctl.events, [])

    def test_old_generation_missing_receipt_still_blocks_newer_complete_generation(self):
        job, attempt, review, api = self.historical()
        (attempt / 'notifications/Review/comment-readback.json').unlink()
        self.holds()


def scenario(role, module, admitted):
    def test(self):
        self.exercise(role,module,admitted)
    return test


for name, role, module in (('predecessor','legacy',predecessor),('candidate','legacy',q),('developer','developer',q)):
    for admitted in (False,True):
        setattr(DeliveryRefreshTests, 'test_' + name + '_refresh_' + ('deleted' if admitted else 'already_absent'),
                scenario(role,module,admitted))

def retained(module, recover):
    return lambda self: self.retained_equal_clock(module, recover)

for name, module in (('predecessor', predecessor), ('candidate', q)):
    for recover in (False, True):
        setattr(DeliveryRefreshTests, 'test_equal_clock_hold_' + name + str(recover),
                retained(module, recover))


if __name__ == '__main__':
    unittest.main()
