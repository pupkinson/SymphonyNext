"""Offline specification checks; no implemented adapter or runtime acceptance."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = 'docs/superpowers/specs/2026-10-02-tracker-selection-design.md'
PLAN = 'planning/tracker-selection.json'


def load(path):
    return json.loads((ROOT / path).read_text())


class TrackerSelectionSpecTests(unittest.TestCase):
    def test_all_three_first_version_choices_and_native_default(self):
        p = load(PLAN)
        self.assertEqual(p['providers'], ['native', 'github', 'linear'])
        self.assertEqual(p['default_provider'], 'native')
        self.assertEqual(p['release_scope'], 'first_accepted_version')
        self.assertEqual(p['active_providers_per_project'], 1)

    def test_no_claim_of_implementation_or_dispatch(self):
        p = load(PLAN)
        self.assertEqual(p['implementation_state'], 'NOT_IMPLEMENTED')
        self.assertFalse(p['dispatch_enabled'])
        self.assertTrue(all(t['status'] == 'planned' and not t['admitted'] for t in p['tasks']))

    def test_amendment_and_plan_registered_with_correct_hash(self):
        entries = load('planning/spec-index.json')['required_addenda']
        for path in (DOC, PLAN):
            rows = [x for x in entries if x['path'] == path]
            self.assertEqual(len(rows), 1, path)
            self.assertEqual(rows[0]['sha256'], hashlib.sha256((ROOT/path).read_bytes()).hexdigest())

    def test_baseline_and_mcp_hashes_preserved(self):
        index = load('planning/spec-index.json')
        for row in index['base_files']:
            self.assertEqual(row['sha256'], hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest())
        self.assertEqual(index['task_refinements'][0]['sha256'], '41d08997853a09131fc6d02e57887a87fc7e3fd8a6b050c6bc386f01ac948caf')
        self.assertFalse(index['dispatch_enabled'])
        self.assertIn('MCP-SN031-r2', index['revision'])

    def test_each_requirement_has_acceptance_and_work_owner(self):
        p = load(PLAN)
        expected = {f'TRK-{i:02}' for i in range(1, 15)}
        self.assertEqual(set(p['requirements']), expected)
        doc = (ROOT/DOC).read_text()
        self.assertEqual(set(re.findall(r'\*\*(TRK-\d{2})[. ]', doc)), expected)
        covered = {r for ac in p['acceptance'] for r in ac['requirements']}
        owners = {r for t in p['tasks'] for r in t['requirements']}
        self.assertEqual(covered, expected)
        self.assertEqual(owners, expected)
        self.assertEqual({a['id'] for a in p['acceptance']}, {f'AC-TRK-{i:02}' for i in range(1, 13)})

    def test_existing_conflicts_are_explicitly_scoped(self):
        p = load(PLAN)
        required = {'INV-02','DEC-04','DEC-05','DATA-01','DATA-03','DATA-05','DATA-09',
                    'UI-02','INT-01','INT-02','INT-07','INT-08','NFR-11','AC-34','AC-73','SN-043',
                    'TSK-01','TSK-04','TSK-10','TSK-13'}
        self.assertTrue(required <= set(p['baseline_clauses_reinterpreted']))
        doc = (ROOT/DOC).read_text()
        for clause in required:
            self.assertIn(clause, doc)

    def test_new_task_graph_is_acyclic_and_prerequisites_exist(self):
        p = load(PLAN)
        base = load('planning/backlog.json')['tasks']
        graph = {t['id']: t['depends_on'] for t in base + p['tasks']}
        self.assertEqual(len(graph), len(base) + len(p['tasks']))
        done, active = set(), set()
        def visit(k):
            self.assertIn(k, graph)
            self.assertNotIn(k, active)
            if k in done:
                return
            active.add(k)
            for d in graph[k]:
                visit(d)
            active.remove(k)
            done.add(k)
        for task in graph:
            visit(task)
        self.assertEqual(set(p['final_milestone_required_tasks']), {t['id'] for t in p['tasks']})

    def test_all_source_manifest_entries_match(self):
        for line in (ROOT/'MANIFEST.sha256').read_text().splitlines():
            digest, path = line.split('  ', 1)
            self.assertEqual(digest, hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), path)

    def test_readme_links_effective_spec_not_only_frozen_baseline(self):
        readme = (ROOT/'README.md').read_text()
        self.assertIn(DOC, readme)
        self.assertIn('GitHub Issues', readme)
        self.assertIn('Linear', readme)


if __name__ == '__main__':
    unittest.main()
