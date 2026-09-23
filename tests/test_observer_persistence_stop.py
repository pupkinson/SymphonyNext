"""A failed diagnostic checkpoint must not veto an otherwise proven safe stop.

Executes the generated launch/finally control flow with inert systemd adapters.
No host service, model, credentials or external API is touched.
"""
import json
import unittest
import test_observer_start_boundary as boundary


class PersistenceStopTests(unittest.TestCase):
    def scenario(self, **kwargs):
        return boundary.StartBoundaryTests().case('none', details=True, **kwargs)

    def assert_owned_cleanup(self, data):
        self.assertIsNone(data['escaped'], 'persistence exception escaped cleanup')
        self.assertFalse(data['active'], 'owned service still active after checkpoint failure')
        self.assertEqual(sum('start' in a for a in data['commands']), 1)
        self.assertEqual(sum('stop' in a for a in data['commands']), 1)
        self.assertTrue(data['workflow_restored'])
        self.assertFalse(data['ready_present'])
        self.assertFalse(data['window_present'])
        self.assertFalse(data['dropin_present'])
        self.assertEqual(data['cleanup_calls'], ['label', 'readback'])
        self.assertGreater(data['persistence_calls'], 0)
        result = data['result']
        self.assertEqual(result['status'], 'STOP')
        self.assertIn('observer_checkpoint_failed', result['cleanup_warnings'])
        self.assertNotIn('service_stop_unconfirmed', result['cleanup_warnings'])
        self.assertTrue(result['runtime_observations']['persistence_error'])
        self.assertEqual(result['runtime_observations']['invocation_id'], boundary.INVOCATION)

    def test_enospc_after_start_before_confirmation_does_not_veto_stop(self):
        self.assert_owned_cleanup(self.scenario(persistence_fault='OSError'))

    def test_observer_error_after_start_does_not_abort_cleanup(self):
        self.assert_owned_cleanup(self.scenario(persistence_fault='ObserverError'))

    def test_enospc_after_observed_session_keeps_history_and_stops(self):
        data = self.scenario(persistence_fault='OSError', after_observation=True)
        self.assert_owned_cleanup(data)
        self.assertTrue(data['result']['runtime_observations']['session_observed'])

    def test_observer_error_after_observed_session_still_stops(self):
        self.assert_owned_cleanup(self.scenario(persistence_fault='ObserverError', after_observation=True))

    def test_lost_start_ack_and_enospc_still_stops_once(self):
        data = boundary.StartBoundaryTests().case('timeout', persistence_fault='OSError', details=True)
        self.assert_owned_cleanup(data)

    def test_interrupted_start_and_observer_error_still_stops_once(self):
        data = boundary.StartBoundaryTests().case('interrupt', persistence_fault='ObserverError', details=True)
        self.assert_owned_cleanup(data)

    def test_foreign_invocation_and_disk_failure_never_allow_stop(self):
        data = self.scenario(persistence_fault='OSError', foreign=True)
        self.assertIsNone(data['escaped'])
        self.assertTrue(data['active'])
        self.assertEqual(sum('start' in a for a in data['commands']), 1)
        self.assertEqual(sum('stop' in a for a in data['commands']), 0)
        self.assertIn('service_stop_unconfirmed', data['result']['cleanup_warnings'])
        self.assertEqual(data['cleanup_calls'], ['label', 'readback'])

    def test_last_identity_read_still_protects_replacement_invocation(self):
        data = self.scenario(persistence_fault='ObserverError', replace_before_stop=True)
        self.assertIsNone(data['escaped'])
        self.assertTrue(data['active'])
        self.assertEqual(sum('stop' in a for a in data['commands']), 0)
        self.assertIn('service_stop_unconfirmed', data['result']['cleanup_warnings'])

    def test_missing_witness_does_not_become_ownership_under_disk_failure(self):
        data = boundary.StartBoundaryTests().case('timeout', persistence_fault='OSError', missing_witness=True, details=True)
        self.assertIsNone(data['escaped'])
        self.assertTrue(data['active'])
        self.assertEqual(sum('stop' in a for a in data['commands']), 0)
        self.assertLessEqual(data['elapsed'], 15)
        self.assertEqual(data['cleanup_calls'], ['label', 'readback'])

    def test_final_report_write_failure_is_visible_after_safe_stop(self):
        data = self.scenario(persistence_fault='OSError', result_write_failure=True)
        self.assertIsNone(data['escaped'])
        self.assertFalse(data['active'])
        self.assertIsNone(data['result'])
        self.assertEqual(sum('stop' in a for a in data['commands']), 1)
        self.assertTrue(data['workflow_restored'])
        self.assertEqual(data['cleanup_calls'], ['label', 'readback'])
        output = data['printed'].split('=== BOOT-P01 RESULT ===\n', 1)[-1]
        result = json.loads(output)
        self.assertEqual(result['status'], 'STOP')
        self.assertIn('result_persistence_failed', result['cleanup_warnings'])
        self.assertTrue(result['runtime_observations']['persistence_error'])


if __name__ == '__main__':
    unittest.main()
