"""Real kernel mkdir barrier against the exact installed 7fa0ee predecessor.

Only owned temporary files and unprivileged child processes are used. This is
neither a systemd transition nor a native model-agent pilot.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_queue_updater as fixtures

PREDECESSOR = Path(__file__).resolve().parents[1] / 'evidence/predecessor/queue.py'


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.UpdateTests('test_check_is_read_only_and_apply_keeps_workflow_state_and_execution_disabled')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_exact_predecessor_denies_new_admission_but_existing_work_finishes(self):
        f = self.f
        raw = PREDECESSOR.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), f.u.PREDECESSOR['queue.py'])
        predecessor = f.root / 'predecessor.py'
        predecessor.write_bytes(raw)
        predecessor.chmod(0o644)

        # Work's single-UID namespace cannot chown/setuid to an unmapped UID.
        # Drop *all* child capabilities after exec, instead of asking for more
        # UID mappings. On 1c-db the ordinary rdc process already has no caps.
        script = '''import ctypes,importlib.util,json,pathlib,sys
class Header(ctypes.Structure): _fields_=[('version',ctypes.c_uint),('pid',ctypes.c_int)]
class Data(ctypes.Structure): _fields_=[('effective',ctypes.c_uint),('permitted',ctypes.c_uint),('inheritable',ctypes.c_uint)]
h=Header(0x20080522,0);d=(Data*2)()
assert ctypes.CDLL(None,use_errno=True).capset(ctypes.byref(h),ctypes.byref(d))==0
s=importlib.util.spec_from_file_location('actual_predecessor',sys.argv[1])
q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
q.QROOT=pathlib.Path(sys.argv[2]);op=sys.argv[3]
if op=='claim': q.claim(q.QROOT,104)
elif op=='deny':
 class NoApi:
  def get(self,*args): raise AssertionError('API/auth/model must not be reached')
 try: q.prepare_task(105,NoApi())
 except PermissionError: pass
 else: raise AssertionError('predecessor admitted a new issue')
elif op=='finish':
 q.save(q.job_dir(104)/'final.json',{'status':'source-complete'})
 q.save(q.job_dir(104)/'label-removed.json',{'confirmed':True})
elif op=='resume': q.claim(q.QROOT,105)
'''

        def child(op):
            result = subprocess.run(['/usr/bin/python3', '-I', '-B', '-c', script,
                                     str(predecessor), str(f.state), op],
                                    capture_output=True, text=True, timeout=10,
                                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
            self.assertEqual(result.returncode, 0, result.stderr)

        f.update.check()
        f.update.make_backup()
        child('claim')
        # This fixture already has unprivileged credentials. Do not invoke
        # production root's setgroups/setuid preexec from ordinary rdc.
        # Use the stronger ACK: actual predecessor prepare_task must be denied.
        with patch.object(f.ctl, 'admission_probe', side_effect=lambda jobs: child('deny')):
            f.update.intake()
            self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o500)
            child('deny')
            self.assertFalse((f.state / 'jobs/GH-105').exists())
            with self.assertRaises(f.u.Hold):
                f.update.drain()
            child('finish')  # Accepted worker still writes below existing root.
            f.update.drain()
            child('deny')  # Barrier remains effective until confirmed stop.
            f.update.intake(release=True)
        child('resume')
        self.assertTrue((f.state / 'jobs/GH-104/final.json').is_file())
        self.assertTrue((f.state / 'jobs/GH-105/claim.json').is_file())
        self.assertEqual(f.ctl.events, [])

    def test_pause_probe_failure_releases_only_our_gate_without_stopping(self):
        f = self.f
        with patch.object(f.ctl, 'admission_probe', side_effect=f.u.Hold('NO_ACK')):
            with self.assertRaisesRegex(f.u.Hold, 'NO_ACK'):
                f.update.apply()
        self.assertEqual(f.ctl.events, [])
        self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o700)
        self.assertEqual((f.install / 'queue.py').read_bytes(), f.original['queue.py'])

    def test_claim_during_backup_drains_before_stop_with_gate_held(self):
        f = self.f
        backup = f.update.make_backup

        def arriving():
            value = backup()
            job = f.state / 'jobs/GH-99'
            job.mkdir()
            fixtures.save(job / 'claim.json', {'late_task': True})
            return value

        def finishing():
            self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o500)
            fixtures.save(f.state / 'jobs/GH-99/label-removed.json', {'confirmed': True})

        with patch.object(f.update, 'make_backup', side_effect=arriving), \
             patch.object(f.u.time, 'sleep', side_effect=lambda seconds: finishing()):
            f.update.drain_seconds = 1
            f.update.apply()
        self.assertEqual(f.ctl.events, ['stop', 'start'])

    def test_interrupt_before_stop_preserves_history_and_reopens_own_intake(self):
        f = self.f
        with patch.object(f.update, 'drain', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                f.update.apply()
        self.assertEqual(f.ctl.events, [])
        self.assertEqual(f.state_bytes(), f.before)
        self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o700)
        receipt = json.loads((f.update.backup / 'intake.json').read_bytes())
        self.assertEqual([x['phase'] for x in receipt['events']], ['intent', 'paused', 'released'])

    def test_process_death_after_chmod_is_recoverable_by_explicit_rollback(self):
        f = self.f
        f.update.check()
        f.update.make_backup()
        save = f.u.save

        def killed(path, value):
            if path.name == 'intake.json' and value['phase'] == 'paused':
                raise SystemExit('simulate updater death after chmod before ack write')
            save(path, value)

        with patch.object(f.u, 'save', side_effect=killed):
            with self.assertRaises(SystemExit):
                f.update.intake()
        self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o500)
        self.assertEqual(f.ctl.events, [])
        self.assertEqual(f.update.rollback()['status'], 'ROLLED_BACK')
        self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o700)
        self.assertEqual(f.state_bytes(), f.before)

    def test_unknown_gate_or_replaced_directory_is_never_reopened(self):
        f = self.f
        (f.state / 'jobs').chmod(0o500)
        with self.assertRaisesRegex(f.u.Hold, 'INTAKE_PAUSE_UNOWNED'):
            f.update.apply()
        self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o500)
        self.assertEqual(f.ctl.events, [])

    def test_directory_replacement_cannot_borrow_an_old_pause_receipt(self):
        f = self.f
        f.update.check()
        f.update.make_backup()
        f.update.intake()
        (f.state / 'jobs').rename(f.state / 'preserved-old-jobs')
        (f.state / 'jobs').mkdir(mode=0o500)
        with self.assertRaisesRegex(f.u.Hold, 'INTAKE_RECEIPT_CHANGED'):
            f.update.intake(release=True)
        self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o500)
        self.assertEqual(f.ctl.events, [])

    def test_failed_candidate_with_active_recovery_is_not_stopped_for_auto_rollback(self):
        f = self.f

        def recovering():
            job = f.state / 'jobs/GH-77'
            fixtures.save(job / 'recovery.json', {'recovery': True})
            f.ctl.busy = True
            return False

        with patch.object(f.ctl, 'healthy', side_effect=recovering):
            with self.assertRaisesRegex(f.u.Hold, 'WORK_NOT_DRAINED'):
                f.update.apply()
        self.assertEqual(f.ctl.events, ['stop', 'start'])
        self.assertTrue(f.ctl.running)
        self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o500)
        self.assertTrue((f.state / 'jobs/GH-77/recovery.json').is_file())

    def test_service_uid_or_effective_capability_change_cannot_ack_pause(self):
        f = self.f
        ctl = f.u.Controller()
        jobs = unittest.mock.Mock()
        jobs.stat.return_value = SimpleNamespace(st_uid=995, st_gid=995)
        account = SimpleNamespace(pw_uid=995, pw_gid=995)
        properties = dict(ControlGroup='/system.slice/' + f.u.UNIT, MainPID='123', ActiveState='active')
        status = b'Uid:\t995 995 995 995\nCapEff:\t0000000000000000\n'

        def reads(path, maximum):
            return b'123\n' if path.name == 'cgroup.procs' else status

        with patch.object(f.u.pwd, 'getpwnam', return_value=account), \
             patch.object(ctl, 'properties', return_value=properties), patch.object(f.u, 'read', side_effect=reads):
            self.assertIs(ctl.admission_identity(jobs), account)
            for bad in (b'Uid:\t995 995 995 995\nCapEff:\t1\n',
                        b'Uid:\t0 0 0 0\nCapEff:\t0\n'):
                status = bad
                with self.assertRaises(f.u.Hold):
                    ctl.admission_identity(jobs)
            account.pw_uid = 0
            with self.assertRaises(f.u.Hold):
                ctl.admission_identity(jobs)

    def test_root_ack_probe_drops_groups_then_gid_then_uid_and_rejects_non_eacces(self):
        f = self.f
        ctl = f.u.Controller()
        account = SimpleNamespace(pw_uid=995, pw_gid=995)
        jobs = f.state / 'jobs'
        with patch.object(ctl, 'admission_identity', return_value=account), \
             patch.object(f.u.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            ctl.admission_probe(jobs)
            args, kwargs = run.call_args
            self.assertEqual(args[0][:4], ['/usr/bin/python3', '-I', '-B', '-c'])
            self.assertEqual(args[0][-1], str(jobs))
            calls = []
            with patch.object(f.u.os, 'setgroups', side_effect=lambda v: calls.append(('groups', v))), \
                 patch.object(f.u.os, 'setgid', side_effect=lambda v: calls.append(('gid', v))), \
                 patch.object(f.u.os, 'setuid', side_effect=lambda v: calls.append(('uid', v))):
                kwargs['preexec_fn']()
            self.assertEqual(calls, [('groups', []), ('gid', 995), ('uid', 995)])
            for code in (3, 4):
                run.return_value = SimpleNamespace(returncode=code)
                with self.assertRaisesRegex(f.u.Hold, 'ADMISSION_PAUSE_UNCONFIRMED'):
                    ctl.admission_probe(jobs)


if __name__ == '__main__':
    unittest.main()
