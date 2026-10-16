"""Actual GH104/105 Git objects, plus bounded raw-transport negatives.

No model, production service, native sandbox or remote write is involved.
The pinned predecessor is deliberately independent of the mutable worktree.
"""
import base64
import copy
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_queue_context import q
from test_queue_executor_lifecycle import DeveloperGit
from test_queue_executor import developer_row

REPO = Path(__file__).resolve().parents[3]
HEAD = 'e6fa3d22396fb078895ca76ff32c6614aa38c3f0'
TREE = '0a3a664ce14246ba6373fb6af172c8da186e99eb'
VIDEO = '.github/media/symphony-demo.mp4'
VIDEO_OID = '32b1f857f45eb901905ea24355b599fb417f53c5'
VIDEO_SIZE = 30446771


def git(*args, data=None, env=None):
    return subprocess.check_output(['git', '-C', str(REPO), *args], input=data, env=env)


def actual_entries():
    entries = []
    for line in git('ls-tree', '-r', '-t', '-l', '-z', HEAD).split(b'\0'):
        if not line:
            continue
        meta, name = line.decode().split('\t', 1)
        mode, kind, oid, size = meta.split()
        entry = dict(path=name, mode=mode, type=kind, sha=oid)
        if size != '-':
            entry['size'] = int(size)
        entries.append(entry)
    return entries


class ActualGitObjects:
    def __init__(self):
        self.entries = actual_entries()
        self.reads = []

    def get(self, path):
        if path == '/git/commits/' + HEAD:
            return {'sha': HEAD, 'tree': {'sha': TREE}}
        if path == '/git/trees/' + TREE + '?recursive=1':
            return dict(sha=TREE, truncated=False, tree=copy.deepcopy(self.entries))
        if path.startswith('/git/blobs/'):
            oid = path.rsplit('/', 1)[1]
            raw = git('cat-file', 'blob', oid)
            return dict(sha=oid, encoding='base64', content=base64.b64encode(raw).decode())
        raise AssertionError(path)

    def blob_bytes(self, oid, size):
        self.reads.append((oid, size))
        return git('cat-file', 'blob', oid)


class ActualRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.a = q.execution_adapter()
        self.api = ActualGitObjects()

    def test_materializes_actual_pilot_base(self):
        self.assertEqual(git('rev-parse', HEAD + '^{tree}').decode().strip(), TREE)
        files = {e['path']: e for e in self.api.entries if e['type'] == 'blob'}
        self.assertEqual(len(files), 199)
        self.assertEqual(sum(e['size'] for e in files.values()), 33232573)
        try:
            baseline = self.a.materialize(self.api, HEAD, TREE, self.repo)
        except q.Hold as exc:
            self.fail('Actual repository cannot be prepared: ' + str(exc))
        self.assertEqual(set(baseline), set(files))
        for name, entry in files.items():
            self.assertEqual(baseline[name]['blob'], entry['sha'], name)
            self.assertEqual(baseline[name]['mode'], entry['mode'], name)
        self.assertEqual((self.repo / VIDEO).stat().st_size, VIDEO_SIZE)
        self.assertIn((VIDEO_OID, VIDEO_SIZE), self.api.reads)
        self.assertEqual(self.a.changes(self.repo, baseline, ['tools/executor-pilot/state_summary.py'])[1], [])
        with self.assertRaises(q.Hold):
            self.a.read_file(self.repo, VIDEO)
        with self.assertRaises(q.Hold):
            self.a.write_file(self.repo, [VIDEO], VIDEO, 'replacement', baseline[VIDEO]['sha256'])

    def test_published_delta_preserves_every_untouched_real_git_object(self):
        baseline = self.a.materialize(self.api, HEAD, TREE, self.repo)
        changed = 'tools/executor-pilot/state_summary.py'
        self.a.write_file(self.repo, [changed], changed, 'value = 2\n', None)
        current = self.a.snapshot(self.repo)
        directory = self.root / 'job'
        (directory / 'outbox').mkdir(parents=True)
        command = ['/usr/bin/python3', '-B', '-c', 'assert True']
        q.save(directory / 'tests.json', {'unit': dict(exit_code=0, argv=command,
               input_sha256=q.sha(q.wire_json(current)))})
        grant = dict(writable_paths=[changed], tests={'unit': command}, tree_sha=TREE,
                     base_sha=HEAD, generation=1, base_ref='pilot-base', requirements=['fixture'])
        task = dict(workspace=str(self.repo), grant=grant, baseline=baseline, issue=123,
                    branch='snq/gh-123/g1', started_at=q.utc(), sandbox_receipt={'fixture': True})
        api = DeveloperGit(developer_row())
        api.refs[task['branch']] = HEAD
        posted = {}

        def objects(_api, _outbox, key, path, payload, known_sha=None):
            posted[key] = copy.deepcopy(payload)
            return known_sha or ('e' * 40 if key == 'tree' else 'a' * 40)

        def once(_directory, key, payload, send, lookup):
            if key == 'pr':
                api.prs.append(dict(draft=True, state='open', head={'sha': 'a' * 40}, base={'sha': HEAD}))
                return {'number': 555}
            return {'sha': 'a' * 40}

        with patch.object(self.a, 'guard'), patch.object(self.a, 'object_write', side_effect=objects), \
             patch.object(self.a, 'publish_once', side_effect=once), patch.object(self.a, 'create_review'):
            self.a.publish_candidate(task, directory, api, {'thread_id': 'fixture-author'})
        delta = posted['tree']
        self.assertEqual(delta['base_tree'], TREE)
        self.assertEqual([x['path'] for x in delta['tree']], [changed])
        # Apply the emitted payload through Git's own index/tree machinery in a
        # separate object directory. Never write objects/refs in the real repo.
        odb = self.root / 'objects'
        odb.mkdir()
        env = dict(os.environ, GIT_OBJECT_DIRECTORY=str(odb),
                   GIT_ALTERNATE_OBJECT_DIRECTORIES=git('rev-parse', '--path-format=absolute', '--git-common-dir').decode().strip() + '/objects',
                   GIT_INDEX_FILE=str(self.root / 'index'))
        raw = base64.b64decode(posted['blob-0']['content'])
        oid = git('hash-object', '-w', '--stdin', data=raw, env=env).decode().strip()
        self.assertEqual(oid, delta['tree'][0]['sha'])
        git('read-tree', delta['base_tree'], env=env)
        git('update-index', '--add', '--cacheinfo', '100644', oid, changed, env=env)
        result = git('write-tree', env=env).decode().strip()
        before = {e['path']: (e['mode'], e['sha']) for e in self.api.entries if e['type'] == 'blob'}
        after = {}
        for line in git('ls-tree', '-r', '-z', result, env=env).split(b'\0'):
            if line:
                meta, name = line.decode().split('\t', 1)
                mode, kind, sha = meta.split()
                after[name] = (mode, sha)
        self.assertEqual({p: after[p] for p in before}, before)
        self.assertEqual(set(after) - set(before), {changed})
        self.assertEqual(after[VIDEO], ('100644', VIDEO_OID))

    def test_large_asset_binding_cannot_be_changed_by_tree_metadata(self):
        for field, value in [('path', 'src/big.py'), ('sha', 'a' * 40),
                             ('mode', '100755'), ('size', VIDEO_SIZE + 1), ('type', 'commit')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                api = ActualGitObjects()
                api.entries = [copy.deepcopy(next(e for e in api.entries if e['path'] == VIDEO))]
                api.entries[0][field] = value
                with self.assertRaises(q.Hold):
                    self.a.materialize(api, HEAD, TREE, Path(root) / 'repo')
                self.assertEqual(api.reads, [])

    def test_wrong_raw_blob_hash_or_size_cannot_be_materialized(self):
        for raw in (b'', b'wrong'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as root:
                api = ActualGitObjects()
                api.entries = [next(e for e in api.entries if e['path'] == VIDEO)]
                with patch.object(api, 'blob_bytes', return_value=raw), self.assertRaises(q.Hold):
                    self.a.materialize(api, HEAD, TREE, Path(root) / 'repo')
                self.assertFalse((Path(root) / 'repo' / VIDEO).exists())

    def test_materialized_large_asset_tampering_is_detected_by_snapshot(self):
        self.a.materialize(self.api, HEAD, TREE, self.repo)
        with (self.repo / VIDEO).open('r+b') as f:
            f.write(b'corrupted')
        with self.assertRaisesRegex(q.Hold, 'READ_ONLY_ASSET_CHANGED'):
            self.a.snapshot(self.repo)

    def test_aggregate_workspace_limit_still_precedes_blob_download(self):
        self.api.entries = [next(e for e in self.api.entries if e['path'] == VIDEO)]
        with patch.dict(self.a.materialize.__globals__, MAX_TOTAL=VIDEO_SIZE - 1):
            with self.assertRaisesRegex(q.Hold, 'WORKSPACE_LIMIT'):
                self.a.materialize(self.api, HEAD, TREE, self.repo)
        self.assertEqual(self.api.reads, [])


class RawBlobTransportTests(unittest.TestCase):
    def api(self):
        api = q.Api('offline-fixture-not-a-credential')
        api.execution_scope = lambda *args: False
        return api

    def test_raw_blob_avoids_json_response_cap_and_binds_hash(self):
        raw = b'x' * 3800000  # base64 JSON would exceed the unchanged 5MB cap.
        response = io.BytesIO(raw)
        response.status = 200
        response.getheader = lambda key: None
        with patch.object(q.http.client, 'HTTPSConnection') as connection:
            connection.return_value.getresponse.return_value = response
            api = self.api()
            self.assertTrue(hasattr(api, 'blob_bytes'), 'bounded developer raw transport missing')
            result = api.blob_bytes(q.git_blob_sha(raw), len(raw))
            self.assertEqual(result, raw)
            args, kwargs = connection.return_value.request.call_args
            self.assertEqual(args[:2], ('GET', '/repos/' + q.REPO + '/git/blobs/' + q.git_blob_sha(raw)))
            self.assertEqual(kwargs['headers']['Accept'], 'application/vnd.github.raw+json')
            self.assertEqual(q.API_RESPONSE_LIMIT, 5000000)

    def test_reviewer_cannot_use_raw_transport(self):
        api = q.Api('offline-fixture-not-a-credential')
        self.assertTrue(hasattr(api, 'blob_bytes'), 'raw transport missing')
        with patch.object(q.http.client, 'HTTPSConnection') as connection, self.assertRaises(q.Hold):
            api.blob_bytes(q.git_blob_sha(b'x'), 1)
        connection.assert_not_called()

    def test_raw_transport_refuses_unbounded_or_non_blob_requests(self):
        api = self.api()
        self.assertTrue(hasattr(api, 'blob_bytes'), 'raw transport missing')
        for oid, size in [('a/../b', 1), ('a' * 40, -1), ('a' * 40, True), ('a' * 40, 33554433)]:
            with self.subTest(oid=oid, size=size), patch.object(q.http.client, 'HTTPSConnection') as connection:
                with self.assertRaises(q.Hold):
                    api.blob_bytes(oid, size)
                connection.assert_not_called()

    def test_raw_transport_rejects_truncation_overflow_hash_error_redirect_and_http_error(self):
        api = self.api()
        self.assertTrue(hasattr(api, 'blob_bytes'), 'raw transport missing')
        for status, raw in [(200, b''), (200, b'xx'), (200, b'y'), (302, b'x'), (403, b'x')]:
            with self.subTest(status=status, raw=raw):
                response = io.BytesIO(raw)
                response.status = status
                response.getheader = lambda key: None
                with patch.object(q.http.client, 'HTTPSConnection') as connection:
                    connection.return_value.getresponse.return_value = response
                    with self.assertRaises(q.Hold):
                        api.blob_bytes(q.git_blob_sha(b'x'), 1)
                    connection.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
