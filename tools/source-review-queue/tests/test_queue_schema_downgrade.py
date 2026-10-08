"""GH94: prepared schema/profile cannot be downgraded into legacy handling.

Uses real temporary journal files; Git, account and process launch are test doubles.
"""
import contextlib
import copy
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_queue_context import q, H, manifest
from test_queue_profiles import environment, account_result, add_prompt_receipt, V1, V2

@contextlib.contextmanager
def prepared(v2=True):
    profile=q.review_profile(V2 if v2 else V1)
    with environment(v2) as (root,api,m,row,meta), patch.object(q,'probe',return_value=account_result(profile)), patch.object(q,'deliver'):
        q.prepare_task(887,api)
        yield root,api,m,root/'jobs/GH-887',profile

def downgrade(directory, remove_profile=False):
    path=directory/'task.json';task=json.loads(path.read_text())
    task['manifest']['schema']=V1
    task['manifest'].pop('context_sources',None)
    if remove_profile:task.pop('review_profile',None)
    q.save(path,task)
    return task

@contextlib.contextmanager
def worker_boundary():
    mask=os.umask(0o077);os.umask(mask)
    try:
        with patch.object(q.sys,'argv',['queue.py','_agent']),patch.object(q.os,'geteuid',return_value=q.UID),patch.object(q.os,'getegid',return_value=q.GID),patch.object(q,'job_number',return_value=887),patch.object(q.signal,'signal'),patch.object(q.signal,'setitimer'),patch.object(q,'proxy',return_value=(SimpleNamespace(complete=lambda:True,state={'app_server_exit':0}),'APP_SERVER_EOF')) as launch:
            yield launch
    finally:os.umask(mask)

def completed_fixture(directory, profile):
    task=json.loads((directory/'task.json').read_text())
    reader=q.load_source_reader(directory,task['manifest'])
    for source_id,page in sorted(reader.required):reader.read_page({'source_id':source_id,'page':page})
    q.save(directory/'run/protocol.json',add_prompt_receipt(directory,dict(thread_requests=1,turn_requests=1,turn_status='completed',app_server_exit=0,proxy_outcome='APP_SERVER_EOF',model=profile['model'],review_profile=profile,source_read=reader.receipt())))
    q.save(directory/'run/review.json',dict(head=H,text=H+' Complete synthetic source review; not live model or release approval.'))

class SchemaDowngradeTests(unittest.TestCase):
    def test_loader_rejects_legacy_schema_with_paged_profile(self):
        task={'manifest':manifest(False),'review_profile':q.review_profile(V2)}
        with self.assertRaisesRegex(q.Hold,'^REVIEW_PROFILE_CHANGED$'):q.load_job_profile(task)

    def test_preparation_pins_schema_and_whole_task_snapshot(self):
        with prepared() as (_,_,_,d,_):
            task=json.loads((d/'task.json').read_text());meta=json.loads((d/'packet.json').read_text())
            self.assertEqual(meta.get('task_schema'),V2)
            self.assertEqual(meta.get('task_sha256'),q.sha(q.wire_json(task)))

    def test_worker_rejects_v2_to_v1_downgrade(self):
        with prepared() as (_,_,_,d,_),worker_boundary() as launch:
            downgrade(d)
            with self.assertRaisesRegex(q.Hold,'^(REVIEW_PROFILE_CHANGED|TASK_SNAPSHOT_CHANGED)$'):q.main()
            launch.assert_not_called()

    def test_worker_rejects_downgrade_even_with_profile_field_removed(self):
        with prepared() as (_,_,_,d,_),worker_boundary() as launch:
            downgrade(d,True)
            with self.assertRaisesRegex(q.Hold,'^TASK_SNAPSHOT_CHANGED$'):q.main()
            launch.assert_not_called()

    def test_worker_rejects_changed_task_signature(self):
        with prepared() as (_,_,_,d,_),worker_boundary() as launch:
            task=json.loads((d/'task.json').read_text());task['issue_signature']='0'*64;q.save(d/'task.json',task)
            with self.assertRaisesRegex(q.Hold,'^TASK_SNAPSHOT_CHANGED$'):q.main()
            launch.assert_not_called()

    def test_finalization_rejects_v2_to_v1_downgrade(self):
        with prepared() as (_,api,_,d,p):
            completed_fixture(d,p);downgrade(d)
            result=q.finish_task(887,api)
            self.assertIn(result['status'],('REVIEW_PROFILE_CHANGED','TASK_SNAPSHOT_CHANGED'))
            self.assertFalse(result['release_approval'])
            self.assertNotIn('review_text',result)

    def test_finalization_rejects_downgrade_with_deleted_profile(self):
        with prepared() as (_,api,_,d,p):
            completed_fixture(d,p);downgrade(d,True)
            result=q.finish_task(887,api)
            self.assertEqual(result['status'],'TASK_SNAPSHOT_CHANGED')
            self.assertNotIn('review_text',result)

    def test_missing_preparation_pins_do_not_convert_paged_job_to_legacy(self):
        with prepared() as (_,_,_,d,_),worker_boundary() as launch:
            downgrade(d,True);meta=json.loads((d/'packet.json').read_text())
            meta.pop('task_schema',None);meta.pop('task_sha256',None);q.save(d/'packet.json',meta)
            with self.assertRaisesRegex(q.Hold,'^TASK_SNAPSHOT_CHANGED$'):q.main()
            launch.assert_not_called()

    def test_actual_old_v1_job_without_new_fields_still_runs(self):
        with prepared(False) as (_,api,_,d,_),patch.object(q,'Api',return_value=api),worker_boundary() as launch:
            task=json.loads((d/'task.json').read_text());task.pop('limits_profile',None);task.pop('prompt_binding',None);q.save(d/'task.json',task)
            meta=json.loads((d/'packet.json').read_text());meta.pop('limits_profile',None);meta.pop('prompt_binding',None);meta.pop('task_schema',None);meta.pop('task_sha256',None);q.save(d/'packet.json',meta)
            self.assertEqual(q.main(),0)
            self.assertEqual(launch.call_args.kwargs['profile']['task_schema'],V1)
            self.assertIsNone(launch.call_args.kwargs['source_reader'])

if __name__=='__main__':unittest.main()
