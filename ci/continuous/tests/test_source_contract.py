"""Added/deleted source versions and fatal denials must stay distinguishable."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, canonical, decode, sha256
from snci.reviewer import ReadOnlyContext, handle_request, thread_params, validate_verdict

T={'pr':1,'head':'a'*40,'base':'b'*40,'tree':'c'*40}


class Source:
    def __init__(self):self.reads=[]
    def blob(self,entry):self.reads.append(entry);return entry['data']


class SourceContractTests(unittest.TestCase):
    def setUp(self):
        self.source=Source()
        self.ctx=ReadOnlyContext(self.source,
            {'added.txt':{'data':b'added'},'same.txt':{'data':b'new'}},
            {'deleted.txt':{'data':b'deleted'},'same.txt':{'data':b'old'}},
            ['added.txt','deleted.txt','same.txt'])

    def call(self,path,revision):
        return handle_request({'id':7,'method':'item/tool/call','params':{
            'threadId':'t','namespace':'snci_source','tool':'read_source',
            'arguments':{'page':0,'path':path,'revision':revision}}},self.ctx,'t')

    def test_added_base_and_deleted_head_are_explicit_nonfatal_misses(self):
        for path,revision,available in [('added.txt','base',['head']),('deleted.txt','head',['base'])]:
            result=self.call(path,revision)
            self.assertIs(result['success'],False)
            self.assertEqual(decode(result['contentItems'][0]['text']),{
                'status':'missing_revision','path':path,'revision':revision,'available_revisions':available})
        self.assertEqual(self.ctx.calls,2)
        self.assertEqual(self.source.reads,[])
        self.assertEqual(self.ctx.seen,set())
        self.assertEqual(self.ctx.bytes,0)
        self.assertFalse(self.ctx.complete())

    def test_missing_versions_do_not_replace_real_source_coverage(self):
        self.call('added.txt','base');self.call('deleted.txt','head')
        verdict=dict(T,verdict='READY',findings=[],limitations=[])
        with self.assertRaisesRegex(Hold,'review_incomplete_source'):validate_verdict(verdict,T,self.ctx)
        for path,revision in [('added.txt','head'),('deleted.txt','base'),('same.txt','head'),('same.txt','base')]:
            self.assertTrue(self.call(path,revision)['success'])
        self.assertEqual(validate_verdict(verdict,T,self.ctx)['verdict'],'READY')
        self.assertEqual(self.ctx.reads,4)
        self.assertEqual(self.ctx.calls,6)

    def test_misses_use_the_existing_finite_request_budget(self):
        self.ctx.calls=400
        with self.assertRaisesRegex(Hold,'review_call_budget'):self.call('added.txt','base')
        self.assertEqual(self.source.reads,[])

    def test_advertised_paths_match_only_the_verified_union(self):
        params=thread_params('/empty','gpt-6-astra',paths=sorted(set(self.ctx.entries['head'])|set(self.ctx.entries['base'])))
        tool=params['dynamicTools'][0]['tools'][0]
        self.assertEqual(tool['inputSchema']['properties']['path']['enum'],['added.txt','deleted.txt','same.txt'])
        self.assertEqual(tool['inputSchema']['properties']['revision']['enum'],['head','base'])

    def test_unknown_and_unsafe_paths_remain_fatal_and_sanitized(self):
        for path in ['auth.json','/etc/passwd','../auth.json','./added.txt','secret-token-is-untrusted']:
            with self.subTest(path=path),self.assertRaisesRegex(Hold,'review_source_only') as raised:
                self.call(path,'head')
            diagnostic=raised.exception.diagnostic
            self.assertEqual(diagnostic['schema'],'snci-source-denial/v1')
            self.assertEqual(diagnostic['category'],'unknown_path')
            self.assertEqual(diagnostic['arguments_sha256'],sha256(canonical({'page':0,'path':path,'revision':'head'})))
            self.assertNotIn(path,canonical(diagnostic).decode())
        self.assertEqual(self.source.reads,[])

    def test_invalid_revision_types_cannot_crash_or_become_missing(self):
        for revision in ['HEAD','a'*40,None,[],{}]:
            with self.subTest(revision=revision),self.assertRaisesRegex(Hold,'review_source_only') as raised:
                self.call('added.txt',revision)
            self.assertEqual(raised.exception.diagnostic['category'],'invalid_revision')
            self.assertIsNone(raised.exception.diagnostic['revision'])
        self.assertEqual(self.source.reads,[])

    def test_argument_shape_denial_has_no_argument_values(self):
        args={'page':0,'path':'private-value','revision':'head','extra':'private-value'}
        with self.assertRaisesRegex(Hold,'review_tool_arguments') as raised:self.ctx.read(args)
        self.assertEqual(raised.exception.diagnostic['category'],'arguments')
        self.assertNotIn('private-value',canonical(raised.exception.diagnostic).decode())

    def test_fatal_diagnostic_preserves_real_read_counters(self):
        self.call('same.txt','head');self.call('added.txt','base')
        with self.assertRaises(Hold) as raised:self.call('outside','head')
        diagnostic=raised.exception.diagnostic
        self.assertEqual(diagnostic['read_count'],1)
        self.assertEqual(diagnostic['request_count'],2)
        self.assertEqual(diagnostic['source_bytes'],3)
        self.assertFalse(diagnostic['complete'])


if __name__=='__main__':unittest.main()
