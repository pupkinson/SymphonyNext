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


from snci.source import PR75_REQUEST, validate_owner_request, validate_target, select_profile

SUCCESSOR = dict(PR75_REQUEST, head="8c5828b1a5c4a2261fb2cd0a021235109a8e07a3",
                 tree="496889153378c3e22bd58c96cf0f6855364117e5")

class SuccessorAdmissionTests(unittest.TestCase):
    def test_exact_reviewed_successor_is_a_valid_closed_request(self):
        try: validate_owner_request(SUCCESSOR)
        except Hold as e: self.fail("Reviewed successor cannot be admitted: " + str(e))
    def test_historical_request_remains_valid_for_archived_proofs(self):
        validate_owner_request(PR75_REQUEST)
    def test_unreviewed_sha_or_branch_or_extra_fields_are_rejected(self):
        for key, value in (("head", "f"*40), ("base", "e"*40), ("head_ref", "other"),
                           ("tree", "a"*40), ("draft", False), ("extra", True)):
            with self.subTest(key=key), self.assertRaises(Hold):
                validate_owner_request(dict(SUCCESSOR, **{key:value}))
    def test_installed_old_request_still_rejects_live_successor(self):
        pr={"state":"open","merged":False,"number":75,"draft":True}
        for side in ("head","base"):
            pr[side]={"sha":SUCCESSOR[side],"ref":SUCCESSOR[side+"_ref"],
                      "repo":{"id":SUCCESSOR["repository_id"]}}
        with self.assertRaisesRegex(Hold, "owner_request_target"):
            validate_target(pr, owner_request=PR75_REQUEST)


class SuccessorTransitionTests(unittest.TestCase):
    def setUp(self):
        import importlib
        import test_review_paging_repair as old_fixture
        from snci.common import blob_hash, canonical, decode, sha256, write_new
        self.canonical, self.decode, self.sha256 = canonical, decode, sha256
        old_fixture.PagingRepairTests.setUp(self)
        self.paging = self.m
        self.paging.perform(self.owner, "df9db5b37d0227c3d66170b4b952ecca32484620", None, self.source)
        self.m = importlib.import_module("snci.repair_pr75_target")
        trust=patch.object(self.m,"trusted",lambda p,**kw:Path(p));trust.start();self.addCleanup(trust.stop)
        self.original_raw=(self.etc/"policy.json").read_bytes();old=decode(self.original_raw)
        journal=Journal(self.state/"journal.sqlite3")
        key=journal.claim(TARGET,sha256(self.original_raw),None)
        journal.set(key,"hold",{"reason":"review_not_ready"});journal.close()
        root=self.state/"attempts"/key;root.mkdir()
        inputs=canonical({"target":REQUEST});review=canonical({"verdict":{"verdict":"CHANGES_REQUESTED"}})
        write_new(root/"inputs.json",inputs);write_new(root/"review.json",review)
        from snci import pr75_profile, refresh
        from snci import daily_limit
        history={"rows":daily_limit.journal_rows(self.state),"files":{str(p.relative_to(self.state)):sha256(p.read_bytes())
            for p in self.state.rglob("*") if p.is_file() and not p.name.startswith("journal.sqlite3")}}
        complete=self.state/("review-paging-"+self.m.BASE)/"COMPLETE.json"
        data={"worker.py":b"original installed worker","marker":b"successor package"}
        entries={p:{"sha":blob_hash(raw),"mode":"100644","size":len(raw)} for p,raw in data.items()}
        candidate={p:{"sha":sha,"mode":"100644","size":1} for p,sha in self.m.definition()["locked"].items()}
        self.snapshot=dict(policy=old,policy_raw=self.original_raw,tree="7"*40,package=entries,
            new={"ci/continuous/"+p:e for p,e in entries.items()},old_manifest=sha256((self.inst/"installed.json").read_bytes()),
            units={},history=history,entries=candidate)
        self.real_preflight=self.m.preflight
        class Source:
            def blob(_,entry):return next(raw for raw in data.values() if blob_hash(raw)==entry["sha"])
            def materialize(_,entries,directory):Path(directory).mkdir();(Path(directory)/"candidate.exs").write_bytes(b"fixture")
        self.source=Source()
        patches=[(self.m,"STATE",self.state),(self.m,"ETC",self.etc),(self.m,"INSTALL",self.inst),
            (self.m,"POLICY_SHA",sha256(self.original_raw)),(self.m,"ORIGINAL_COMPLETE_SHA",sha256(complete.read_bytes())),
            (self.m,"HOLD_KEY",key),(self.m,"INPUTS_SHA",sha256(inputs)),(self.m,"REVIEW_SHA",sha256(review)),
            (self.m,"trusted",lambda p,**kw:Path(p)),(self.m,"preflight",lambda *a:copy.deepcopy(self.snapshot))]
        for obj,name,value in patches:
            q=patch.object(obj,name,value);q.start();self.addCleanup(q.stop)
        from snci import runner
        good={"stages":dict.fromkeys(("build","format","lint","coverage","dialyzer"),0),"tests":464,
              "failures":0,"skipped":6,"coverage":100.0,"dialyzer_errors":0,"source_before":True,"source_after":True,"cleanup":0}
        q=patch.object(runner,"run",return_value=good);self.worker=q.start();self.addCleanup(q.stop)
        self.held={p:p.read_bytes() for p in root.iterdir()}
    def perform(self):return self.m.perform(self.owner,"a"*40,None,self.source)
    def proof(self):
        raw=(self.etc/"policy.json").read_bytes()
        return self.m.validate_preparation(self.state,self.decode(raw),raw)
    def test_native_quality_is_required_and_only_reviewed_definition_advances(self):
        before=self.decode(self.original_raw);result=self.perform();after=self.decode((self.etc/"policy.json").read_bytes())
        self.assertEqual(result["status"],"PR75_TARGET_INSTALLED_PAUSED")
        self.assertEqual(after["owner_request"],SUCCESSOR);self.assertEqual(after["profiles"][0],before["profiles"][0])
        old=before["profiles"][1];new=after["profiles"][1]
        self.assertEqual(old["image"],new["image"]);self.assertEqual(new["minimum_tests"],464);self.assertEqual(new["maximum_skips"],6)
        differences=[p for p in old["locked"] if old["locked"][p]!=new["locked"][p]]
        self.assertEqual(differences,["elixir/test/symphony_control/auth/oidc_test.exs"])
        self.assertEqual({p:p.read_bytes() for p in self.held},self.held);self.worker.assert_called_once();self.proof()
    def test_new_publishing_row_does_not_block_read_only_completion(self):
        self.perform();raw=(self.etc/"policy.json").read_bytes();journal=Journal(self.state/"journal.sqlite3")
        key=journal.claim({k:SUCCESSOR[k] for k in ("pr","head","base")},self.sha256(raw),None)
        journal.set(key,"publishing",{"fixture":"pending"});journal.close();self.proof()
    def test_mutated_current_or_archive_package_cannot_certify_completion(self):
        self.perform()
        for root in (self.inst,self.m.paths("a"*40)[2]):
            p=root/"worker.py";raw=p.read_bytes();p.write_bytes(b"changed")
            with self.assertRaisesRegex(Hold,"daily_limit_package"):self.proof()
            p.write_bytes(raw)
    def test_profile_receipt_and_original_hold_cannot_be_mutated(self):
        self.perform();policy=self.decode((self.etc/"policy.json").read_bytes());p=self.state/policy["profiles"][1]["preparation"]
        raw=p.read_bytes();p.write_bytes(b"changed")
        with self.assertRaises(Hold):self.proof()
        p.write_bytes(raw);p=next(iter(self.held));p.write_bytes(b"changed old hold")
        with self.assertRaises(Hold):self.proof()
    def test_low_count_or_quality_failure_preserves_predecessor_and_blocks_replay(self):
        from snci import runner
        bad=copy.deepcopy(self.worker.return_value);bad["tests"]=463
        with patch.object(runner,"run",return_value=bad),self.assertRaises(Hold):self.perform()
        self.assertEqual((self.etc/"policy.json").read_bytes(),self.original_raw)
        self.assertFalse(self.m.paths("a"*40)[2].exists())
        with self.assertRaisesRegex(Hold,"pr75_target_already_claimed"):self.perform()
    def test_unknown_successful_policy_write_preserves_archive_intent_without_replay(self):
        def unknown(p):(self.etc/"policy.json").write_bytes(self.canonical(p));raise OSError("lost policy response")
        with patch.object(self.owner,"replace_policy",side_effect=unknown),self.assertRaises(OSError):self.perform()
        directory,_,archive=self.m.paths("a"*40)
        self.assertTrue(archive.exists());self.assertTrue((directory/"commit-intent.json").exists())
        self.assertFalse((directory/"COMPLETE.json").exists())
        with self.assertRaisesRegex(Hold,"pr75_target_already_claimed"):self.perform()
    def test_failure_before_policy_write_restores_package_without_removing_claim(self):
        with patch.object(self.owner,"replace_policy",side_effect=OSError("before write")),self.assertRaises(OSError):self.perform()
        self.assertEqual((self.etc/"policy.json").read_bytes(),self.original_raw)
        self.assertEqual((self.inst/"revision").read_text(),self.m.BASE)
        with self.assertRaisesRegex(Hold,"pr75_target_already_claimed"):self.perform()
    def test_wrong_profile_or_unadmitted_request_cannot_be_hidden_in_completion(self):
        self.perform();p=self.etc/"policy.json";raw=p.read_bytes();policy=self.decode(raw)
        for mutate in (lambda x:x["profiles"][1].update(minimum_tests=462),lambda x:x.update(owner_request=REQUEST),
                       lambda x:x["profiles"][1]["locked"].update({"elixir/mix.lock":"0"*40})):
            changed=copy.deepcopy(policy);mutate(changed);p.write_bytes(self.canonical(changed))
            with self.assertRaises(Hold):self.proof()
        p.write_bytes(raw)
    def test_closed_source_delta_rejects_profile_owner_or_dependency_expansion(self):
        from snci import refresh
        old={p:{"sha":"old","mode":"100644"} for p in self.m.DELTA};new={p:{"sha":"new","mode":"100644"} for p in self.m.DELTA}
        refresh.package_delta(old,new,self.m.DELTA)
        for path in ("ci/continuous/owner.py","ci/continuous/profiles-pr75.json","elixir/mix.lock"):
            with self.assertRaises(Hold):refresh.package_delta(old,dict(new,**{path:{"sha":"new","mode":"100644"}}),self.m.DELTA)
    def test_nonpaused_or_changed_original_policy_cannot_claim_transition(self):
        from snci import daily_limit
        directory=self.m.paths("a"*40)[0]
        with patch.object(self.m,"preflight",self.real_preflight),patch.object(daily_limit,"paused",side_effect=Hold("paused")):
            with self.assertRaisesRegex(Hold,"paused"):self.perform()
        self.assertFalse(directory.exists())
        (self.etc/"policy.json").write_bytes(self.original_raw+b" ")
        with patch.object(self.m,"preflight",self.real_preflight),self.assertRaisesRegex(Hold,"pr75_target_original_policy"):
            self.perform()
        self.assertFalse(directory.exists())

class SuccessorDispatchTests(unittest.TestCase):
    def test_successor_requires_own_completion_before_claim_or_publication(self):
        from snci import repair_pr75_target,pr75_profile,repair_review_paging
        with patch.object(repair_pr75_target,"validate_preparation",side_effect=Hold("missing successor proof")) as own, \
             patch.object(pr75_profile,"validate_preparation") as initial,patch.object(repair_review_paging,"validate_preparation") as paging:
            with self.assertRaisesRegex(Hold,"missing successor proof"):
                controller.validate_owner_preparation(Path("/fixture"),{"owner_request":SUCCESSOR},b"fixture")
            own.assert_called_once();initial.assert_not_called();paging.assert_not_called()

if __name__ == '__main__':
    unittest.main()
