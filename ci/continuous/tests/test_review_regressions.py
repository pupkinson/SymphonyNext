from pathlib import Path
import os
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, blob_hash, write_new
from snci.source import Source, select_profile

class ReviewRegressions(unittest.TestCase):
    def test_private_umask_does_not_change_explicit_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=os.umask(0o077)
            try:
                public=Path(tmp)/'public';private=Path(tmp)/'private'
                write_new(public,b'x',0o644);write_new(private,b'y')
                self.assertEqual(public.stat().st_mode&0o777,0o644)
                self.assertEqual(private.stat().st_mode&0o777,0o600)
                raw=b'fixture';entries={'a/b/c':{'sha':blob_hash(raw),'size':len(raw),'mode':'100755'}}
                source=object.__new__(Source);source.blob=lambda _:raw
                source.materialize(entries,Path(tmp)/'source')
                for suffix in ('','/a','/a/b'):
                    self.assertEqual(Path(tmp+'/source'+suffix).stat().st_mode&0o777,0o755)
                self.assertEqual(Path(tmp+'/source/a/b/c').stat().st_mode&0o777,0o755)
            finally:os.umask(old)
    def test_new_quality_control_files_require_new_profile(self):
        entries={'elixir/mix.exs':{'sha':'a'*40}}
        policy={'profiles':[{'name':'baseline','locked':{'elixir/mix.exs':'a'*40}}]}
        self.assertEqual(select_profile(entries,policy)['name'],'baseline')
        for path in ('elixir/.credo.exs','elixir/config/.credo.exs','.credo.exs',
                     'elixir/config/runtime.exs','elixir/lib/mix/tasks/test.ex'):
            with self.subTest(path=path),self.assertRaises(Hold):
                select_profile(dict(entries,**{path:{'sha':'b'*40}}),policy)
        self.assertEqual(select_profile(dict(entries,**{'elixir/test/new_test.exs':{'sha':'b'*40}}),policy)['name'],'baseline')

class ActualProfileTrees(unittest.TestCase):
    def test_real_profiles_fit_after_exact_inert_asset_omission(self):
        import json
        from snci.source import parse_tree, OMITTED_BLOBS
        trees=json.loads(Path(__file__).with_name('profile-trees.json').read_text())
        for name,tree in trees.items():
            with self.subTest(profile=name):
                entries=parse_tree(tree,tree['sha'],OMITTED_BLOBS)
                profiles=json.loads(Path(__file__).resolve().parents[1].joinpath('profiles.json').read_text())
                self.assertEqual(select_profile(entries,{'profiles':list(profiles.values())})['name'],name)
                self.assertNotIn('.github/media/symphony-demo.mp4',entries)
                self.assertLess(sum(e['size'] for e in entries.values()),16*1024*1024)

    def test_asset_change_deletion_and_other_large_file_hold(self):
        import copy,json
        from snci.source import parse_tree, OMITTED_BLOBS
        baseline=json.loads(Path(__file__).with_name('profile-trees.json').read_text())['main']
        name='.github/media/symphony-demo.mp4'
        for mutation in ('changed','deleted','new'):
            tree=copy.deepcopy(baseline)
            asset=next(e for e in tree['tree'] if e['path']==name)
            if mutation=='changed':asset['sha']='a'*40
            elif mutation=='deleted':tree['tree'].remove(asset)
            else:tree['tree'].append(dict(asset,path='.github/media/new.mp4'))
            with self.subTest(mutation=mutation),self.assertRaises(Hold):
                parse_tree(tree,tree['sha'],OMITTED_BLOBS)

if __name__=='__main__':unittest.main()
