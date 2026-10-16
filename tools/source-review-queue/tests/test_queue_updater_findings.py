"""Permanent reproductions of PR103 review4281361556/4281361568.

The two original RED cases are preserved; no real service/model is invoked.
"""
import unittest
from unittest.mock import patch

import test_queue_updater as fixtures

save = fixtures.save


class ReproducedUpdaterP1s(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.UpdateTests('test_check_is_read_only_and_apply_keeps_workflow_state_and_execution_disabled')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_rollback_refuses_unapplied_linked_review_with_partial_acceptance(self):
        f = self.f
        f.update.apply()
        developer = f.state / 'jobs/GH-104'
        (developer / 'attempts/1').mkdir(parents=True)
        save(developer / 'label-removed.json', {'confirmed': False,
             'scope': 'developer-journal-skip-for-legacy-recovery'})
        save(developer / 'execution.json', {'role': 'developer', 'generation': 1})
        acceptance = {'state': 'AcceptedSource', 'head': 'a' * 40, 'base': 'b' * 40}
        save(developer / 'attempts/1/final.json', acceptance)
        save(developer / 'attempts/1/acceptance.json', acceptance)
        links = f.state / 'review-links'
        links.mkdir()
        save(links / 'GH-77.json', {'issue': 104, 'generation': 1, 'review_issue': 77,
                                  'head': 'a' * 40, 'base': 'b' * 40})
        self.assertFalse((f.state / 'jobs/GH-77/linked-review-applied.json').exists())
        self.assertFalse((f.state / 'accepted/GH-104.json').exists())
        with self.assertRaises(f.u.Hold,
             msg='Rollback must wait for linked review/accepted-artifact convergence'):
            f.update.rollback()

    def test_late_task_is_not_killed_between_idle_check_and_stop(self):
        f = self.f
        backup = f.update.make_backup

        def task_arrives():
            result = backup()
            f.ctl.busy = True
            job = f.state / 'jobs/GH-99'
            job.mkdir()
            save(job / 'claim.json', {'late_task': True})
            return result

        with patch.object(f.update, 'make_backup', side_effect=task_arrives):
            try:
                f.update.apply()
            except f.u.Hold:
                pass
        self.assertNotIn('stop', f.ctl.events,
            'A late task was stopped without an intake-freeze/drain handshake')


if __name__ == '__main__':
    unittest.main()
