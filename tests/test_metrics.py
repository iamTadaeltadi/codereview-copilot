import unittest

try:
    from experiments.matcher import Outcome
    from experiments.metrics import compare, summarise_condition, table

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def rows(condition, spec):
    """spec: {task_id: [hit, hit, ...]}"""
    out = []
    for task_id, hits in spec.items():
        for index, hit in enumerate(hits):
            out.append(
                Outcome(
                    defect_id=f"{task_id}#{index}",
                    task_id=task_id,
                    condition=condition,
                    hit=hit,
                )
            )
    return out


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class SummaryTests(unittest.TestCase):
    def test_recall_counts_defects_not_tasks(self):
        s = summarise_condition("B", rows("B", {"t1": [True, False, False], "t2": [True]}), bootstrap=200)
        self.assertEqual(s.tasks, 2)
        self.assertEqual(s.defects, 4)
        self.assertEqual(s.hits, 2)
        self.assertAlmostEqual(s.recall, 0.5)

    def test_only_the_requested_condition_is_counted(self):
        mixed = rows("B", {"t1": [True]}) + rows("D", {"t1": [False]})
        self.assertEqual(summarise_condition("B", mixed, bootstrap=200).recall, 1.0)

    def test_the_interval_brackets_the_point_estimate(self):
        s = summarise_condition("B", rows("B", {f"t{i}": [i % 3 != 0] for i in range(40)}), bootstrap=400)
        self.assertLessEqual(s.recall_low, s.recall)
        self.assertGreaterEqual(s.recall_high, s.recall)

    def test_the_interval_narrows_as_tasks_are_added(self):
        few = summarise_condition("B", rows("B", {f"t{i}": [i % 2 == 0] for i in range(8)}), bootstrap=600)
        many = summarise_condition("B", rows("B", {f"t{i}": [i % 2 == 0] for i in range(200)}), bootstrap=600)
        self.assertLess(many.recall_high - many.recall_low, few.recall_high - few.recall_low)

    def test_precision_and_f1_use_false_positives(self):
        s = summarise_condition("B", rows("B", {"t1": [True, True]}), false_positives=2, bootstrap=200)
        self.assertAlmostEqual(s.precision, 0.5)
        self.assertAlmostEqual(s.f1, 2 * 0.5 * 1.0 / 1.5)

    def test_cost_per_true_finding(self):
        s = summarise_condition(
            "B",
            rows("B", {"t1": [True, True, False]}),
            usage={"input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.02},
            bootstrap=200,
        )
        self.assertAlmostEqual(s.cost_per_true_finding, 0.01)
        self.assertAlmostEqual(s.tokens_per_true_finding, 600.0)

    def test_a_condition_that_found_nothing_has_no_cost_per_finding(self):
        s = summarise_condition("A", rows("A", {"t1": [False]}), usage={"cost_usd": 0.5}, bootstrap=200)
        self.assertIsNone(s.cost_per_true_finding)
        self.assertEqual(s.f1, 0.0)

    def test_an_empty_condition_does_not_divide_by_zero(self):
        s = summarise_condition("Z", [], bootstrap=100)
        self.assertEqual((s.tasks, s.defects, s.hits, s.recall), (0, 0, 0, 0.0))


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ClusteringTests(unittest.TestCase):
    def test_clustered_interval_is_wider_than_ignoring_clusters(self):
        clustered = summarise_condition(
            "B", rows("B", {f"t{i}": [i % 2 == 0] * 10 for i in range(20)}), bootstrap=800
        )
        spread = summarise_condition(
            "B", rows("B", {f"t{i}": [i % 2 == 0] for i in range(200)}), bootstrap=800
        )
        self.assertGreater(
            clustered.recall_high - clustered.recall_low,
            spread.recall_high - spread.recall_low,
        )

    def test_results_are_reproducible_for_a_seed(self):
        data = rows("B", {f"t{i}": [i % 3 != 0, i % 2 == 0] for i in range(30)})
        a = summarise_condition("B", data, bootstrap=300, seed=7)
        b = summarise_condition("B", data, bootstrap=300, seed=7)
        self.assertEqual((a.recall_low, a.recall_high), (b.recall_low, b.recall_high))


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ComparisonTests(unittest.TestCase):
    def test_a_large_consistent_lift_is_detected(self):
        data = rows("B", {f"t{i}": [True] for i in range(60)}) + rows(
            "A", {f"t{i}": [i < 12] for i in range(60)}
        )
        c = compare(data, "B", "A", bootstrap=600)
        self.assertGreater(c.lift, 0.5)
        self.assertTrue(c.distinguishable)
        self.assertIn("higher", c.verdict())

    def test_no_difference_is_reported_as_not_distinguishable(self):
        data = rows("B", {f"t{i}": [i % 2 == 0] for i in range(40)}) + rows(
            "A", {f"t{i}": [i % 2 == 0] for i in range(40)}
        )
        c = compare(data, "B", "A", bootstrap=600)
        self.assertAlmostEqual(c.lift, 0.0)
        self.assertFalse(c.distinguishable)
        self.assertIn("not distinguishable", c.verdict())

    def test_the_verdict_never_claims_no_difference(self):
        data = rows("B", {f"t{i}": [i % 2 == 0] for i in range(40)}) + rows(
            "A", {f"t{i}": [i % 2 == 0] for i in range(40)}
        )
        self.assertNotIn("no difference", compare(data, "B", "A", bootstrap=400).verdict().lower())

    def test_discordant_pairs_are_counted_in_both_directions(self):
        data = rows("B", {"t1": [True, False]}) + rows("A", {"t1": [False, True]})
        c = compare(data, "B", "A", bootstrap=200)
        self.assertEqual(c.discordant_treatment_only, 1)
        self.assertEqual(c.discordant_baseline_only, 1)

    def test_only_defects_present_in_both_conditions_are_paired(self):
        data = rows("B", {"t1": [True, True]}) + rows("A", {"t1": [False]})
        c = compare(data, "B", "A", bootstrap=200)
        self.assertEqual(c.discordant_treatment_only, 1)

    def test_a_negative_result_is_reported_as_lower_not_hidden(self):
        data = rows("B", {f"t{i}": [False] for i in range(60)}) + rows(
            "A", {f"t{i}": [True] for i in range(60)}
        )
        c = compare(data, "B", "A", bootstrap=600)
        self.assertLess(c.lift, 0)
        self.assertIn("lower", c.verdict())


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class TableTests(unittest.TestCase):
    def test_the_table_prints_a_row_per_condition_with_intervals(self):
        summaries = [
            summarise_condition(c, rows(c, {f"t{i}": [i % 2 == 0] for i in range(10)}), bootstrap=200)
            for c in ("A", "B", "D")
        ]
        rendered = table(summaries)
        self.assertIn("recall", rendered)
        for condition in ("A", "B", "D"):
            self.assertIn(condition, rendered)
        self.assertEqual(len(rendered.splitlines()), 5)


if __name__ == "__main__":
    unittest.main()
