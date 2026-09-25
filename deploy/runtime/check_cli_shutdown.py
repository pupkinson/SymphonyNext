#!/usr/bin/env python3
"""Owner-only, one-shot CLI regression check; never starts Symphony's scheduler."""
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import urllib.request

BASE = '4551ab01a4e1f1bd91805922cda1d55a6df02a9e'
IMAGE = 'sha256:577cbf4158762f7811ef0a3fde32f3a8ed3951ebf5c8d0de27b857c03ca58a7e'
FILES = {
    'elixir/lib/symphony_elixir/cli.ex': 'cli.ex',
    'elixir/test/symphony_elixir/cli_test.exs': 'test/symphony_elixir/cli_test.exs',
    'elixir/test/symphony_elixir/cli_shutdown_test.exs': 'test/symphony_elixir/cli_shutdown_test.exs',
    'elixir/test/support/cli_shutdown_fixture.exs': 'test/support/cli_shutdown_fixture.exs',
}
SUITE = '''
[stage, expected_ebin] = System.argv()
true = System.version() == "1.19.6" and System.otp_release() == "28"
Code.ensure_loaded!(SymphonyElixir.CLI)
actual = SymphonyElixir.CLI |> :code.which() |> List.to_string() |> Path.dirname()
true = actual == expected_ebin
ExUnit.start(autorun: false, seed: 0, max_cases: 1)
Code.require_file("/probe/test/symphony_elixir/cli_test.exs")
Code.require_file("/probe/test/symphony_elixir/cli_shutdown_test.exs")
r = ExUnit.run()
File.write!("/evidence/#{stage}.json",
  ~s({"total":#{r.total},"failures":#{r.failures},"skipped":#{r.skipped},"excluded":#{r.excluded}}))
System.halt(if r.failures == 0, do: 0, else: 1)
'''
RUN = '''set -eu
ebin=/opt/symphony/elixir/_build/prod/lib/symphony_elixir/ebin
elixir --version > /evidence/version.txt
set +e
elixir -pa "$ebin" /probe/suite.exs baseline "$ebin" > /evidence/baseline.log 2>&1
baseline_status=$?
set -e
[ "$baseline_status" -eq 1 ] || exit 21
mkdir /tmp/candidate
elixirc --ignore-module-conflict -pa "$ebin" -o /tmp/candidate /probe/cli.ex > /evidence/compile.log 2>&1
elixir -pa "$ebin" -pa /tmp/candidate /probe/suite.exs candidate /tmp/candidate > /evidence/candidate.log 2>&1
'''


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def main(source):
    require(os.getuid() == 0 and socket.gethostname() == '1c-db', 'wrong_host_or_identity')
    require(re.fullmatch('[0-9a-f]{40}', source), 'invalid_source_sha')
    root = Path('/var/tmp') / ('symphonynext-cli-shutdown-' + source[:12])
    root.mkdir(mode=0o700, exist_ok=False)
    inputs, evidence = root / 'inputs', root / 'evidence'
    inputs.mkdir(mode=0o755)
    evidence.mkdir(mode=0o700)
    os.chown(evidence, 10001, 10001)
    config = root / 'docker-config'
    config.mkdir(mode=0o700)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(root), 'LANG': 'C.UTF-8'}
    docker = ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock', '--config', str(config)]
    cid, timer = None, None
    stopped, timed_out = threading.Event(), threading.Event()
    lock, stop_errors = threading.Lock(), []
    sequence = itertools.count(1)
    result = {'status': 'STOP', 'source': source, 'baseline': BASE, 'image': IMAGE,
              'model_turn': 'NOT_RUN', 'work_launch': 'NOT_RUN', 'production_deploy': 'NOT_RUN',
              'evidence_dir': str(root)}

    def call(args, timeout=10):
        number = next(sequence)
        p = subprocess.run(docker + args, env=env, capture_output=True, timeout=timeout)
        # Dispatch even a cleanup command before attempting evidence writes.
        prefix = root / ('command-%03d' % number)
        prefix.with_suffix('.stdout').write_bytes(p.stdout)
        prefix.with_suffix('.stderr').write_bytes(p.stderr)
        prefix.with_suffix('.json').write_text(json.dumps({'args': args, 'exit_code': p.returncode}) + '\n')
        require(p.returncode == 0, 'docker_' + args[0] + '_failed')
        return p.stdout

    def stop_once():
        with lock:
            if cid and not stopped.is_set():
                stopped.set()
                try:
                    call(['stop', '--time=10', cid], timeout=15)
                except Exception as exc:
                    stop_errors.append(type(exc).__name__ + ': ' + str(exc))

    def watchdog():
        timed_out.set()
        stop_once()

    try:
        hashes = {}
        for remote, local in FILES.items():
            url = 'https://raw.githubusercontent.com/pupkinson/SymphonyNext/' + source + '/' + remote
            with urllib.request.urlopen(url, timeout=15) as response:
                data = response.read(131073)
            require(0 < len(data) <= 131072, 'source_size_invalid')
            target = inputs / local
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            hashes[remote] = hashlib.sha256(data).hexdigest()
        (root / 'input-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
        (inputs / 'suite.exs').write_text(SUITE)
        (inputs / 'run.sh').write_text(RUN)
        for path in inputs.rglob('*'):
            path.chmod(0o555 if path.is_dir() else 0o444)
        inputs.chmod(0o555)
        data = json.loads(call(['image', 'inspect', IMAGE]))[0]
        require(data['Id'] == IMAGE and data['Config']['Labels']['org.opencontainers.image.revision'] == BASE,
                'image_identity_mismatch')
        (root / 'image.json').write_text(json.dumps(data, indent=2) + '\n')
        args = ['create', '--name', 'snv-cli-' + source[:12], '--pull=never', '--restart=no',
                '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
                '--user=10001:10001', '--cpus=2', '--memory=2g', '--memory-swap=2g', '--pids-limit=256',
                '--log-driver=json-file', '--log-opt=max-size=2m', '--log-opt=max-file=1',
                '--stop-signal=SIGTERM', '--stop-timeout=10',
                '--env', 'ERL_FLAGS=+S 2:2 +SDcpu 1 +SDio 1',
                '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777',
                '--mount', 'type=bind,src=' + str(inputs) + ',dst=/probe,readonly',
                '--mount', 'type=bind,src=' + str(evidence) + ',dst=/evidence',
                '--entrypoint=/bin/sh', IMAGE, '/probe/run.sh']
        cid = call(args, timeout=15).decode().strip()
        require(re.fullmatch('[0-9a-f]{64}', cid), 'invalid_container_id')
        result['container_id'] = cid
        timer = threading.Timer(45, watchdog)
        timer.start()
        call(['start', cid])
        call(['wait', cid], timeout=65)
    except BaseException as exc:
        result['reason'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        stop_once()
        if timer:
            timer.cancel()
            timer.join(timeout=16)
        if cid:
            try:
                after = json.loads(call(['inspect', cid]))[0]
                (root / 'after.json').write_text(json.dumps(after, indent=2) + '\n')
                (root / 'docker.log').write_bytes(call(['logs', cid]))
                state = after['State']
                result['state'] = {k: state.get(k) for k in ('Status', 'Running', 'ExitCode', 'OOMKilled', 'Error')}
                require(not result.get('reason') and not timed_out.is_set() and not stop_errors, 'runner_incomplete')
                require(state['Status'] == 'exited' and not state['Running'] and state['ExitCode'] == 0
                        and not state['OOMKilled'] and not state['Error'], 'container_failed')
                for stage, failures in [('baseline', 2), ('candidate', 0)]:
                    stats = json.loads((evidence / (stage + '.json')).read_text())
                    result[stage + '_tests'] = stats
                    require(stats == {'total': 13, 'failures': failures, 'skipped': 0, 'excluded': 0},
                            stage + '_unexpected_test_results')
                names = set(re.findall(r'^\s+\d+\) test (.+) \(SymphonyElixir.CLIShutdownTest\)',
                                       (evidence / 'baseline.log').read_text(), re.M))
                require(names == {
                    'SIGTERM preserves zero exit and completes the application stop callback',
                    'VM shutdown preserves its nonzero exit code and completes callbacks'}, 'unexpected_red_failures')
                result['status'] = 'CLI_REGRESSION_PASS_NO_MODEL'
            except Exception as exc:
                result.setdefault('reason', type(exc).__name__ + ': ' + str(exc))
        result['watchdog_fired'], result['stop_errors'] = timed_out.is_set(), stop_errors
        (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2), flush=True)
        print('RESULT_PATH=' + str(root / 'result.json'), flush=True)
    return 0 if result['status'] == 'CLI_REGRESSION_PASS_NO_MODEL' else 2


if __name__ == '__main__':
    try:
        require(len(sys.argv) == 2, 'one_source_sha_required')
        raise SystemExit(main(sys.argv[1]))
    except Exception as exc:
        print(json.dumps({'status': 'STOP', 'reason': type(exc).__name__ + ': ' + str(exc),
                          'instruction': 'Preserve all artifacts; do not retry.'}))
        raise SystemExit(2)
