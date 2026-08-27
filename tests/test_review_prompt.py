import unittest

try:
    from experiments.benchmark import BenchmarkTask, GroundTruthDefect
    from experiments.review import (
        OUTPUT_CONTRACT,
        SYSTEM_PROMPT,
        TOOL_CLAUSE,
        build_messages,
        parse_findings,
    )

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def task():
    return BenchmarkTask(
        task_id="t1",
        source="c-crab",
        repo="acme/widget",
        language="python",
        base_commit="0" * 40,
        diff="diff --git a/app.py b/app.py\n+x = 1\n",
        defects=(GroundTruthDefect("d1", "app.py", 3, "bug"),),
    )


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class PromptTests(unittest.TestCase):
    def test_the_diff_and_repository_always_reach_the_model(self):
        text = build_messages(task(), "A")[1]["content"]
        self.assertIn("acme/widget", text)
        self.assertIn("x = 1", text)

    def test_the_output_contract_is_present_in_every_condition(self):
        for condition in ("A", "B", "C", "D", "E", "F", "G"):
            with self.subTest(condition=condition):
                self.assertIn(OUTPUT_CONTRACT, build_messages(task(), condition)[1]["content"])

    def test_the_system_prompt_is_identical_across_conditions(self):
        systems = {build_messages(task(), c)[0]["content"] for c in ("A", "B", "D", "G")}
        self.assertEqual(systems, {SYSTEM_PROMPT})

    def test_tool_conditions_mention_the_tool(self):
        for condition in ("B", "C", "D", "G"):
            with self.subTest(condition=condition):
                self.assertIn(TOOL_CLAUSE, build_messages(task(), condition)[1]["content"])

    def test_conditions_without_a_tool_never_mention_one(self):
        for condition in ("A", "E", "F"):
            with self.subTest(condition=condition):
                text = build_messages(task(), condition)[1]["content"]
                self.assertNotIn(TOOL_CLAUSE, text)
                self.assertNotIn("retrieve_graph", text)

    def test_supplied_context_is_included_when_present(self):
        text = build_messages(task(), "B", context_text='{"neighbors": []}')[1]["content"]
        self.assertIn("Repository context", text)
        self.assertIn('{"neighbors": []}', text)

    def test_no_context_section_appears_when_there_is_none(self):
        self.assertNotIn("Repository context", build_messages(task(), "A")[1]["content"])

    def test_two_conditions_with_the_same_context_differ_only_by_the_tool_clause(self):
        with_tool = build_messages(task(), "B", context_text="CTX")[1]["content"]
        without = build_messages(task(), "A", context_text="CTX")[1]["content"]
        self.assertEqual(with_tool.replace("\n\n" + TOOL_CLAUSE, ""), without)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ParserTests(unittest.TestCase):
    def test_bare_json_is_parsed(self):
        found, failed = parse_findings('{"findings":[{"path":"a.py","line":3,"message":"m"}]}', "t", "B")
        self.assertFalse(failed)
        self.assertEqual((found[0].path, found[0].line), ("a.py", 3))

    def test_fenced_json_is_parsed(self):
        found, failed = parse_findings('```json\n{"findings":[{"path":"a.py","line":1}]}\n```', "t", "B")
        self.assertFalse(failed)
        self.assertEqual(len(found), 1)

    def test_json_buried_in_prose_is_recovered(self):
        text = 'Sure. {"findings":[{"path":"a.py","line":9,"message":"x"}]} Hope that helps.'
        found, failed = parse_findings(text, "t", "B")
        self.assertFalse(failed)
        self.assertEqual(found[0].line, 9)

    def test_an_empty_finding_list_is_a_valid_answer_not_a_failure(self):
        found, failed = parse_findings('{"findings":[]}', "t", "A")
        self.assertEqual(found, [])
        self.assertFalse(failed)

    def test_unparseable_output_is_reported_as_a_failure(self):
        found, failed = parse_findings("I could not review this.", "t", "A")
        self.assertEqual(found, [])
        self.assertTrue(failed)

    def test_a_non_numeric_line_becomes_none_rather_than_raising(self):
        found, _ = parse_findings('{"findings":[{"path":"a.py","line":"unknown"}]}', "t", "B")
        self.assertIsNone(found[0].line)

    def test_the_file_key_is_accepted_as_well_as_path(self):
        found, _ = parse_findings('{"findings":[{"file":"a.py","line":2}]}', "t", "B")
        self.assertEqual(found[0].path, "a.py")

    def test_finding_ids_are_unique_within_a_review(self):
        found, _ = parse_findings(
            '{"findings":[{"path":"a.py","line":1},{"path":"a.py","line":2}]}', "t", "B"
        )
        self.assertEqual(len({f.finding_id for f in found}), 2)

    def test_the_condition_is_encoded_in_the_finding_id(self):
        found, _ = parse_findings('{"findings":[{"path":"a.py","line":1}]}', "t9", "D")
        self.assertTrue(found[0].finding_id.startswith("t9:D:"))


if __name__ == "__main__":
    unittest.main()
