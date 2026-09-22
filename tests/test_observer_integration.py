"""Real local files/signals + exact legacy control flow with fake host adapters.

No network request, service action, model process or production path is executed.
"""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch

from test_pilot_observer import BASE, INVOCATION, Clock, artifact, runtime, service

ROOT=Path(__file__).resolve().parents[1]
LEGACY=ROOT/'tests/fixtures/boot_p01_launcher_v1.txt'


def load(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return m


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        builder=load(ROOT/'bootstrap/build_observer_candidate.py','builder_integration')
        self.original=LEGACY.read_bytes()
        self.assertEqual(hashlib.sha256(self.original).hexdigest(),builder.LEGACY_SHA256)
        self.candidate=builder.build_candidate(self.original)
        self.file=self.root/'candidate.py';self.file.write_bytes(self.candidate)
        self.c=load(self.file,'candidate_under_test')
        self.clock=Clock()
        self.c.RUN=self.root/'run';self.c.RUN.mkdir()
        self.c.RECORD=self.root/'record';self.c.RECORD.mkdir(mode=0o700)
        self.mon=self.c.PilotObserver(self.c.RECORD/'observer-state.json',operation='offline',
            source=BASE,clock=self.clock.mono,wall=self.clock.wall,idle_grace=6,
            startup_limit=12,wall_limit=120)
        self.addCleanup(self.mon.close)
        self.mon.start_requested();self.mon.service_started(INVOCATION)

    def run_observer(self, read_runtime, alive, sleep=None, st=None, readback=None):
        self.c.unit_state=st or (lambda:service())
        self.c.observer_runtime_read=read_runtime
        self.c.observer_worker_alive=alive
        self.c.result_readback=readback or (lambda api:artifact())
        with patch.object(self.c.time,'monotonic',self.clock.mono),patch.object(self.c.time,'sleep',sleep or self.clock.advance):
            return self.c.observer(self.mon,object())

    def test_patch_preserves_old_sources_and_all_launch_guards(self):
        self.assertEqual(self.original,LEGACY.read_bytes())
        old=ast.parse(self.original);new=ast.parse(self.candidate)
        funcs=lambda tree:{n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        a,b=funcs(old),funcs(new)
        changed={name for name in a if a[name]!=b[name]}
        self.assertEqual(changed,{'observer','launch','result_readback'})
        for name in ('guard','claim_once','validate_api','workflow_text','codex_args','admit','dropin_text'):
            self.assertEqual(a[name],b[name])

    def test_python310_syntax(self):
        ast.parse(self.candidate,feature_version=(3,10))

    def test_missing_hook_exits_instead_of_waiting_wall_limit(self):
        (self.c.RUN/'agent-started').write_text('fixed marker')
        def data(): return runtime(self.clock,self.clock.n==0)
        reason,obs=self.run_observer(data,lambda:self.clock.n==0)
        self.assertEqual(reason,'worker_exited_without_hook')
        self.assertTrue(obs['session_observed'])
        self.assertLess(self.clock.n,120)

    def test_success_path_does_not_attest_normal_turn(self):
        (self.c.RUN/'agent-started').touch();(self.c.RUN/'worker-finished').touch()
        reason,obs=self.run_observer(lambda:runtime(self.clock,self.clock.n==0),lambda:self.clock.n==0)
        self.assertEqual(reason,'worker_finished_awaiting_acceptance')
        self.assertEqual(obs['normal_turn_completion'],'UNKNOWN')
        self.assertFalse(obs['accepted'])

    def test_three_read_failures_keep_checkpoint_and_stop(self):
        self.mon.sample(service(),runtime(self.clock),agent_started=True,hook_finished=False,worker_alive=True)
        calls=[]
        def data(): calls.append(self.clock.n);return None
        reason,obs=self.run_observer(data,lambda:True)
        self.assertEqual(reason,'observation_lost_after_three_reads')
        self.assertEqual(calls,[0,10,70])
        self.assertTrue(obs['session_observed'])
        self.assertEqual(obs['observed_token_counts']['total_tokens'],120)

    def test_readback_permission_error_is_not_retried(self):
        (self.c.RUN/'agent-started').touch();calls=[]
        def rejected(api): calls.append(1);raise self.c.Stop('github_http_403')
        reason,obs=self.run_observer(lambda:runtime(self.clock,self.clock.n==0),lambda:self.clock.n==0,readback=rejected)
        self.assertEqual(reason,'artifact_readback_rejected');self.assertEqual(len(calls),1)

    def test_readback_transport_retries_are_bounded(self):
        (self.c.RUN/'agent-started').touch();calls=[]
        def lost(api): calls.append(self.clock.n);raise self.c.Stop('github_transport_or_json')
        reason,obs=self.run_observer(lambda:runtime(self.clock,self.clock.n==0),lambda:self.clock.n==0,readback=lost)
        self.assertEqual(reason,'artifact_readback_unavailable')
        self.assertEqual(len(calls),3);self.assertEqual(calls[1]-calls[0],10);self.assertEqual(calls[2]-calls[1],60)

    def test_interrupted_callee_already_saved_runtime(self):
        (self.c.RUN/'agent-started').touch()
        def interrupt(n): self.c.interrupted(signal.SIGINT,None)
        with self.assertRaises(self.c.Stop):
            self.run_observer(lambda:runtime(self.clock),lambda:True,sleep=interrupt)
        saved=json.loads(self.mon.path.read_text())
        self.assertTrue(saved['session_observed'])
        self.assertEqual(saved['observed_token_counts']['total_tokens'],120)

    def test_persistence_failure_is_not_network_retry(self):
        (self.c.RUN/'agent-started').touch();calls=[]
        def data():calls.append(1);return runtime(self.clock)
        with patch.object(self.mon,'_save',side_effect=OSError('disk fault')):
            with self.assertRaises(OSError): self.run_observer(data,lambda:True)
        self.assertEqual(calls,[1])

    def test_exact_caller_finally_keeps_observations_and_cleans(self):
        self.exercise_lifecycle(interrupt=True)

    def test_exact_caller_normal_finish_stops_without_ctrl_c(self):
        self.exercise_lifecycle(interrupt=False)

    def exercise_lifecycle(self,interrupt):
        # Execute the candidate's real mutation/observation/finally AST, but ALL
        # systemd/GitHub actions are replaced by inert local fixture adapters.
        self.mon.close();self.mon.path.unlink()
        node=next(n for n in ast.parse(self.candidate).body if isinstance(n,ast.FunctionDef) and n.name=='launch')
        outer=next(n for n in node.body if isinstance(n,ast.Try))
        start=next(i for i,n in enumerate(node.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='wf' for t in n.targets))
        subset=node.body[start:]
        fn=ast.FunctionDef(name='fixture_lifecycle',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),
            body=[ast.Assign(targets=[ast.Name(id='original',ctx=ast.Store())],value=ast.Constant(value=b'original disabled workflow')),
                  ast.Assign(targets=[ast.Name(id='report',ctx=ast.Store())],value=ast.Dict(keys=[ast.Constant(value='model_profile')],values=[ast.Dict(keys=[],values=[])])),
                  ast.Assign(targets=[ast.Name(id='api',ctx=ast.Store())],value=ast.Constant(value=None))]+subset,
            decorator_list=[])
        code=compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<exact-candidate-lifecycle>','exec')
        c=self.c;c.CONF=self.root/'conf';c.CONF.mkdir();c.READY=c.CONF/'READY';c.WORKFLOW=c.CONF/'WORKFLOW.md';c.WORKFLOW.write_bytes(b'original disabled workflow')
        c.DROP=self.root/'drop'/'90.conf';c.UNIT_PATH=self.root/'unit';c.DRIVER=self.file
        (c.RUN/'agent-started').touch()
        if not interrupt:(c.RUN/'worker-finished').touch()
        commands=[];active=[False]
        c.run=lambda args,**kw:(commands.append(args),active.__setitem__(0,True if 'start' in args else False if 'stop' in args else active[0]),'')[2]
        c.unit_state=lambda:service(active[0])
        c.admit=lambda api:None;c.remove_admission=lambda api:'already_absent';c.result_readback=lambda api:artifact()
        c.atomic_bytes=lambda p,b,*args,**kw:Path(p).write_bytes(b)
        c.create_file=lambda p,b,*args,**kw:Path(p).write_bytes(b)
        c.read_file=lambda p,*args,**kw:Path(p).read_bytes()
        c.observer_runtime_read=lambda:runtime(self.clock,self.clock.n==0)
        c.observer_worker_alive=lambda:self.clock.n==0
        c.PilotObserver=lambda p,**kw:load(ROOT/'bootstrap/pilot_observer.py','lifecycle_observer').PilotObserver(
            p,operation=kw['operation'],source=kw['source'],clock=self.clock.mono,wall=self.clock.wall,
            idle_grace=6,startup_limit=12,wall_limit=120,emit=kw['emit'])
        def sleep(n):
            if interrupt:raise c.Stop('operator_interrupted')
            self.clock.advance(n)
        exec(code,c.__dict__)
        with patch.object(c.time,'monotonic',self.clock.mono),patch.object(c.time,'sleep',sleep),patch.object(c.signal,'signal'),contextlib.redirect_stdout(io.StringIO()):
            if interrupt:
                with self.assertRaises(SystemExit): c.fixture_lifecycle()
            else: c.fixture_lifecycle()
        report=json.loads((c.RECORD/'result.json').read_text())
        self.assertTrue(report['runtime_observations']['session_observed'])
        self.assertNotEqual(report['stop_reason'],'not_started')
        self.assertEqual(report['cleanup_warnings'],[])
        self.assertEqual(c.WORKFLOW.read_bytes(),b'original disabled workflow')
        self.assertFalse(c.READY.exists());self.assertFalse(c.DROP.exists())
        self.assertEqual(sum('start' in cmd for cmd in commands),1)
        self.assertEqual(sum('stop' in cmd for cmd in commands),1)
        self.assertEqual(report['status'],'STOP' if interrupt else 'PILOT_STOPPED_AWAITING_ACCEPTANCE')


class RealSignalTests(unittest.TestCase):
    def test_real_sigint_preserves_checkpoint(self): self.signal_case(signal.SIGINT)
    def test_real_sigterm_preserves_checkpoint(self): self.signal_case(signal.SIGTERM)
    def test_real_sigkill_leaves_last_durable_checkpoint(self): self.signal_case(signal.SIGKILL)

    def signal_case(self, signum):
        with tempfile.TemporaryDirectory() as root:
            child=Path(root)/'child.py'
            child.write_text(textwrap.dedent('''
                import importlib.util,json,signal,sys,time
                from pathlib import Path
                spec=importlib.util.spec_from_file_location('core',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
                out=Path(sys.argv[2]);o=m.PilotObserver(out,operation='native-signal',source='a'*40)
                def stop(sig,frame):raise InterruptedError('fixture-signal')
                signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
                o.start_requested();o.service_started('b'*32)
                try:
                    stamp=m.datetime.datetime.now(m.datetime.timezone.utc).isoformat()
                    o.sample(dict(MainPID='42',ActiveState='active',InvocationID='b'*32),
                        dict(generated_at=stamp,counts=dict(running=1,blocked=0,retrying=0),running=[dict(issue_id='2',session_id='session',last_event_at=stamp)],blocked=[],retrying=[],codex_totals=dict(total_tokens=123)),
                        agent_started=True,hook_finished=False,worker_alive=True)
                    print('READY',flush=True)
                    while True: time.sleep(0.01)
                except InterruptedError:
                    o.finish('operator_interrupted')
                finally: o.close()
            '''))
            checkpoint=Path(root)/'observer-state.json'
            p=subprocess.Popen([sys.executable,'-I','-B',str(child),str(ROOT/'bootstrap/pilot_observer.py'),str(checkpoint)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                # A bounded read: do not let a broken child hang the suite.
                import select
                self.assertTrue(select.select([p.stdout],[],[],5)[0], 'child readiness timeout')
                self.assertEqual(p.stdout.readline().strip(),'READY')
                os.kill(p.pid,signum)
                stdout,stderr=p.communicate(timeout=5)
                self.assertEqual(p.returncode,-signal.SIGKILL if signum==signal.SIGKILL else 0,stderr)
                saved=json.loads(checkpoint.read_text())
                self.assertTrue(saved['session_observed'])
                self.assertEqual(saved['observed_token_counts']['total_tokens'],123)
                self.assertEqual(saved['termination_reason'],None if signum==signal.SIGKILL else 'operator_interrupted')
                self.assertFalse(saved['accepted'])
            finally:
                if p.poll() is None:p.kill();p.wait()
                p.stdout.close();p.stderr.close()


if __name__=='__main__':unittest.main()
