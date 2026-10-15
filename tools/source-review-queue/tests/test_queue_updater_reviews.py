"""Rollback must preserve already-converged exact linked-review histories."""
import copy
import hashlib
import json
import unittest

import test_queue_updater as fixtures
from test_queue_context import q


class ReviewConvergenceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.UpdateTests('test_check_is_read_only_and_apply_keeps_workflow_state_and_execution_disabled')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.update.apply()

    def linked(self, generation=1, number=77, verdict='accepted', complete=True):
        f = self.f
        developer = f.state / 'jobs/GH-104'
        attempt = developer / 'attempts' / str(generation)
        attempt.mkdir(parents=True)
        fixtures.save(developer / 'label-removed.json', {'confirmed': False,
                      'scope': 'developer-journal-skip-for-legacy-recovery'})
        fixtures.save(developer / 'execution.json', {'role': 'developer', 'generation': generation})
        head, base = ('a' if generation == 1 else 'c') * 40, 'b' * 40
        candidate = dict(issue=104, generation=generation, head=head, base=base,
                         author_thread='author-thread', tests={'unit': {'exit_code': 0}},
                         required_tests=['unit'], artifact=dict(repo=q.REPO, head=head, tree='d' * 40, pr=103))
        fixtures.save(attempt / 'candidate.json', candidate)
        source = f.state / 'jobs' / f'GH-{number}'
        source.mkdir(exist_ok=True)
        result = dict(issue=number, head=head, release_approval=False,
                      status=q.SUCCESS if complete else 'SOURCE_REVIEW_INCOMPLETE',
                      at=q.utc(), tests_by_reviewer='NOT_RUN',
                      protocol={'thread_id': 'reviewer-thread'},
                      review_text='```snq-verdict\n' + json.dumps(dict(head_sha=head, base_sha=base, verdict=verdict)) + '\n```')
        # Reusing GH77 replaces the base fixture's delivery; not a replay.
        for name in ('comment-intent.json', 'comment-readback.json', 'label-removed.json'):
            (source / name).unlink(missing_ok=True)
        fixtures.complete_source(source, result)
        links = f.state / 'review-links'
        links.mkdir(exist_ok=True)
        link = links / f'GH-{number}.json'
        fixtures.save(link, dict(issue=104, generation=generation, review_issue=number, head=head, base=base))
        fixtures.save(source / 'linked-review-applied.json',
                      dict(source_result_sha256=hashlib.sha256(q.wire_json(result)).hexdigest(),
                           link_sha256=hashlib.sha256(link.read_bytes()).hexdigest()))
        review = dict(issue=number, head=head, base=base, verdict=verdict,
                      reviewer_thread='reviewer-thread', source_status=result['status'])
        if complete:
            disposition = q.execution_adapter().acceptance(candidate, review)
        else:
            disposition = dict(state='Blocked', head=head, base=base, release_approval=False,
                               reason='INDEPENDENT_REVIEW_INCOMPLETE')
        disposition.update(issue=104, generation=generation)
        for name in ('final.json', 'acceptance.json'):
            fixtures.save(attempt / name, disposition)
        fixtures.complete_notice(attempt, disposition)
        if disposition['state'] == 'AcceptedSource':
            (f.state / 'accepted').mkdir(exist_ok=True)
            fixtures.save(f.state / 'accepted/GH-104.json', disposition)
        return attempt, source, link

    def assert_rollback_holds(self):
        f = self.f
        before, events = f.state_bytes(), list(f.ctl.events)
        with self.assertRaises(f.u.Hold):
            f.update.rollback()
        self.assertEqual(f.ctl.events, events)
        self.assertEqual(f.state_bytes(), before)

    def test_complete_accepted_review_rolls_back_without_losing_any_history(self):
        self.linked()
        before = self.f.state_bytes()
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')
        self.assertEqual(self.f.state_bytes(), before)

    def test_applied_rework_and_incomplete_reviews_are_terminal_without_artifacts(self):
        for complete in (True, False):
            with self.subTest(complete=complete):
                self.setUp()
                self.linked(verdict='rework', complete=complete)
                self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')

    def test_old_accepted_artifact_remains_valid_after_later_applied_rework(self):
        self.linked()
        self.linked(generation=2, number=78, verdict='rework')
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')
        pointer = json.loads((self.f.state / 'accepted/GH-104.json').read_bytes())
        self.assertEqual(pointer['generation'], 1)

    def test_retired_review_is_not_applied_until_all_sinks_exist(self):
        for missing in ('linked-review-applied.json', 'acceptance.json', 'final.json', 'candidate.json', 'artifact'):
            with self.subTest(missing=missing):
                self.setUp()
                attempt, source, _ = self.linked()
                if missing == 'artifact':
                    (self.f.state / 'accepted/GH-104.json').unlink()
                elif missing == 'linked-review-applied.json':
                    (source / missing).unlink()
                else:
                    (attempt / missing).unlink()
                self.assert_rollback_holds()

    def test_inexact_issue_generation_head_or_artifact_blocks_without_any_stop(self):
        for name, field, value in [('candidate.json', 'generation', 2), ('candidate.json', 'head', 'c' * 40),
                                   ('acceptance.json', 'issue', 105), ('final.json', 'generation', 2),
                                   ('artifact', 'generation', 2), ('artifact', 'head', 'c' * 40),
                                   ('execution.json', 'generation', 0), ('link', 'head', 'e' * 40)]:
            with self.subTest(name=name, field=field):
                self.setUp()
                attempt, _, link = self.linked()
                path = (self.f.state / 'accepted/GH-104.json' if name == 'artifact' else
                        attempt.parent.parent / name if name == 'execution.json' else
                        link if name == 'link' else attempt / name)
                value_json = json.loads(path.read_bytes())
                value_json[field] = value
                fixtures.save(path, value_json)
                self.assert_rollback_holds()

    def test_marker_cannot_hide_changed_result_or_source_identity(self):
        for field, value in [('review_text', 'changed'), ('issue', 78), ('head', 'f' * 40),
                             ('protocol', {'thread_id': 'author-thread'})]:
            with self.subTest(field=field):
                self.setUp()
                _, source, _ = self.linked()
                data = json.loads((source / 'final.json').read_bytes())
                data[field] = value
                fixtures.save(source / 'final.json', data)
                self.assert_rollback_holds()

    def test_self_review_even_with_coherently_rewritten_sinks_is_refused(self):
        attempt, source, link = self.linked()
        data = json.loads((source / 'final.json').read_bytes())
        data['protocol']['thread_id'] = 'author-thread'
        fixtures.save(source / 'final.json', data)
        fixtures.save(source / 'linked-review-applied.json', dict(
            source_result_sha256=hashlib.sha256(q.wire_json(data)).hexdigest(),
            link_sha256=hashlib.sha256(link.read_bytes()).hexdigest()))
        for path in (attempt / 'acceptance.json', attempt / 'final.json', self.f.state / 'accepted/GH-104.json'):
            result = json.loads(path.read_bytes())
            result['review']['reviewer_thread'] = 'author-thread'
            fixtures.save(path, result)
        self.assert_rollback_holds()

    def test_linked_review_is_included_in_transition_seal(self):
        _, _, link = self.linked()
        before = self.f.update.seal()
        data = json.loads(link.read_bytes())
        data['generation'] = 2
        fixtures.save(link, data)
        self.assertNotEqual(before, self.f.update.seal())

    def test_empty_receipt_does_not_resolve_an_unknown_write(self):
        outbox = self.f.state / 'jobs/GH-77/attempts/1/outbox'
        outbox.mkdir(parents=True)
        fixtures.save(outbox / 'review-intent.json', {'payload': {'title': 'review'}})
        fixtures.save(outbox / 'review-receipt.json', {})
        self.assert_rollback_holds()

    def test_boolean_generation_cannot_match_integer_generation(self):
        for name in ('final', 'artifact'):
            with self.subTest(name=name):
                self.setUp()
                attempt, _, _ = self.linked()
                path = attempt / 'final.json' if name == 'final' else self.f.state / 'accepted/GH-104.json'
                result = json.loads(path.read_bytes())
                result['generation'] = True
                fixtures.save(path, result)
                self.assert_rollback_holds()

    def test_nonempty_unknown_receipt_is_not_an_authoritative_write_outcome(self):
        outbox = self.f.state / 'jobs/GH-77/attempts/1/outbox'
        outbox.mkdir(parents=True)
        fixtures.save(outbox / 'review-intent.json', {'payload': {'title': 'review'}})
        fixtures.save(outbox / 'review-receipt.json', {'unknown': True})
        self.assert_rollback_holds()

    def test_all_known_authoritative_outbox_receipt_shapes_are_preserved(self):
        outbox = self.f.state / 'jobs/GH-77/attempts/1/outbox'
        outbox.mkdir(parents=True)
        shapes = dict(branch={'sha': 'a' * 40}, tree={'sha': 'b' * 40}, commit={'sha': 'c' * 40},
                      pr={'number': 103}, review={'number': 104})
        shapes.update({'blob-0': {'sha': 'd' * 40}, 'publish-ref': {'sha': 'a' * 40},
                       'review-label': {'admitted': True}})
        for key, value in shapes.items():
            fixtures.save(outbox / (key + '-intent.json'), {'payload': {'sha': 'a' * 40, 'head': 'a' * 40}})
            fixtures.save(outbox / (key + '-receipt.json'), value)
        before = self.f.state_bytes()
        self.assertEqual(self.f.update.rollback()['status'], 'ROLLED_BACK')
        self.assertEqual(self.f.state_bytes(), before)


if __name__ == '__main__':
    unittest.main()
