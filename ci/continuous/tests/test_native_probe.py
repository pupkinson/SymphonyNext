"""Both native wire formats must expose the capability inventory to the probe."""
import unittest
import native_codex_probe as probe


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


if __name__=='__main__':unittest.main()
