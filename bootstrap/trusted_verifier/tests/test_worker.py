import importlib
import sys
from pathlib import Path
import tempfile
import unittest

class WorkerTests(unittest.TestCase):
    def setUp(self):
        try:self.worker=importlib.import_module('worker')
        except ImportError:self.fail('test worker implementation is missing')
    def exercise(self,body):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'tests').mkdir()
            (p/'tests/test_fixture_snv.py').write_text('import unittest\nclass T(unittest.TestCase):\n'+body)
            try:return self.worker.run_suite(p)
            finally:sys.modules.pop('test_fixture_snv',None)
    def test_actual_suite_success_records_all_ids(self):
        r=self.exercise('    def test_good(self): self.assertEqual(2+2,4)\n')
        self.assertEqual(r['passed'],['test_fixture_snv.T.test_good']);self.assertTrue(r['successful'])
        self.assertEqual(r['tests_run'],1)
    def test_actual_failure_cannot_report_success(self):
        r=self.exercise('    def test_bad(self): self.assertEqual(2+2,5)\n')
        self.assertFalse(r['successful']);self.assertEqual(r['failures'],['test_fixture_snv.T.test_bad'])
    def test_actual_skip_is_recorded_even_if_unittest_succeeds(self):
        r=self.exercise('    @unittest.skip("fixture")\n    def test_skip(self): pass\n')
        self.assertEqual(r['skipped'],['test_fixture_snv.T.test_skip'])
    def test_import_error_is_recorded(self):
        r=self.exercise('    def test_error(self): raise RuntimeError("fixture")\n')
        self.assertFalse(r['successful']);self.assertEqual(r['errors'],['test_fixture_snv.T.test_error'])
    def test_no_tests_is_not_an_accepted_complete_report(self):
        r=self.exercise('    pass\n')
        self.assertEqual(r['tests_run'],0)

