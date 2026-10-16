"""Application time and inode time are distinct clocks; preserve delivery proof.

Real1c-db samples use the unchanged installed writer, API doubles and device2065;
the owner separately observed the same failing predicate on GH25/device2050.
No runtime journal is read or retimed by these tests.
"""
import copy
import datetime
import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_queue_updater as fixtures
from test_queue_context import q


class ClockDomainTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.UpdateTests('test_check_is_read_only_and_apply_keeps_workflow_state_and_execution_disabled')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def legacy_module(self):
        spec = importlib.util.spec_from_file_location('clock_pinned_predecessor',
            fixtures.UPDATER.parent / 'evidence/predecessor/queue.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    class Api:
        """Successful, fully observed local responses; no external transport."""
        def __init__(self, admitted=False):
            self.admitted = admitted
            self.posts = self.deletes = 0

        def request(self, method, path, body=None):
            if method == 'POST':
                self.posts += 1
                return {'id':12345, 'body':body['body']}
            if method == 'DELETE':
                self.deletes += 1
                self.admitted = False
                return None
            raise AssertionError(method)

        def get(self, path):
            return {'labels':[{'name':q.LABEL}] if self.admitted else []}

    def source(self, module=q, admitted=False, number=88):
        job = self.f.state / ('jobs/GH-' + str(number))
        job.mkdir()
        fixtures.save(job / 'final.json', dict(issue=number,head='a'*40,
            status='SOURCE_REVIEW_INCOMPLETE',at=module.utc(),protocol={},
            tests_by_reviewer='NOT_RUN',release_approval=False))
        api = self.Api(admitted)
        with patch.object(module, 'QROOT', self.f.state):
            module.finish_task(number, api)
        self.assertEqual((api.posts,api.deletes),(1,int(admitted)))
        return job

    def developer(self, admitted=False):
        job = self.f.state / 'jobs/GH-104'
        attempt = job / 'attempts/1'
        attempt.mkdir(parents=True)
        fixtures.save(job/'execution.json',dict(role='developer',generation=1))
        fixtures.save(job/'label-removed.json',dict(confirmed=False,
            scope='developer-journal-skip-for-legacy-recovery'))
        result = dict(state='Blocked',issue=104,release_approval=False)
        fixtures.save(attempt/'final.json',result)
        api = self.Api(admitted)
        q.execution_adapter().notify(104,attempt,api,result)
        self.assertEqual((api.posts,api.deletes),(1,int(admitted)))
        return attempt/'notifications/Blocked'

    @contextmanager
    def coarse(self, names=None, lag=1000000000):
        original = self.f.u.journal
        def read(path,*args,**kwargs):
            result = original(path,*args,**kwargs)
            if not kwargs.get('observed') or names is not None and Path(path).name not in names:
                return result
            value,s = result
            fields = {n:getattr(s,n) for n in ('st_dev','st_ino','st_nlink','st_mode',
                'st_uid','st_gid','st_size','st_mtime_ns','st_ctime_ns')}
            fields['st_mtime_ns'] -= lag  # Test double only; actual files untouched.
            return value,SimpleNamespace(**fields)
        with patch.object(self.f.u,'journal',side_effect=read):
            yield

    def assert_check_preserves(self):
        before = self.f.state_bytes()
        self.assertEqual(self.f.update.check()['status'],'UPDATE_CHECK_PASS')
        self.assertEqual(self.f.state_bytes(),before)
        self.assertEqual(self.f.ctl.events,[])

    def test_native_16_completed_writer_observations_pass(self):
        observed = json.loads((fixtures.UPDATER.parent/'evidence/gh102-clock-native-observations.json').read_bytes())
        self.assertEqual(observed['samples'],16)
        for row in observed['details']:
            with self.subTest(sample=row['sample']):
                self.replay(row['metadata'],row['label_at'])

    def replay(self, metadata, at, now=None):
        directory = self.f.root / ('replay-' + str(len(list(self.f.root.glob('replay-*')))))
        directory.mkdir()
        payloads = {'comment-intent.json':{'body':'completed local delivery'},
            'comment-readback.json':{'id':12345},
            'label-removed.json':{'confirmed':True,'at':at}}
        def journal(path,*args,**kwargs):
            name = Path(path).name
            m = metadata[name]
            s = SimpleNamespace(st_dev=m['device'],st_ino=m.get('inode',1),
                st_nlink=m['nlink'],st_mtime_ns=int(m['mtime_ns']),st_ctime_ns=int(m['ctime_ns']))
            return (payloads[name],s) if kwargs.get('observed') else payloads[name]
        with patch.object(self.f.u,'journal',side_effect=journal):
            if now is None:
                result = self.f.update.delivery(directory,legacy=True)
            else:
                with patch.object(self.f.u.time,'time_ns',return_value=now):
                    result = self.f.update.delivery(directory,legacy=True)
        self.assertEqual(result,payloads['comment-intent.json']['body'])

    def owner_metadata(self):
        values = [(1790927759539582233,1790927759539582233),
                  (1790927760487622135,1790927760487622135),
                  (1790927762279697559,1790927762283697727)]
        return {n:dict(device=2050,nlink=1,mtime_ns=str(m),ctime_ns=str(c))
            for n,(m,c) in zip(('comment-intent.json','comment-readback.json','label-removed.json'),values)}

    def test_owner_GH25_reported_clock_clause_passes(self):
        # Isolates the reported clause, not unknown later GH25 proofs or quiet().
        self.replay(self.owner_metadata(),'2026-10-02T07:56:02.283405+00:00')

    def test_candidate_legacy_complete_delivery_with_coarse_files_passes(self):
        self.source()
        with self.coarse():
            self.assert_check_preserves()

    def test_pinned_predecessor_complete_delivery_with_coarse_files_passes(self):
        self.source(self.legacy_module())
        with self.coarse():
            self.assert_check_preserves()

    def test_developer_complete_delivery_with_coarse_files_passes(self):
        self.developer()
        with self.coarse():
            self.assert_check_preserves()

    def test_label_delete_intent_application_time_need_not_precede_its_mtime(self):
        self.source(admitted=True)
        with self.coarse(names={'label-remove-intent.json'}):
            self.assert_check_preserves()

    def recover(self, module=q):
        job = self.source(module)
        module.save(job/'delivery-hold.json',dict(reason='COMMENT_PUBLICATION_UNRESOLVED',at=module.utc()))
        body = json.loads((job/'comment-intent.json').read_bytes())['body']
        class ReadOnlyRecovery:
            def get(self,path):
                return [{'id':12345,'body':body}] if '/comments?' in path else {'labels':[]}
            def request(self,*args,**kwargs):
                raise AssertionError('Recovery must not replay POST/DELETE')
        with patch.object(module,'QROOT',self.f.state):
            module.finish_task(88,ReadOnlyRecovery())
        return job

    def test_retained_hold_application_time_need_not_precede_its_mtime(self):
        self.recover()
        with self.coarse(names={'delivery-hold.json'}):
            self.assert_check_preserves()

    def test_actual_predecessor_recovery_with_all_coarse_files_passes(self):
        self.recover(self.legacy_module())
        with self.coarse():
            self.assert_check_preserves()

    def test_developer_delete_with_coarse_files_passes(self):
        self.developer(admitted=True)
        with self.coarse():
            self.assert_check_preserves()

    def test_coarse_delivery_can_apply_and_rollback_without_state_change(self):
        self.source(admitted=True)
        self.developer(admitted=True)
        before = self.f.state_bytes()
        with self.coarse():
            self.assertEqual(self.f.update.apply()['status'],'APPLIED_EXECUTOR_DISABLED')
            self.assertEqual(self.f.update.rollback()['status'],'ROLLED_BACK')
        self.assertEqual(self.f.state_bytes(),before)
        self.assertEqual(self.f.ctl.events,['stop','start','stop','start'])

    def test_json_future_label_still_holds_before_stop(self):
        job = self.source()
        fixtures.save(job/'label-removed.json',dict(confirmed=True,at='2099-01-01T00:00:00Z'))
        with self.coarse(),self.assertRaises(self.f.u.Hold):
            self.f.update.check()
        self.assertEqual(self.f.ctl.events,[])

    def test_application_order_violation_still_holds_with_coarse_files(self):
        job = self.source(admitted=True)
        fixtures.save(job/'label-remove-intent.json',dict(at='2099-01-01T00:00:00Z'))
        with self.coarse(),self.assertRaises(self.f.u.Hold):
            self.f.update.check()

    def test_unknown_comment_or_label_still_holds_with_coarse_files(self):
        for name in ('comment-readback.json','label-removed.json'):
            with self.subTest(name=name):
                self.setUp()
                job = self.source()
                (job/name).unlink()
                before = self.f.state_bytes()
                with self.coarse(),self.assertRaises(self.f.u.Hold):
                    self.f.update.check()
                self.assertEqual(self.f.state_bytes(),before)
                self.assertEqual(self.f.ctl.events,[])

    def test_stale_receipt_after_hold_still_holds_with_coarse_files(self):
        for module in (q,self.legacy_module()):
            with self.subTest(module=module.__name__):
                self.setUp()
                job = self.source(module)
                class MissingComment:
                    def get(self,path):
                        return [] if '/comments?' in path else {'labels':[]}
                    def request(self,*args,**kwargs):
                        raise AssertionError('No write replay')
                with patch.object(module,'QROOT',self.f.state),self.assertRaises(module.Hold):
                    module.finish_task(88,MissingComment())
                before = self.f.state_bytes()
                with self.coarse(),self.assertRaises(self.f.u.Hold):
                    self.f.update.check()
                self.assertEqual(self.f.state_bytes(),before)
                self.assertEqual(self.f.ctl.events,[])

    def test_exact_wall_time_boundary_and_timezone_offsets(self):
        at_ns = 1790927762283405000
        for at in ('2026-10-02T07:56:02.283405Z','2026-10-02T10:56:02.283405+03:00'):
            with self.subTest(at=at):
                metadata = self.owner_metadata()
                # Boundary isolation: every observed inode time precedes now.
                metadata['label-removed.json']['ctime_ns'] = str(at_ns-1000)
                self.replay(metadata,at,now=at_ns)
                with self.assertRaises(self.f.u.Hold):
                    self.replay(metadata,at,now=at_ns-1)

    def test_future_or_reversed_file_metadata_remains_hold(self):
        original = self.owner_metadata()
        for kind in ('future','reversed','multiple_links','different_device'):
            with self.subTest(kind=kind):
                m = copy.deepcopy(original)
                if kind=='future':
                    m['label-removed.json']['ctime_ns']='9999999999999999999'
                elif kind=='reversed':
                    m['comment-readback.json']['mtime_ns']=str(int(m['comment-intent.json']['mtime_ns'])-1)
                elif kind=='multiple_links':
                    m['comment-readback.json']['nlink']=2
                else:
                    m['comment-readback.json']['device']=999
                with self.assertRaises(self.f.u.Hold):
                    self.replay(m,'2026-10-02T07:56:02.283405Z')


if __name__ == '__main__':
    unittest.main()

