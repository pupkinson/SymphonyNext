"""Prospective limits; no real GitHub, model, installed service, or native checks."""
import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from test_queue_context import q, FakeGit, manifest
from test_queue_profiles import environment, account_result
from test_queue_schema_downgrade import prepared, worker_boundary

NEW='snq-development-limits/2026-10-08'
OLD='snq-legacy-limits/v1'

class DevelopmentLimitTests(unittest.TestCase):
    def scope(self):
        self.assertTrue(hasattr(q,'limits_scope'),'versioned prospective limits not implemented')
        return q.limits_scope(NEW)

    def old_journal(self,d):
        task=q.decode(q.read(d/'task.json'));meta=q.decode(q.read(d/'packet.json'))
        task.pop('limits_profile',None);meta.pop('limits_profile',None)
        meta['task_sha256']=q.sha(q.wire_json(task))
        q.save(d/'task.json',task);q.save(d/'packet.json',meta)
        return task

    def test_legacy_constants_unchanged(self):
        self.assertEqual((q.MAX_PACKET,q.PROMPT_LIMIT,q.WALL),(650000,670000,1700))
        self.assertEqual((q.SOURCE_TOTAL_LIMIT,q.SOURCE_PAGE_LIMIT,q.SOURCE_CALL_LIMIT),(2097152,8192,400))

    def test_new_v1_packet_exceeds_old_cap_without_truncation(self):
        api=FakeGit(extra={'large.md':b'x'*270000,'other.md':b'y'*270000})
        with self.assertRaisesRegex(q.Hold,'^SOURCE_PACKET_LIMIT$'):
            q.source_packet(api,manifest(False),api.pr)
        with self.scope():
            text=q.source_packet(api,manifest(False),api.pr)
            self.assertGreaterEqual(len(text.encode()),1005922)
            self.assertIn('x'*270000,text);self.assertIn('y'*270000,text)
            self.assertLessEqual(len(text.encode()),2097152)

    def test_new_single_blob_larger_than_legacy(self):
        api=FakeGit(extra={'large.md':b'x'*600000})
        with self.assertRaises(q.Hold):q.build_review_sources(api,manifest(),api.pr)
        with self.scope():
            store=q.build_review_sources(api,manifest(),api.pr)
            self.assertTrue(any(len(d['text'])==600000 for d in store['documents']))

    def test_source_reader_retains_new_paging_outside_scope(self):
        raw=('Денис🙂'*35000+'\0'*10000).encode()
        api=FakeGit(extra={'unicode.md':raw})
        with self.scope():reader=q.SourceReader(q.build_review_sources(api,manifest(),api.pr))
        self.assertEqual(reader.catalog()['limits']['page_response_bytes'],32768)
        doc=next(d for d in reader.catalog()['documents'] if any(a['path']=='unicode.md' for a in d['aliases']))
        chunks=[reader.read_page({'source_id':doc['id'],'page':i}) for i in range(doc['pages'])]
        self.assertEqual(''.join(c['text'] for c in chunks).encode(),raw)
        self.assertLess(doc['pages'],len(raw)//4096)
        for page in chunks:self.assertLessEqual(len(q.wire_json(q.source_tool_result(page))),32768)

    def test_legacy_reader_layout_does_not_change_in_new_scope(self):
        api=FakeGit(extra={'text.md':b'x'*20000})
        reader=q.SourceReader(q.build_review_sources(api,manifest(),api.pr))
        before=reader.catalog()
        with self.scope():self.assertEqual(reader.catalog(),before)
        self.assertEqual(before['limits']['page_response_bytes'],8192)

    def test_larger_store_exceeds_2mib_without_losing_sources(self):
        api=FakeGit(extra={f'x{i}.md':bytes([65+i])*450000 for i in range(6)})
        with self.scope():
            store=q.build_review_sources(api,manifest(),api.pr)
            self.assertGreater(sum(len(d['text'].encode()) for d in store['documents']),2097152)
            reader=q.SourceReader(store)
        for sid,page in sorted(reader.required):reader.read_page({'source_id':sid,'page':page})
        self.assertTrue(reader.complete())
        q.verify_source_receipt(q.SourceReader(store,limits_profile=NEW),reader.receipt())

    def test_blob_over_new_limit_refused(self):
        api=FakeGit(extra={'oversized.md':b'x'*(4194304+1)})
        with self.scope(),self.assertRaisesRegex(q.Hold,'^BLOB_HASH_OR_SIZE$'):
            q.build_review_sources(api,manifest(),api.pr)

    def test_store_over_new_limit_refused(self):
        api=FakeGit(extra={f'x{i}.md':bytes([65+i])*4194304 for i in range(4)})
        with self.scope(),self.assertRaisesRegex(q.Hold,'^SOURCE_TOTAL_LIMIT$'):
            q.build_review_sources(api,manifest(),api.pr)

    def test_explicit_refs_above_64_supported_but_bounded(self):
        refs=[dict(revision='head',path=f'x{i}.md',blob_sha='a'*40) for i in range(65)]
        with self.assertRaises(q.Hold):q.validate_context_sources(refs)
        with self.scope():
            q.validate_context_sources(refs)
            refs=[dict(revision='head',path=f'x{i}.md',blob_sha='a'*40) for i in range(513)]
            with self.assertRaises(q.Hold):q.validate_context_sources(refs)

    def test_context_is_restored_after_error(self):
        self.assertTrue(hasattr(q,'limit_value'))
        try:
            with self.scope():
                self.assertEqual(q.limit_value('WALL'),5400)
                raise ValueError('fixture')
        except ValueError:pass
        self.assertEqual(q.limit_value('WALL'),1700)

    def test_unknown_profile_refused(self):
        with self.scope():
            with self.assertRaises(q.Hold):
                with q.limits_scope('arbitrary-unlimited'):pass

    def test_prepare_pins_new_profile_and_limits_do_not_leak(self):
        with prepared(False) as (_,_,_,d,_):
            task=q.decode(q.read(d/'task.json'));meta=q.decode(q.read(d/'packet.json'))
            self.assertEqual(task.get('limits_profile'),NEW)
            self.assertEqual(meta.get('limits_profile'),NEW)
            self.assertEqual(meta['task_sha256'],q.sha(q.wire_json(task)))
            self.assertEqual(q.load_prepared_limits(d,task),NEW)
        self.assertEqual(q.limit_value('WALL'),1700)

    def test_new_worker_uses_5400_not_old_global_default(self):
        with prepared(False),worker_boundary() as launch,patch.object(q.signal,'setitimer') as timer:
            self.assertEqual(q.main(),0)
            self.assertEqual(timer.call_args_list[0].args[1],5400)
            self.assertEqual(launch.call_args.kwargs['limit'],5400)

    def test_old_worker_retains_original_budget(self):
        with prepared(False) as (_,_,_,d,_),worker_boundary() as launch,patch.object(q.signal,'setitimer') as timer:
            self.old_journal(d)
            self.assertEqual(q.main(),0)
            self.assertEqual(timer.call_args_list[0].args[1],1700)
            self.assertEqual(launch.call_args.kwargs['limit'],1700)

    def test_changed_limit_profile_rejected_before_worker(self):
        with prepared(False) as (_,_,_,d,_),worker_boundary() as launch:
            task=q.decode(q.read(d/'task.json'));task['limits_profile']='unlimited';q.save(d/'task.json',task)
            with self.assertRaises(q.Hold):q.main()
            launch.assert_not_called()

    def test_missing_limit_marker_is_not_auto_upgraded(self):
        with prepared(False) as (_,_,_,d,_),worker_boundary() as launch:
            meta=q.decode(q.read(d/'packet.json'));meta.pop('limits_profile',None);q.save(d/'packet.json',meta)
            with self.assertRaises(q.Hold):q.main()
            launch.assert_not_called()

    def test_pre_pin_v1_stays_legacy(self):
        with prepared(False) as (_,_,_,d,_),worker_boundary() as launch,patch.object(q.signal,'setitimer') as timer:
            task=self.old_journal(d);meta=q.decode(q.read(d/'packet.json'))
            meta.pop('task_sha256',None);meta.pop('task_schema',None);q.save(d/'packet.json',meta)
            self.assertEqual(q.load_prepared_limits(d,task),OLD)
            self.assertEqual(q.main(),0);self.assertEqual(timer.call_args_list[0].args[1],1700)

    def test_default_metadata_reader_handles_large_receipt_only_in_new_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'receipt';raw=b'x'*1500000;path.write_bytes(raw)
            with self.assertRaises(q.Hold):q.read(path)
            with self.scope():self.assertEqual(q.read(path),raw)

    def test_generated_workflow_encloses_new_worker_budget(self):
        text=q.workflow_text()
        self.assertIn('turn_timeout_ms: 5700000',text)
        self.assertIn('timeout_ms: 900000',text)
        self.assertIn('read_timeout_ms: 120000',text)
        self.assertIn('stall_timeout_ms: 900000',text)
        self.assertIn('max_turns: 1',text)

    def test_proxy_default_budget_resolved_at_call_time(self):
        for profile,expected in [(OLD,1700),(NEW,5400)]:
            additions=[]
            class Instant(float):
                def __add__(self,other):
                    additions.append(other)
                    return float(self)+other
            with tempfile.TemporaryDirectory() as tmp,q.limits_scope(profile),patch.object(q.time,'monotonic',return_value=Instant(10)),patch.object(q.subprocess,'Popen',side_effect=OSError('offline process double')):
                gate,code=q.proxy([],run_dir=Path(tmp))
                self.assertEqual(code,'OSError')
                self.assertEqual(additions[0],expected)

    def test_finalization_rejects_changed_limits_snapshot(self):
        from test_queue_schema_downgrade import completed_fixture
        with prepared() as (_,api,_,d,p):
            completed_fixture(d,p)
            meta=q.decode(q.read(d/'packet.json'));meta['limits_profile']='unlimited';q.save(d/'packet.json',meta)
            result=q.finish_task(887,api)
            self.assertEqual(result['status'],'LIMIT_PROFILE_CHANGED')
            self.assertFalse(result['release_approval']);self.assertNotIn('review_text',result)

if __name__=='__main__':unittest.main()
