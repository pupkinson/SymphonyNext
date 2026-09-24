"""Bounded, allowlisted GitHub diagnostics. No provider text is emitted.

The caller validates authorization before calling this helper. Transport returns
(status, headers, bounded bytes), never writes evidence, and respects timeout.
"""
import email.utils
import http.client
import json
import re
import time


class GithubDiagnosticError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def github_safe_headers(headers):
    safe = {}
    for name, value in headers.items():
        name = name.lower()
        if not isinstance(value, str) or len(value) > 256:
            continue
        valid = False
        if name == 'x-github-request-id':
            valid = re.fullmatch(r'[0-9A-Fa-f]{4,32}(?::[0-9A-Fa-f]{4,32}){1,5}', value)
        elif name == 'x-accepted-github-permissions':
            valid = re.fullmatch(r'(?:contents|metadata|issues|pull_requests)=(?:read|write)(?:[;,] ?(?:contents|metadata|issues|pull_requests)=(?:read|write))*', value)
        elif name in ('x-ratelimit-remaining', 'x-ratelimit-limit', 'x-ratelimit-reset'):
            valid = re.fullmatch(r'[0-9]{1,12}', value)
        elif name == 'retry-after':
            valid = re.fullmatch(r'[0-9]{1,10}', value)
            if not valid:
                try:
                    date = email.utils.parsedate_to_datetime(value)
                    valid = date.tzinfo is not None and email.utils.format_datetime(date, usegmt=True) == value
                except (TypeError, ValueError, OverflowError):
                    pass
        if valid:
            safe[name] = value
    return safe


def github_retry_after(headers, wall):
    value = headers.get('retry-after')
    if value is None:
        return 0
    if value.isdigit():
        return int(value)
    return max(0, email.utils.parsedate_to_datetime(value).timestamp() - wall())


def github_request(method, endpoint, transport, *, emit, deadline,
                   clock=time.monotonic, sleep=time.sleep, wall=time.time,
                   expected_404=False, delivery_state=None):
    # This is a diagnostic safety boundary, not an authorization grant.
    if method not in ('GET', 'POST', 'DELETE', 'PATCH', 'PUT') or not re.fullmatch(
            r'/repos/pupkinson/SymphonyNext(?:/[A-Za-z0-9_./-]+)?', endpoint):
        raise GithubDiagnosticError('diagnostic_scope_refused')
    if any(part in ('.', '..') for part in endpoint.split('/')):
        raise GithubDiagnosticError('diagnostic_scope_refused')
    for attempt in range(1, 4):
        remaining = deadline - clock()
        if remaining <= 0:
            raise GithubDiagnosticError('deadline_exhausted')
        started = clock()
        status = None
        headers = {}
        transport_error = None
        value = None
        try:
            status, received_headers, raw = transport(min(15, remaining))
            headers = github_safe_headers(received_headers)
            if len(raw) > 2_000_000:
                reason = 'oversized_response'
            else:
                try:
                    value = json.loads(raw) if raw else None
                    malformed = not raw and status != 204
                except (ValueError, UnicodeError, RecursionError):
                    malformed = True
                message = value.get('message') if isinstance(value, dict) else None
                if status == 401:
                    reason = 'auth'
                elif status == 429 or (status == 403 and (
                        headers.get('x-ratelimit-remaining') == '0' or
                        'retry-after' in headers or message in (
                            'You have exceeded a secondary rate limit.',
                            'API rate limit exceeded'))):
                    reason = 'rate_limit'
                elif status == 403 and message in (
                        'Resource not accessible by personal access token',
                        'Resource not accessible by integration'):
                    reason = 'permission'
                elif status == 403:
                    reason = 'unknown_403'
                elif 500 <= status <= 599:
                    reason = 'transient_http'
                elif malformed:
                    reason = 'malformed_response'
                elif status == 404 and expected_404 and method == 'GET':
                    reason = 'expected_404'
                elif status in (200, 201, 204):
                    reason = 'success'
                else:
                    reason = 'http_error'
        except (OSError, http.client.HTTPException) as exc:
            transport_error = 'timeout' if isinstance(exc, TimeoutError) else 'network'
            reason = 'transient_network'
        if method != 'GET' and reason in (
                'transient_network', 'transient_http', 'malformed_response', 'oversized_response'):
            reason = 'unknown_outcome'
        if clock() >= deadline:
            reason = 'unknown_outcome' if method != 'GET' else 'deadline_exhausted'
        record = dict(method=method, endpoint=endpoint, status=status,
                      transport_error=transport_error, elapsed_seconds=round(max(0, clock()-started), 6),
                      attempt=attempt, headers=headers, classification=reason)
        try:
            emit(record)
        except Exception:
            # Delivery is not the HTTP outcome. Keep a bounded, text-free signal;
            # never prevent the caller's reconciliation or admission cleanup.
            # BaseException (including operator interruption) still propagates.
            if delivery_state is not None:
                delivery_state['delivery_failed'] = True
        if clock() >= deadline:
            raise GithubDiagnosticError('unknown_outcome' if method != 'GET' else 'deadline_exhausted')
        if reason in ('success', 'expected_404'):
            return status, value
        if method != 'GET' or reason not in ('rate_limit', 'transient_http', 'transient_network') or attempt == 3:
            raise GithubDiagnosticError(reason)
        delay = max((10, 60)[attempt-1], github_retry_after(headers, wall))
        if delay >= deadline - clock():
            raise GithubDiagnosticError('deadline_exhausted')
        sleep(delay)
