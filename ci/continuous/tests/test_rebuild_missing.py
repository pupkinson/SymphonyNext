"""Rebuild lost preparation images while preserving historical evidence."""
import copy
import fcntl
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, canonical, sha256
import test_refresh as fixtures

HEAD = 'a' * 40
SEED = 'sha256:a93a7c8e7a2d292c924f461d06a27986b1a95818c1be1fbb5b68b290b409256c'
LOST = {
    'main': 'sha256:b6ef7528c8e8435208c0856698d50158e545c2e4fc7624ca6bda49f585a392c0',
    'sn004': 'sha256:9233988cb5fbbf405a565fc1d0bb92e9296e189b90f3381c50221463801a1172',
}
NEW = {'main': 'sha256:' + '1' * 64, 'sn004': 'sha256:' + '2' * 64}
LAYERS = ['sha256:' + '3' * 64]


class RebuildMissingTests(unittest.TestCase):
    def setUp(self):
        try:
            self.recovery = importlib.import_module('snci.rebuild_missing')
        except ImportError:
            self.fail('missing-image recovery is not implemented')
        self.f = fixtures.RefreshTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.r = self.f.r
        self.real_preflight = self.r.preflight
        self.profiles = [dict(p, image=LOST[p['name']]) for p in self.f.profiles]
        self.seed = {'id': SEED, 'reference': 'localhost/symphony-next-ci-seed:' + SEED.split(':')[1],
                     'layers': LAYERS}
        for name in LOST:
            root = self.f.state / ('prepare-' + name)
            root.mkdir()
            (root / 'seed.json').write_bytes(canonical(self.seed))
        self.images = {SEED: {'Id': SEED, 'RootFS': {'Type': 'layers', 'Layers': LAYERS}},
                       self.seed['reference']: {'Id': SEED, 'RootFS': {'Type': 'layers', 'Layers': LAYERS}}}
        self.events = []
        self.owner = importlib.import_module('owner')
        self.o = types.SimpleNamespace(SEED=SEED, inspect_image=self.inspect,
                                      image_layers=self.owner.image_layers, runner=self.owner.runner,
                                      build_dependency_image=self.build, verify_seed_build=self.verify_seed,
                                      run=self.docker_run)

    def inspect(self, image, missing_ok=False):
        if image in self.images:
            return self.images[image]
        if missing_ok:
            return None
        raise Hold('local_image_inspect_failed')

    def docker_run(self, args, **kwargs):
        if args[:4] == self.owner.runner.DOCKER + ['image', 'tag']:
            self.images[args[-1]] = copy.deepcopy(self.images[args[-2]])
            self.events.append(('tag', args[-2]))
            return types.SimpleNamespace(stdout=b'')
        raise AssertionError('unexpected external command: ' + str(args))

    def build(self, root):
        name = root.name
        self.assertEqual((root / 'Dependency.Dockerfile').read_bytes(), b'fixture recipe')
        self.assertEqual((root / '.dockerignore').read_bytes(), b'*\n!Dependency.Dockerfile\n!source\n!source/**\n')
        self.assertTrue((root / 'source').is_dir())
        image = NEW[name]
        (root / 'seed.json').write_bytes(canonical(self.seed))
        (root / 'image.id').write_text(image)
        self.images[image] = {'Id': image, 'RootFS': {'Type': 'layers', 'Layers': LAYERS + ['sha256:' + '4' * 64]}}
        self.events.append(('build', name))
        return image

    def verify_seed(self, seed, image):
        self.assertEqual(seed, self.seed)
        actual = self.inspect(image)
        if actual['RootFS']['Layers'][:len(LAYERS)] != LAYERS:
            raise Hold('built_image_seed_layers')

    def snapshot(self):
        return dict(self.recovery.preflight(self.o, HEAD, self.profiles), recipe=b'fixture recipe')

    def flow(self):
        f = self.f
        f.profiles = self.profiles
        f.flow()
        f.snapshot.update(self.snapshot())
        def preflight(owner, head, api, source, rebuild=False):
            self.assertTrue(rebuild)
            return f.snapshot
        def recheck(owner, snapshot, api, source, rebuild=False):
            self.assertTrue(rebuild)
            self.assertEqual(f.o.load_policy(), f.policy)
        for name, implementation in [('preflight', preflight), ('recheck', recheck)]:
            mock = patch.object(self.r, name, side_effect=implementation)
            mock.start()
            self.addCleanup(mock.stop)
        for name in ('inspect_image', 'build_dependency_image', 'verify_seed_build', 'run', 'image_layers', 'SEED', 'runner'):
            setattr(f.o, name, getattr(self.o, name))
        native = f.native_run
        def verify(root, profile, *args):
            self.assertEqual(profile['image'], NEW[profile['name']])
            self.assertEqual(self.images[self.recovery.image_tag(HEAD, profile['name'])]['Id'], profile['image'])
            self.assertEqual(f.o.load_policy(), f.policy)
            self.events.append(('quality', profile['name']))
            return native(root, profile, *args)
        mock = patch.object(self.r, 'native_quality', side_effect=verify)
        mock.start()
        self.addCleanup(mock.stop)

    def test_only_exact_two_lost_images_are_eligible(self):
        self.snapshot()
        changed = [dict(self.profiles[0], image=NEW['main']), self.profiles[1]]
        with self.assertRaisesRegex(Hold, 'lost_image_binding'):
            self.recovery.preflight(self.o, HEAD, changed)
        self.images[LOST['main']] = {'Id': LOST['main']}
        with self.assertRaisesRegex(Hold, 'image_not_missing'):
            self.recovery.preflight(self.o, HEAD, self.profiles)

    def test_docker_failure_is_not_treated_as_a_missing_image(self):
        self.o.inspect_image = lambda *a, **k: (_ for _ in ()).throw(Hold('local_image_inspect_failed'))
        with self.assertRaisesRegex(Hold, 'local_image_inspect_failed'):
            self.snapshot()
        self.assertEqual(self.events, [])

    def test_seed_and_both_historical_layer_receipts_must_match(self):
        self.snapshot()
        path = self.f.state / 'prepare-sn004/seed.json'
        path.write_bytes(canonical(dict(self.seed, layers=['sha256:' + '0' * 64])))
        with self.assertRaisesRegex(Hold, 'seed_receipt'):
            self.snapshot()
        path.write_bytes(canonical(self.seed))
        self.images[SEED]['RootFS']['Layers'] = ['sha256:' + '0' * 64]
        with self.assertRaises(Hold):
            self.snapshot()

    def test_missing_seed_holds_before_any_build(self):
        del self.images[SEED]
        with self.assertRaises(Hold):
            self.snapshot()
        self.assertEqual(self.events, [])

    def test_existing_output_tag_holds_before_build_or_overwrite(self):
        tag = self.recovery.image_tag(HEAD, 'main')
        self.images[tag] = {'Id': NEW['sn004']}
        with self.assertRaisesRegex(Hold, 'tag_exists'):
            self.snapshot()
        self.assertEqual(self.images[tag]['Id'], NEW['sn004'])
        self.assertEqual(self.events, [])

    def test_rebuild_publishes_both_new_receipts_once_and_keeps_history(self):
        self.flow()
        f = self.f
        result = self.r.perform(f.o, HEAD, f.api, f.source, rebuild=True)
        policy = f.o.load_policy()
        self.assertFalse(policy['enabled'])
        self.assertEqual(policy['installed_revision'], HEAD)
        self.assertEqual(len(f.published), 1)
        self.assertEqual(self.events, [('build', 'main'), ('tag', NEW['main']), ('quality', 'main'),
                                       ('build', 'sn004'), ('tag', NEW['sn004']), ('quality', 'sn004')])
        for p in policy['profiles']:
            self.assertEqual(p['image'], NEW[p['name']])
            self.r.read_acceptance(f.state, p, fixtures.CODEX, fixtures.NOW)
            self.assertEqual((f.state / ('prepare-' + p['name']) / 'acceptance.json').read_bytes(), f.historical[p['name']])
        self.r.completed_refresh(f.state, policy, f.policy_path.read_bytes())
        self.assertEqual(json.loads(result.read_bytes())['status'], 'REFRESHED_DISABLED')

    def test_second_build_failure_retains_first_image_and_uncommitted_policy(self):
        self.flow()
        f = self.f
        build = f.o.build_dependency_image
        def fail(root):
            if root.name == 'sn004':
                raise Hold('synthetic_build_failure')
            return build(root)
        f.o.build_dependency_image = fail
        with self.assertRaisesRegex(Hold, 'synthetic_build_failure'):
            self.r.perform(f.o, HEAD, f.api, f.source, rebuild=True)
        self.assertEqual(f.o.load_policy(), f.policy)
        self.assertEqual((f.install / 'revision').read_text(), self.r.BASE)
        self.assertEqual(self.images[self.recovery.image_tag(HEAD, 'main')]['Id'], NEW['main'])
        before = list(self.events)
        with self.assertRaisesRegex(Hold, 'already_claimed'):
            self.r.perform(f.o, HEAD, f.api, f.source, rebuild=True)
        self.assertEqual(self.events, before)

    def test_second_quality_failure_does_not_publish_either_profile(self):
        self.flow()
        f = self.f
        def fail(root, profile, *args):
            if profile['name'] == 'sn004':
                raise Hold('synthetic_quality_failure')
            return f.native_run(root, profile, *args)
        with patch.object(self.r, 'native_quality', side_effect=fail), self.assertRaises(Hold):
            self.r.perform(f.o, HEAD, f.api, f.source, rebuild=True)
        self.assertEqual(f.o.load_policy(), f.policy)
        self.assertEqual(f.published, [])
        self.assertFalse((f.state / ('refresh-' + HEAD) / 'commit-intent.json').exists())

    def test_seed_drift_after_build_prevents_policy_publication(self):
        self.flow()
        f = self.f
        native = f.native_run
        def drift(root, profile, *args):
            result = native(root, profile, *args)
            if profile['name'] == 'sn004':
                self.images[SEED]['RootFS']['Layers'] = ['sha256:' + '0' * 64]
            return result
        with patch.object(self.r, 'native_quality', side_effect=drift), self.assertRaises(Hold):
            self.r.perform(f.o, HEAD, f.api, f.source, rebuild=True)
        self.assertEqual(f.o.load_policy(), f.policy)
        self.assertEqual((f.install / 'revision').read_text(), self.r.BASE)

    def test_tag_or_image_receipt_drift_cannot_commit(self):
        self.flow()
        f = self.f
        native = f.native_run
        def drift(root, profile, *args):
            result = native(root, profile, *args)
            if profile['name'] == 'sn004':
                (root / 'image.id').write_text(NEW['main'])
            return result
        with patch.object(self.r, 'native_quality', side_effect=drift), self.assertRaises(Hold):
            self.r.perform(f.o, HEAD, f.api, f.source, rebuild=True)
        self.assertEqual(f.o.load_policy(), f.policy)

    def test_unrelated_source_changes_cannot_enter_recovery_package(self):
        old = {'ci/continuous/owner.py': {'sha': '0' * 40, 'mode': '100644'}}
        reviewed = {p: {'sha': '1' * 40, 'mode': '100644'} for p in self.r.DELTA}
        new = dict(reviewed, **{p: {'sha': '2' * 40, 'mode': '100644'} for p in self.recovery.DELTA})
        self.recovery.package(old, reviewed, new)
        for path in ('ci/continuous/owner.py', 'ci/continuous/Dependency.Dockerfile', 'elixir/mix.exs'):
            changed = dict(new, **{path: {'sha': '3' * 40, 'mode': '100644'}})
            with self.subTest(path=path), self.assertRaises(Hold):
                self.recovery.package(old, reviewed, changed)

    def test_rebuild_history_must_reach_accepted_refresh_source(self):
        commits = {HEAD: {'sha': HEAD, 'parents': [{'sha': self.r.BASE}], 'tree': {'sha': 'f' * 40}}}
        api = types.SimpleNamespace(request=lambda method, url: commits[url.rsplit('/', 1)[1]])
        with self.assertRaises(Hold):
            self.r.reviewed_commit(api, HEAD, base=self.recovery.SOURCE_BASE)
        commits[HEAD]['parents'] = [{'sha': self.recovery.SOURCE_BASE}]
        self.assertEqual(self.r.reviewed_commit(api, HEAD, base=self.recovery.SOURCE_BASE), commits[HEAD])

    def test_cli_requires_owner_before_touching_native_or_policy(self):
        with patch.object(self.r.os, 'geteuid', return_value=997), self.assertRaisesRegex(Hold, 'owner_identity'):
            self.r.apply(HEAD, rebuild=True)

    def test_shared_lock_serializes_supported_refresh_and_rebuild_writers(self):
        lock_path = self.f.state / 'controller.lock'
        def git(args, **kwargs):
            if args == ['git', 'rev-parse', 'HEAD']:
                return types.SimpleNamespace(stdout=HEAD.encode())
            if args == ['git', 'status', '--porcelain', '--untracked-files=all']:
                return types.SimpleNamespace(stdout=b'')
            raise AssertionError(args)
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(self.r.os, 'geteuid', return_value=0), \
                    patch.object(self.r.os, 'uname', return_value=types.SimpleNamespace(nodename='1c-db')), \
                    patch.object(self.owner, 'run', side_effect=git):
                for rebuild in (False, True):
                    with self.subTest(rebuild=rebuild), self.assertRaisesRegex(Hold, 'controller_busy'):
                        self.r.apply(HEAD, rebuild=rebuild)
        self.assertEqual(self.events, [])

    def test_external_writer_ignoring_lock_can_race_docker_tag_outside_contract(self):
        # Characterization of Docker's non-CAS boundary, not a no-overwrite guarantee.
        snapshot = self.snapshot()
        root = self.f.state / 'external-race-fixture' / 'main'
        (root / 'source').mkdir(parents=True)
        tag = self.recovery.image_tag(HEAD, 'main')
        conflicts = []
        def external_writer(args, **kwargs):
            self.images[tag] = {'Id': NEW['sn004']}
            conflicts.append(self.images[tag]['Id'])
            return self.docker_run(args, **kwargs)
        self.o.run = external_writer
        profile = self.recovery.build(self.o, root, self.profiles[0], snapshot, HEAD)
        self.assertEqual(conflicts, [NEW['sn004']])
        self.assertEqual(self.images[tag]['Id'], NEW['main'])
        self.assertEqual(profile['image'], NEW['main'])

    def test_complete_preflight_wires_source_installation_history_and_missing_guards(self):
        f = self.f
        f.profiles = self.profiles
        f.flow()
        binary = f.root / 'codex'
        binary.write_bytes(b'fixture native binary')
        f.o.BINARY = str(binary)
        f.o.BINARY_SHA = sha256(binary.read_bytes())
        f.policy.update(codex_binary=str(binary), codex_sha256=f.o.BINARY_SHA)
        f.policy_path.write_bytes(canonical(f.policy))
        for name in LOST:
            path = f.state / ('prepare-' + name) / 'acceptance.json'
            receipt = json.loads(path.read_bytes())
            receipt['codex_sha256'] = f.o.BINARY_SHA
            path.write_bytes(canonical(receipt))
            (path.parent / 'image.id').write_text(LOST[name])
        f.o.inspect_image = self.inspect
        f.o.image_layers = self.owner.image_layers
        f.o.SEED = SEED
        old = {}
        manifest = {}
        for name in ('profiles.json', 'worker.py', 'Dependency.Dockerfile'):
            raw = (f.install / name).read_bytes()
            old['ci/continuous/' + name] = dict(sha=blob_hash(raw), size=len(raw), mode='100644')
            manifest[name] = sha256(raw)
        (f.install / 'installed.json').write_bytes(canonical(manifest))
        reviewed = dict(old, **{p: {'sha': '1' * 40, 'size': 1, 'mode': '100644'} for p in self.r.DELTA})
        candidate = dict(reviewed, **{p: {'sha': '2' * 40, 'size': 2, 'mode': '100644'} for p in self.recovery.DELTA})
        def request(method, url):
            if url.endswith('/git/commits/' + HEAD):
                return dict(sha=HEAD, parents=[{'sha': self.recovery.SOURCE_BASE}], tree={'sha': 'f' * 40})
            if url.endswith('/rulesets/23980199'):
                return {}
            raise AssertionError(url)
        trees = {self.r.BASE: ('0' * 40, old), self.recovery.SOURCE_BASE: (self.recovery.SOURCE_TREE, reviewed),
                 HEAD: ('f' * 40, candidate)}
        api = types.SimpleNamespace(request=request)
        source = types.SimpleNamespace(tree=lambda sha: trees[sha])
        with patch.object(self.r, 'stopped'), patch.object(self.r, 'idle_native'), patch.object(self.r, 'validate_rules'):
            result = self.real_preflight(f.o, HEAD, api, source, rebuild=True)
            self.assertEqual(result['seed'], self.seed)
            self.assertEqual(result['targets'][1]['head'], '21ce4282e7ef8330cc1155bcb7b94fbf132032a8')
            self.images[LOST['sn004']] = {'Id': LOST['sn004']}
            with self.assertRaisesRegex(Hold, 'image_not_missing'):
                self.real_preflight(f.o, HEAD, api, source, rebuild=True)
            del self.images[LOST['sn004']]
            (f.install / 'worker.py').write_bytes(b'tampered')
            with self.assertRaisesRegex(Hold, 'installed_changed'):
                self.real_preflight(f.o, HEAD, api, source, rebuild=True)


if __name__ == '__main__':
    unittest.main()
