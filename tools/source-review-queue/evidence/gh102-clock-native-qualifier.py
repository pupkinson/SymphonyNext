import ast, datetime, hashlib, io, json, os, re, socket, stat, sys, tarfile, tempfile, time
from pathlib import Path
assert socket.gethostname() == '1c-db' and os.getuid() == 997
handoff = Path(sys.argv[2])
assert str(handoff).startswith('/srv/rdc-workspace/handoffs/')
assert handoff.is_dir() and not handoff.is_symlink()
source = Path('/opt/symphony-next-queue-v1/queue.py').read_bytes()
source_hash = hashlib.sha256(source).hexdigest()
assert source_hash == '7fa0ee5624132253e487cf8093af5b1bd90fe5680c682d9672114cdbeccd33d1'
tree = ast.parse(source)
selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in
            {'Hold', 'utc', 'require', 'once', 'save', 'read', 'decode', 'redact', 'job_dir', 'finish_task', 'remove_admission', 'deliver'}]
assert len(selected) == 12
legacy = dict(os=os, json=json, datetime=datetime, re=re, stat=stat, Path=Path, LABEL='symphony-next-queue-ready')
exec(compile(ast.Module(body=selected, type_ignores=[]), '<pinned-predecessor-functions>', 'exec'), legacy)
updater = Path(sys.argv[1]).read_bytes()
updater_hash = hashlib.sha256(updater).hexdigest()
assert updater_hash == sys.argv[3]
ns = dict(__name__='sn102_diagnostic_only', __file__='<frozen-reviewed-updater>')
exec(compile(updater, '<frozen-reviewed-updater>', 'exec'), ns)
base = Path(tempfile.mkdtemp(prefix='sn102-fs-chronology-', dir=str(handoff)))
print('PROBE_DIR '+str(base), flush=True)
u = ns['Updater'](base, base, base, object())
class FakeApi:
    def __init__(self, mode):
        self.mode=mode
        self.admitted=mode in ('delete','lost-delete')
        self.posts=self.deletes=0
        self.comments=[]
        self.lost=False
    def request(self,method,path,payload=None):
        if method=='POST':
            assert path=='/issues/25/comments'
            self.posts+=1
            self.comments.append(dict(body=payload['body'],id=1))
            if self.mode=='lost-post' and not self.lost:
                self.lost=True
                raise legacy['Hold']('FIXTURE_POST_ACK_LOST')
            return self.comments[-1]
        assert method=='DELETE' and path.endswith('/labels/symphony-next-queue-ready')
        self.deletes+=1
        self.admitted=False
        if self.mode=='lost-delete' and not self.lost:
            self.lost=True
            raise legacy['Hold']('FIXTURE_DELETE_ACK_LOST')
    def get(self,path):
        if '/comments?' in path:
            return self.comments
        assert path=='/issues/25'
        return dict(labels=[dict(name='symphony-next-queue-ready')] if self.admitted else [])
def exact_at_ns(text):
    delta = datetime.datetime.fromisoformat(text) - datetime.datetime(1970,1,1,tzinfo=datetime.timezone.utc)
    return (delta.days*86400 + delta.seconds)*10**9 + delta.microseconds*1000
samples = []
for i in range(32):
    mode=('direct','delete','lost-post','lost-delete')[i//8]
    case=base/str(i)
    directory=case/'jobs/GH-25'
    directory.mkdir(mode=0o700,parents=True)
    legacy['QROOT']=case
    legacy['save'](directory/'final.json',dict(issue=25,head='a'*40,
        status='SOURCE_REVIEW_INCOMPLETE',at=legacy['utc'](),protocol={},
        tests_by_reviewer='NOT_RUN',release_approval=False))
    api=FakeApi(mode)
    initial_hold=False
    if mode.startswith('lost-'):
        try:
            legacy['finish_task'](25,api)
        except legacy['Hold']:
            initial_hold=True
        assert initial_hold
        try:
            u.delivery(directory,legacy=True)
        except ns['Hold']:
            pass
        else:
            raise AssertionError('Unknown/stale proof accepted before recovery')
        # Make the subsequent real file replacement unambiguously later.
        # The gate's strict post-hold ordering/equality refusal is unchanged.
        time.sleep(0.02)
    legacy['finish_task'](25,api)
    assert api.posts==1 and api.deletes==int(mode in ('delete','lost-delete'))
    files = {n: (directory/n).stat() for n in ('comment-intent.json','comment-readback.json','label-removed.json')}
    label = json.loads((directory/'label-removed.json').read_bytes())
    at = exact_at_ns(label['at'])
    a,b,c = [files[n] for n in ('comment-intent.json','comment-readback.json','label-removed.json')]
    now = time.time_ns()
    result = 'PASS'
    try:
        u.delivery(directory, legacy=True)
    except ns['Hold'] as exc:
        result = 'HOLD:'+str(exc)
    samples.append(dict(sample=i, mode=mode, initial_unknown_hold=initial_hold, posts=api.posts, deletes=api.deletes, result=result, label_at=label['at'],
        label_minus_mtime_ns=str(at-c.st_mtime_ns), ctime_minus_label_ns=str(c.st_ctime_ns-at),
        label_at_le_mtime=at <= c.st_mtime_ns,
        ordered_mtimes=a.st_mtime_ns <= b.st_mtime_ns <= c.st_mtime_ns,
        ordered_ctimes=a.st_ctime_ns <= b.st_ctime_ns <= c.st_ctime_ns,
        coherent=all(s.st_dev == a.st_dev and s.st_nlink == 1 and 0 < s.st_mtime_ns <= s.st_ctime_ns <= now for s in files.values()),
        metadata={n:dict(device=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,
            mtime_ns=str(s.st_mtime_ns),ctime_ns=str(s.st_ctime_ns)) for n,s in files.items()}))
report = dict(schema='sn102-filesystem-chronology-diagnostic/v1', host=socket.gethostname(),
    uid=os.getuid(), at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    fixture_root=str(base), predecessor_sha256=source_hash, updater_sha256=updater_hash,
    samples=len(samples), completed_delivery_api_doubles=True, real_external_writes=0,
    service_or_runtime_journal_changes=False, source_or_archive_changes=False,
    cases_by_mode={mode:sum(x['mode']==mode for x in samples) for mode in ('direct','delete','lost-post','lost-delete')},
    unknown_outcomes_blocked_before_recovery=sum(x['initial_unknown_hold'] for x in samples),
    post_hold_separation_seconds=0.02,
    chronology_holds=sum(x['result']=='HOLD:NOTIFICATION_FILE_CHRONOLOGY' for x in samples),
    label_at_after_mtime=sum(not x['label_at_le_mtime'] for x in samples),
    all_file_metadata_coherent=all(x['coherent'] for x in samples),
    all_intent_receipt_label_ordered=all(x['ordered_mtimes'] and x['ordered_ctimes'] for x in samples),
    details=samples)
raw=(json.dumps(report,sort_keys=True,indent=2)+'\n').encode()
with (base/'report.json').open('xb') as f:
    f.write(raw);f.flush();os.fsync(f.fileno())
print(json.dumps({k:v for k,v in report.items() if k!='details'},sort_keys=True))
print('REPORT_SHA256 '+hashlib.sha256(raw).hexdigest())


assert report['chronology_holds'] == 0 and all(x['result'] == 'PASS' for x in samples)
assert report['all_file_metadata_coherent'] and report['all_intent_receipt_label_ordered']
