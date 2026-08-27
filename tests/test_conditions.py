import json
import unittest

try:
    import networkx as nx

    from Utils.ToolOrganizer import (
        CONDITION_GRAPH,
        CONDITION_LEXICAL,
        CONDITION_NONE,
        CONDITION_RANDOM,
        CONDITION_WHOLE_FILE,
        build_tools,
    )

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def repo_graph():
    graph = nx.DiGraph()

    def add(node_id, name, node_type, path):
        graph.add_node(node_id, name=name, type=node_type, relative_path=path, line_range=[1, 5], metadata={})

    add("f:models", "models.py", "file", "models.py")
    add("c:Review", "Review", "class", "models.py")
    add("c:User", "User", "class", "models.py")
    add("fn:review_summary", "review_summary", "function", "models.py")
    add("fn:review_detail", "review_detail", "function", "views.py")
    add("fn:unrelated", "shipping_label", "function", "billing.py")
    for index in range(30):
        add(f"v:{index}", f"var_{index}", "variable", "models.py")
        graph.add_edge("f:models", f"v:{index}")

    graph.add_edge("f:models", "c:Review")
    graph.add_edge("f:models", "c:User")
    graph.add_edge("c:Review", "fn:review_summary")
    return graph


QUERY = "models.py::class::Review"


def call(tools, query=QUERY):
    return json.loads(tools[0].invoke({"node": query}))


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class ConditionSwitchTests(unittest.TestCase):
    def test_condition_a_supplies_no_tool(self):
        self.assertEqual(build_tools(repo_graph(), "/tmp", condition=CONDITION_NONE), [])

    def test_condition_e_supplies_no_tool(self):
        self.assertEqual(build_tools(repo_graph(), "/tmp", condition=CONDITION_WHOLE_FILE), [])

    def test_conditions_b_c_and_d_each_supply_exactly_one_tool(self):
        for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL):
            with self.subTest(condition=condition):
                self.assertEqual(len(build_tools(repo_graph(), "/tmp", condition=condition)), 1)

    def test_the_tool_name_is_identical_across_conditions(self):
        names = {
            build_tools(repo_graph(), "/tmp", condition=condition)[0].name
            for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL)
        }
        self.assertEqual(names, {"retrieve_graph"})

    def test_an_unknown_condition_is_rejected(self):
        with self.assertRaises(ValueError):
            build_tools(repo_graph(), "/tmp", condition="Z")

    def test_every_condition_reports_which_one_it_is(self):
        for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL):
            with self.subTest(condition=condition):
                tools = build_tools(repo_graph(), "/tmp", condition=condition)
                self.assertEqual(call(tools)["condition"], condition)


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class BudgetParityTests(unittest.TestCase):
    def test_no_condition_exceeds_the_budget(self):
        for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL):
            with self.subTest(condition=condition):
                tools = build_tools(repo_graph(), "/tmp", condition=condition, budget_tokens=120)
                report = call(tools)["budget"]
                self.assertLessEqual(report["used_tokens"], 120)
                self.assertEqual(report["budget_tokens"], 120)

    def test_a_tight_budget_reduces_what_is_returned(self):
        wide = build_tools(repo_graph(), "/tmp", condition=CONDITION_GRAPH, budget_tokens=4000)
        tight = build_tools(repo_graph(), "/tmp", condition=CONDITION_GRAPH, budget_tokens=40)
        self.assertGreater(len(call(wide)["neighbors"]), len(call(tight)["neighbors"]))

    def test_a_zero_budget_returns_no_context_in_any_condition(self):
        for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL):
            with self.subTest(condition=condition):
                tools = build_tools(repo_graph(), "/tmp", condition=condition, budget_tokens=0)
                self.assertEqual(call(tools)["neighbors"], [])


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class ConditionBehaviourTests(unittest.TestCase):
    def test_graph_condition_returns_structural_neighbours(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_GRAPH, max_depth=1, budget_tokens=4000)
        names = {n["name"] for n in call(tools)["neighbors"]}
        self.assertIn("review_summary", names)
        self.assertIn("models.py", names)

    def test_depth_one_excludes_a_two_hop_sibling(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_GRAPH, max_depth=1, budget_tokens=4000)
        self.assertNotIn("User", {n["name"] for n in call(tools)["neighbors"]})

    def test_depth_two_includes_the_two_hop_sibling(self):
        tools = build_tools(
            repo_graph(),
            "/tmp",
            condition=CONDITION_GRAPH,
            max_depth=2,
            max_neighbors=60,
            budget_tokens=8000,
        )
        self.assertIn("User", {n["name"] for n in call(tools)["neighbors"]})

    def test_a_hub_node_saturates_the_cap_before_reaching_a_sibling_class(self):
        tools = build_tools(
            repo_graph(),
            "/tmp",
            condition=CONDITION_GRAPH,
            max_depth=2,
            max_neighbors=12,
            budget_tokens=8000,
        )
        names = {n["name"] for n in call(tools)["neighbors"]}
        self.assertNotIn("User", names)
        self.assertGreaterEqual(len([n for n in names if n.startswith("var_")]), 8)

    def test_random_condition_is_reproducible_for_a_seed(self):
        first = build_tools(repo_graph(), "/tmp", condition=CONDITION_RANDOM, seed=7, budget_tokens=4000)
        second = build_tools(repo_graph(), "/tmp", condition=CONDITION_RANDOM, seed=7, budget_tokens=4000)
        self.assertEqual(call(first)["neighbors"], call(second)["neighbors"])

    def test_a_different_seed_gives_a_different_sample(self):
        first = build_tools(repo_graph(), "/tmp", condition=CONDITION_RANDOM, seed=1, budget_tokens=4000)
        second = build_tools(repo_graph(), "/tmp", condition=CONDITION_RANDOM, seed=2, budget_tokens=4000)
        self.assertNotEqual(call(first)["neighbors"], call(second)["neighbors"])

    def test_random_condition_matches_the_graph_node_type_mix(self):
        graph_tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_GRAPH, budget_tokens=4000)
        random_tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_RANDOM, seed=3, budget_tokens=4000)
        from collections import Counter

        graph_mix = Counter(n["type"] for n in call(graph_tools)["neighbors"])
        random_mix = Counter(n["type"] for n in call(random_tools)["neighbors"])
        self.assertEqual(graph_mix, random_mix)

    def test_lexical_condition_matches_on_the_name_not_the_edges(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_LEXICAL, budget_tokens=4000)
        names = {n["name"] for n in call(tools)["neighbors"]}
        self.assertIn("review_detail", names)
        self.assertNotIn("shipping_label", names)

    def test_lexical_condition_reaches_across_files(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_LEXICAL, budget_tokens=4000)
        paths = {n["relative_path"] for n in call(tools)["neighbors"]}
        self.assertIn("views.py", paths)

    def test_a_missing_node_is_reported_not_raised(self):
        for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL):
            with self.subTest(condition=condition):
                tools = build_tools(repo_graph(), "/tmp", condition=condition, budget_tokens=4000)
                result = call(tools, "nope.py::class::Missing")
                self.assertFalse(result["found"])
                self.assertEqual(result["neighbors"], [])


if __name__ == "__main__":
    unittest.main()


try:
    from Utils.ToolOrganizer import CONDITION_DENSE, CONDITION_ORACLE, hashing_embedder
except Exception:
    pass


ORACLE_TARGETS = [{"path": "views.py", "line": 3}]


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class DenseConditionTests(unittest.TestCase):
    def test_the_tool_is_indistinguishable_from_the_others(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_DENSE)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "retrieve_graph")

    def test_it_reports_its_condition(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_DENSE, budget_tokens=4000)
        self.assertEqual(call(tools)["condition"], CONDITION_DENSE)

    def test_it_respects_the_shared_budget(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_DENSE, budget_tokens=120)
        self.assertLessEqual(call(tools)["budget"]["used_tokens"], 120)

    def test_it_ranks_by_similarity_and_reports_the_score(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_DENSE, budget_tokens=4000)
        neighbors = call(tools)["neighbors"]
        self.assertTrue(neighbors)
        self.assertIn("score", neighbors[0])
        scores = [n["score"] for n in neighbors]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_it_is_deterministic(self):
        first = build_tools(repo_graph(), "/tmp", condition=CONDITION_DENSE, budget_tokens=4000)
        second = build_tools(repo_graph(), "/tmp", condition=CONDITION_DENSE, budget_tokens=4000)
        self.assertEqual(call(first)["neighbors"], call(second)["neighbors"])

    def test_a_supplied_embedder_is_used_instead_of_the_default(self):
        calls = []

        def counting_embedder(text, dimensions=256):
            calls.append(text)
            return hashing_embedder(text, dimensions)

        tools = build_tools(
            repo_graph(), "/tmp", condition=CONDITION_DENSE, budget_tokens=4000, embed_fn=counting_embedder
        )
        call(tools)
        self.assertTrue(calls)

    def test_it_finds_a_name_related_node_across_files(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_DENSE, budget_tokens=4000)
        names = {n["name"] for n in call(tools)["neighbors"]}
        self.assertTrue(names & {"review_summary", "review_detail"})


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class OracleConditionTests(unittest.TestCase):
    def test_the_tool_is_indistinguishable_from_the_others(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_ORACLE, oracle_targets=ORACLE_TARGETS)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "retrieve_graph")

    def test_it_returns_the_node_covering_the_target_line(self):
        tools = build_tools(
            repo_graph(), "/tmp", condition=CONDITION_ORACLE, oracle_targets=ORACLE_TARGETS, budget_tokens=4000
        )
        names = {n["name"] for n in call(tools)["neighbors"]}
        self.assertEqual(names, {"review_detail"})

    def test_a_target_in_another_file_is_not_returned(self):
        tools = build_tools(
            repo_graph(),
            "/tmp",
            condition=CONDITION_ORACLE,
            oracle_targets=[{"path": "billing.py", "line": 3}],
            budget_tokens=4000,
        )
        names = {n["name"] for n in call(tools)["neighbors"]}
        self.assertEqual(names, {"shipping_label"})

    def test_a_line_outside_every_span_returns_nothing(self):
        tools = build_tools(
            repo_graph(),
            "/tmp",
            condition=CONDITION_ORACLE,
            oracle_targets=[{"path": "views.py", "line": 9999}],
            budget_tokens=4000,
        )
        self.assertEqual(call(tools)["neighbors"], [])

    def test_with_no_targets_it_supplies_no_context(self):
        tools = build_tools(repo_graph(), "/tmp", condition=CONDITION_ORACLE, budget_tokens=4000)
        result = call(tools)
        self.assertEqual(result["neighbors"], [])
        self.assertEqual(result["oracle_targets"], 0)

    def test_it_respects_the_shared_budget(self):
        tools = build_tools(
            repo_graph(), "/tmp", condition=CONDITION_ORACLE, oracle_targets=ORACLE_TARGETS, budget_tokens=0
        )
        self.assertEqual(call(tools)["neighbors"], [])

    def test_it_reports_its_condition_so_a_ceiling_run_is_never_mistaken_for_a_real_one(self):
        tools = build_tools(
            repo_graph(), "/tmp", condition=CONDITION_ORACLE, oracle_targets=ORACLE_TARGETS, budget_tokens=4000
        )
        self.assertEqual(call(tools)["condition"], CONDITION_ORACLE)


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class ConditionIsolationTests(unittest.TestCase):
    def test_no_honest_condition_can_see_the_answer_key(self):
        for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL, CONDITION_DENSE):
            with self.subTest(condition=condition):
                tools = build_tools(
                    repo_graph(),
                    "/tmp",
                    condition=condition,
                    oracle_targets=ORACLE_TARGETS,
                    budget_tokens=4000,
                )
                self.assertNotIn("oracle_targets", call(tools))

    def test_every_condition_returns_the_same_payload_shape(self):
        shapes = []
        for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL, CONDITION_DENSE):
            tools = build_tools(repo_graph(), "/tmp", condition=condition, budget_tokens=4000)
            result = call(tools)
            shapes.append({"query", "found", "condition", "node", "neighbors", "budget"} <= set(result))
        self.assertTrue(all(shapes))


def wide_graph(classes=120):
    graph = nx.DiGraph()

    def add(node_id, name, node_type, path):
        graph.add_node(node_id, name=name, type=node_type, relative_path=path,
                       line_range=[1, 5], metadata={})

    add("f", "models.py", "file", "models.py")
    add("target", "Review", "class", "models.py")
    graph.add_edge("f", "target")
    for index in range(classes):
        add(f"c{index}", f"Review{index}", "class", "models.py")
        graph.add_edge("f", f"c{index}")
        add(f"v{index}", f"variable_number_{index}", "variable", "models.py")
        graph.add_edge(f"c{index}", f"v{index}")
    return graph


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class BudgetParityTests(unittest.TestCase):
    """The delivered string is what must be equal, not the entry list.

    Budgeting the entries alone let condition B deliver roughly twice the text
    of G, because each condition wraps its entries differently and B's entries
    carry extra fields. That is the confound this study exists to remove, so it
    is pinned here.
    """

    CONDITIONS = (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL, CONDITION_DENSE)

    def _usage(self, budget_tokens):
        graph = wide_graph()
        out = {}
        for condition in self.CONDITIONS:
            tools = build_tools(graph, "/tmp", condition=condition,
                                budget_tokens=budget_tokens, seed=1, max_neighbors=150)
            payload = call(tools)
            out[condition] = payload["budget"]
            out[condition]["chars"] = len(json.dumps(payload))
        return out

    def test_no_condition_exceeds_the_budget(self):
        for budget in (300, 800, 1500):
            for condition, report in self._usage(budget).items():
                with self.subTest(budget=budget, condition=condition):
                    self.assertLessEqual(report["used_tokens"], budget)

    def test_every_condition_uses_almost_all_of_the_budget(self):
        for budget in (300, 800, 1500):
            for condition, report in self._usage(budget).items():
                with self.subTest(budget=budget, condition=condition):
                    self.assertGreater(report["used_tokens"], budget * 0.85)

    def test_the_spread_between_conditions_stays_within_a_tenth_of_the_budget(self):
        for budget in (300, 800, 1500):
            used = [r["used_tokens"] for r in self._usage(budget).values()]
            with self.subTest(budget=budget):
                self.assertLessEqual(max(used) - min(used), budget * 0.10)

    def test_the_graph_arm_never_delivers_much_more_text_than_the_others(self):
        usage = self._usage(1500)
        chars = [r["chars"] for r in usage.values()]
        self.assertLess(max(chars) / min(chars), 1.35)

    def test_conditions_differ_in_entries_kept_not_in_text_delivered(self):
        usage = self._usage(1500)
        kept = {c: r["entries_kept"] for c, r in usage.items()}
        self.assertGreater(max(kept.values()), min(kept.values()))

    def test_rejected_entries_are_accounted_for(self):
        for condition, report in self._usage(300).items():
            with self.subTest(condition=condition):
                self.assertEqual(
                    report["entries_kept"] + report["entries_rejected"],
                    report["entries_offered"],
                )
