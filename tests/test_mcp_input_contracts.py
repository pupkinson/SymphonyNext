"""Offline checks of this exact MCP refinement; not a runtime backlog importer."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator
ROOT = Path(__file__).resolve().parents[1]
def load(name): return json.loads((ROOT / name).read_text())
def compose_fixture(base, refinement):
    tasks = {t['id']: copy.deepcopy(t) for t in base['tasks']}
    for change in refinement['task_overrides']:
        task = tasks[change['id']]
        if task['depends_on'] != change['expected_depends_on']: raise ValueError('dependency_precondition_mismatch')
        if 'interfaces_consumes' in change:
            if task['interfaces']['consumes'] != change['expected_interfaces_consumes']: raise ValueError('consumes_precondition_mismatch')
            task['interfaces']['consumes'] = copy.deepcopy(change['interfaces_consumes'])
        task['depends_on'] = change['depends_on'][:]
    for child in refinement['tasks']: tasks[child['id']] = copy.deepcopy(child)
    return tasks

def check_graph(tasks, include_contracts=True):
    edges = {k: set(v['depends_on']) for k, v in tasks.items()}
    if include_contracts:
        for key, value in tasks.items(): edges[key].update(x['task'] for x in value.get('interfaces', {}).get('consumes', []))
    done, visiting = set(), set()
    def visit(k):
        if k not in edges: raise ValueError('missing_task')
        if k in visiting: raise ValueError('contract_cycle')
        if k in done: return
        visiting.add(k)
        for item in edges[k]: visit(item)
        visiting.remove(k); done.add(k)
    for k in edges: visit(k)
    return edges

class InputContractTests(unittest.TestCase):
    def setUp(self):
        self.base = load('planning/backlog.json'); self.r = load('planning/mcp-execution.json')
        self.schema = Draft202012Validator(load('schemas/task-refinement.schema.json'))
        self.change = next(t for t in self.r['task_overrides'] if t['id'] == 'SN-032')
    def test_replacement_has_exact_baseline_precondition(self):
        original = next(t for t in self.base['tasks'] if t['id'] == 'SN-032')
        self.assertEqual(self.change.get('expected_interfaces_consumes'), original['interfaces']['consumes'])
        self.assertEqual([c['task'] for c in self.change.get('interfaces_consumes', [])], self.change['depends_on'])
    def test_contract_edges_are_acyclic_not_only_depends_on(self):
        self.schema.validate(self.r); effective = compose_fixture(self.base, self.r); check_graph(effective, True)
        self.assertNotIn('SN-031', [c['task'] for c in effective['SN-032']['interfaces']['consumes']])
    def test_removed_contract_override_reproduces_semantic_cycle(self):
        self.change.pop('interfaces_consumes', None); self.change.pop('expected_interfaces_consumes', None)
        tasks = compose_fixture(self.base, self.r); check_graph(tasks, False)
        with self.assertRaisesRegex(ValueError, 'contract_cycle'): check_graph(tasks, True)
    def test_schema_requires_both_contract_fields(self):
        self.change.pop('interfaces_consumes', None); self.change.pop('expected_interfaces_consumes', None)
        self.assertTrue(list(self.schema.iter_errors(self.r)))
    def test_changed_baseline_contract_is_rejected(self):
        task = next(t for t in self.base['tasks'] if t['id'] == 'SN-032')
        task['interfaces']['consumes'][-1]['contract'] = 'different input obligation'
        with self.assertRaisesRegex(ValueError, 'consumes_precondition_mismatch'): compose_fixture(self.base, self.r)
    def test_no_other_baseline_field_changes(self):
        effective = compose_fixture(self.base, self.r)
        for task in self.base['tasks']:
            result = copy.deepcopy(effective[task['id']]); result['depends_on'] = task['depends_on']
            result['interfaces']['consumes'] = task['interfaces']['consumes']; self.assertEqual(result, task)
    def test_final_acceptance_keeps_complete_mcp(self):
        graph = check_graph(compose_fixture(self.base, self.r))
        def dependencies(k):
            seen=set(); todo=list(graph[k])
            while todo:
                x=todo.pop()
                if x not in seen: seen.add(x);todo.extend(graph[x])
            return seen
        children = {x['id'] for x in self.r['tasks']}
        for k in ('SN-042', 'SN-043', 'SN-044'): self.assertTrue(children.issubset(dependencies(k)))
    def test_unknown_override_field_is_rejected(self):
        self.change['silently_ignored_input'] = 'SN-031'
        self.assertTrue(list(self.schema.iter_errors(self.r)))
    def test_each_consumed_task_is_a_prerequisite(self):
        tasks=compose_fixture(self.base,self.r)
        for task in tasks.values():
            seen=set();queue=list(task['depends_on'])
            while queue:
                item=queue.pop()
                if item not in seen: seen.add(item);queue.extend(tasks[item]['depends_on'])
            self.assertTrue({x['task'] for x in task.get('interfaces',{}).get('consumes',[])}.issubset(seen))
    def test_revision_is_consistent(self):
        self.assertEqual(self.r['revision'],self.schema.schema['properties']['revision']['const'])
        self.assertIn(self.r['revision'],(ROOT/'PROJECT_RULES.md').read_text())
    def test_source_composition_hashes_match_delta(self):
        index = load('planning/spec-index.json')
        for collection in ('task_refinements', 'implementation_plans'):
            for item in index[collection]:
                self.assertEqual(hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest(), item['sha256'])
                if 'schema' in item: self.assertEqual(hashlib.sha256((ROOT/item['schema']).read_bytes()).hexdigest(), item['schema_sha256'])
if __name__ == '__main__': unittest.main()
