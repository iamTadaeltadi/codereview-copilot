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
