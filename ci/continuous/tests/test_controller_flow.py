from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci import controller
from snci.common import Hold
from snci.state import Journal
from snci.reviewer import ReadOnlyContext
from snci.common import canonical, sha256
from test_pipeline import API, T

class Source:
    def tree(self,sha):return 'c'*40,{'x':{'sha':sha}}
    def materialize(self,head,path):Path(path).mkdir()

class ControllerFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'attempts').mkdir()
        self.j=Journal(self.root/'db');self.api=API()
        self.policy={'daily_attempts':4}
        self.patches=[patch.object(controller,'STATE',self.root),patch.object(controller,'guard'),
                      patch.object(controller,'protected_change'),patch.object(controller,'select_profile',return_value={'name':'fixture'})]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.j.close();self.tmp.cleanup()
    def attempt(self,review=None,worker=None):
        return controller.process(self.api,self.j,Source(),T,self.policy,'digest',
          review_fn=review or (lambda *a:{'verdict':{'verdict':'READY'}}),
          run_fn=worker or (lambda *a:{'stages':'fixture-only'}))
    def test_full_orchestration_deduplicates_target(self):
        self.assertTrue(self.attempt());self.assertFalse(self.attempt())
        self.assertEqual(sum(x[0]=='POST' for x in self.api.calls),1)
        self.assertEqual(len(list((self.root/'attempts').glob('*/result.json'))),1)
    def test_review_hold_never_runs_worker_or_posts(self):
        ran=[]
        with self.assertRaisesRegex(Hold,'review_not_ready'):
            self.attempt(lambda *a:{'verdict':{'verdict':'HOLD'}},lambda *a:ran.append(1))
        self.assertFalse(ran);self.assertFalse(self.api.calls)
        self.assertFalse(self.attempt())
    def test_failed_worker_never_posts_and_no_retry(self):
        def fail(*a):raise Hold('worker_failed')
        with self.assertRaisesRegex(Hold,'worker_failed'):self.attempt(worker=fail)
        self.assertFalse(self.api.calls);self.assertFalse(self.attempt())
    def test_source_denial_is_saved_without_untrusted_argument_values_or_retry(self):
        ctx=ReadOnlyContext(None,{'x':{}},{'x':{}},['x'])
        args={'path':'private-canary-value','revision':'head','page':0}
        def denied(*a):ctx.read(args)
        ran=[]
        with self.assertRaisesRegex(Hold,'review_source_only'):
            self.attempt(denied,lambda *a:ran.append(1))
        row=self.j.db.execute('SELECT key FROM attempts').fetchone()
        data=self.j.get(row[0])['data']
        self.assertEqual(data['reason'],'review_source_only')
        self.assertEqual(data['review_diagnostic']['category'],'unknown_path')
        self.assertEqual(data['review_diagnostic']['arguments_sha256'],sha256(canonical(args)))
        self.assertNotIn('private-canary-value',canonical(data).decode())
        self.assertFalse(ran);self.assertFalse(self.api.calls);self.assertFalse(self.attempt())
        self.assertEqual({p.name for p in (self.root/'attempts'/row[0]).iterdir()},{'inputs.json'})
    def test_unknown_post_preserves_durable_intent(self):
        self.api.fail=True
        with self.assertRaises(Hold):self.attempt()
        self.assertEqual(self.j.pending()[0]['state'],'publishing')
        self.assertFalse(self.attempt())

class OwnerPreparationDispatchTests(unittest.TestCase):
    def validate(self, policy):
        self.assertTrue(hasattr(controller, 'validate_owner_preparation'),
                        'Controller cannot distinguish a preserved original receipt from package maintenance')
        return controller.validate_owner_preparation(Path('/fixture-state'), policy, canonical(policy))

    def test_maintenance_requires_its_own_completion_before_any_attempt(self):
        from snci import pr75_profile, repair_review_paging as repair
        policy = {'installed_revision':'a'*40, 'profiles':[{'name':'sn004',
            'preparation':'refresh-'+repair.BASE+'/sn004/acceptance.json'}]}
        with patch.object(pr75_profile, 'validate_preparation') as ordinary, \
             patch.object(repair, 'validate_preparation', side_effect=Hold('missing_paging_completion')) as maintained:
            with self.assertRaisesRegex(Hold, 'missing_paging_completion'): self.validate(policy)
            ordinary.assert_not_called(); maintained.assert_called_once()

    def test_original_e7_profile_keeps_original_gate(self):
        from snci import pr75_profile, repair_review_paging as repair
        policy = {'installed_revision':repair.BASE, 'profiles':[{'name':'sn004',
            'preparation':'refresh-'+repair.BASE+'/sn004/acceptance.json'}]}
        with patch.object(pr75_profile, 'validate_preparation', return_value='original-proof') as ordinary, \
             patch.object(repair, 'validate_preparation') as maintained:
            self.assertEqual(self.validate(policy), 'original-proof')
            ordinary.assert_called_once(); maintained.assert_not_called()

if __name__=='__main__':unittest.main()
