"""Inlined fixed-driver helpers for start reconciliation, not a new launcher.

ExecStartPre records this operation's systemd INVOCATION_ID before ExecStart.
Only UID995 writes the witness; root-owned nonce/driver and no prior UID995
processes are preconditions. This is operational correlation, not an assertion
that a malicious process sharing the service UID cannot forge a receipt.
"""

def start_guard_state():
    names = ('Id,Type,Restart,RuntimeMaxUSec,TimeoutStartUSec,TimeoutStopUSec,'
             'KillMode,SendSIGKILL,InvocationID,MainPID,ActiveState,Job,DropInPaths')
    raw = run(['/usr/bin/systemctl', 'show', UNIT, '--no-pager', '--property='+names], seconds=3)
    return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)


def _duration_seconds(value):
    # systemctl show renders microsecond properties as time spans, not always integers.
    if not isinstance(value, str): raise Stop('manager_duration_unknown')
    if value.isdigit(): return int(value) / 1_000_000
    units = {'us': 0.000001, 'ms': 0.001, 's': 1, 'min': 60, 'h': 3600}
    parts = re.findall(r'(\d+(?:\.\d+)?)(us|ms|min|s|h)', value)
    if not parts or ''.join(a+b for a,b in parts) != value.replace(' ', ''):
        raise Stop('manager_duration_unknown')
    return sum(float(n)*units[u] for n,u in parts)


def verify_manager_deadline(state):
    # The lifetime bound lives in PID1, not in an observer that can itself die.
    if (state.get('Id') != UNIT or state.get('Type') not in ('simple', 'exec')
            or state.get('Restart') != 'no' or state.get('KillMode') != 'control-group'
            or state.get('SendSIGKILL') != 'yes' or state.get('DropInPaths') != str(DROP)):
        raise Stop('manager_safety_profile_mismatch')
    for key, maximum in [('RuntimeMaxUSec', 1800), ('TimeoutStartUSec', 45), ('TimeoutStopUSec', 45)]:
        if not 0 < _duration_seconds(state.get(key)) <= maximum:
            raise Stop('manager_deadline_not_bounded')


def make_start_ticket(window):
    data = json.loads(window)
    if (data.get('unit') != UNIT or data.get('operation') != RECORD.name
            or not re.fullmatch(r'[0-9a-f]{32}', data.get('nonce', ''))):
        raise Stop('invalid_start_window')
    return dict(operation=RECORD.name, unit=UNIT, nonce=data['nonce'],
                window_sha256=hashlib.sha256(window).hexdigest(),
                driver_sha256=hashlib.sha256(read_file(DRIVER)).hexdigest(),
                dropin_sha256=hashlib.sha256(read_file(DROP)).hexdigest(),
                boot_id=read_file(Path('/proc/sys/kernel/random/boot_id'), limit=100).decode().strip(),
                requested_monotonic=time.monotonic())


def record_start_witness():
    # Runs as ExecStartPre, before the model, without root/extra capabilities.
    if (os.getuid(), os.getgid(), socket.gethostname()) != (995, 995, '1c-db'):
        raise Stop('start_witness_identity_mismatch')
    invocation = os.environ.get('INVOCATION_ID', '')  # not a credential
    if not re.fullmatch(r'[0-9a-f]{32}', invocation): raise Stop('missing_systemd_invocation')
    window = read_file(CONF/'BOOT_P01_WINDOW', limit=1024, owner=(0,995), mode=0o640)
    data = json.loads(window)
    if data.get('unit') != UNIT or data.get('operation') != RECORD.name:
        raise Stop('start_witness_wrong_operation')
    witness = dict(operation=RECORD.name, unit=UNIT, nonce=data['nonce'],
        invocation_id=invocation, window_sha256=hashlib.sha256(window).hexdigest(),
        driver_sha256=hashlib.sha256(read_file(DRIVER)).hexdigest(),
        boot_id=read_file(Path('/proc/sys/kernel/random/boot_id'), limit=100).decode().strip(),
        witnessed_monotonic=time.monotonic())
    create_file(RUN/'service-invocation.json', (json.dumps(witness)+'\n').encode())
    # Existing witness means the launch is consumed. Never overwrite/reuse it.
    fd = os.open(RUN, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def reconcile_start_ownership(ticket, monitor):
    """Verify ownership without writing diagnostics; at most three reads/15s.

    Returning a verified state must not depend on checkpoint storage. The caller
    records the observation separately and still rechecks identity before stop.
    """
    deadline = time.monotonic()+15
    for delay in (0, 2, 3):
        if delay: time.sleep(min(delay, max(0, deadline-time.monotonic())))
        if time.monotonic() >= deadline: break
        try:
            state = start_guard_state()
            if state.get('ActiveState') in ('inactive','failed') and state.get('MainPID') == '0' and state.get('Job') == '0':
                monitor.state['start_reconciliation'] = 'not_running_no_job'
                return state
            verify_manager_deadline(state)
            if hashlib.sha256(read_file(DROP)).hexdigest() != ticket['dropin_sha256']:
                raise Stop('start_dropin_changed')
            witness = json.loads(read_file(RUN/'service-invocation.json', limit=2048, owner=(995,995), mode=0o600))
        except (FileNotFoundError, OSError):
            continue
        except Stop as exc:
            if str(exc) in ('local_command_timeout_systemctl', 'local_command_failed_systemctl_1'):
                continue
            raise
        except (ValueError, KeyError, TypeError):
            raise Stop('start_witness_invalid') from None
        keys = ('operation','unit','nonce','window_sha256','driver_sha256','boot_id')
        if any(witness.get(k) != ticket.get(k) for k in keys): raise Stop('start_witness_not_owned')
        timestamp = witness.get('witnessed_monotonic')
        if (type(timestamp) not in (int,float) or not ticket['requested_monotonic'] <= timestamp <= ticket['requested_monotonic']+45):
            raise Stop('start_witness_wrong_window')
        invocation = witness.get('invocation_id')
        if (not isinstance(invocation,str) or not re.fullmatch(r'[0-9a-f]{32}',invocation)
                or invocation != state.get('InvocationID')
                or monitor.state.get('invocation_id') not in (None,invocation)):
            raise Stop('service_owner_changed_no_stop')
        monitor.state['start_reconciliation'] = 'owned_invocation_witness'
        return state
    monitor.state['start_reconciliation'] = 'unconfirmed_manager_deadline_retained'
    raise Stop('start_ownership_unconfirmed_no_stop')


def record_reconciled_start(state, monitor):
    """Diagnostics only; never used as the authority to stop an invocation.

    Call only with the state returned by reconcile_start_ownership. A write
    failure must reach normal error finalization, but must not veto safe stop
    from inside that finalization. No I/O failure is reclassified as success.
    """
    if (state.get('ActiveState') not in ('inactive', 'failed')
            and not monitor.state.get('service_start_confirmed')):
        monitor.service_started(state.get('InvocationID'))
    if monitor.state.get('termination_reason'):
        monitor.state['phase'] = 'observation_ended'
    monitor._save()
