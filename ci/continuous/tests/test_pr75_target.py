"""Exact owner requests cannot turn a stacked draft into a general CI bypass."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci import controller
from snci.common import Hold
from snci.source import validate_target
from snci.state import Journal
from test_daily_limit import policy

REQUEST = {'pr': 75, 'head': 'be5371e71db363d5a07c7109d6dd010a6ceca7ef',
           'base': '233dda1878533a425574074b8d34344b50d41cf7',
           'tree': 'b0f828141ca90851f6e037d6f1741aaaa28496de',
           'head_ref': 'feat/sn005-oidc-protocol-20261004',
           'base_ref': 'docs/sn005-authentik-project-access-20261004',
           'repository_id': 1381693716, 'draft': True}
TARGET = {key: REQUEST[key] for key in ('pr', 'head', 'base')}


def candidate():
    return {'number': 75, 'state': 'open', 'merged': False, 'draft': True, 'labels': [],
            'head': {'sha': REQUEST['head'], 'ref': REQUEST['head_ref'], 'repo': {'id': 1381693716}},
            'base': {'sha': REQUEST['base'], 'ref': REQUEST['base_ref'], 'repo': {'id': 1381693716}}}


class TargetTests(unittest.TestCase):
    def admitted(self, pr, request=REQUEST):
        try:
            return validate_target(pr, owner_request=request)
        except TypeError:
            self.fail('The installed target guard cannot accept a closed owner request yet')

    def test_exact_owner_request_admits_only_this_unlabelled_stacked_draft(self):
        self.assertEqual(self.admitted(candidate()), TARGET)

    def test_unrequested_stacked_draft_stays_rejected_even_with_verify_label(self):
        pr = candidate(); pr['labels'] = [{'name': 'snv:verify'}]
        with self.assertRaisesRegex(Hold, 'base_branch'):
            validate_target(pr)

    def test_head_base_refs_repository_draft_and_closed_state_cannot_drift(self):
        for side, field, value in [('head', 'sha', 'a' * 40), ('base', 'sha', 'b' * 40),
                                   ('head', 'ref', 'other'), ('base', 'ref', 'main'),
                                   ('head', 'repo', {'id': 1}), ('base', 'repo', {'id': 1})]:
            pr = candidate(); pr[side][field] = value
            with self.subTest(side=side, field=field), self.assertRaises(Hold):
                self.admitted(pr)
        for field, value in [('number', 14), ('draft', False), ('state', 'closed'), ('merged', True)]:
            pr = candidate(); pr[field] = value
            with self.subTest(field=field), self.assertRaises(Hold):
                self.admitted(pr)

    def test_a_label_cannot_retarget_or_extend_the_owner_request(self):
        pr = candidate(); pr['labels'] = [{'name': 'snv:verify'}]
        for key, value in [('pr', 14), ('head', 'a' * 40), ('tree', 'b' * 40),
                           ('base_ref', 'main'), ('draft', False), ('extra', True)]:
            request = dict(REQUEST); request[key] = value
            with self.subTest(key=key), self.assertRaises(Hold):
                self.admitted(pr, request)

    def test_policy_rejects_malformed_requests_instead_of_ignoring_unknown_fields(self):
        for request in (None, {}, dict(REQUEST, head='a' * 40), dict(REQUEST, pr=True)):
            p = policy(None); p['owner_request'] = request
            with self.subTest(request=request), self.assertRaises(Hold):
                controller.validate_policy(p)

    def test_wrong_target_is_rejected_before_claiming_a_journal_row(self):
        class Source:
            def tree(self, _): return 'a' * 40, {'same': {'sha': 'b' * 40}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'attempts').mkdir()
            journal = Journal(root / 'journal.sqlite3')
            try:
                with patch.object(controller, 'STATE', root), self.assertRaises(Hold):
                    controller.process(None, journal, Source(), dict(TARGET, head='a' * 40),
                                       {'daily_attempts': None, 'owner_request': REQUEST}, 'fixture-policy')
                self.assertEqual(journal.db.execute('SELECT count(*) FROM attempts').fetchone()[0], 0)
            finally:
                journal.close()

    def test_tree_mismatch_cannot_create_inputs_or_invoke_review(self):
        class Source:
            def tree(self, _): return 'a' * 40, {'changed': {'sha': 'b' * 40}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'attempts').mkdir()
            journal = Journal(root / 'journal.sqlite3')
            try:
                with patch.object(controller, 'STATE', root), self.assertRaisesRegex(Hold, 'owner_request_tree'):
                    controller.process(None, journal, Source(), TARGET,
                                       {'daily_attempts': None, 'owner_request': REQUEST}, 'fixture-policy')
                self.assertEqual(list(root.glob('attempts/*/inputs.json')), [])
            finally:
                journal.close()

    def test_one_shot_fetches_the_admitted_pr_and_holds_on_drift(self):
        class API:
            def request(self, method, path):
                if (method, path) != ('GET', '/repos/pupkinson/SymphonyNext/pulls/75'):
                    raise AssertionError('Unexpected remote operation')
                return candidate()
        select = getattr(controller, 'targets', None)
        self.assertIsNotNone(select, 'No owner-specific target selection exists yet')
        self.assertEqual(select(API(), {'owner_request': REQUEST}), [TARGET])
        with patch.dict(REQUEST, head='a' * 40), self.assertRaises(Hold):
            select(API(), {'owner_request': REQUEST})


if __name__ == '__main__':
    unittest.main()
