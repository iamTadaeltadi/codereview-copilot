"""Sanity checks for data/foreign-snippets.jsonl (no network)."""
import ast
import json
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNIPPETS = ROOT / "data" / "foreign-snippets.jsonl"
CROSSFILE = ROOT / "data" / "crossfile.jsonl"
REQUIRED_KEYS = {"repo", "path", "start_line", "end_line", "text", "label"}


def _load_jsonl(path):
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


@unittest.skipUnless(SNIPPETS.exists(), "data/foreign-snippets.jsonl not present")
class ForeignSnippetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = _load_jsonl(SNIPPETS)

    def test_minimum_count(self):
        self.assertGreaterEqual(len(self.records), 100)

    def test_required_keys(self):
        for i, rec in enumerate(self.records):
            missing = REQUIRED_KEYS - set(rec)
            self.assertFalse(missing, f"record {i} missing keys {missing}")
            self.assertIsInstance(rec["text"], str)
            self.assertTrue(rec["text"].strip(), f"record {i} has empty text")
            self.assertLessEqual(rec["start_line"], rec["end_line"], f"record {i}")

    def test_labels_unique_and_well_formed(self):
        labels = [rec["label"] for rec in self.records]
        self.assertEqual(len(labels), len(set(labels)))
        for rec in self.records:
            stem = Path(rec["path"]).stem
            self.assertEqual(rec["label"], f"{stem}:{rec['start_line']}")

    def test_text_parses_as_python(self):
        ok = 0
        for rec in self.records:
            try:
                ast.parse(textwrap.dedent(rec["text"]))
                ok += 1
            except SyntaxError:
                # Allowed: the window may cut a function mid-block.
                pass
        rate = ok / len(self.records)
        self.assertGreaterEqual(rate, 0.8, f"only {rate:.1%} of snippets parse")

    @unittest.skipUnless(CROSSFILE.exists(), "data/crossfile.jsonl not present")
    def test_repos_disjoint_from_benchmark(self):
        benchmark_repos = {rec["repo"] for rec in _load_jsonl(CROSSFILE)}
        foreign_repos = {rec["repo"] for rec in self.records}
        overlap = foreign_repos & benchmark_repos
        self.assertFalse(overlap, f"foreign repos overlap benchmark: {overlap}")


if __name__ == "__main__":
    unittest.main()
