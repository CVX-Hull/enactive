"""Reader navigation regressions using actual Markdown parsing and GitHub IDs."""
from pathlib import Path
import tempfile
import unittest
from tools.check import REQUIRED_DOCS, check_documents


class DocumentLinkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in REQUIRED_DOCS:
            self.write(name, "")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def current(self, text):
        return "---\nstatus: active\n---\n\n" + text

    def test_current_fragments_include_duplicates_markup_unicode_and_explicit_ids(self):
        self.write("docs/protocol.md", self.current('''# Protocol
[leaf](contracts/leaf.md#café-test)
[duplicate](contracts/leaf.md#café-test-1)
[html](contracts/leaf.md#owned)
[self](#protocol)
'''))
        self.write("docs/contracts/leaf.md", self.current('''# **Café** `test`
# Café test
<a id="owned"></a>
'''))
        self.assertEqual(check_documents(self.root), [])
        self.write("docs/protocol.md", self.current("[miss](contracts/leaf.md#cafe-test)"))
        self.assertTrue(any("Broken local fragment" in error for error in check_documents(self.root)))

    def test_historical_prose_keeps_original_fragments_but_current_links_to_it_are_checked(self):
        self.write("docs/old.md", "---\nstatus: historical\n---\n# Evidence\n[old](protocol.md#removed)")
        self.assertEqual(check_documents(self.root), [])
        self.write("docs/protocol.md", self.current("[bad evidence](old.md#absent)"))
        self.assertTrue(any("Broken local fragment" in error for error in check_documents(self.root)))

    def test_responsibility_leaf_must_be_reachable_from_its_index(self):
        self.write("docs/contracts/leaf.md", self.current("# Lifecycle"))
        errors = check_documents(self.root)
        self.assertTrue(any("unreachable from docs/protocol.md" in error for error in errors))
        self.write("docs/protocol.md", self.current("[adoption](contracts/leaf.md#lifecycle)"))
        self.assertEqual(check_documents(self.root), [])

    def test_missing_files_and_path_escape_are_always_rejected(self):
        self.write("README.md", "[missing](docs/absent.md) ![escape](../elsewhere.png)")
        errors = check_documents(self.root)
        self.assertEqual(sum("Broken local link" in error for error in errors), 2)
