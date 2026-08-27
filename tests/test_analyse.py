import json
import tempfile
import unittest
from pathlib import Path

try:
    from experiments.analyse import balance, latex, load, usage_by_condition
    from experiments.matcher import Outcome
    from experiments.metrics import compare, summarise_condition

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def outcome(task, condition, hit, index=0):
    return Outcome(defect_id=f"{task}#{index}", task_id=task, condition=condition, hit=hit)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class BalanceTests(unittest.TestCase):
    def test_a_task_missing_from_one_condition_is_excluded_entirely(self):
        rows = [
            outcome("t1", "A", True), outcome("t1", "B", True),
            outcome("t2", "A", True),  # B never ran
        ]
        balanced, complete = balance(rows, ["A", "B"])
        self.assertEqual(complete, {"t1"})
        self.assertEqual({o.task_id for o in balanced}, {"t1"})

    def test_a_fully_scored_task_survives(self):
        rows = [outcome("t1", c, True) for c in ("A", "B", "D", "G")]
        balanced, complete = balance(rows, ["A", "B", "D", "G"])
        self.assertEqual(len(balanced), 4)
        self.assertEqual(complete, {"t1"})

    def test_balancing_cannot_let_one_arm_be_scored_on_easier_tasks(self):
        rows = [
            outcome("easy", "A", True), outcome("easy", "B", True),
            outcome("hard", "A", False),  # B failed to fetch on the hard task
        ]
        balanced, _ = balance(rows, ["A", "B"])
        per_condition = {}
        for o in balanced:
            per_condition.setdefault(o.condition, []).append(o.hit)
        self.assertEqual(len(per_condition["A"]), len(per_condition["B"]))

    def test_an_empty_run_balances_to_nothing(self):
        balanced, complete = balance([], ["A"])
        self.assertEqual(balanced, [])
        self.assertEqual(complete, set())


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class UsageTests(unittest.TestCase):
    def raw(self, condition, cost, findings, ctx, parse_failed=False):
        return {
            "condition": condition,
            "usage": {"input_tokens": 100, "output_tokens": 10, "cost_usd": cost},
            "findings": [{}] * findings,
            "context_chars": ctx,
            "parse_failed": parse_failed,
        }

    def test_cost_and_tokens_accumulate_per_condition(self):
        usage, _, _, _ = usage_by_condition([self.raw("B", 0.01, 1, 100), self.raw("B", 0.02, 1, 100)])
        self.assertAlmostEqual(usage["B"]["cost_usd"], 0.03)
        self.assertEqual(usage["B"]["input_tokens"], 200)

    def test_context_sizes_are_kept_per_call(self):
        _, context, _, _ = usage_by_condition([self.raw("B", 0, 0, 500), self.raw("B", 0, 0, 700)])
        self.assertEqual(context["B"], [500, 700])

    def test_reported_findings_are_counted_separately_from_hits(self):
        _, _, reported, _ = usage_by_condition([self.raw("A", 0, 7, 0)])
        self.assertEqual(reported["A"], 7)

    def test_parse_failures_are_counted(self):
        _, _, _, failures = usage_by_condition(
            [self.raw("A", 0, 0, 0, parse_failed=True), self.raw("A", 0, 1, 0)]
        )
        self.assertEqual(failures["A"], 1)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class LoadTests(unittest.TestCase):
    def test_a_run_directory_round_trips(self):
        run = Path(tempfile.mkdtemp())
        (run / "outcomes.jsonl").write_text(
            json.dumps({"defect_id": "d", "task_id": "t", "condition": "A", "hit": True}) + "\n"
        )
        (run / "raw.jsonl").write_text(
            json.dumps({"condition": "A", "usage": {"input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0},
                        "findings": [], "context_chars": 0}) + "\n"
        )
        outcomes, raw = load(run)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(len(raw), 1)
        self.assertTrue(outcomes[0].hit)

    def test_blank_lines_do_not_break_loading(self):
        run = Path(tempfile.mkdtemp())
        (run / "outcomes.jsonl").write_text(
            json.dumps({"defect_id": "d", "task_id": "t", "condition": "A", "hit": False}) + "\n\n"
        )
        (run / "raw.jsonl").write_text("\n")
        outcomes, raw = load(run)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(raw, [])


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class LatexTests(unittest.TestCase):
    def _tables(self):
        rows = [outcome(f"t{i}", "A", i % 2 == 0) for i in range(10)]
        rows += [outcome(f"t{i}", "B", i % 3 != 0) for i in range(10)]
        summaries = [summarise_condition(c, rows, bootstrap=200) for c in ("A", "B")]
        return latex(summaries, [compare(rows, "B", "A", bootstrap=200)])

    def test_percent_signs_are_escaped_for_latex(self):
        rendered = self._tables()
        self.assertNotIn("% \\", rendered)
        self.assertIn(r"\%", rendered)

    def test_both_tables_are_emitted(self):
        rendered = self._tables()
        self.assertEqual(rendered.count(r"\begin{tabular}"), 2)
        self.assertEqual(rendered.count(r"\end{tabular}"), 2)

    def test_every_condition_appears_as_a_row(self):
        rendered = self._tables()
        for condition in ("A", "B"):
            self.assertIn(f"{condition} &", rendered)


if __name__ == "__main__":
    unittest.main()
