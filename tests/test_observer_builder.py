"""Build-only contract. Native launcher integration is certified with the pinned input."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuilderTests(unittest.TestCase):
    def setUp(self):
        path=ROOT/'bootstrap/build_observer_candidate.py'
        self.assertTrue(path.exists(), 'build-only integration is not implemented')
        spec=importlib.util.spec_from_file_location('observer_builder',path)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def test_rejects_unpinned_input(self):
        with self.assertRaises(ValueError): self.m.build_candidate(b'print("no")\n')

    def test_builder_does_not_import_or_execute_supplied_launcher(self):
        import ast
        tree=ast.parse((ROOT/'bootstrap/build_observer_candidate.py').read_text())
        forbidden={'exec','eval','__import__'}
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                            and n.func.id in forbidden for n in ast.walk(tree)))

    def test_output_never_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'candidate.py';p.write_text('keep')
            with self.assertRaises(FileExistsError): self.m.write_new(p,b'new')
            self.assertEqual(p.read_text(),'keep')

    def test_parent_traversal_cannot_target_host_installation(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'invalid-source';source.write_bytes(b'not a launcher')
            with self.assertRaisesRegex(ValueError, 'host_install_target_refused'):
                self.m.main(['--source',str(source),'--out','/tmp/../etc/observer-candidate.py'])

    def test_no_host_mutation_cli(self):
        with self.assertRaises(SystemExit): self.m.main(['launch'])


if __name__=='__main__':unittest.main()
