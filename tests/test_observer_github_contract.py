"""Exercise only the built API definitions, never the generated launcher."""
import ast
import importlib.util
import inspect
import io
import json
import os
import signal
import sys
import tempfile
import time
from unittest.mock import patch
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuiltGithubContractTests(unittest.TestCase):
    def built_api(self):
        spec = importlib.util.spec_from_file_location('builder', ROOT / 'bootstrap/build_observer_candidate.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        candidate = builder.build_candidate((ROOT / 'tests/fixtures/boot_p01_launcher_v1.txt').read_bytes())
        tree = ast.parse(candidate)
        self.assertIn('Api.request = diagnostic_api_request', candidate.decode(),
                      'built API is not connected to diagnostics')
        # Select definitions/imports/constants and the explicit API binding only.
        nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))]
        binding = next(n for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Attribute) and t.attr == 'request' for t in n.targets))
        namespace = {'API': '/repos/pupkinson/SymphonyNext', 'MAIN': 'a'*40,
                     'BRANCH': 'pilot/boot-p01', 'LABEL': 'symphony-next-ready'}
        exec(compile(ast.Module(body=nodes + [binding], type_ignores=[]), '<inert-built-api>', 'exec'), namespace)
        return namespace

    def test_actual_built_api_metadata_then_ref403(self):
        namespace = self.built_api()
        records = []; calls = []
        responses = [(200, {}, b'{"id":1381693716}'), (403, {}, b'{}')]
        def transport(api, method, path, body, timeout, **kwargs):
            calls.append((method, path)); return responses.pop(0)
        namespace['github_http_transport'] = transport
        namespace['github_diagnostic_emit'] = records.append
        api = namespace['Api']('inert-credential')
        self.assertEqual(api.get(namespace['API'])['id'], 1381693716)
        with self.assertRaisesRegex(namespace['Stop'], 'github_unknown_403'):
            api.get(namespace['API'] + '/git/ref/heads/main')
        self.assertEqual(len(calls), 2)
        self.assertEqual(records[-1]['endpoint'], namespace['API'] + '/git/ref/heads/main')
        self.assertEqual(records[-1]['classification'], 'unknown_403')
        with self.assertRaisesRegex(namespace['Stop'], 'api_scope_refused'):
            api.request('PUT', namespace['API'])
        self.assertEqual(len(calls), 2)

    def test_lost_mutation_is_reconciled_by_existing_readback(self):
        namespace = self.built_api()
        calls = []; records = []
        label = namespace['LABEL']
        responses = [(200, {}, b'{}'), TimeoutError('injected credential'),
                     (200, {}, ('{"labels":[{"name":"'+label+'"}]}').encode()),
                     (200, {}, b'[{"number":2}]')]
        def transport(api, method, path, body, timeout, **kwargs):
            calls.append(method)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        namespace['github_http_transport'] = transport
        namespace['github_diagnostic_emit'] = records.append
        namespace['atomic_json'] = lambda *args: None
        namespace['RECORD'] = Path('inert-record')
        namespace['admit'](namespace['Api']('inert-credential'))
        self.assertEqual(calls, ['GET', 'POST', 'GET', 'GET'])
        self.assertEqual(records[1]['classification'], 'unknown_outcome')

    def test_actual_http_adapter_with_inert_connection(self):
        namespace = self.built_api()
        records = []
        events = tempfile.TemporaryFile()
        self.addCleanup(events.close)
        def record(event):
            os.write(events.fileno(), json.dumps(event).encode() + b'\n')
        class Response:
            status = 200
            def getheaders(self): return [('Authorization', 'secret')]
            def read(self, limit):
                record(('read', limit)); return b'{}'
        class Connection:
            def request(self, method, path, **kwargs): record((method, path))
            def getresponse(self): return Response()
            def close(self): record(('close',))
        from unittest.mock import patch
        namespace['github_diagnostic_emit'] = records.append
        with patch.object(namespace['http'].client, 'HTTPSConnection', return_value=Connection()):
            self.assertEqual(namespace['Api']('inert-credential').get(namespace['API']), {})
        events.seek(0)
        calls = [json.loads(line) for line in events]
        self.assertEqual(calls, [['GET', namespace['API']], ['read', 2_000_001], ['close']])
        self.assertEqual(records[0]['headers'], {})

    def test_sink_failure_does_not_skip_unknown_write_readback(self):
        ns = self.built_api()
        ns['atomic_json'] = lambda *args: None
        ns['RECORD'] = Path('inert-no-write')
        calls = []
        responses = [(200, {}, b'{}'), TimeoutError('secret'),
                     (200, {}, json.dumps({'labels': [{'name': ns['LABEL']}]}).encode()),
                     (200, {}, b'[{"number":2}]')]
        def transport(api, method, path, body, timeout, **kwargs):
            calls.append(method)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        def sink(text, **kwargs):
            if '"method": "POST"' in text:
                raise BrokenPipeError('secret sink detail')
        ns['github_http_transport'] = transport
        ns['print'] = sink
        api = ns['Api']('inert-credential')
        escaped = None
        try:
            ns['admit'](api)
        except Exception as exc:
            escaped = type(exc).__name__
        self.assertEqual(calls, ['GET', 'POST', 'GET', 'GET'], escaped)
        self.assertIsNone(escaped)
        self.assertEqual(api.github_diagnostics, {'delivery_failed': True})

    def test_sink_failure_does_not_block_admission_cleanup(self):
        for error in (BrokenPipeError, OSError, ValueError):
            with self.subTest(error=error.__name__):
                ns = self.built_api()
                calls = []
                responses = [(200, {}, json.dumps({'labels': [{'name': ns['LABEL']}]}).encode()),
                             (204, {}, b''), (200, {}, b'{"labels":[]}')]
                def transport(api, method, path, body, timeout, **kwargs):
                    calls.append(method)
                    return responses.pop(0)
                def sink(*args, **kwargs):
                    raise error('secret sink detail')
                ns['github_http_transport'] = transport
                ns['print'] = sink
                api = ns['Api']('inert-credential')
                escaped = None
                result = None
                try:
                    result = ns['remove_admission'](api)
                except Exception as exc:
                    escaped = type(exc).__name__
                self.assertEqual(calls, ['GET', 'DELETE', 'GET'], escaped)
                self.assertEqual(result, 'removed_by_owner_cleanup')
                self.assertEqual(api.github_diagnostics, {'delivery_failed': True})

    def test_complete_transport_deadline_stops_each_blocking_stage(self):
        # Real elapsed time and real stdlib HTTPResponse, no external sockets.
        # The legacy signature fallback lets the same assertion reproduce R2.
        for stage in ('connection', 'request', 'headers', 'body'):
            with self.subTest(stage=stage):
                ns = self.built_api()
                events = tempfile.TemporaryFile()
                self.addCleanup(events.close)
                head = b'HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n'
                class Trickle(io.RawIOBase):
                    def __init__(self):
                        self.data = head + b' ' * 18 + b'{}'
                        self.offset = 0
                    def readable(self): return True
                    def readinto(self, target):
                        if self.offset >= len(self.data): return 0
                        in_body = self.offset >= len(head)
                        if (stage == 'body' and in_body) or (stage == 'headers' and not in_body):
                            time.sleep(0.03)
                        target[0] = self.data[self.offset]
                        self.offset += 1
                        return 1
                class Socket:
                    def makefile(self, *args, **kwargs): return io.BufferedReader(Trickle())
                class Connection:
                    def __init__(self, *args, **kwargs):
                        os.write(events.fileno(), str(os.getpid()).encode())
                        if stage == 'connection': time.sleep(0.6)
                    def request(self, *args, **kwargs):
                        if stage == 'request': time.sleep(0.6)
                    def getresponse(self):
                        response = ns['http'].client.HTTPResponse(Socket())
                        response.begin()
                        return response
                    def close(self): pass
                fn = ns['github_http_transport']
                started = time.monotonic()
                deadline = started + 0.12
                kwargs = {'deadline': deadline} if 'deadline' in inspect.signature(fn).parameters else {}
                escaped = None
                with patch.object(ns['http'].client, 'HTTPSConnection', Connection):
                    try:
                        fn(ns['Api']('inert-credential'), 'GET', ns['API'], None, 15, **kwargs)
                    except TimeoutError:
                        escaped = 'timeout'
                elapsed = time.monotonic() - started
                self.assertEqual(escaped, 'timeout', f'{stage} returned after {elapsed:.3f}s')
                self.assertLess(elapsed, 0.5, stage)
                events.seek(0)
                child_pid = int(events.read())
                self.assertNotEqual(child_pid, os.getpid())
                with self.assertRaises(ChildProcessError):
                    os.waitpid(child_pid, os.WNOHANG)

    def test_deadline_after_mutation_is_unknown_and_never_replayed(self):
        ns = self.built_api()
        records = []
        with tempfile.TemporaryFile() as events:
            class Connection:
                def request(self, method, path, **kwargs):
                    os.write(events.fileno(), method.encode() + b'\n')
                    time.sleep(0.6)
                def getresponse(self):
                    return type('Response', (), {'status': 201,
                        'getheaders': lambda self: [], 'read': lambda self, size: b'{}'})()
                def close(self): pass
            deadline = time.monotonic() + 0.12
            fn = ns['github_http_transport']
            kwargs = {'deadline': deadline} if 'deadline' in inspect.signature(fn).parameters else {}
            with patch.object(ns['http'].client, 'HTTPSConnection', return_value=Connection()):
                with self.assertRaisesRegex(ns['GithubDiagnosticError'], 'unknown_outcome'):
                    ns['github_request']('POST', ns['API'] + '/labels',
                        lambda timeout: fn(ns['Api']('inert-credential'), 'POST', ns['API']+'/labels', {}, timeout, **kwargs),
                        emit=records.append, deadline=deadline)
            events.seek(0)
            self.assertEqual(events.read(), b'POST\n')
        self.assertEqual(records[-1]['classification'], 'unknown_outcome')

    def test_unverified_child_cleanup_blocks_all_later_transport(self):
        ns = self.built_api()
        self.assertIn('github_reap_transport', ns, 'no supervised transport cleanup')
        api = ns['Api']('inert-credential')
        # No real child is created by this fixture. A refused kill must latch
        # the failure before the caller attempts its mandatory readback.
        with patch.object(ns['os'], 'fork', return_value=123456789) as fork, \
             patch.object(ns['select'], 'select', return_value=([], [], [])), \
             patch.object(ns['os'], 'kill', side_effect=PermissionError('secret')):
            for _ in range(2):
                reason = None
                try:
                    ns['github_http_transport'](api, 'GET', ns['API'], None, 15,
                        deadline=time.monotonic()+1)
                except Exception as exc:
                    reason = exc.reason if isinstance(exc, ns['GithubDiagnosticError']) else type(exc).__name__
                self.assertEqual(reason, 'transport_cleanup_unverified')
            self.assertEqual(fork.call_count, 1)

    def test_parent_interruption_kills_and_reaps_only_its_transport(self):
        ns = self.built_api()
        self.assertIn('github_reap_transport', ns, 'no supervised transport cleanup')
        api = ns['Api']('inert-credential')
        events = tempfile.TemporaryFile()
        self.addCleanup(events.close)
        class Connection:
            def request(self, *args, **kwargs):
                os.write(events.fileno(), str(os.getpid()).encode())
                time.sleep(10)
            def close(self): pass
        def interrupted(*args):
            # Wait only for our child to enter request, then interrupt its owner.
            until = time.monotonic() + 1
            while os.fstat(events.fileno()).st_size == 0 and time.monotonic() < until:
                time.sleep(0.005)
            raise KeyboardInterrupt()
        with patch.object(ns['http'].client, 'HTTPSConnection', return_value=Connection()), \
             patch.object(ns['select'], 'select', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                ns['github_http_transport'](api, 'GET', ns['API'], None, 15,
                    deadline=time.monotonic()+2)
        events.seek(0)
        child_pid = int(events.read())
        self.assertNotEqual(child_pid, os.getpid())
        with self.assertRaises(ChildProcessError):
            os.waitpid(child_pid, os.WNOHANG)

    def test_foreign_child_reaper_is_refused_before_fork(self):
        ns = self.built_api()
        with patch.object(ns['signal'], 'getsignal', return_value=ns['signal'].SIG_IGN), \
             patch.object(ns['os'], 'fork', side_effect=AssertionError('fork must not be called')) as fork:
            reason = None
            try:
                ns['github_http_transport'](ns['Api']('inert'), 'GET', ns['API'], None, 15,
                    deadline=time.monotonic()+1)
            except Exception as exc:
                reason = exc.reason if isinstance(exc, ns['GithubDiagnosticError']) else type(exc).__name__
            self.assertEqual(reason, 'transport_context_unsupported')
            fork.assert_not_called()

    def test_child_has_its_own_deadline_if_parent_stops_observing(self):
        ns = self.built_api()
        events = tempfile.TemporaryFile()
        self.addCleanup(events.close)
        class Connection:
            def request(self, *args, **kwargs):
                os.write(events.fileno(), str(os.getpid()).encode())
                time.sleep(0.6)
            def getresponse(self):
                return type('Response', (), {'status': 200,
                    'getheaders': lambda self: [], 'read': lambda self, size: b'{}'})()
            def close(self): pass
        exit_status = []
        real_waitpid = os.waitpid
        def waitpid(pid, flags):
            value = real_waitpid(pid, flags)
            if value[0]: exit_status.append(value[1])
            return value
        def delayed_observer(*args):
            time.sleep(0.25)
            return ([args[0][0]], [], [])
        with patch.object(ns['http'].client, 'HTTPSConnection', return_value=Connection()), \
             patch.object(ns['select'], 'select', side_effect=delayed_observer), \
             patch.object(ns['os'], 'waitpid', side_effect=waitpid):
            with self.assertRaises(TimeoutError):
                ns['github_http_transport'](ns['Api']('inert'), 'GET', ns['API'], None, 15,
                    deadline=time.monotonic()+0.12)
        self.assertEqual(len(exit_status), 1)
        self.assertTrue(os.WIFSIGNALED(exit_status[0]))
        self.assertEqual(os.WTERMSIG(exit_status[0]), ns['signal'].SIGALRM)


class ActualOwnerSignals(unittest.TestCase):
    def setUp(self):
        self.ns=BuiltGithubContractTests().built_api()
        self.original_handler=signal.getsignal(signal.SIGINT)
        self.original_mask=signal.pthread_sigmask(signal.SIG_UNBLOCK,{signal.SIGINT})
        signal.signal(signal.SIGINT,self.ns['interrupted'])
        self.real_kill=os.kill;self.real_waitpid=os.waitpid;self.real_fork=os.fork
        self.own_pid=os.getpid()
    def tearDown(self):
        signal.signal(signal.SIGINT,self.original_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK,self.original_mask)
    def send_owner_interrupt(self):
        assert self.own_pid==os.getpid()
        self.real_kill(self.own_pid,signal.SIGINT)
    def test_second_sigint_at_cleanup_entry_cannot_abandon_child(self):
        # R5: inject at the first cleanup line, independent of how many mask
        # calls the implementation uses. Only real SIGINT to this test PID.
        ns=self.ns; api=ns['Api']('inert'); owned=[]; sent=[]
        fn=ns['github_http_transport']; unwinding=False
        previous_trace=sys.gettrace()
        def trace(frame,event,arg):
            nonlocal unwinding
            if os.getpid()==self.own_pid and frame.f_code is fn.__code__:
                if event=='exception' and isinstance(arg[1],ns['Stop']) and not sent[1:]:
                    unwinding=True
                elif event=='line' and unwinding:
                    unwinding=False
                    sent.append('cleanup-entry')
                    self.send_owner_interrupt()
            return trace
        with tempfile.TemporaryFile() as events:
            class Connection:
                def request(self,*args,**kwargs):
                    os.write(events.fileno(),b'entered');time.sleep(0.6)
                def close(self):pass
            def fork():
                pid=self.real_fork()
                if pid:owned.append(pid)
                return pid
            def interrupt_observation(*args):
                until=time.monotonic()+0.1
                while not os.fstat(events.fileno()).st_size and time.monotonic()<until:time.sleep(0.001)
                sent.append('observation')
                self.send_owner_interrupt()
                return ([],[],[])
            escaped=None;live=None
            try:
                with patch.object(ns['http'].client,'HTTPSConnection',return_value=Connection()), \
                     patch.object(ns['os'],'fork',side_effect=fork), \
                     patch.object(ns['select'],'select',side_effect=interrupt_observation):
                    sys.settrace(trace)
                    try:fn(api,'POST',ns['API']+'/labels',{},15,deadline=time.monotonic()+0.2)
                    except BaseException as exc:escaped=(type(exc).__name__,str(exc))
                    finally:sys.settrace(previous_trace)
                self.assertEqual(len(owned),1)
                try:live=self.real_waitpid(owned[0],os.WNOHANG)==(0,0)
                except ChildProcessError:live=False
            finally:
                sys.settrace(previous_trace)
                for pid in owned:
                    try:self.real_waitpid(pid,0)
                    except ChildProcessError:pass
            self.assertTrue(os.fstat(events.fileno()).st_size,'inert request was not entered')
            print(json.dumps({'case':'R5_cleanup_entry','sent':sent,'escaped':escaped,
                'live_child_after_return':live,'cleanup_latched':getattr(api,'github_transport_cleanup_failed',False)}),flush=True)
            self.assertEqual(sent,['observation','cleanup-entry'])
            self.assertFalse(live,'second SIGINT escaped cleanup with an active owned child')
            self.assertEqual(escaped,('Stop','operator_interrupted'))
    def test_second_sigint_during_cleanup_does_not_leave_live_child(self):
        ns=self.ns; api=ns['Api']('inert'); owned=[]
        real_send=signal.pidfd_send_signal
        with tempfile.TemporaryFile() as events:
            class Connection:
                def request(self,*args,**kwargs):
                    os.write(events.fileno(),b'entered'); time.sleep(0.6)
                def close(self):pass
            def fork():
                pid=self.real_fork()
                if pid:owned.append(pid)
                return pid
            def interrupt_observation(*args):
                until=time.monotonic()+0.1
                while not os.fstat(events.fileno()).st_size and time.monotonic()<until:time.sleep(0.001)
                self.send_owner_interrupt()
            def interrupt_cleanup(fd,sig):
                self.send_owner_interrupt()
                return real_send(fd,sig)
            escaped=None;live=None
            try:
                with patch.object(ns['http'].client,'HTTPSConnection',return_value=Connection()), \
                     patch.object(ns['os'],'fork',side_effect=fork), \
                     patch.object(ns['select'],'select',side_effect=interrupt_observation), \
                     patch.object(ns['signal'],'pidfd_send_signal',side_effect=interrupt_cleanup):
                    try:ns['github_http_transport'](api,'POST',ns['API']+'/labels',{},15,deadline=time.monotonic()+0.2)
                    except BaseException as exc:escaped=(type(exc).__name__,str(exc))
                self.assertEqual(len(owned),1)
                try:live=self.real_waitpid(owned[0],os.WNOHANG)==(0,0)
                except ChildProcessError:live=False
            finally:
                for pid in owned:
                    try:self.real_waitpid(pid,0)
                    except ChildProcessError:pass
            self.assertFalse(live,'a second owner interrupt skipped child cleanup')
            self.assertEqual(escaped,('Stop','operator_interrupted'))
    def test_pending_stop_is_prompt_and_handler_runs_after_resource_cleanup(self):
        for signum in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):
            with self.subTest(signum=signum):
                ns=self.ns;owned=[];fds=[];maps=[];handler_observations=[]
                real_select=ns['select'].select;real_pipe=os.pipe2
                real_pidfd=os.pidfd_open;real_mmap=ns['mmap'].mmap
                previous=signal.getsignal(signum)
                previous_mask=signal.pthread_sigmask(signal.SIG_UNBLOCK,{signum})
                def handler(sig,frame):
                    closed=[]
                    for fd in fds:
                        try:os.fstat(fd);closed.append(False)
                        except OSError:closed.append(True)
                    try:self.real_waitpid(owned[0],os.WNOHANG);reaped=False
                    except ChildProcessError:reaped=True
                    handler_observations.append((all(closed),all(m.closed for m in maps),reaped))
                    ns['interrupted'](sig,frame)
                signal.signal(signum,handler)
                with tempfile.TemporaryFile() as events:
                    class Connection:
                        def request(self,*args,**kwargs):
                            os.write(events.fileno(),b'entered');time.sleep(3)
                        def close(self):pass
                    def fork():
                        pid=self.real_fork()
                        if pid:owned.append(pid)
                        return pid
                    def pipe(flags):
                        pair=real_pipe(flags);fds.extend(pair);return pair
                    def pidfd(pid,*args):
                        fd=real_pidfd(pid,*args);fds.append(fd);return fd
                    def mapping(*args):
                        m=real_mmap(*args);maps.append(m);return m
                    def interrupt_wait(*args):
                        until=time.monotonic()+0.1
                        while not os.fstat(events.fileno()).st_size and time.monotonic()<until:time.sleep(0.001)
                        assert os.getpid()==self.own_pid
                        self.real_kill(self.own_pid,signum)
                        return real_select(*args)
                    started=time.monotonic()
                    try:
                        with patch.object(ns['http'].client,'HTTPSConnection',return_value=Connection()), \
                             patch.object(ns['os'],'fork',side_effect=fork), \
                             patch.object(ns['os'],'pipe2',side_effect=pipe), \
                             patch.object(ns['os'],'pidfd_open',side_effect=pidfd), \
                             patch.object(ns['mmap'],'mmap',side_effect=mapping), \
                             patch.object(ns['select'],'select',side_effect=interrupt_wait):
                            with self.assertRaisesRegex(ns['Stop'],'operator_interrupted'):
                                ns['github_http_transport'](ns['Api']('inert'),'POST',ns['API']+'/labels',{},15,
                                    deadline=time.monotonic()+2)
                        elapsed=time.monotonic()-started
                        self.assertLess(elapsed,0.5,'operator stop waited for the two-second HTTP deadline')
                        self.assertEqual(handler_observations,[(True,True,True)])
                        self.assertIs(signal.getsignal(signum),handler)
                        self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK,set()),previous_mask-{signum})
                    finally:
                        for pid in owned:
                            try:self.real_waitpid(pid,0)
                            except ChildProcessError:pass
                        signal.signal(signum,previous)
                        signal.pthread_sigmask(signal.SIG_SETMASK,previous_mask)
    def test_caller_blocked_pending_signal_is_preserved(self):
        ns=self.ns
        class Connection:
            def request(self,*args,**kwargs):pass
            def getresponse(self):return type('Response',(),{'status':200,'getheaders':lambda self:[], 'read':lambda self,size:b'{}'})()
            def close(self):pass
        previous_mask=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT})
        try:
            self.send_owner_interrupt()
            with patch.object(ns['http'].client,'HTTPSConnection',return_value=Connection()):
                response=ns['github_http_transport'](ns['Api']('inert'),'GET',ns['API'],None,15,
                    deadline=time.monotonic()+1)
            self.assertEqual(response,(200,{},b'{}'))
            self.assertIn(signal.SIGINT,signal.sigpending())
            self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK,set()),previous_mask|{signal.SIGINT})
        finally:
            # Consume only the self-SIGINT queued by this fixture before restoring.
            if signal.SIGINT in signal.sigpending():signal.sigwait({signal.SIGINT})
            signal.pthread_sigmask(signal.SIG_SETMASK,previous_mask)
    def test_actual_sigint_after_reap_does_not_signal_released_pid(self):
        ns=self.ns;api=ns['Api']('inert');owned=[];events=[]
        class Connection:
            def request(self,*args,**kwargs):pass
            def getresponse(self):return type('Response',(),{'status':200,'getheaders':lambda self:[], 'read':lambda self,size:b'{}'})()
            def close(self):pass
        def fork():
            pid=self.real_fork()
            if pid:owned.append(pid)
            return pid
        def waitpid(pid,flags):
            result=self.real_waitpid(pid,flags)
            if result[0]:
                events.append(('reaped',pid))
                self.send_owner_interrupt()
            return result
        def record_kill(pid,sig):events.append(('would_signal',pid,int(sig)))
        escaped=None
        try:
            with patch.object(ns['http'].client,'HTTPSConnection',return_value=Connection()), \
                 patch.object(ns['os'],'fork',side_effect=fork), \
                 patch.object(ns['os'],'waitpid',side_effect=waitpid), \
                 patch.object(ns['os'],'kill',side_effect=record_kill):
                try:ns['github_http_transport'](api,'GET',ns['API'],None,15,deadline=time.monotonic()+0.25)
                except BaseException as exc:escaped=(type(exc).__name__,str(exc))
        finally:
            for pid in owned:
                try:self.real_waitpid(pid,0)
                except ChildProcessError:pass
        print(json.dumps({'case':'actual_sigint_after_reap','events':events,'escaped':escaped,'cleanup_latched':getattr(api,'github_transport_cleanup_failed',False)}),flush=True)
        self.assertEqual([e for e in events if e[0]=='would_signal'],[], 'released numeric PID must not be signalled')
        self.assertEqual(escaped,('Stop','operator_interrupted'))
    def test_actual_sigint_at_fork_return_does_not_leave_live_child(self):
        ns=self.ns;api=ns['Api']('inert');owned=[]
        with tempfile.TemporaryFile() as events:
            class Connection:
                def request(self,*args,**kwargs):
                    os.write(events.fileno(),b'inert-post-entered');time.sleep(0.6)
                def close(self):pass
            def fork():
                pid=self.real_fork()
                if pid:
                    owned.append(pid)
                    until=time.monotonic()+0.1
                    while not os.fstat(events.fileno()).st_size and time.monotonic()<until:time.sleep(0.001)
                    self.send_owner_interrupt()
                return pid
            escaped=None;live=None
            try:
                with patch.object(ns['http'].client,'HTTPSConnection',return_value=Connection()), \
                     patch.object(ns['os'],'fork',side_effect=fork):
                    try:ns['github_http_transport'](api,'POST',ns['API']+'/labels',{},15,deadline=time.monotonic()+0.2)
                    except BaseException as exc:escaped=(type(exc).__name__,str(exc))
                self.assertEqual(len(owned),1)
                try:live=self.real_waitpid(owned[0],os.WNOHANG)==(0,0)
                except ChildProcessError:live=False
            finally:
                for pid in owned:
                    try:self.real_waitpid(pid,0)
                    except ChildProcessError:pass
            events.seek(0)
            print(json.dumps({'case':'actual_sigint_at_fork_return','escaped':escaped,'live_child_after_return':live,'request_entered':bool(events.read()),'cleanup_latched':getattr(api,'github_transport_cleanup_failed',False)}),flush=True)
            self.assertFalse(live,'owner interruption returned with an untracked live HTTP child')
            self.assertEqual(escaped,('Stop','operator_interrupted'))
