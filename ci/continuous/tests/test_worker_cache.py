"""Exercise actual worker setup against disposable source and cache files."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import worker
from snci import runner


class ReachedIsolation(Exception):pass


class WorkerCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name);self.root=self.path/'work/source'
        self.seed=self.path/'seed';self.input=self.path/'input'
        for p in ('input/elixir/priv','seed/home','seed/source/elixir/deps',
                  'work','usr/lib/postgresql/fixture/bin'):
            (self.path/p).mkdir(parents=True,exist_ok=True)
        (self.path/'usr/lib/postgresql/fixture/bin/initdb').write_bytes(b'fixture')
        (self.input/'elixir/mix.lock').write_bytes(b'locked dependency fixture')
        (self.input/'elixir/priv/tracked.txt').write_bytes(b'tracked source')
        for p in self.input.rglob('*'):
            if p.is_file():p.chmod(0o644)
        (self.seed/'lock.sha256').write_text(hashlib.sha256((self.input/'elixir/mix.lock').read_bytes()).hexdigest())
        entries={p.relative_to(self.input).as_posix():dict(sha=worker.git_hash(p.read_bytes()),mode='100644')
                 for p in self.input.rglob('*') if p.is_file()}
        (self.path/'source.json').write_text(json.dumps(entries))
        self.before={p.relative_to(self.input).as_posix():p.read_bytes() for p in self.input.rglob('*') if p.is_file()}
        original_path=Path;original_copy=shutil.copytree
        def mapped(value):
            value=os.fspath(value)
            if value.startswith(('/seed/','/work/','/usr/lib/postgresql')) or value in ('/input','/source.json'):
                return self.path/value.lstrip('/')
            return original_path(value)
        def copy(source,dest,*args,**kw):return original_copy(mapped(source),mapped(dest),*args,**kw)
        for name,value in [('ROOT',self.root),('Path',mapped)]:
            p=patch.object(worker,name,value);p.start();self.addCleanup(p.stop)
        p=patch.object(worker.shutil,'copytree',side_effect=copy);p.start();self.addCleanup(p.stop)
        p=patch.object(worker.os,'getuid',return_value=0);p.start();self.addCleanup(p.stop)
        p=patch.object(worker.os,'chown');p.start();self.addCleanup(p.stop)
        p=patch.object(worker,'stage',side_effect=ReachedIsolation);self.stage=p.start();self.addCleanup(p.stop)

    def cache(self,application=True):
        build=self.seed/'source/elixir/_build'
        (self.seed/'source/elixir/priv').mkdir(exist_ok=True)
        (self.seed/'source/elixir/priv/static.txt').write_bytes(b'valid seed priv')
        for env in ('dev','test'):
            directory=build/env
            (directory/'lib/dependency/ebin').mkdir(parents=True)
            (directory/'lib/dependency/ebin/dep.beam').write_bytes(b'dependency beam')
            (directory/'dependency-target').write_bytes(b'dependency link bytes')
            (directory/'lib/dependency/valid-link').symlink_to('../../dependency-target')
            (directory/'project.plt').write_bytes(b'project PLT')
            (directory/'project.plt.hash').write_bytes(b'project PLT hash')
            # Same application name outside the exact excluded roots stays.
            (directory/'retained/symphony_elixir').mkdir(parents=True)
            (directory/'retained/symphony_elixir/data').write_bytes(b'keep this')
            if application:
                (directory/'lib/symphony_elixir').mkdir(parents=True)
                (directory/'lib/symphony_elixir/app.beam').write_bytes(b'stale app')
                (directory/'lib/symphony_elixir/priv').symlink_to('../../../../priv')
                (directory/'phoenix-colocated/symphony_elixir').mkdir(parents=True)
                (directory/'phoenix-colocated/symphony_elixir/node_modules').symlink_to('../../../../assets/node_modules')
        return build

    def test_own_application_excluded_before_dereference_and_other_bytes_unchanged(self):
        build=self.cache()
        before={p.relative_to(build).as_posix():p.read_bytes() for p in build.rglob('*') if p.is_file() and not p.is_symlink()}
        with self.assertRaises(ReachedIsolation):worker.main()
        for env in ('dev','test'):
            output=self.root/'elixir/_build'/env
            self.assertFalse((output/'lib/symphony_elixir').exists())
            self.assertFalse((output/'phoenix-colocated/symphony_elixir').exists())
            self.assertEqual((output/'lib/dependency/valid-link').read_bytes(),b'dependency link bytes')
            self.assertFalse((output/'lib/dependency/valid-link').is_symlink())
        for name,raw in before.items():
            if '/lib/symphony_elixir/' not in '/'+name and '/phoenix-colocated/symphony_elixir/' not in '/'+name:
                self.assertEqual((self.root/'elixir/_build'/name).read_bytes(),raw,name)
        for name,raw in self.before.items():self.assertEqual((self.root/name).read_bytes(),raw,name)

    def test_broken_dependency_link_still_fails_closed(self):
        build=self.cache(application=False)
        (build/'dev/lib/dependency/missing').symlink_to('PRIVATE_DEPENDENCY_TARGET')
        with self.assertRaises(shutil.Error):worker.main()
        self.stage.assert_not_called()

    def diagnostic(self):
        output=io.StringIO()
        with redirect_stdout(output):self.assertEqual(worker.run_main(),1)
        text=output.getvalue();self.assertNotIn('PRIVATE_',text)
        lines=[line for line in text.splitlines() if line.startswith('SNCI_FAILURE ')]
        self.assertEqual(len(lines),1);self.assertNotIn('SNCI_RESULT ',text)
        return json.loads(lines[0][len('SNCI_FAILURE '):]),text.encode()

    def test_build_cache_failure_identifies_closed_setup_step_without_paths(self):
        build=self.cache(application=False)
        (build/'dev/lib/dependency/missing').symlink_to('PRIVATE_CACHE_SECRET')
        details,logs=self.diagnostic()
        self.assertEqual(details['setup_step'],'build_cache')
        self.assertEqual(details['kind'],'io_error')
        self.assertEqual(runner.failure_code(logs),'worker_io_error_setup_build_cache')
        self.stage.assert_not_called()

    def test_home_cache_failure_is_distinct_from_build_cache_without_paths(self):
        (self.seed/'home/missing').symlink_to('PRIVATE_HOME_SECRET')
        details,logs=self.diagnostic()
        self.assertEqual(details['setup_step'],'home_cache')
        self.assertEqual(runner.failure_code(logs),'worker_io_error_setup_home_cache')
        self.stage.assert_not_called()

    def tearDown(self):
        if hasattr(worker,'SETUP_STEP'):worker.SETUP_STEP=None


if __name__=='__main__':unittest.main()
