import json
import tempfile
import unittest
from pathlib import Path

try:
    from experiments.benchmark import (
        SOURCE_CCRAB,
        SUPPORTED_LANGUAGES,
        is_supported_language,
        load_ccrab,
        oracle_targets,
        summarise,
    )

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def instance(instance_id, language="Python", comments=None, repo="acme/widget"):
    return {
        "instance_id": instance_id,
        "language": language,
        "repo": repo,
        "base_commit": "0" * 40,
        "merged_patch": "diff --git a/x b/x",
        "problem_statement": "something is wrong",
        "metadata": {"difficulty": "medium"},
        "reference_review_comments": comments
        if comments is not None
        else [{"path": "src/app.py", "line": 12, "text": "bug here", "diff_hunk": "@@"}],
    }


def write(rows):
    handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for row in rows:
        handle.write(json.dumps(row) + "\n")
    handle.close()
    return handle.name


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class LanguageSupportTests(unittest.TestCase):
    def test_the_four_parser_languages_are_supported(self):
        self.assertEqual(set(SUPPORTED_LANGUAGES), {"python", "javascript", "java", "c"})

    def test_languages_the_parser_cannot_read_are_rejected(self):
        for language in ("Go", "Rust", "TypeScript", "C#", "C++", "PHP"):
            with self.subTest(language=language):
                self.assertFalse(is_supported_language(language))

    def test_language_matching_ignores_case(self):
        self.assertTrue(is_supported_language("PYTHON"))
        self.assertTrue(is_supported_language("Java"))


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class LoaderTests(unittest.TestCase):
    def test_an_instance_becomes_a_task_with_its_defects(self):
        tasks = load_ccrab(write([instance("i1")]))
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "i1")
        self.assertEqual(tasks[0].source, SOURCE_CCRAB)
        self.assertEqual(tasks[0].defect_count, 1)

    def test_unsupported_languages_are_skipped(self):
        tasks = load_ccrab(write([instance("i1", language="Rust"), instance("i2", language="Python")]))
        self.assertEqual([t.task_id for t in tasks], ["i2"])

    def test_the_language_filter_can_be_narrowed(self):
        rows = [instance("py", language="Python"), instance("js", language="JavaScript")]
        tasks = load_ccrab(write(rows), languages=["python"])
        self.assertEqual([t.task_id for t in tasks], ["py"])

    def test_original_line_is_used_when_line_is_null(self):
        rows = [instance("i1", comments=[{"path": "a.py", "line": None, "original_line": 44, "text": "t"}])]
        self.assertEqual(load_ccrab(write(rows))[0].defects[0].line, 44)

    def test_defects_without_a_location_are_dropped_by_default(self):
        rows = [instance("i1", comments=[{"path": "", "line": None, "original_line": None, "text": "t"}])]
        self.assertEqual(load_ccrab(write(rows)), [])

    def test_a_task_with_no_usable_defect_is_not_loaded(self):
        self.assertEqual(load_ccrab(write([instance("i1", comments=[])])), [])

    def test_every_defect_gets_a_unique_id(self):
        rows = [
            instance(
                "i1",
                comments=[
                    {"path": "a.py", "line": 1, "text": "one"},
                    {"path": "a.py", "line": 2, "text": "two"},
                ],
            )
        ]
        ids = [d.defect_id for d in load_ccrab(write(rows))[0].defects]
        self.assertEqual(len(set(ids)), 2)

    def test_blank_lines_in_the_file_are_tolerated(self):
        path = write([instance("i1")])
        Path(path).write_text(Path(path).read_text() + "\n\n")
        self.assertEqual(len(load_ccrab(path)), 1)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class OracleTargetTests(unittest.TestCase):
    def test_targets_are_the_answer_key_in_the_tool_shape(self):
        rows = [
            instance(
                "i1",
                comments=[
                    {"path": "a.py", "line": 1, "text": "one"},
                    {"path": "b.py", "line": 9, "text": "two"},
                ],
            )
        ]
        self.assertEqual(
            oracle_targets(load_ccrab(write(rows))[0]),
            [{"path": "a.py", "line": 1}, {"path": "b.py", "line": 9}],
        )


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class SummaryTests(unittest.TestCase):
    def test_the_summary_counts_defects_not_only_tasks(self):
        rows = [
            instance("i1", comments=[{"path": "a.py", "line": 1, "text": "x"}]),
            instance(
                "i2",
                repo="acme/other",
                comments=[
                    {"path": "b.py", "line": 2, "text": "y"},
                    {"path": "b.py", "line": 3, "text": "z"},
                ],
            ),
        ]
        summary = summarise(load_ccrab(write(rows)))
        self.assertEqual(summary["tasks"], 2)
        self.assertEqual(summary["defects"], 3)
        self.assertEqual(summary["repos"], 2)
        self.assertEqual(summary["languages"], {"python": 2})

    def test_an_empty_set_summarises_without_dividing_by_zero(self):
        self.assertEqual(summarise([])["defects_per_task"], 0.0)


if __name__ == "__main__":
    unittest.main()
