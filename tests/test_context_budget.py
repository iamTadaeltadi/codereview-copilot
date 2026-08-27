import unittest

try:
    from Utils.ContextBudget import ContextBudget, estimate_tokens

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class EstimateTokensTests(unittest.TestCase):
    def test_empty_text_costs_nothing(self):
        self.assertEqual(estimate_tokens(""), 0)

    def test_longer_text_costs_more(self):
        self.assertGreater(estimate_tokens("x" * 400), estimate_tokens("x" * 40))


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class ContextBudgetTests(unittest.TestCase):
    def test_entries_are_accepted_until_the_budget_runs_out(self):
        budget = ContextBudget(max_tokens=20)
        kept = budget.fill([{"body": "word " * 8} for _ in range(20)])
        self.assertGreater(len(kept), 0)
        self.assertLess(len(kept), 20)
        self.assertLessEqual(budget.used_tokens, 20)

    def test_a_zero_budget_keeps_nothing(self):
        budget = ContextBudget(max_tokens=0)
        self.assertEqual(budget.fill([{"body": "anything"}]), [])
        self.assertEqual(budget.used_tokens, 0)

    def test_an_entry_larger_than_the_budget_is_rejected_whole(self):
        budget = ContextBudget(max_tokens=5)
        self.assertFalse(budget.offer({"body": "word " * 200}))
        self.assertEqual(budget.entries, [])
        self.assertEqual(budget.rejected, 1)

    def test_reserve_is_withheld_from_the_usable_budget(self):
        plain = ContextBudget(max_tokens=100)
        reserved = ContextBudget(max_tokens=100, reserve_tokens=80)
        self.assertEqual(plain.available, 100)
        self.assertEqual(reserved.available, 20)

    def test_two_different_candidate_sets_stop_at_the_same_ceiling(self):
        graph_like = ContextBudget(max_tokens=60)
        random_like = ContextBudget(max_tokens=60)
        graph_like.fill([{"name": f"graph_node_{i}"} for i in range(200)])
        random_like.fill([{"name": f"random_node_{i}"} for i in range(200)])
        self.assertLessEqual(graph_like.used_tokens, 60)
        self.assertLessEqual(random_like.used_tokens, 60)
        self.assertLessEqual(abs(graph_like.used_tokens - random_like.used_tokens), 6)

    def test_report_accounts_for_every_candidate(self):
        budget = ContextBudget(max_tokens=30)
        budget.fill([{"body": "word " * 10} for _ in range(10)])
        report = budget.report()
        self.assertEqual(report["entries_kept"] + report["entries_rejected"], 10)
        self.assertEqual(report["budget_tokens"], 30)
        self.assertEqual(report["used_tokens"] + report["remaining_tokens"], 30)

    def test_a_negative_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            ContextBudget(max_tokens=-1)


if __name__ == "__main__":
    unittest.main()
