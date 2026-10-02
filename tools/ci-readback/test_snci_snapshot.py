"""Offline tests: no installed CI files, credentials or subprocesses are touched."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('snci_snapshot', Path(__file__).with_name('snci_snapshot.py'))
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class SnapshotTests(unittest.TestCase):
    def test_fixed_read_scope_excludes_secrets_and_mutating_helpers(self):
        paths = list(m.FILES.values())
        self.assertEqual(len(paths), 6)
        self.assertTrue(all(p.startswith(('/opt/symphony-next-ci/', '/etc/symphony-next-ci/', '/var/lib/symphony-next-ci/')) for p in paths))
        self.assertFalse(any(x in p for p in paths for x in ('auth.json', 'app.pem', 'runtime.env', 'journal.sqlite3', 'owner.py')))

    def test_policy_summary_drops_credentials_and_unknown_fields(self):
        value = {'enabled': False, 'review_model': 'SECRET', 'github_key': '/SECRET.pem',
                 'profiles': [{'name': 'sn004', 'head': m.HEAD, 'tree': m.TREE,
                               'minimum_tests': 331, 'maximum_skips': 6,
                               'locked': {m.LOCK: m.BLOB}, 'token': 'SECRET'}]}
        summary = m.summarize('policy', json.dumps(value).encode())
        text = json.dumps(summary)
        self.assertNotIn('SECRET', text)
        self.assertEqual(summary['profiles'][0]['reviewed_target_matches'], True)
        self.assertEqual(summary['enabled'], False)

    def test_target_mismatch_is_not_readiness(self):
        value = {'sn004': {'head': 'a'*40, 'tree': 'b'*40, 'minimum_tests':328, 'maximum_skips':6, 'locked':{m.LOCK:'c'*40}}}
        row = m.summarize('definitions', json.dumps(value).encode())['profiles'][0]
        self.assertFalse(row['reviewed_target_matches'])
        self.assertEqual(row['minimum_tests'], 328)

    def test_readback_is_not_an_acceptance_check(self):
        raw = json.dumps({'profile':'sn004', 'head':m.HEAD, 'tree':m.TREE, 'time':1,
                          'quality': {'tests':331, 'failures':0, 'skipped':6, 'coverage':100,
                                      'stages':{k:0 for k in m.STAGES}, 'secret':'SECRET'}}).encode()
        out = m.summarize('prepare_sn004', raw)
        self.assertEqual(out['quality']['tests'], 331)
        self.assertNotIn('SECRET', json.dumps(out))
        self.assertNotIn('accepted', out)
        self.assertNotIn('ready', out)

    def test_json_duplicate_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            m.summarize('policy', b'{"enabled":true,"enabled":false}')

    def test_nonfinite_numbers_and_bad_shapes_are_rejected(self):
        for data in (b'{"coverage":NaN}', b'[]', b'{"profiles":"SECRET"}'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                m.summarize('policy', data)

    def test_untrusted_strings_and_boolean_numbers_not_printed(self):
        row = m.profile({'head':'SECRET','tree':'SECRET','minimum_tests':True,'maximum_skips':'SECRET',
                         'image':'SECRET','locked':{m.LOCK:'SECRET'}}, 'sn004')
        self.assertIsNone(row['head'])
        self.assertIsNone(row['minimum_tests'])
        self.assertNotIn('SECRET', json.dumps(row))

    def test_revision_requires_exact_digest(self):
        self.assertEqual(m.summarize('revision', (m.HEAD+'\n').encode())['revision'], m.HEAD)
        with self.assertRaises(ValueError):
            m.summarize('revision', b'SECRET')

    def test_read_error_does_not_leak_exception_text(self):
        def reader(path):
            raise PermissionError('SECRET access token')
        out = m.snapshot(reader=reader, get_units=lambda:{})
        self.assertNotIn('SECRET', json.dumps(out))
        self.assertEqual(out['status'], 'SNCI_SNAPSHOT_PARTIAL')
        self.assertEqual(out['files']['policy']['state'], 'unreadable')

    def test_missing_receipt_stays_missing(self):
        def reader(path):
            raise FileNotFoundError(path)
        out = m.snapshot(reader=reader, get_units=lambda:{})
        self.assertTrue(all(x['state']=='missing' for x in out['files'].values()))
        self.assertEqual(out['tests_executed'], False)
        self.assertEqual(out['service_changed'], False)
        self.assertEqual(out['readiness'], 'NOT_ATTESTED')

    def test_complete_snapshot_never_promotes_readiness(self):
        def reader(path):
            return m.HEAD.encode() if path.endswith('/revision') else b'{}'
        out = m.snapshot(reader=reader, get_units=lambda:{'probe':'ok'})
        self.assertEqual(out['status'], 'SNCI_SNAPSHOT_COLLECTED')
        self.assertEqual(out['readiness'], 'NOT_ATTESTED')

    def test_guard_precedes_reads(self):
        with patch.object(m.os, 'geteuid', return_value=997), patch.object(m, 'snapshot') as run:
            self.assertEqual(m.main(['--read']), 2)
            run.assert_not_called()

    def test_wrong_host_precedes_reads(self):
        with patch.object(m.os, 'geteuid', return_value=0), patch.object(m.socket, 'gethostname', return_value='other'), patch.object(m, 'snapshot') as run:
            self.assertEqual(m.main(['--read']), 2)
            run.assert_not_called()

    def test_safe_reader_regular_file_no_content_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'state.json'; p.write_bytes(b'{}'); p.chmod(0o600)
            before = p.stat()
            self.assertEqual(m.read_fixed(str(p), owner=os.getuid()), b'{}')
            after = p.stat()
            self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)
            self.assertEqual(before.st_atime_ns, after.st_atime_ns)

    def test_safe_reader_rejects_symlinks_in_file_and_parents(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'real').mkdir(); (root/'real/f').write_bytes(b'{}')
            (root/'filelink').symlink_to(root/'real/f'); (root/'dirlink').symlink_to(root/'real',target_is_directory=True)
            for p in (root/'filelink',root/'dirlink/f'):
                with self.subTest(p=p), self.assertRaises((OSError,ValueError)):
                    m.read_fixed(str(p), owner=os.getuid())

    def test_safe_reader_rejects_large_file_fifo_and_writable_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=root/'large'; p.write_bytes(b'x'*32); p.chmod(0o600)
            with self.assertRaises(ValueError):m.read_fixed(str(p), limit=8, owner=os.getuid())
            fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaises(ValueError):m.read_fixed(str(fifo), owner=os.getuid())
            p.chmod(0o666)
            with self.assertRaises(ValueError):m.read_fixed(str(p), owner=os.getuid())

    def test_systemctl_contract_is_fixed_and_read_only(self):
        calls=[]
        def fake(args, **kw):
            calls.append((args,kw))
            return type('Result', (), {'returncode':0, 'stdout':'MainPID=0\nActiveState=inactive\nUser=root\nSecret=SECRET\n'})()
        with patch.object(m.subprocess, 'run', side_effect=fake):out=m.unit_metadata()
        self.assertEqual(len(calls), 2)
        for args,kw in calls:
            self.assertEqual(args[0:2], ['/usr/bin/systemctl','show'])
            self.assertFalse(kw.get('shell',False)); self.assertLessEqual(kw['timeout'],10)
            self.assertNotIn('TOKEN',json.dumps(kw['env']))
        self.assertNotIn('SECRET',json.dumps(out))


if __name__ == '__main__':unittest.main()
