import unittest

try:
    from experiments.config import (
        BUDGETED_CONDITIONS,
        CONDITION_GRAPH,
        CONDITION_WHOLE_FILE,
        MODELS,
        RunMatrix,
        estimate_cost,
    )
    from experiments.power import mcnemar_p, simulate_power

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class RunMatrixTests(unittest.TestCase):
    def test_every_budgeted_condition_shares_one_budget(self):
        matrix = RunMatrix()
        budgets = {
            cell["budget_tokens"]
            for cell in matrix.cells()
            if cell["condition"] in BUDGETED_CONDITIONS
        }
        self.assertEqual(budgets, {matrix.budget_tokens})

    def test_the_whole_file_condition_is_deliberately_unbudgeted(self):
        cells = [c for c in RunMatrix().cells() if c["condition"] == CONDITION_WHOLE_FILE]
        self.assertTrue(cells)
        self.assertTrue(all(cell["budget_tokens"] is None for cell in cells))

    def test_only_the_graph_condition_carries_a_depth(self):
        for cell in RunMatrix().cells():
            with self.subTest(condition=cell["condition"]):
                if cell["condition"] == CONDITION_GRAPH:
                    self.assertIsNotNone(cell["depth"])
                else:
                    self.assertIsNone(cell["depth"])

    def test_the_depth_ablation_raises_the_node_cap(self):
        matrix = RunMatrix()
        graph_cells = [c for c in matrix.cells() if c["condition"] == CONDITION_GRAPH]
        self.assertTrue(graph_cells)
        for cell in graph_cells:
            self.assertEqual(cell["max_nodes"], matrix.depth_ablation_max_nodes)
            self.assertGreater(cell["max_nodes"], matrix.default_max_nodes)

    def test_each_depth_appears_once_per_model_and_seed(self):
        matrix = RunMatrix()
        graph_cells = [c for c in matrix.cells() if c["condition"] == CONDITION_GRAPH]
        expected = len(matrix.depths) * len(matrix.models) * len(matrix.seeds)
        self.assertEqual(len(graph_cells), expected)

    def test_more_than_one_model_family_is_configured(self):
        matrix = RunMatrix()
        providers = {MODELS[key].provider for key in matrix.models}
        self.assertGreater(len(providers), 1)

    def test_the_matrix_is_frozen(self):
        with self.assertRaises(Exception):
            RunMatrix().budget_tokens = 99


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class CostEstimateTests(unittest.TestCase):
    def test_the_full_matrix_costs_more_than_a_single_model(self):
        both = estimate_cost(RunMatrix())
        single = estimate_cost(RunMatrix(models=("primary",)))
        self.assertGreater(both.usd, single.usd)
        self.assertEqual(both.runs, single.runs * 2)

    def test_cost_scales_with_the_number_of_tasks(self):
        small = estimate_cost(RunMatrix(tasks=10))
        large = estimate_cost(RunMatrix(tasks=100))
        self.assertAlmostEqual(large.usd / small.usd, 10.0, places=4)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class PowerAnalysisTests(unittest.TestCase):
    def test_no_discordant_pairs_is_not_significant(self):
        self.assertEqual(mcnemar_p(0, 0), 1.0)

    def test_a_lopsided_split_is_significant(self):
        self.assertLess(mcnemar_p(30, 4), 0.05)

    def test_an_even_split_is_not_significant(self):
        self.assertGreater(mcnemar_p(15, 15), 0.05)

    def test_power_rises_with_the_size_of_the_effect(self):
        small = simulate_power(184, 0.30, 0.03, 0.7, 0.05, 400, 0)
        large = simulate_power(184, 0.30, 0.20, 0.7, 0.05, 400, 0)
        self.assertLess(small, large)

    def test_power_rises_with_the_number_of_tasks(self):
        few = simulate_power(40, 0.30, 0.08, 0.7, 0.05, 400, 0)
        many = simulate_power(400, 0.30, 0.08, 0.7, 0.05, 400, 0)
        self.assertLess(few, many)

    def test_a_ten_point_effect_is_detectable_at_the_benchmark_size(self):
        self.assertGreaterEqual(simulate_power(184, 0.30, 0.10, 0.7, 0.05, 800, 0), 0.75)

    def test_a_three_point_effect_is_not_detectable_at_the_benchmark_size(self):
        self.assertLess(simulate_power(184, 0.30, 0.03, 0.7, 0.05, 800, 0), 0.40)


if __name__ == "__main__":
    unittest.main()
