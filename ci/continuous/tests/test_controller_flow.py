from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci import controller
from snci.common import Hold
from snci.state import Journal
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
    def test_unknown_post_preserves_durable_intent(self):
        self.api.fail=True
        with self.assertRaises(Hold):self.attempt()
        self.assertEqual(self.j.pending()[0]['state'],'publishing')
        self.assertFalse(self.attempt())

if __name__=='__main__':unittest.main()
