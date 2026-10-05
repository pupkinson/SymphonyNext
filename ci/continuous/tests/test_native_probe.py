"""Both native wire formats must expose the capability inventory to the probe."""
import unittest
import native_codex_probe as probe
from snci.common import canonical, decode
from snci.reviewer import ReadOnlyContext


class NativeInventoryTests(unittest.TestCase):
    def test_responses_inventory(self):
        tool={'type':'function','name':'read_source','parameters':{'type':'object'}}
        self.assertEqual(probe.request_tools({'tools':[tool],'input':[]}),[tool])

    def test_lite_inventory_inside_input_and_multiple_additions(self):
        tool={'type':'namespace','name':'snci_source','tools':[{'type':'function','name':'read_source'}]}
        request={'input':[{'type':'message','content':[]},
                          {'type':'additional_tools','tools':[tool]},
                          {'type':'additional_tools','tools':[{'type':'function','name':'wait'}]}]}
        self.assertEqual(probe.request_tools(request),[tool,{'type':'function','name':'wait'}])
        self.assertEqual(probe.inventory(request),['snci_source.read_source','wait'])

    def test_missing_inventory_is_not_silently_accepted(self):
        with self.assertRaises(AssertionError):probe.request_tools({'input':[{'type':'message'}]})

    def test_both_output_item_kinds_are_preserved(self):
        requests=[{'input':[{'type':'custom_tool_call_output','output':'host disabled'},
                           {'type':'function_call_output','output':'source'},
                           {'type':'message','content':[]}]}]
        self.assertEqual(probe.tool_outputs(requests),['host disabled','source'])

    def pages(self):
        raw=('start'+ 'a'*40000+'MIDDLE_Ж😀'+ 'z'*40000+'END').encode()
        ctx=ReadOnlyContext(probe.FixtureSource(),{'README.md':{'data':raw}}, {}, ['README.md'])
        first=ctx.read({'path':'README.md','revision':'head','page':0})
        count=decode(first)['page_count']
        outputs=[first]+[ctx.read({'path':'README.md','revision':'head','page':n}) for n in range(1,count)]
        return raw,outputs

    def verifier(self):
        self.assertTrue(hasattr(probe,'verify_pages'),'Provider-visible reconstruction is missing')
        return probe.verify_pages

    def test_provider_visible_pages_reconstruct_exact_raw_bytes(self):
        verify=self.verifier();raw,outputs=self.pages()
        self.assertEqual(verify(outputs+outputs,{('head','README.md'):raw})['bytes'],len(raw))

    def test_missing_middle_or_truncated_json_fails_native_proof(self):
        verify=self.verifier();raw,outputs=self.pages()
        for bad in [outputs[:1]+outputs[2:],outputs[:-1],outputs[:1]+['truncated']+outputs[2:]]:
            with self.subTest(count=len(bad)),self.assertRaises(AssertionError):
                verify(bad,{('head','README.md'):raw})

    def test_conflicting_page_identity_or_content_fails_native_proof(self):
        verify=self.verifier();raw,outputs=self.pages()
        for key,value in [('content','changed'),('source_sha256','0'*64),('byte_start',99),('page_count',1)]:
            changed=decode(outputs[0]);changed[key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):
                verify([canonical(changed).decode()]+outputs[1:],{('head','README.md'):raw})


if __name__=='__main__':unittest.main()
