import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import owner
from snci.common import Hold

LAYER = 'sha256:' + 'a' * 64
OTHER = 'sha256:' + 'b' * 64
BUILT = 'sha256:' + 'c' * 64
REF = 'localhost/symphony-next-ci-seed:' + owner.SEED.split(':')[1]
SEED_INFO = {'Id': owner.SEED, 'RootFS': {'Type': 'layers', 'Layers': [LAYER]}}


class LocalSeedTests(unittest.TestCase):
    def test_missing_local_tag_is_created_from_exact_image_id(self):
        def inspect(reference, missing_ok=False):
            if reference == REF and len(inspected) == 1:
                inspected.append(reference)
                return None
            inspected.append(reference)
            return copy.deepcopy(SEED_INFO)
        inspected = []
        with patch.object(owner, 'inspect_image', side_effect=inspect), patch.object(owner, 'run') as run:
            run.return_value.stdout = b'Name: default\nDriver: docker\nNodes:\n'
            seed = owner.prepare_seed()
        self.assertEqual(seed['reference'], REF)
        self.assertEqual(seed['id'], owner.SEED)
        self.assertEqual(seed['layers'], [LAYER])
        self.assertEqual([c.args[0] for c in run.call_args_list if 'tag' in c.args[0]],
                         [owner.runner.DOCKER + ['image', 'tag', owner.SEED, REF]])

    def test_existing_correct_tag_causes_no_write(self):
        with patch.object(owner, 'inspect_image', return_value=SEED_INFO), patch.object(owner, 'run') as run:
            run.return_value.stdout = b'Name: default\nDriver: docker\nNodes:\n'
            owner.prepare_seed()
        self.assertFalse(any('tag' in c.args[0] for c in run.call_args_list))

    def test_existing_foreign_tag_is_not_overwritten(self):
        with patch.object(owner, 'inspect_image', side_effect=[SEED_INFO, dict(SEED_INFO, Id=OTHER)]), patch.object(owner, 'run') as run:
            run.return_value.stdout = b'Name: default\nDriver: docker\nNodes:\n'
            with self.assertRaises(Hold): owner.prepare_seed()
        self.assertFalse(any('tag' in c.args[0] for c in run.call_args_list))

    def test_different_builder_driver_holds_before_tagging(self):
        with patch.object(owner, 'run') as run:
            run.return_value.stdout = b'Name: default\nDriver: docker-container\nNodes:\n'
            with self.assertRaises(Hold): owner.prepare_seed()
        self.assertFalse(any('tag' in c.args[0] for c in run.call_args_list))

    def test_missing_seed_is_not_pulled_or_replaced(self):
        with patch.object(owner, 'run') as run, patch.object(owner, 'inspect_image', return_value=None):
            run.return_value.stdout = b'Name: default\nDriver: docker\nNodes:\n'
            with self.assertRaises(Hold): owner.prepare_seed()
        self.assertFalse(any('tag' in c.args[0] or 'pull' in c.args[0] for c in run.call_args_list))

    def test_inspect_transport_error_is_not_treated_as_missing_image(self):
        error = subprocess.CompletedProcess([], 1, b'', b'Cannot connect to the Docker daemon')
        with patch.object(owner, 'run', side_effect=subprocess.CalledProcessError(1, [], stderr=error.stderr)):
            with self.assertRaises(Hold): owner.inspect_image(REF, missing_ok=True)

    def test_expected_missing_image_error_can_return_none(self):
        error = subprocess.CalledProcessError(1, [], output=b'', stderr=('Error response from daemon: No such image: ' + REF + '\n').encode())
        with patch.object(owner, 'run', side_effect=error):
            self.assertIsNone(owner.inspect_image(REF, missing_ok=True))

    def test_changed_tag_after_build_holds(self):
        seed = {'reference': REF, 'id': owner.SEED, 'layers': [LAYER]}
        with patch.object(owner, 'inspect_image', return_value=dict(SEED_INFO, Id=OTHER)):
            with self.assertRaises(Hold): owner.verify_seed_build(seed, BUILT)

    def test_built_image_requires_exact_seed_layers(self):
        seed = {'reference': REF, 'id': owner.SEED, 'layers': [LAYER]}
        built = {'Id': BUILT, 'RootFS': {'Type': 'layers', 'Layers': [OTHER]}}
        with patch.object(owner, 'inspect_image', side_effect=[SEED_INFO, built]):
            with self.assertRaises(Hold): owner.verify_seed_build(seed, BUILT)

    def test_valid_build_retains_seed_and_uses_local_reference(self):
        seed = {'reference': REF, 'id': owner.SEED, 'layers': [LAYER]}
        built = {'Id': BUILT, 'RootFS': {'Type': 'layers', 'Layers': [LAYER, OTHER]}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def run(args, **kwargs):
                self.assertIn('--builder=default', args)
                self.assertIn('--pull=false', args)
                self.assertIn('BASE_IMAGE=' + REF, args)
                self.assertNotIn('BASE_IMAGE=' + owner.SEED, args)
                (root / 'image.id').write_text(BUILT + '\n')
            with patch.object(owner, 'prepare_seed', return_value=seed), patch.object(owner, 'run', side_effect=run), patch.object(owner, 'inspect_image', side_effect=[SEED_INFO, built]):
                self.assertEqual(owner.build_dependency_image(root), BUILT)
            self.assertTrue((root / 'seed.json').is_file())


if __name__ == '__main__': unittest.main()
