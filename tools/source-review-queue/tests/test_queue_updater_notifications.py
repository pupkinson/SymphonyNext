"""Complete delivery contract, all roles/generations; no remote/service writes.

Includes both original4285700019 counterexamples, strengthened to use actual
notify/deliver bodies. Positive fixtures are written by the unchanged queue.
"""
import copy
import json
import stat
import unittest
from unittest.mock import patch

import test_queue_updater as fixtures
from test_queue_context import q
import test_queue_updater_reviews as review_fixtures


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.UpdateTests('test_check_is_read_only_and_apply_keeps_workflow_state_and_execution_disabled')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.update.apply()

    def developer(self, generation=1, state='Blocked', complete=True):
        job = self.f.state / 'jobs/GH-104'
        attempt = job / 'attempts' / str(generation)
        attempt.mkdir(parents=True)
        fixtures.save(job / 'execution.json', dict(role='developer', generation=generation))
        fixtures.save(job / 'label-removed.json', dict(confirmed=False,
                      scope='developer-journal-skip-for-legacy-recovery'))
        result = dict(state=state, issue=104, release_approval=False)
        fixtures.save(attempt / 'final.json', result)
        if complete:
            fixtures.complete_notice(attempt, result)
        return attempt, attempt / 'notifications' / state

    def holds(self, mode='rollback'):
        f = self.f
        before, events = f.state_bytes(), list(f.ctl.events)
        with self.assertRaises(f.u.Hold):
            getattr(f.update, mode)()
        self.assertEqual(f.state_bytes(), before, 'HOLD must preserve all journals')
        self.assertEqual(f.ctl.events, events, 'HOLD must precede service stop')
        self.assertTrue(f.ctl.running)
        self.assertEqual(stat.S_IMODE((f.state / 'jobs').stat().st_mode), 0o700)

    def test_unconfirmed_notification_comment_blocks_rollback(self):
        _, notice = self.developer()
        (notice / 'comment-readback.json').unlink()
        self.holds()

    def test_unconfirmed_nested_label_removal_blocks_rollback(self):
        _, notice = self.developer()
        fixtures.save(notice / 'label-remove-intent.json', {'at': q.utc()})
        (notice / 'label-removed.json').unlink()
        self.holds()

    def test_unknown_root_legacy_comment_is_not_retired_by_label_marker(self):
        (self.f.state / 'jobs/GH-77/comment-readback.json').unlink()
        self.holds()

    def test_unknown_root_legacy_label_removal_blocks(self):
        job = self.f.state / 'jobs/GH-77'
        fixtures.save(job / 'label-remove-intent.json', {'at': q.utc()})
        (job / 'label-removed.json').unlink()
        self.holds()

    def test_missing_required_developer_notice_is_not_success(self):
        self.developer(complete=False)
        self.holds()

    def test_empty_required_notice_directory_is_not_success(self):
        _, notice = self.developer(complete=False)
        notice.mkdir(parents=True)
        self.holds()

    def test_every_previous_generation_requires_its_final_notice(self):
        first, _ = self.developer(complete=False)
        self.developer(generation=2)
        self.holds()
        fixtures.complete_notice(first, json.loads((first / 'final.json').read_bytes()))
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')

    def test_unfinished_noncurrent_state_in_previous_generation_blocks(self):
        attempt, _ = self.developer()
        old = attempt / 'notifications/Review'
        old.mkdir()
        fixtures.save(old / 'comment-intent.json', {'body': 'old unknown comment'})
        self.developer(generation=2)
        self.holds()

    def test_all_three_generations_and_nonaccepted_terminal_states_pass(self):
        for generation, state in enumerate(('Stopped', 'Rework', 'Blocked'), 1):
            self.developer(generation, state)
        before = self.f.state_bytes()
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')
        self.assertEqual(self.f.state_bytes(), before)

    def test_historical_review_body_binds_own_candidate_not_later_final(self):
        review = review_fixtures.ReviewConvergenceTests()
        review.f = self.f
        attempt, _, _ = review.linked()
        candidate = json.loads((attempt / 'candidate.json').read_bytes())
        old_result = dict(state='Review', issue=104, release_approval=False,
                          **{k: candidate[k] for k in ('head', 'base', 'artifact', 'tests')})
        fixtures.complete_notice(attempt, old_result)
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')

    def test_linked_review_delivery_is_required_in_addition_to_applied_sinks(self):
        review = review_fixtures.ReviewConvergenceTests()
        review.f = self.f
        _, source, _ = review.linked()
        (source / 'comment-readback.json').unlink()
        self.holds()

    def test_missing_every_required_record_holds_for_legacy_and_developer(self):
        for role in ('legacy', 'developer'):
            for name in ('final.json', 'comment-intent.json', 'comment-readback.json', 'label-removed.json'):
                with self.subTest(role=role, name=name):
                    self.setUp()
                    if role == 'developer':
                        attempt, notice = self.developer()
                        path = attempt / name if name == 'final.json' else notice / name
                    else:
                        path = self.f.state / 'jobs/GH-77' / name
                    path.unlink()
                    self.holds()

    def test_invalid_receipt_schemas_are_not_proof(self):
        bad = [('comment-readback.json', {}), ('comment-readback.json', {'id': None}),
               ('comment-readback.json', {'id': True}), ('comment-readback.json', {'id': 0}),
               ('comment-readback.json', {'id': '12345'}),
               ('comment-readback.json', {'id': 12345, 'unknown': True}),
               ('label-removed.json', {}), ('label-removed.json', {'confirmed': True}),
               ('label-removed.json', {'confirmed': False, 'at': q.utc()}),
               ('label-removed.json', {'confirmed': 1, 'at': q.utc()}),
               ('label-removed.json', {'confirmed': True, 'at': 'yesterday'}),
               ('label-remove-intent.json', {'at': None}),
               ('label-remove-intent.json', {'at': '2026-10-15T16:38:32'}),
               ('comment-intent.json', {'body': []}),
               ('delivery-hold.json', {'reason': 'unknown'})]
        for role in ('legacy', 'developer'):
            for name, value in bad:
                with self.subTest(role=role, name=name, value=value):
                    self.setUp()
                    notice = self.developer()[1] if role == 'developer' else self.f.state / 'jobs/GH-77'
                    fixtures.save(notice / name, value)
                    self.holds()

    def test_corrupt_duplicate_and_nonfinite_json_are_not_receipts(self):
        for raw in ('{', '[]', '{"id":12345,"id":0}', '{"id":NaN}'):
            with self.subTest(raw=raw):
                self.setUp()
                _, notice = self.developer()
                (notice / 'comment-readback.json').write_text(raw)
                self.holds()

    def test_receipt_older_than_delete_intent_is_contradictory(self):
        _, notice = self.developer()
        fixtures.save(notice / 'label-remove-intent.json', {'at': '2026-10-15T18:00:00Z'})
        fixtures.save(notice / 'label-removed.json', {'confirmed': True, 'at': '2026-10-15T17:00:00Z'})
        self.holds()

    def test_unresolved_delivery_hold_is_not_hidden_by_old_receipts(self):
        job = self.f.state / 'jobs/GH-77'
        fixtures.save(job / 'delivery-hold.json', {'reason': 'LABEL_REMOVAL_OUTCOME_UNKNOWN',
                                                  'at': '2026-10-16T00:00:00Z'})
        self.holds()

    def test_old_delivery_hold_can_remain_after_confirmed_recovery(self):
        job = self.f.state / 'jobs/GH-77'
        fixtures.save(job / 'delivery-hold.json', {'reason': 'COMMENT_PUBLICATION_UNRESOLVED',
                                                  'at': '2026-10-15T00:00:00Z'})
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')
        self.assertTrue((job / 'delivery-hold.json').exists())

    def test_developer_body_issue_generation_state_head_and_final_must_match(self):
        for field, value in [('issue', 105), ('issue', True), ('generation', 2), ('generation', True),
                             ('state', 'Stopped'), ('head', 'e' * 40), ('release_approval', True)]:
            with self.subTest(field=field):
                self.setUp()
                _, notice = self.developer()
                intent = json.loads((notice / 'comment-intent.json').read_bytes())
                prefix, raw = intent['body'].split('\n\n', 1)
                result = json.loads(raw)
                result[field] = value
                fixtures.save(notice / 'comment-intent.json', {'body': prefix + '\n\n' + json.dumps(result, sort_keys=True)})
                self.holds()

    def test_legacy_body_must_bind_exact_result_not_only_issue_prefix(self):
        job = self.f.state / 'jobs/GH-77'
        data = json.loads((job / 'comment-intent.json').read_bytes())
        data['body'] = data['body'].replace('SOURCE_REVIEW_INCOMPLETE', 'DIFFERENT_RESULT')
        fixtures.save(job / 'comment-intent.json', data)
        self.holds()

    def test_developer_compatibility_marker_is_not_legacy_success(self):
        job = self.f.state / 'jobs/GH-77'
        fixtures.save(job / 'label-removed.json', dict(confirmed=False,
                      scope='developer-journal-skip-for-legacy-recovery'))
        self.holds()

    def test_developer_compatibility_marker_itself_must_be_exact(self):
        attempt, _ = self.developer()
        fixtures.save(attempt.parent.parent / 'label-removed.json', {'confirmed': True, 'at': q.utc()})
        self.holds()

    def test_legacy_missing_delivery_cannot_use_generic_compatibility_skip(self):
        job = self.f.state / 'jobs/GH-77'
        for name in ('comment-intent.json', 'comment-readback.json', 'final.json'):
            (job / name).unlink()
        self.holds()

    def test_noncanonical_or_missing_generations_are_not_skipped(self):
        for name in ('01', '0', '4'):
            with self.subTest(name=name):
                self.setUp()
                attempt, _ = self.developer()
                attempt.rename(attempt.with_name(name))
                self.holds()
        self.setUp()
        self.developer(generation=2)
        self.holds()

    def test_unknown_state_or_nested_notification_directory_is_not_skipped(self):
        for name in ('Unknown', 'Blocked/nested'):
            with self.subTest(name=name):
                self.setUp()
                attempt, _ = self.developer()
                (attempt / 'notifications' / name).mkdir(parents=True, exist_ok=True)
                self.holds()

    def test_notification_parent_and_receipt_symlinks_are_refused(self):
        for kind in ('parent', 'receipt'):
            with self.subTest(kind=kind):
                self.setUp()
                attempt, notice = self.developer()
                path = attempt / 'notifications' if kind == 'parent' else notice / 'comment-readback.json'
                target = self.f.root / ('preserved-' + kind)
                path.rename(target)
                path.symlink_to(target, target_is_directory=kind == 'parent')
                self.holds()

    def test_completed_label_delete_intent_and_no_delete_intent_both_pass(self):
        _, notice = self.developer()
        fixtures.save(notice / 'label-remove-intent.json', {'at': '2026-10-15T00:00:00Z'})
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')

    def test_atomic_save_leftovers_are_not_confirmations_or_pending_api_writes(self):
        _, notice = self.developer()
        # save() may die before replace. Only the canonical filename can
        # trigger an external write; leftovers cannot replace its receipt.
        (notice / '.comment-intent.json.1234').write_text('{"body":')
        (notice / '.label-removed.json.1234').write_text('{"confirmed":')
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')

    def test_atomic_save_leftover_cannot_replace_missing_canonical_receipt(self):
        _, notice = self.developer()
        (notice / 'comment-readback.json').rename(notice / '.comment-readback.json.1234')
        self.holds()

    def test_malformed_body_is_hold_and_not_an_uncaught_parser_error(self):
        _, notice = self.developer()
        fixtures.save(notice / 'comment-intent.json',
                      {'body': 'snq-v1 GH-104\n## Symphony developer result\n\n{'})
        self.holds()

    def test_source_formatter_preserves_long_unicode_and_redaction_contract(self):
        job = self.f.state / 'jobs/GH-88'
        job.mkdir()
        result = dict(issue=88, head='UNKNOWN', status='SOURCE_REVIEW_INCOMPLETE', at=q.utc(),
                      protocol={}, tests_by_reviewer='NOT_RUN', release_approval=False,
                      review_text='\x1b[31mReport\x1b[0m\x01 Bearer fixture-token\n' + 'я' * 60000)
        fixtures.complete_source(job, result)
        self.assertGreater((job / 'final.json').stat().st_size, 100000)
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')

    def test_apply_hold_releases_gate_and_preserves_notification_history(self):
        # Fresh predecessor transition, not the already applied fixture.
        self.f.doCleanups()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.developer(complete=False)
        self.holds('apply')

    def test_interrupted_owned_pause_is_released_on_notification_hold(self):
        _, notice = self.developer()
        self.f.update.intake()
        (notice / 'comment-readback.json').unlink()
        self.holds()
        receipt = json.loads((self.f.update.backup / 'intake.json').read_bytes())
        self.assertEqual(receipt['phase'], 'released')

    def test_interruption_before_stop_preserves_and_reopens_only_owned_gate(self):
        self.f.update.intake()
        events, before = list(self.f.ctl.events), self.f.state_bytes()
        with patch.object(self.f.update, 'quiet', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.f.update.rollback()
        self.assertEqual(self.f.state_bytes(), before)
        self.assertEqual(self.f.ctl.events, events)
        self.assertEqual(stat.S_IMODE((self.f.state / 'jobs').stat().st_mode), 0o700)

    def test_stopped_hold_retains_explicit_closed_gate_and_recoverable_receipt(self):
        _, notice = self.developer()
        self.f.update.intake()
        self.f.ctl.stop()
        (notice / 'comment-readback.json').unlink()
        before = self.f.state_bytes()
        with self.assertRaises(self.f.u.Hold):
            self.f.update.rollback()
        self.assertEqual(self.f.state_bytes(), before)
        self.assertFalse(self.f.ctl.running)
        self.assertEqual(stat.S_IMODE((self.f.state / 'jobs').stat().st_mode), 0o500)

    def test_unknown_comment_is_recovered_by_existing_queue_without_reposting(self):
        self._recover_unknown('POST')

    def test_unknown_label_delete_is_recovered_by_existing_queue_without_redeleting(self):
        self._recover_unknown('DELETE')

    def _recover_unknown(self, unknown):
        attempt, _ = self.developer(complete=False)
        result = json.loads((attempt / 'final.json').read_bytes())

        class AmbiguousApi:
            def __init__(self):
                self.posts, self.deletes, self.comments = 0, 0, []
                self.admitted = unknown == 'DELETE'

            def get(self, path):
                if '/comments?' in path:
                    return copy.deepcopy(self.comments)
                return {'labels': [{'name': q.LABEL}] if self.admitted else []}

            def request(self, method, path, body=None):
                if method == 'POST':
                    self.posts += 1
                    value = {'id': 12345, 'body': body['body']}
                    self.comments.append(value)
                    if unknown == 'POST':
                        raise q.Hold('RESPONSE_LOST_AFTER_POST')
                    return value
                self.deletes += 1
                self.admitted = False
                raise q.Hold('RESPONSE_LOST_AFTER_DELETE')

        api = AmbiguousApi()
        with self.assertRaises(q.Hold):
            q.execution_adapter().notify(104, attempt, api, result)
        self.holds()
        self.holds()  # Updater is read-only, never a notification dispatcher.
        self.assertEqual((api.posts, api.deletes), (1, int(unknown == 'DELETE')))
        q.execution_adapter().notify(104, attempt, api, result)
        self.assertEqual((api.posts, api.deletes), (1, int(unknown == 'DELETE')))
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')


if __name__ == '__main__':
    unittest.main()
