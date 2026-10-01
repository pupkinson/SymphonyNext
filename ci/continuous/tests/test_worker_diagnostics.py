"""Real child-process failures survive supervisor cleanup and runner transport."""
from contextlib import redirect_stdout
import copy
import io
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import worker
from snci import runner
from snci.common import Hold
from test_runner_isolation import container, KEY, IMAGE


class WorkerDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name); self.path.chmod(0o755)
        self.root = self.path/'source'; (self.root/'elixir').mkdir(parents=True)
        self.work = self.path/'work'; self.work.mkdir()
        original = Path
        for name, value in [('ROOT', self.root), ('LOG_BYTES', 0),
                            ('Path', lambda x: self.work if x == '/work' else original(x))]:
            p=patch.object(worker,name,value); p.start(); self.addCleanup(p.stop)
        # Exercise real processes in this workspace, whose root lacks SETUID/
        # SETGID. The native UID/capability acceptance belongs to the owner.
        popen=subprocess.Popen
        self.children=[]
        def local_child(*args,**kwargs):
            for field in ('user','group','extra_groups'):kwargs.pop(field,None)
            child=popen(*args,**kwargs);self.children.append(child);return child
        p=patch.object(worker.subprocess,'Popen',side_effect=local_child)
        p.start();self.addCleanup(p.stop)

    def child_failure(self, script, timeout=2):
        output=io.StringIO()
        with redirect_stdout(output):
            try: worker.stage('dialyzer', ['/usr/bin/python3','-I','-c',script],timeout)
            except Exception as error: return error,output.getvalue()
        self.fail('Failed stage was accepted')

    def test_real_timeout_retains_output_and_classifies_original_failure(self):
        error, output=self.child_failure('import time;print("before_timeout",flush=True);time.sleep(30)',0.2)
        self.assertIn('before_timeout',output)
        self.assertEqual(worker.failure_details(error)['kind'],'timeout')
        self.assertEqual(worker.failure_details(error)['stage'],'dialyzer')
        self.assertIsNotNone(self.children[0].poll())
        self.assertEqual((self.work/'dialyzer.log').stat().st_mode&0o777,0o600)

    def test_real_nonzero_exit_has_output_and_exit_code(self):
        error,output=self.child_failure('print("before_exit",flush=True);raise SystemExit(7)')
        self.assertIn('before_exit',output)
        self.assertEqual(worker.failure_details(error)['kind'],'stage_exit')
        self.assertEqual(worker.failure_details(error)['exit_code'],7)

    def test_spawn_error_is_classified_without_exception_text(self):
        with redirect_stdout(io.StringIO()):
            try: worker.stage('dialyzer',['/missing/PRIVATE_FIXTURE_SECRET'])
            except Exception as error:
                detail=worker.failure_details(error)
            else:self.fail('Missing command accepted')
        self.assertEqual(detail['kind'],'spawn_error')
        self.assertNotIn('PRIVATE_FIXTURE_SECRET',json.dumps(detail))

    def test_top_level_failure_reports_once_without_exception_text(self):
        output=io.StringIO()
        with patch.object(worker,'main',side_effect=RuntimeError('PRIVATE_FIXTURE_SECRET')),redirect_stdout(output):
            self.assertEqual(worker.run_main(),1)
        lines=[line for line in output.getvalue().splitlines() if line.startswith('SNCI_FAILURE ')]
        self.assertEqual(len(lines),1);self.assertNotIn('PRIVATE_FIXTURE_SECRET',output.getvalue())
        self.assertIn('SNCI_WORKER_FAILED',output.getvalue())

    def test_real_large_output_is_bounded_and_cannot_be_accepted(self):
        with patch.object(worker,'LOG_LIMIT',64):
            error,output=self.child_failure('print("x"*1000,flush=True)')
        self.assertLess(len(output),120)
        self.assertEqual(worker.failure_details(error)['kind'],'log_budget')
        self.assertTrue(worker.failure_details(error)['log_truncated'])

    def test_cleanup_exception_preserves_original_timeout_details(self):
        error,output=self.child_failure('import time;time.sleep(30)',0.05)
        try:
            try:raise error
            finally:raise RuntimeError('PRIVATE_CLEANUP_ERROR')
        except Exception as cleanup:
            with patch.object(worker,'CLEANUP_EXIT_CODE',7):detail=worker.failure_details(cleanup)
        self.assertEqual(detail['kind'],'timeout');self.assertEqual(detail['cleanup_exit_code'],7)
        self.assertNotIn('PRIVATE_CLEANUP_ERROR',json.dumps(detail))

    def test_invalid_utf8_cannot_expand_bounded_emitted_output(self):
        with patch.object(worker,'LOG_LIMIT',64):
            error,output=self.child_failure('import sys;sys.stdout.buffer.write(bytes([255])*1000)')
        self.assertLess(len(output.encode()),120)
        self.assertEqual(worker.failure_details(error)['kind'],'log_budget')


class RunnerDiagnosticsTests(unittest.TestCase):
    def run_failure(self,logs):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=container(['CHOWN','KILL','SETGID','SETUID'])
            data['Mounts'][0]['Source']=str(root/'source');data['Mounts'][2]['Source']=str(root/'source.json')
            data['State'].update(ExitCode=1,OOMKilled=False,Error='')
            calls=[]
            def command(args,**kw):
                calls.append(args)
                if args[0]=='inspect':return json.dumps([data]).encode()
                if args[0]=='wait':return b'1'
                if args[0]=='logs':return logs
                if args[0]=='ps':return ('snci-'+KEY).encode()
                return b''
            with patch.object(runner,'command',side_effect=command):
                with self.assertRaises(Hold) as caught:runner.run(root,KEY,{},dict(image=IMAGE))
            self.assertEqual((root/'worker.log').read_bytes(),logs)
            self.assertEqual(len([c for c in calls if c[0]=='rm']),1)
            return str(caught.exception)

    def diagnostic(self):
        return dict(stage='dialyzer',kind='timeout',exit_code=-15,timeout_seconds=600,
                    duration_seconds=600.1,log_bytes=100,log_truncated=False,cleanup_exit_code=0)

    def test_closed_timeout_diagnostic_reaches_hold_code(self):
        logs=b'SNCI_FAILURE '+json.dumps(self.diagnostic()).encode()+b'\nSNCI_WORKER_FAILED\n'
        self.assertEqual(self.run_failure(logs),'worker_timeout_dialyzer')

    def test_malformed_duplicate_extra_or_arbitrary_diagnostic_is_generic(self):
        d=self.diagnostic();line=b'SNCI_FAILURE '+json.dumps(d).encode()+b'\n'
        cases=[line+line,b'SNCI_FAILURE {bad}\n']
        for change in [dict(private='PRIVATE_FIXTURE_SECRET'),dict(kind='PRIVATE_FIXTURE_SECRET'),
                       dict(stage='PRIVATE_FIXTURE_SECRET'),dict(log_bytes=True),dict(duration_seconds=float('nan'))]:
            cases.append(b'SNCI_FAILURE '+json.dumps(dict(d,**change)).encode()+b'\n')
        for logs in cases:
            with self.subTest(logs=logs):self.assertEqual(self.run_failure(logs),'worker_failed')


if __name__=='__main__':unittest.main()
