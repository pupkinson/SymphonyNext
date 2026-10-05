"""A model must be able to read the middle, and partial pages cannot earn READY."""
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import Hold, canonical, decode
from snci.reviewer import ReadOnlyContext, handle_request, validate_verdict

TARGET = {'pr': 1, 'head': 'a' * 40, 'base': 'b' * 40, 'tree': 'c' * 40}
HEAD = ('start\r\n' + 'x' * 39000 + '\nMIDDLE_Ж😀\\\"\x00\n' + 'z' * 39000 + '\nEND').encode()
BASE = HEAD.replace(b'MIDDLE_', b'OLD_MIDDLE_')


class Source:
    def blob(self, entry):
        return entry['data']


def context(head=HEAD, base=BASE, extra=None):
    h, b = {'x': {'data': head}}, {'x': {'data': base}}
    if extra is not None:
        h['context.md'] = {'data': extra}
    return ReadOnlyContext(Source(), h, b, ['x'])


class SourcePagingTests(unittest.TestCase):
    def page(self, ctx, revision, number, path='x'):
        try:
            result = handle_request({'id': 1, 'method': 'item/tool/call', 'params': {
                'threadId': 't', 'namespace': 'snci_source', 'tool': 'read_source',
                'arguments': {'path': path, 'revision': revision, 'page': number}}}, ctx, 't')
        except Hold as error:
            self.fail('Immutable source paging is unavailable: ' + str(error))
        self.assertIs(result['success'], True)
        self.assertLessEqual(len(canonical(result)), 8192)
        value = decode(result['contentItems'][0]['text'])
        self.assertEqual(value['schema'], 'snci-source-page/v1')
        self.assertEqual((value['path'], value['revision'], value['page']), (path, revision, number))
        return value

    def ready(self, ctx):
        return validate_verdict(dict(TARGET, verdict='READY', findings=[], limitations=[]), TARGET, ctx)

    def full(self, ctx, revision, path='x'):
        first = self.page(ctx, revision, 0, path)
        pages = [first] + [self.page(ctx, revision, n, path) for n in range(1, first['page_count'])]
        return pages

    def test_large_source_is_accessible_without_claiming_full_read_after_first_page(self):
        ctx = context()
        first = self.page(ctx, 'head', 0)
        self.assertGreater(first['page_count'], 1)
        self.assertLess(len(first['content'].encode()), len(HEAD))
        self.assertFalse(ctx.complete())
        with self.assertRaisesRegex(Hold, 'review_incomplete_source'):
            self.ready(ctx)

    def test_pages_reconstruct_both_exact_versions_with_bound_identity(self):
        ctx = context()
        for revision, raw in [('head', HEAD), ('base', BASE)]:
            pages = self.full(ctx, revision)
            offset = 0
            for n, page in enumerate(pages):
                part = page['content'].encode()
                self.assertEqual(page['byte_start'], offset)
                offset += len(part)
                self.assertEqual(page['byte_end'], offset)
                self.assertEqual(page['page_sha256'], hashlib.sha256(part).hexdigest())
                self.assertEqual(page['next_page'], n + 1 if n + 1 < len(pages) else None)
                self.assertEqual(page['source_bytes'], len(raw))
                self.assertEqual(page['source_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(page['blob_sha1'], hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest())
            self.assertEqual(b''.join(p['content'].encode() for p in pages), raw)
        self.assertEqual(ctx.bytes, len(HEAD) + len(BASE))
        self.assertEqual(self.ready(ctx)['verdict'], 'READY')

    def test_skipped_middle_and_duplicate_last_page_do_not_complete_version(self):
        ctx = context()
        first = self.page(ctx, 'head', 0)
        missing = first['page_count'] // 2
        for n in reversed(range(1, first['page_count'])):
            if n != missing:
                self.page(ctx, 'head', n)
        self.page(ctx, 'head', first['page_count'] - 1)
        self.full(ctx, 'base')
        with self.assertRaisesRegex(Hold, 'review_incomplete_source'):
            self.ready(ctx)
        self.page(ctx, 'head', missing)
        self.assertEqual(self.ready(ctx)['verdict'], 'READY')

    def test_started_unchanged_context_must_also_be_finished(self):
        ctx = context(extra=HEAD)
        self.full(ctx, 'head'); self.full(ctx, 'base')
        first = self.page(ctx, 'head', 0, 'context.md')
        with self.assertRaisesRegex(Hold, 'review_incomplete_source'):
            self.ready(ctx)
        for n in range(1, first['page_count']):
            self.page(ctx, 'head', n, 'context.md')
        self.assertEqual(self.ready(ctx)['verdict'], 'READY')

    def test_empty_file_is_one_real_page(self):
        ctx = context(b'', b'')
        for revision in ('head', 'base'):
            p = self.page(ctx, revision, 0)
            self.assertEqual((p['page_count'], p['content'], p['byte_start'], p['byte_end'], p['next_page']),
                             (1, '', 0, 0, None))
        self.assertTrue(ctx.complete())

    def test_serialized_response_limit_includes_unicode_escapes_and_long_lines(self):
        raw = ('😀Ж\\\"\x00\r\n' * 9000 + 'one-long-line-' + 'q' * 30000).encode()
        ctx = context(raw, b'old')
        pages = self.full(ctx, 'head')
        self.assertEqual(b''.join(p['content'].encode() for p in pages), raw)
        self.assertGreater(len(pages), 10)

    def test_repeated_pages_use_call_and_actual_served_byte_budgets(self):
        ctx = context()
        first = self.page(ctx, 'head', 0)
        self.page(ctx, 'head', 0)
        self.assertEqual((ctx.calls, ctx.reads, ctx.bytes), (2, 2, 2 * len(first['content'].encode())))
        ctx.calls = 400
        with self.assertRaisesRegex(Hold, 'review_call_budget'):
            ctx.read({'path': 'x', 'revision': 'head', 'page': 0})
        ctx = context()
        ctx.bytes = 2 * 1024 * 1024
        with self.assertRaisesRegex(Hold, 'review_context_budget'):
            ctx.read({'path': 'x', 'revision': 'head', 'page': 0})
        self.assertFalse(ctx.complete())

    def test_invalid_pages_and_extra_arguments_are_sanitized_fatal_denials(self):
        for value in (True, False, -1, 1.5, '1', None, [], {}, 10**100):
            ctx = context()
            with self.subTest(page=value), self.assertRaises(Hold):
                ctx.read({'path': 'x', 'revision': 'head', 'page': value})
            self.assertFalse(ctx.complete())
        for args in ({'path': 'x', 'revision': 'head'},
                     {'path': 'private-value', 'revision': 'head', 'page': 0, 'extra': 'private-value'}):
            with self.assertRaises(Hold) as caught:
                context().read(args)
            self.assertNotIn('private-value', canonical(caught.exception.diagnostic).decode())

    def test_binary_source_cannot_be_turned_into_text_pages(self):
        with self.assertRaisesRegex(Hold, 'review_binary_input'):
            context(b'\xff', b'old').read({'path': 'x', 'revision': 'head', 'page': 0})


if __name__ == '__main__':
    unittest.main()
