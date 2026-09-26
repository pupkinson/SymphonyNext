from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold
from snci.github import GitHub, wire
from snci.reviewer import Session, ReadOnlyContext
from snci import runner
spec=importlib.util.spec_from_file_location('worker',Path(__file__).resolve().parents[1]/'worker.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)

class TransportWorkerTest(unittest.TestCase):
    def test_reconcile_pagination_reads_second_page(self):
        api=object.__new__(GitHub);seen=[]
        def request(method,path):
            seen.append(path)
            return {'check_runs':[{'id':x} for x in range(100)] if 'page=1'==path.split('&')[-1] else [{'id':101}]}
        api.request=request
        self.assertEqual(len(api.pages('/repos/pupkinson/SymphonyNext/commits/'+'a'*40+'/check-runs?filter=all','check_runs')),101)
        self.assertTrue(seen[-1].endswith('page=2'))
    def test_post_transport_failure_never_retried(self):
        class Opener:
            count=0
            def open(self,*a,**k):self.count+=1;raise OSError('lost')
        o=Opener()
        with patch('urllib.request.build_opener',return_value=o),self.assertRaises(Hold):wire('POST','/repos/pupkinson/SymphonyNext/check-runs','fake',{})
        self.assertEqual(o.count,1)
    def test_real_pipe_timeout_terminates_process(self):
        p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,start_new_session=True)
        s=Session(p,ReadOnlyContext(None,{},{},[]),0.03)
        start=time.monotonic()
        try:
            with self.assertRaisesRegex(Hold,'review_timeout'):s.read()
        finally:s.close()
        self.assertLess(time.monotonic()-start,6);self.assertIsNotNone(p.returncode)
    def test_stage_failure_always_cleans_owned_container(self):
        called=[]
        def command(args,timeout=30):
            called.append(args[0])
            if args[0]=='start':raise Hold('docker_transport')
            return b''
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'command',command),patch.object(runner,'inspect_container'),patch.object(runner,'stop_owned') as stop:
            with self.assertRaises(Hold):runner.run(tmp,'a'*64,{}, {'image':'sha256:'+'b'*64})
            stop.assert_called_once_with('a'*64)
    def test_quality_parser_rejects_missing_duplicated_or_nonzero(self):
        coverage='328 tests, 0 failures, 6 skipped\n| 100.00% | Total |\n'
        dial='Total errors: 0, Skipped: 0, Unnecessary Skips: 0\n'
        self.assertEqual(worker.parse_quality(coverage,dial)['tests'],328)
        for c,d in [(coverage*2,dial),(coverage,dial.replace('errors: 0','errors: 1')),('',dial)]:
            with self.assertRaises(RuntimeError):worker.parse_quality(c,d)
    @unittest.skipUnless(os.geteuid()==0 and int(next(x.split()[1] for x in Path('/proc/self/status').read_text().splitlines() if x.startswith('CapEff:')),16)&0xc0==0xc0,'native owner gate: requires SETUID/SETGID capabilities')
    def test_candidate_cannot_signal_supervisor(self):
        code='import os,signal,json\ntry:\n os.kill(os.getppid(),signal.SIGCONT)\n blocked=False\nexcept PermissionError:blocked=True\nprint(json.dumps(dict(uid=os.getuid(),blocked=blocked)))'
        p=subprocess.run([sys.executable,'-I','-c',code],user=10001,group=10001,extra_groups=[],capture_output=True,check=True)
        self.assertEqual(json.loads(p.stdout),{'uid':10001,'blocked':True})

if __name__=='__main__':unittest.main()
