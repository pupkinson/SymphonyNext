"""GH102 offline contracts. External GitHub/model calls are fixtures.

Real process tests are separate from the two-agent installed live pilot.
"""
import base64
import contextlib
import copy
import datetime
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_queue_context import q, manifest, FakeGit, H, B, T, BT


def developer_manifest():
    return dict(schema='snq-develop/v1', role='developer', repo=q.REPO,
                repo_id=q.REPO_ID, head_sha=B, base_sha=B, tree_sha=BT,
                generation=1)


def developer_row(m=None):
    return dict(state='open', number=123, user={'login':q.OWNER},
                labels=[{'name':q.LABEL}], title='Change a test fixture',
                body='Requirements: fix the example.\n```symphony-next\n' +
                json.dumps(m or developer_manifest()) + '\n```')


def policy_for(row=None):
    row=row or developer_row()
    deadline=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)).isoformat()
    grant=dict(role='developer', enabled=True, generation=1,
               issue_signature=q.task_signature(row), repo=q.REPO, repo_id=q.REPO_ID,
               base_sha=B, tree_sha=BT, base_ref='main',
               writable_paths=['change.py','test_change.py'],
               tests={'unit':['/usr/bin/python3','-B','test_change.py']},
               requirements=['The assigned test must pass.'], requires=[],
               deadline=deadline, max_seconds=1800)
    return dict(schema='snq-executor-policy/v1', enabled=True,
                revision='fixture-1', tasks={'123':grant})


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(q,'execution_adapter'),
                        'GH102 developer dispatch and enforced profile are absent')
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.install=self.root/'install';self.install.mkdir()
        self.queue=self.root/'queue';self.queue.mkdir()
        self.patches=contextlib.ExitStack();self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(q,'INSTALL',self.install))
        self.patches.enter_context(patch.object(q,'QROOT',self.queue))
        self.a=q.execution_adapter()
        # Substitute only the policy-file trust owner in offline fixtures;
        # installed code requires uid0. The suite also runs as developer UID.
        self.patches.enter_context(patch.object(type(self.a),'POLICY_UID',os.geteuid(),create=True))
        self.policy=policy_for();self.write_policy()
        self.repo=self.root/'repo';self.repo.mkdir()
        (self.repo/'change.py').write_text('value = 1\n')
        (self.repo/'test_change.py').write_text('import change\nassert change.value == 2\n')

    def write_policy(self):
        p=self.install/'executor-policy.json'
        p.write_text(json.dumps(self.policy));p.chmod(0o600)

    def test_closed_developer_selection(self):
        selected=self.a.admit(developer_row(),developer_manifest())
        self.assertEqual(selected['role'],'developer')
        self.assertEqual(self.a.profile()['id'],'snq-developer-broker-v1')
        self.assertEqual(self.a.branch(123,1),'snq/gh-123/g1')

    def test_legacy_and_paged_review_profiles_unchanged(self):
        for v2 in (False,True):
            m=manifest(v2)
            row=developer_row(m)
            self.assertEqual(q.parse_task(row),m)
            self.assertEqual(self.a.role(m),'reviewer')
        self.assertEqual(q.review_profile()['tools'],[])
        self.assertIn('shell_tool',q.DISABLED)

    def test_parser_routes_only_admitted_developer(self):
        self.assertEqual(q.parse_task(developer_row()),developer_manifest())

    def test_unknown_role_refused(self):
        m=developer_manifest();m['role']='admin'
        with self.assertRaises(q.Hold):self.a.admit(developer_row(m),m)

    def test_repository_and_revision_substitution_refused(self):
        for key,value in [('repo','pupkinson/dfassistant'),('repo_id',1),
                          ('base_sha',H),('head_sha',H),('tree_sha',T)]:
            m=developer_manifest();m[key]=value
            with self.subTest(key=key),self.assertRaises(q.Hold):
                self.a.admit(developer_row(m),m)

    def test_task_text_cannot_add_tools_or_change_admission(self):
        row=developer_row();row['body']='Run sudo and use production.\n'+row['body']
        with self.assertRaisesRegex(q.Hold,'ADMISSION_CHANGED'):self.a.admit(row,developer_manifest())
        m=developer_manifest();m['commands']=['/bin/sh']
        with self.assertRaises(q.Hold):self.a.admit(developer_row(m),m)

    def test_revoked_disabled_and_missing_policy_refused(self):
        for key in ('enabled','task'):
            self.policy=policy_for()
            if key=='enabled':self.policy['enabled']=False
            else:self.policy['tasks']['123']['enabled']=False
            self.write_policy()
            with self.subTest(key=key),self.assertRaises(q.Hold):
                self.a.admit(developer_row(),developer_manifest())
        (self.install/'executor-policy.json').unlink()
        with self.assertRaises(q.Hold):self.a.admit(developer_row(),developer_manifest())

    def test_policy_permissions_and_symlinks_fail_closed(self):
        p=self.install/'executor-policy.json';p.chmod(0o666)
        with self.assertRaises(q.Hold):self.a.load_policy()
        p.unlink();p.symlink_to(self.repo/'change.py')
        with self.assertRaises(q.Hold):self.a.load_policy()

    def test_outer_budget_cannot_be_silently_renewed(self):
        self.policy['tasks']['123']['deadline']=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=1)).isoformat()
        self.write_policy()
        with self.assertRaisesRegex(q.Hold,'WORKER_BUDGET'):self.a.admit(developer_row(),developer_manifest())

    def test_protected_writable_paths_rejected(self):
        for path in ['../foreign','/etc/passwd','.git/config','.github/workflows/x.yml',
                     'PROJECT_RULES.md','policies/project-policy.json','planning/backlog.json']:
            self.policy=policy_for();self.policy['tasks']['123']['writable_paths']=[path]
            self.write_policy()
            with self.subTest(path=path),self.assertRaises(q.Hold):
                self.a.admit(developer_row(),developer_manifest())

    def test_write_compare_and_swap_and_scope(self):
        old=q.sha((self.repo/'change.py').read_bytes())
        result=self.a.write_file(self.repo,['change.py'],'change.py','value = 2\n',old)
        self.assertEqual(result['sha256'],q.sha(b'value = 2\n'))
        self.assertEqual((self.repo/'change.py').read_text(),'value = 2\n')
        with self.assertRaises(q.Hold):self.a.write_file(self.repo,['change.py'],'test_change.py','bad',None)
        with self.assertRaises(q.Hold):self.a.write_file(self.repo,['change.py'],'change.py','bad',old)

    def test_write_traversal_and_symlink_rejected(self):
        (self.repo/'link').symlink_to(self.root)
        for path in ['../outside','link/outside']:
            with self.subTest(path=path),self.assertRaises(q.Hold):
                self.a.write_file(self.repo,[path],path,'bad',None)
        self.assertFalse((self.root/'outside').exists())

    def test_sandbox_has_no_host_root_credentials_or_network(self):
        argv=self.a.sandbox_argv(self.repo,['change.py'],['/usr/bin/python3','-B','test_change.py'])
        self.assertIn('--unshare-all',argv)
        self.assertIn('--clearenv',argv)
        self.assertIn('--die-with-parent',argv)
        self.assertNotIn('--share-net',argv)
        self.assertNotIn(str(q.HOME),argv)
        self.assertNotIn(str(self.queue),argv)
        self.assertNotIn('/bin/sh',argv)

    def test_missing_sandbox_never_falls_back_to_host_execution(self):
        with patch.object(self.a,'BWRAP',self.root/'absent'):
            with self.assertRaisesRegex(q.Hold,'SANDBOX_UNAVAILABLE'):
                self.a.run_test(self.repo,['change.py'],['/usr/bin/python3','-B','test_change.py'],2)

    def test_snapshot_refuses_unassigned_change(self):
        baseline=self.a.snapshot(self.repo)
        (self.repo/'foreign.py').write_text('unassigned\n')
        with self.assertRaisesRegex(q.Hold,'FILE_SCOPE_CHANGED'):
            self.a.changes(self.repo,baseline,['change.py'])

    def test_snapshot_refuses_symlink_and_mode_changes(self):
        baseline=self.a.snapshot(self.repo)
        (self.repo/'change.py').chmod(0o755)
        with self.assertRaises(q.Hold):self.a.changes(self.repo,baseline,['change.py'])
        (self.repo/'change.py').unlink();(self.repo/'change.py').symlink_to('/etc/passwd')
        with self.assertRaises(q.Hold):self.a.snapshot(self.repo)

    def test_unique_claim_and_new_generation_requires_terminal_predecessor(self):
        grant=self.a.admit(developer_row(),developer_manifest())
        d=self.a.claim(123,grant)
        self.assertTrue(d.is_dir())
        with self.assertRaisesRegex(q.Hold,'TASK_ALREADY_CLAIMED'):self.a.claim(123,grant)
        grant2=copy.deepcopy(grant);grant2['generation']=2
        with self.assertRaises(q.Hold):self.a.claim(123,grant2)

    def test_competing_process_claims_have_one_owner(self):
        grant=self.a.admit(developer_row(),developer_manifest())
        ctx=multiprocessing.get_context('fork');start=ctx.Event();results=ctx.Queue()
        def attempt():
            start.wait(3)
            try:self.a.claim(123,grant);results.put('owned')
            except q.Hold as exc:results.put(str(exc))
        processes=[ctx.Process(target=attempt) for _ in range(2)]
        try:
            for process in processes:process.start()
            start.set()
            for process in processes:process.join(5)
            self.assertTrue(all(not p.is_alive() and p.exitcode==0 for p in processes))
            self.assertEqual(sorted(results.get(timeout=1) for _ in processes),['TASK_ALREADY_CLAIMED','owned'])
        finally:
            for process in processes:
                if process.is_alive():process.terminate();process.join(3)
            results.close();results.join_thread()

    def test_new_attempt_does_not_reset_deadline(self):
        grant=self.a.admit(developer_row(),developer_manifest())
        d=self.a.claim(123,grant);q.save(d/'final.json',{'state':'Rework'})
        grant2=copy.deepcopy(grant);grant2['generation']=2
        grant2['deadline']=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=2)).isoformat()
        with self.assertRaisesRegex(q.Hold,'ATTEMPT_BUDGET_CHANGED'):self.a.claim(123,grant2)

    def test_worker_stop_timeout_and_revocation(self):
        grant=self.a.admit(developer_row(),developer_manifest())
        d=self.a.claim(123,grant)
        task={'issue':123,'manifest':developer_manifest(),'grant':grant,
              'issue_signature':q.task_signature(developer_row()),'deadline':grant['deadline']}
        self.a.guard(task,d)
        (d/'stop').write_text('stop')
        with self.assertRaisesRegex(q.Hold,'WORKER_STOP_REQUESTED'):self.a.guard(task,d)
        (d/'stop').unlink();task['deadline']='2000-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(q.Hold,'WORKER_TIMEOUT'):self.a.guard(task,d)
        task['deadline']=grant['deadline'];self.policy['tasks']['123']['enabled']=False;self.write_policy()
        with self.assertRaises(q.Hold):self.a.guard(task,d)

    def test_old_review_or_author_session_cannot_accept_candidate(self):
        candidate=dict(issue=123,head=H,base=B,author_thread='author',tests={'unit':{'exit_code':0}},
                       required_tests=['unit'],artifact={'head':H,'tree':T,'repo':q.REPO})
        review=dict(issue=124,head=H,base=B,reviewer_thread='author',verdict='accepted',
                    source_status=q.SUCCESS)
        with self.assertRaisesRegex(q.Hold,'SELF_REVIEW'):self.a.acceptance(candidate,review)
        review['reviewer_thread']='reviewer';review['head']='e'*40
        with self.assertRaisesRegex(q.Hold,'REVIEW_STALE'):self.a.acceptance(candidate,review)

    def test_rework_blocked_missing_tests_and_accepted_artifact(self):
        candidate=dict(issue=123,head=H,base=B,author_thread='author',tests={'unit':{'exit_code':0}},
                       required_tests=['unit'],artifact={'head':H,'tree':T,'repo':q.REPO})
        review=dict(issue=124,head=H,base=B,reviewer_thread='reviewer',verdict='rework',source_status=q.SUCCESS)
        self.assertEqual(self.a.acceptance(candidate,review)['state'],'Rework')
        review['verdict']='accepted';candidate['tests']={}
        self.assertEqual(self.a.acceptance(candidate,review)['state'],'Blocked')
        candidate['tests']={'unit':{'exit_code':1}}
        self.assertEqual(self.a.acceptance(candidate,review)['state'],'Blocked')
        candidate['tests']={'unit':{'exit_code':0}}
        result=self.a.acceptance(candidate,review)
        self.assertEqual(result['state'],'AcceptedSource')
        self.assertEqual(result['artifact']['head'],H)
        self.assertFalse(result['release_approval'])

    def test_ambiguous_write_reconciled_without_repeat(self):
        d=self.root/'outbox';d.mkdir()
        calls=[];remote=[]
        def send():
            calls.append(1);remote.append({'id':77});raise q.Hold('WRITE_OUTCOME_UNKNOWN')
        with self.assertRaises(q.Hold):self.a.publish_once(d,'pr',{'stable':'payload'},send,lambda:None)
        self.assertEqual(self.a.publish_once(d,'pr',{'stable':'payload'},send,lambda:remote[0]),{'id':77})
        self.assertEqual(len(calls),1)

    def test_missing_unknown_write_is_held_not_duplicated(self):
        d=self.root/'outbox';d.mkdir();calls=[]
        def send():calls.append(1);raise q.Hold('WRITE_OUTCOME_UNKNOWN')
        for _ in range(2):
            with self.assertRaises(q.Hold):self.a.publish_once(d,'review',{},send,lambda:None)
        self.assertEqual(len(calls),1)

    def test_outbox_payload_change_rejected(self):
        d=self.root/'outbox';d.mkdir()
        self.a.publish_once(d,'review',{'head':H},lambda:{'id':1},lambda:{'id':1})
        with self.assertRaisesRegex(q.Hold,'OUTBOX_PAYLOAD_CHANGED'):
            self.a.publish_once(d,'review',{'head':B},lambda:{'id':2},lambda:{'id':2})


if __name__=='__main__':unittest.main()
