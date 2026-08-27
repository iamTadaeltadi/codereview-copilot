import os
import pickle
import tarfile
import tempfile
import unittest
from pathlib import Path

try:
    from experiments.repo import (
        SUPPORTED_EXTENSIONS,
        GraphInfo,
        _cache_path,
        build_graph_from_tree,
        evict,
        graph_for,
    )

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


SAMPLE_PY = "class Order:\n    def total(self):\n        return tax(1)\n\n\ndef tax(v):\n    return v\n"
SAMPLE_JS = "function greet(n) { return 'hi ' + n; }\n"


def tree_with(files):
    root = Path(tempfile.mkdtemp())
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return root


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ExtensionTests(unittest.TestCase):
    def test_only_the_four_parser_languages_are_collected(self):
        self.assertEqual(SUPPORTED_EXTENSIONS, {".py", ".js", ".java", ".c"})


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class GraphBuildTests(unittest.TestCase):
    def test_a_tree_becomes_a_graph_with_its_entities(self):
        root = tree_with({"orders.py": SAMPLE_PY})
        graph, files = build_graph_from_tree(root)
        self.assertEqual(files, 1)
        names = {(d.get("type"), d.get("name")) for _, d in graph.nodes(data=True)}
        self.assertIn(("class", "Order"), names)
        self.assertIn(("function", "tax"), names)

    def test_more_than_one_language_is_parsed(self):
        root = tree_with({"a.py": SAMPLE_PY, "b.js": SAMPLE_JS})
        graph, files = build_graph_from_tree(root)
        self.assertEqual(files, 2)
        paths = {d.get("relative_path") for _, d in graph.nodes(data=True)}
        self.assertIn("a.py", paths)
        self.assertIn("b.js", paths)

    def test_unsupported_files_are_ignored(self):
        root = tree_with({"a.py": SAMPLE_PY, "notes.md": "# hi", "data.json": "{}"})
        _, files = build_graph_from_tree(root)
        self.assertEqual(files, 1)

    def test_vendor_directories_are_skipped(self):
        root = tree_with({
            "a.py": SAMPLE_PY,
            "node_modules/pkg/index.js": SAMPLE_JS,
            "__pycache__/x.py": SAMPLE_PY,
            ".git/hooks/y.py": SAMPLE_PY,
        })
        _, files = build_graph_from_tree(root)
        self.assertEqual(files, 1)

    def test_the_file_cap_is_respected(self):
        root = tree_with({f"mod{i}.py": SAMPLE_PY for i in range(12)})
        _, files = build_graph_from_tree(root, max_files=5)
        self.assertEqual(files, 5)

    def test_an_unreadable_file_does_not_abort_the_build(self):
        root = tree_with({"good.py": SAMPLE_PY, "bad.py": SAMPLE_PY})
        (root / "bad.py").write_bytes(b"\xff\xfe\x00 not utf8 \x00")
        graph, files = build_graph_from_tree(root)
        self.assertEqual(files, 2)
        self.assertGreater(len(graph.nodes), 0)

    def test_an_empty_tree_yields_an_empty_graph(self):
        graph, files = build_graph_from_tree(tree_with({"README.md": "hi"}))
        self.assertEqual(files, 0)
        self.assertEqual(len(graph.nodes), 0)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class CacheTests(unittest.TestCase):
    def test_the_cache_path_encodes_repo_and_commit(self):
        path = _cache_path("/tmp/c", "psf/requests", "abcdef1234567890")
        self.assertEqual(path.name, "psf__requests@abcdef123456.pkl")

    def test_a_cached_graph_is_returned_without_downloading(self):
        cache = Path(tempfile.mkdtemp())
        graph, _ = build_graph_from_tree(tree_with({"a.py": SAMPLE_PY}))
        target = _cache_path(cache, "acme/widget", "0" * 40)
        with target.open("wb") as handle:
            pickle.dump(graph, handle)

        loaded, info = graph_for("acme/widget", "0" * 40, cache_dir=cache)
        self.assertTrue(info.cached)
        self.assertEqual(len(loaded.nodes), len(graph.nodes))

    def test_eviction_removes_the_oldest_first(self):
        cache = Path(tempfile.mkdtemp())
        for index in range(4):
            path = cache / f"repo{index}@000000000000.pkl"
            path.write_bytes(b"x" * 1000)
            os.utime(path, (index, index))
        removed = evict(cache, keep_bytes=2500)
        self.assertGreaterEqual(removed, 1)
        left = sorted(p.name for p in cache.glob("*.pkl"))
        self.assertNotIn("repo0@000000000000.pkl", left)
        self.assertIn("repo3@000000000000.pkl", left)

    def test_eviction_keeps_everything_under_the_limit(self):
        cache = Path(tempfile.mkdtemp())
        (cache / "one@000000000000.pkl").write_bytes(b"x" * 10)
        self.assertEqual(evict(cache, keep_bytes=10_000), 0)
        self.assertEqual(len(list(cache.glob("*.pkl"))), 1)

    def test_eviction_on_a_missing_directory_is_not_an_error(self):
        self.assertEqual(evict(Path(tempfile.mkdtemp()) / "nope"), 0)


if __name__ == "__main__":
    unittest.main()
