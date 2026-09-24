"""Inert HTTP fixtures; retries use virtual time exclusively."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_core():
    path = ROOT / 'bootstrap/github_diagnostics.py'
    spec = importlib.util.spec_from_file_location('github_diagnostics', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'bootstrap/github_diagnostics.py').exists(),
                        'structured diagnostics is not implemented')
        self.m = load_core()
        self.now = 0
        self.calls = []
        self.records = []

    def sleep(self, seconds):
        self.now += seconds

    def run_request(self, responses, method='GET', deadline=100, expected=False):
        def transport(timeout):
            self.calls.append((self.now, timeout))
            value = responses.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        return self.m.github_request(method, '/repos/pupkinson/SymphonyNext',
            transport, emit=self.records.append, clock=lambda: self.now,
            sleep=self.sleep, deadline=deadline, expected_404=expected)

    def test_classifications(self):
        cases = [(401, {}, b'{}', 'auth'),
                 (403, {}, b'{"message":"Resource not accessible by personal access token"}', 'permission'),
                 (403, {}, b'{}', 'unknown_403'),
                 (404, {}, b'{}', 'http_error'),
                 (200, {}, b'bad', 'malformed_response'),
                 (200, {}, b'x' * 2_000_001, 'oversized_response')]
        for status, headers, raw, reason in cases:
            with self.subTest(reason=reason):
                with self.assertRaises(self.m.GithubDiagnosticError) as caught:
                    self.run_request([(status, headers, raw)])
                self.assertEqual(caught.exception.reason, reason)
                self.assertEqual(self.records[-1]['classification'], reason)

    def test_rate_and_transient_retries(self):
        for response in [(403, {'X-RateLimit-Remaining': '0'}, b'{}'),
                         (429, {}, b'{}'), (503, {}, b'{}'), TimeoutError('secret')]:
            with self.subTest(response=type(response).__name__):
                self.calls.clear(); self.now = 0
                self.assertEqual(self.run_request([response, response, (200, {}, b'{}')]), (200, {}))
                self.assertEqual([x[0] for x in self.calls], [0, 10, 70])

    def test_retry_after_and_deadline(self):
        self.run_request([(429, {'Retry-After': '20'}, b'{}'), (200, {}, b'{}')])
        self.assertEqual(self.calls[1][0], 20)
        self.calls.clear(); self.now = 0
        with self.assertRaisesRegex(self.m.GithubDiagnosticError, 'deadline_exhausted'):
            self.run_request([(503, {}, b'{}')], deadline=5)
        self.assertEqual(len(self.calls), 1)
        self.calls.clear()
        with self.assertRaisesRegex(self.m.GithubDiagnosticError, 'deadline_exhausted'):
            self.run_request([], deadline=0)
        self.assertEqual(self.calls, [])

    def test_expected_404(self):
        self.assertEqual(self.run_request([(404, {}, b'{}')], expected=True), (404, {}))
        self.assertEqual(self.records[-1]['classification'], 'expected_404')

    def test_mutations_never_retry(self):
        for method in ('POST', 'DELETE', 'PATCH', 'PUT'):
            for response in (TimeoutError('credential'), (503, {}, b'{}'), (201, {}, b'bad')):
                self.calls.clear()
                with self.assertRaisesRegex(self.m.GithubDiagnosticError, 'unknown_outcome'):
                    self.run_request([response], method=method)
                self.assertEqual(len(self.calls), 1)

    def test_no_provider_text_or_credentials_in_records(self):
        secret = 'github_pat_injected_credential'
        headers = {key: secret for key in ('Authorization', 'X-GitHub-Request-Id',
                   'X-Accepted-GitHub-Permissions', 'Retry-After', 'X-RateLimit-Reset')}
        self.run_request([(200, headers, json.dumps({'body': secret}).encode())])
        self.assertNotIn(secret, json.dumps(self.records))
        self.assertEqual(self.records[-1]['headers'], {})

    def test_safe_headers(self):
        headers = {'X-GitHub-Request-Id': 'AB12:CD34:EF56:1234',
                   'X-Accepted-GitHub-Permissions': 'contents=read',
                   'X-RateLimit-Remaining': '10', 'Retry-After': '2'}
        self.run_request([(200, headers, b'{}')])
        self.assertEqual(len(self.records[-1]['headers']), 4)

    def test_exhausted_attempts(self):
        with self.assertRaisesRegex(self.m.GithubDiagnosticError, 'transient_http'):
            self.run_request([(502, {}, b'{}')] * 3)
        self.assertEqual([x[0] for x in self.calls], [0, 10, 70])
        self.assertEqual([r['attempt'] for r in self.records], [1, 2, 3])

    def test_http_date_retry_after_and_invalid_headers(self):
        headers = self.m.github_safe_headers({'Retry-After': 'Thu, 01 Jan 1970 00:01:30 GMT'})
        self.assertEqual(self.m.github_retry_after(headers, lambda: 70), 20)
        for value in ('-1', 'nan', 'Bearer secret', 'Thu, 01 Jan 1970 00:01:30 GMT\nsecret'):
            self.assertEqual(self.m.github_safe_headers({'Retry-After': value}), {})

    def test_unknown403_is_single_attempt_and_no_false_permission(self):
        with self.assertRaisesRegex(self.m.GithubDiagnosticError, 'unknown_403'):
            self.run_request([(403, {'X-Accepted-GitHub-Permissions': 'contents=read'},
                               b'{"message":"injected secret"}')])
        self.assertEqual(len(self.calls), 1)

    def test_unsafe_endpoint_rejected_before_transport(self):
        for endpoint in ('https://user:secret@github.com', '/repos/pupkinson/SymphonyNext?token=secret',
                         '/repos/pupkinson/SymphonyNext/../secret'):
            with self.assertRaisesRegex(self.m.GithubDiagnosticError, 'diagnostic_scope_refused'):
                self.m.github_request('GET', endpoint, lambda timeout: self.fail('transport called'),
                                      emit=self.records.append, deadline=100)
        self.assertEqual(self.records, [])
