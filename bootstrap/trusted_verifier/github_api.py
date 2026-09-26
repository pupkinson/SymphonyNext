"""GitHub App authentication and bounded curl transport; secrets never in argv."""
import base64
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import tempfile
import time

from contract import decode_json, require

REPO = 'pupkinson/SymphonyNext'
REPO_ID = 1381693716
PERMISSIONS = {'contents': 'read', 'pull_requests': 'read', 'checks': 'write'}
CLEAN_ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/nonexistent',
             'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
             'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0',
             'PYTHONDONTWRITEBYTECODE': '1'}

def make_jwt(app_id, key, now=None):
    now = int(time.time() if now is None else now)
    require(type(app_id) is int and app_id > 0, 'app_id')
    def b64(value):
        return base64.urlsafe_b64encode(value).rstrip(b'=')
    header = b64(json.dumps({'alg': 'RS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
    payload = b64(json.dumps({'iat': now-60, 'exp': now+540, 'iss': str(app_id)},
                             separators=(',', ':')).encode())
    signing = header + b'.' + payload
    signature = subprocess.run(['/usr/bin/openssl', 'dgst', '-sha256', '-sign', str(key)],
        input=signing, capture_output=True, timeout=10, env=CLEAN_ENV)
    require(signature.returncode == 0, 'app_key_signing_failed')
    return (signing + b'.' + b64(signature.stdout)).decode()

def validate_installation(data, installation_id):
    require(data.get('id') == installation_id
            and data.get('account', {}).get('login') == 'pupkinson'
            and data.get('repository_selection') == 'selected', 'installation_identity')
    perms = data.get('permissions', {})
    require(perms == dict(PERMISSIONS, metadata='read'), 'installation_permissions')

class CurlTransport:
    def __init__(self, private_dir):
        self.private_dir = Path(private_dir)

    def request(self, method, path, token, body=None):
        require(method in ('GET', 'POST'), 'http_method')
        require(re.fullmatch(r'/[A-Za-z0-9_/?=&.%-]+', path) is not None
                and not path.startswith('//') and '..' not in path, 'github_path')
        require(re.fullmatch(r'[A-Za-z0-9_.-]+', token or '') is not None, 'invalid_token')
        # A random private directory holds temporary wire material, never durable receipts.
        with tempfile.TemporaryDirectory(prefix='wire-', dir=self.private_dir) as temp:
            out = Path(temp) / 'response'
            request = Path(temp) / 'request'
            request.write_bytes(json.dumps(body or {}, separators=(',', ':')).encode())
            request.chmod(0o600)
            config = ('header = "Authorization: Bearer ' + token + '"\n'
                      'header = "Accept: application/vnd.github+json"\n'
                      'header = "X-GitHub-Api-Version: 2022-11-28"\n'
                      'header = "Content-Type: application/json"\n')
            cmd = ['/usr/bin/curl', '--disable', '--config', '-', '--silent', '--show-error',
                   '--proto', '=https', '--connect-timeout', '10', '--max-time', '30',
                   '--max-filesize', '1048576', '--request', method,
                   '--output', str(out), '--write-out', '%{http_code}',
                   'https://api.github.com' + path]
            if body is not None:
                cmd.extend(['--data-binary', '@' + str(request)])
            def limit():
                resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
            response = subprocess.run(cmd, input=config.encode(), capture_output=True,
                                      timeout=35, env=CLEAN_ENV, preexec_fn=limit)
            require(response.returncode == 0, 'github_transport_failed')
            try: status = int(response.stdout)
            except ValueError: raise ValueError('github_status_invalid') from None
            require(200 <= status < 300, 'github_http_' + str(status))
            return decode_json(out.read_bytes())

class GitHub:
    def __init__(self, config, key, private_dir):
        self.app_id = config['app_id']
        self.transport = CurlTransport(private_dir)
        jwt = make_jwt(self.app_id, key)
        installation_id = config['installation_id']
        app = self.transport.request('GET', '/app', jwt)
        require(app.get('id') == self.app_id, 'app_identity')
        installation = self.transport.request('GET', '/app/installations/' + str(installation_id), jwt)
        validate_installation(installation, installation_id)
        token = self.transport.request('POST',
            '/app/installations/' + str(installation_id) + '/access_tokens', jwt,
            {'repository_ids': [REPO_ID], 'permissions': PERMISSIONS})
        require(token.get('permissions') == dict(PERMISSIONS, metadata='read'),
                'token_permissions')
        self.token = token['token']
        repositories = self.request('GET', '/installation/repositories?per_page=100')
        require(repositories.get('total_count') == 1
                and [x.get('id') for x in repositories.get('repositories', [])] == [REPO_ID],
                'token_repository_scope')

    def request(self, method, path, body=None):
        return self.transport.request(method, path, self.token, body)

