"""Exact candidate lifecycle with inert systemd; no host/model execution."""
import ast
import contextlib
import errno
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_pilot_observer import BASE, INVOCATION, Clock, artifact, runtime, service
ROOT=Path(__file__).resolve().parents[1]

def load(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class StartBoundaryTests(unittest.TestCase):
    def case(self,fault,foreign=False,delay_witness=False,unsafe_limit=False,missing_witness=False,
             persistence_fault=None, after_observation=False, replace_before_stop=False,
             result_write_failure=False, details=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);clock=Clock();commands=[];active=[False];seen=[0];read_fault=[False]
            started=[False];persistence_armed=[False];persistence_calls=[];cleanup_calls=[]
            builder=load(ROOT/'bootstrap/build_observer_candidate.py','start_builder')
            source=builder.build_candidate((ROOT/'tests/fixtures/boot_p01_launcher_v1.txt').read_bytes())
            path=root/'candidate.py';path.write_bytes(source);c=load(path,'start_candidate')
            node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='launch')
            at=next(i for i,n in enumerate(node.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='wf' for t in n.targets))
            fn=ast.FunctionDef(name='fixture_lifecycle',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=[
                ast.Assign(targets=[ast.Name(id='original',ctx=ast.Store())],value=ast.Constant(value=b'disabled workflow')),
                ast.Assign(targets=[ast.Name(id='report',ctx=ast.Store())],value=ast.Dict(keys=[ast.Constant(value='model_profile')],values=[ast.Dict(keys=[],values=[])])),
                ast.Assign(targets=[ast.Name(id='api',ctx=ast.Store())],value=ast.Constant(value=None))]+node.body[at:],decorator_list=[])
            code=compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<candidate-start-finally>','exec')
            c.CONF=root/'conf';c.CONF.mkdir();c.WORKFLOW=c.CONF/'WORKFLOW.md';c.WORKFLOW.write_bytes(b'disabled workflow');c.READY=c.CONF/'READY'
            c.RUN=root/'run';c.RUN.mkdir();c.RECORD=root/'record';c.RECORD.mkdir(mode=0o700);c.DROP=root/'drop'/'90.conf';c.UNIT_PATH=root/'unit';c.DRIVER=path
            c.create_file=lambda p,b,*a,**k:Path(p).write_bytes(b)
            c.atomic_bytes=lambda p,b,*a,**k:Path(p).write_bytes(b)
            c.read_file=lambda p,*a,**k:Path(p).read_bytes()
            c.admit=lambda api:None
            c.remove_admission=lambda api:(cleanup_calls.append('label'),'already_absent')[1]
            c.result_readback=lambda api:(cleanup_calls.append('readback'),artifact())[1]
            saved_atomic_json=c.atomic_json
            def write_report(p,data):
                if result_write_failure and p==c.RECORD/'result.json':
                    raise OSError(errno.ENOSPC,'fixture_result_disk_full')
                return saved_atomic_json(p,data)
            c.atomic_json=write_report
            def witness():
                if hasattr(c,'record_start_witness') and not missing_witness:
                    with patch.object(c.os,'getuid',return_value=995),patch.object(c.os,'getgid',return_value=995),patch.object(c.socket,'gethostname',return_value='1c-db'),patch.dict(c.os.environ,{'INVOCATION_ID':INVOCATION}):
                        c.record_start_witness()
            def state():
                if active[0]:
                    seen[0]+=1
                    if delay_witness and seen[0]==2:witness()
                d=service(active[0],invocation=('f'*32 if foreign else INVOCATION))
                d.update(Id=c.UNIT,Type='simple',Restart='no',RuntimeMaxUSec='infinity' if unsafe_limit else '30min',TimeoutStartUSec='45s',TimeoutStopUSec='45s',KillMode='control-group',SendSIGKILL='yes',Job='0',DropInPaths=str(c.DROP))
                return d
            def run(args,**kwargs):
                commands.append(args)
                if 'show' in args:
                    if active[0] and fault in ('bind_interrupt','bind_timeout') and not read_fault[0]:
                        read_fault[0]=True
                        raise c.Stop('operator_interrupted' if fault=='bind_interrupt' else 'local_command_timeout_systemctl')
                    return '\n'.join(k+'='+v for k,v in state().items())
                if 'start' in args:
                    active[0]=True;started[0]=True
                    if not delay_witness:witness()
                    if fault=='timeout':raise c.Stop('local_command_timeout_systemctl')
                    if fault=='interrupt':raise c.Stop('operator_interrupted')
                if 'stop' in args:active[0]=False
                return ''
            c.run=run
            def final_state():
                d=state()
                if replace_before_stop and active[0]:d['InvocationID']='f'*32
                return d
            c.unit_state=final_state
            old_class=c.PilotObserver
            original_save=old_class._save
            def fail_checkpoint(monitor):
                if persistence_fault and started[0] and (not after_observation or monitor.state.get('session_observed')):
                    persistence_armed[0]=True
                if persistence_armed[0]:
                    persistence_calls.append('save_failed')
                    if persistence_fault=='ObserverError':raise c.ObserverError('fixture_checkpoint_error')
                    raise OSError(errno.ENOSPC,'fixture_checkpoint_disk_full')
                return original_save(monitor)
            c.PilotObserver=lambda p,**kw:old_class(p,operation=kw['operation'],source=kw['source'],clock=clock.mono,wall=clock.wall,idle_grace=6,startup_limit=12,wall_limit=120)
            c.observer_runtime_read=lambda:runtime(clock,clock.n==0)
            c.observer_worker_alive=lambda:clock.n==0
            exec(code,c.__dict__)
            printed=io.StringIO();escaped=None
            with patch.object(old_class,'_save',fail_checkpoint),patch.object(c.time,'monotonic',clock.mono),patch.object(c.time,'sleep',clock.advance),patch.object(c.signal,'signal'),contextlib.redirect_stdout(printed):
                try:c.fixture_lifecycle()
                except SystemExit:pass
                except (OSError,c.ObserverError) as exc:
                    if not details:raise
                    escaped=type(exc).__name__
            result_path=c.RECORD/'result.json'
            result=json.loads(result_path.read_text()) if result_path.exists() else None
            if details:
                return dict(result=result,commands=commands,active=active[0],elapsed=clock.n,
                    escaped=escaped,persistence_calls=len(persistence_calls),cleanup_calls=cleanup_calls,
                    workflow_restored=c.WORKFLOW.read_bytes()==b'disabled workflow',
                    ready_present=c.READY.exists(),window_present=(c.CONF/'BOOT_P01_WINDOW').exists(),
                    dropin_present=c.DROP.exists(),printed=printed.getvalue())
            return result,commands,active[0],clock.n

    def test_interrupt_after_start_reconciles_and_stops_own_service(self):
        r,cmds,active,_=self.case('interrupt')
        self.assertFalse(active,'started service left running after interruption')
        self.assertEqual(sum('stop' in c for c in cmds),1)
        self.assertEqual(r['runtime_observations']['invocation_id'],INVOCATION)
        self.assertEqual(r['cleanup_warnings'],[])
    def test_timeout_after_start_reconciles_and_stops_own_service(self):
        r,cmds,active,_=self.case('timeout')
        self.assertFalse(active,'started service left running after timeout')
        self.assertEqual(sum('start' in c for c in cmds),1)
        self.assertEqual(sum('stop' in c for c in cmds),1)
    def test_delayed_witness_uses_bounded_reads_not_second_start(self):
        r,cmds,active,elapsed=self.case('timeout',delay_witness=True)
        self.assertFalse(active);self.assertLessEqual(elapsed,15)
        self.assertEqual(sum('start' in c for c in cmds),1)
    def test_interrupt_during_first_invocation_read_is_reconciled(self):
        r,cmds,active,_=self.case('bind_interrupt')
        self.assertFalse(active);self.assertEqual(sum('stop' in c for c in cmds),1)
        self.assertEqual(r['runtime_observations']['invocation_id'],INVOCATION)
    def test_timeout_during_first_invocation_read_is_bounded(self):
        r,cmds,active,elapsed=self.case('bind_timeout')
        self.assertFalse(active);self.assertEqual(sum('start' in c for c in cmds),1)
        self.assertEqual(sum('stop' in c for c in cmds),1)
        self.assertLess(elapsed,120)
    def test_other_invocation_is_not_stopped(self):
        r,cmds,active,_=self.case('interrupt',foreign=True)
        self.assertTrue(active);self.assertEqual(sum('stop' in c for c in cmds),0)
        self.assertIn('service_stop_unconfirmed',r['cleanup_warnings'])
    def test_without_witness_no_false_ownership_and_no_relaunch(self):
        r,cmds,active,elapsed=self.case('timeout',missing_witness=True)
        self.assertTrue(active);self.assertEqual(sum('stop' in c for c in cmds),0)
        self.assertLessEqual(elapsed,15);self.assertEqual(sum('start' in c for c in cmds),1)
        self.assertTrue(r['runtime_observations'].get('manager_deadline_verified'))
    def test_independent_manager_deadline_required_before_start(self):
        r,cmds,active,_=self.case('timeout',unsafe_limit=True)
        self.assertFalse(active);self.assertEqual(sum('start' in c for c in cmds),0)

if __name__=='__main__':unittest.main()
