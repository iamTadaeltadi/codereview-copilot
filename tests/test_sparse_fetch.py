import unittest

try:
    from experiments.sparse import (
        SUPPORTED_EXTENSIONS,
        collect_sources,
        graph_from_sources,
        imported_paths,
        paths_in_diff,
    )

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


DIFF = """diff --git a/pkg/app.py b/pkg/app.py
index 111..222 100644
--- a/pkg/app.py
+++ b/pkg/app.py
@@ -1,2 +1,3 @@
-old
+new
diff --git a/docs/guide.md b/docs/guide.md
--- a/docs/guide.md
+++ b/docs/guide.md
diff --git a/pkg/util.js b/pkg/util.js
--- a/pkg/util.js
+++ b/pkg/util.js
"""

APP = "from pkg.helpers import shout\n\n\ndef run():\n    return shout('hi')\n"
HELPERS = "def shout(text):\n    return text.upper()\n"


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class DiffPathTests(unittest.TestCase):
    def test_code_files_are_extracted_from_the_diff(self):
        self.assertEqual(paths_in_diff(DIFF), ["pkg/app.py", "pkg/util.js"])

    def test_non_code_files_are_ignored(self):
        self.assertNotIn("docs/guide.md", paths_in_diff(DIFF))

    def test_an_empty_diff_yields_nothing(self):
        self.assertEqual(paths_in_diff(""), [])

    def test_a_deleted_file_does_not_produce_dev_null(self):
        diff = "diff --git a/gone.py b/dev/null\n"
        self.assertNotIn("/dev/null", paths_in_diff(diff))

    def test_only_the_four_parser_languages_are_supported(self):
        self.assertEqual(SUPPORTED_EXTENSIONS, {".py", ".js", ".java", ".c"})


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ImportResolutionTests(unittest.TestCase):
    def test_an_absolute_python_import_becomes_a_candidate_path(self):
        found = imported_paths("from pkg.helpers import x\n", "pkg/app.py", ["pkg"])
        self.assertIn("pkg/helpers.py", found)

    def test_a_package_import_also_tries_the_init_file(self):
        found = imported_paths("import pkg.helpers\n", "pkg/app.py", ["pkg"])
        self.assertIn("pkg/helpers/__init__.py", found)

    def test_a_relative_import_is_resolved_against_the_file(self):
        found = imported_paths("from . import sibling\n", "pkg/sub/app.py", ["pkg"])
        self.assertTrue(any("pkg/sub" in p for p in found))

    def test_a_javascript_import_is_recognised(self):
        found = imported_paths("import x from './util';\n", "pkg/app.js", ["pkg"])
        self.assertTrue(found)

    def test_a_file_with_no_imports_yields_nothing(self):
        self.assertEqual(imported_paths("x = 1\n", "a.py", []), [])


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class CollectSourcesTests(unittest.TestCase):
    def setUp(self):
        self.served = {
            "pkg/app.py": APP,
            "pkg/helpers.py": HELPERS,
            "pkg/util.js": "export const a = 1;\n",
        }
        self.requested = []

    def opener(self, url):
        path = url.split("/", 6)[-1]
        self.requested.append(path)
        return self.served.get(path) or (_ for _ in ()).throw(FileNotFoundError(path))

    def _opener(self, url):
        path = url.split("/", 6)[-1]
        self.requested.append(path)
        if path in self.served:
            return self.served[path]
        raise FileNotFoundError(path)

    def test_the_diffs_own_files_are_fetched(self):
        sources = collect_sources("a/b", "c" * 40, DIFF, opener=self._opener)
        self.assertIn("pkg/app.py", sources)
        self.assertIn("pkg/util.js", sources)

    def test_one_import_hop_is_followed(self):
        sources = collect_sources("a/b", "c" * 40, DIFF, opener=self._opener)
        self.assertIn("pkg/helpers.py", sources)

    def test_no_hops_means_only_the_diffs_files(self):
        sources = collect_sources("a/b", "c" * 40, DIFF, import_hops=0, opener=self._opener)
        self.assertNotIn("pkg/helpers.py", sources)

    def test_a_missing_file_is_skipped_rather_than_fatal(self):
        del self.served["pkg/util.js"]
        sources = collect_sources("a/b", "c" * 40, DIFF, opener=self._opener)
        self.assertIn("pkg/app.py", sources)
        self.assertNotIn("pkg/util.js", sources)

    def test_the_file_cap_is_respected(self):
        sources = collect_sources("a/b", "c" * 40, DIFF, max_files=1, opener=self._opener)
        self.assertLessEqual(len(sources), 1)

    def test_a_file_that_was_found_is_never_fetched_again(self):
        collect_sources("a/b", "c" * 40, DIFF, opener=self._opener)
        for path in self.served:
            with self.subTest(path=path):
                self.assertEqual(self.requested.count(path), 1)

    def test_a_missing_file_is_not_retried_on_the_next_hop(self):
        del self.served["pkg/helpers.py"]
        collect_sources("a/b", "c" * 40, DIFF, opener=self._opener)
        misses = [p for p in self.requested if p not in self.served]
        # retries inside one fetch are deliberate; asking again on a later hop
        # is waste, and on a slow link waste is measured in seconds
        for path in set(misses):
            with self.subTest(path=path):
                self.assertLessEqual(self.requested.count(path), 3)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class SparseGraphTests(unittest.TestCase):
    def test_a_graph_is_built_from_fetched_sources(self):
        graph = graph_from_sources({"pkg/app.py": APP, "pkg/helpers.py": HELPERS})
        names = {(d.get("type"), d.get("name")) for _, d in graph.nodes(data=True)}
        self.assertIn(("function", "run"), names)
        self.assertIn(("function", "shout"), names)

    def test_the_graph_keeps_cross_file_structure(self):
        graph = graph_from_sources({"pkg/app.py": APP, "pkg/helpers.py": HELPERS})
        paths = {d.get("relative_path") for _, d in graph.nodes(data=True)}
        self.assertIn("pkg/app.py", paths)
        self.assertIn("pkg/helpers.py", paths)
        self.assertGreater(len(graph.edges), 0)

    def test_an_empty_source_set_yields_an_empty_graph(self):
        self.assertEqual(len(graph_from_sources({}).nodes), 0)


if __name__ == "__main__":
    unittest.main()
