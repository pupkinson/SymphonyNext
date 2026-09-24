"""Exercise only the built API definitions, never the generated launcher."""
import ast
import importlib.util
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
        def transport(api, method, path, body, timeout):
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
        def transport(api, method, path, body, timeout):
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
        calls = []; records = []
        class Response:
            status = 200
            def getheaders(self): return [('Authorization', 'secret')]
            def read(self, limit):
                calls.append(('read', limit)); return b'{}'
        class Connection:
            def request(self, method, path, **kwargs): calls.append((method, path))
            def getresponse(self): return Response()
            def close(self): calls.append(('close',))
        from unittest.mock import patch
        namespace['github_diagnostic_emit'] = records.append
        with patch.object(namespace['http'].client, 'HTTPSConnection', return_value=Connection()):
            self.assertEqual(namespace['Api']('inert-credential').get(namespace['API']), {})
        self.assertEqual(calls, [('GET', namespace['API']), ('read', 2_000_001), ('close',)])
        self.assertEqual(records[0]['headers'], {})
