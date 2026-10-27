"""The repaired c-CRAB retrieval: code in every condition, seeds from the diff,
callers found through attribute calls, aliases, re-exports and inheritance.

Each test pins one fix. The graphs are built from in-memory sources with the
same builder the experiment uses, so a regression in the builder fails here
before it reaches a run.
"""

import json
import textwrap
import unittest
import urllib.error
from types import SimpleNamespace

try:
    from experiments.sparse import graph_from_sources
    from codecontext.retriever import entity_source, retrieve_node_context
    from Utils.ToolOrganizer import (
        CONDITION_GRAPH, CONDITION_LEXICAL, CONDITION_RANDOM, ENTRY_FIELDS, PAYLOAD_FIELDS, build_tools,
    )
    from experiments.run import ENTITY_TYPES, changed_ranges, seed_queries, split_payload

    _AVAILABLE = True
except Exception:  # pragma: no cover
    _AVAILABLE = False


def src(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


REPO = {
    "pkg/__init__.py": src("""
        from .util import helper
        from . import engine
    """),
    "pkg/util.py": src("""
        def helper(x):
            return x + 1

        def shared():
            return 1
    """),
    "pkg/engine.py": src("""
        import pkg.util as u
        from pkg.util import helper as h


        class Base:
            def template(self):
                return self.step()

            def step(self):
                return 0


        def run(values):
            total = len(values)
            for v in values:
                total += u.helper(v)
            return total + h(0)
    """),
    "app/child.py": src("""
        from pkg import helper
        from pkg.engine import Base


        class Child(Base):
            def go(self):
                self.template()
                return helper(2)


        def ambiguous_caller(obj):
            return obj.shared()
    """),
    "other/dup.py": src("""
        def shared():
            return 2


        def rerun(values):
            return list(values)
    """),
}


def edges(graph, label="calls"):
    return {(u, v) for u, v, d in graph.edges(data=True) if d.get("label") == label}


@unittest.skipUnless(_AVAILABLE, "graph service deps not installed")
class BuilderResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = graph_from_sources(REPO)
        cls.calls = edges(cls.graph)

    def test_attribute_call_through_a_module_alias_resolves_to_the_imported_file(self):
        self.assertIn(("pkg/engine.py::function::run", "pkg/util.py::function::helper"), self.calls)

    def test_a_from_import_alias_resolves_to_the_original_name(self):
        # `from pkg.util import helper as h; h(0)` is the same edge as above
        self.assertIn(("pkg/engine.py::function::run", "pkg/util.py::function::helper"), self.calls)

    def test_a_name_re_exported_by_an_init_file_resolves_to_where_it_is_defined(self):
        self.assertIn(("app/child.py::function::go", "pkg/util.py::function::helper"), self.calls)

    def test_self_method_call_resolves_within_the_class_file(self):
        self.assertIn(("pkg/engine.py::function::template", "pkg/engine.py::function::step"), self.calls)

    def test_self_method_call_resolves_to_an_inherited_method_in_another_file(self):
        self.assertIn(("app/child.py::class::Child", "pkg/engine.py::class::Base"), edges(self.graph, "inherits_from"))
        self.assertIn(("app/child.py::function::go", "pkg/engine.py::function::template"), self.calls)

    def test_an_ambiguous_name_on_an_unknown_receiver_is_left_unresolved(self):
        # `shared` is defined in two files neither of which app/child.py imports
        targets = {v for u, v in self.calls if u == "app/child.py::function::ambiguous_caller"}
        self.assertEqual(targets, set())
        self.assertIn("obj.shared", self.graph.nodes["app/child.py::function::ambiguous_caller"]["metadata"]["unresolved_calls"])

    def test_a_builtin_creates_no_node_and_no_edge(self):
        self.assertFalse(any(n.endswith("::function::len") for n in self.graph.nodes))

    def test_no_function_node_exists_without_a_definition(self):
        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "function":
                defining = [u for u, _, d in self.graph.in_edges(node, data=True) if d.get("label") == "contains"]
                self.assertTrue(defining, f"{node} has no defining file or class")

    def test_import_edges_follow_dotted_packages(self):
        self.assertIn(("pkg/engine.py", "pkg/util.py"), edges(self.graph, "imports"))
        self.assertIn(("app/child.py", "pkg/engine.py"), edges(self.graph, "imports"))

    def test_sources_are_kept_and_an_entity_is_trimmed_to_its_line_range(self):
        self.assertEqual(self.graph.graph["sources"]["pkg/util.py"], REPO["pkg/util.py"])
        text = entity_source(self.graph, "pkg/util.py::function::helper")
        self.assertEqual(text, "def helper(x):\n    return x + 1")

    def test_a_long_entity_is_cut_at_the_line_cap(self):
        text = entity_source(self.graph, "pkg/engine.py::function::run", max_lines=2)
        self.assertEqual(text.count("\n"), 2)
        self.assertIn("more lines", text)


@unittest.skipUnless(_AVAILABLE, "graph service deps not installed")
class PayloadParityTests(unittest.TestCase):
    """What the model receives differs between conditions only in which
    entities were selected."""

    @classmethod
    def setUpClass(cls):
        cls.graph = graph_from_sources(REPO)
        cls.seeds = "pkg/engine.py::function::run\npkg/engine.py::class::Base"

    def payload(self, condition, **kwargs):
        tools = build_tools(self.graph, "/tmp", condition=condition, budget_tokens=4000,
                            max_neighbors=20, entity_types=ENTITY_TYPES, **kwargs)
        return json.loads(tools[0].invoke({"node": self.seeds}))

    def conditions(self):
        return {
            "B": self.payload(CONDITION_GRAPH),
            "C": self.payload(CONDITION_RANDOM, seed=1),
            "Cx": self.payload(CONDITION_RANDOM, seed=1, prefer_cross_file=True),
            "D": self.payload(CONDITION_LEXICAL),
        }

    def test_every_condition_returns_the_same_payload_fields(self):
        fields = {name: tuple(sorted(p.keys())) for name, p in self.conditions().items()}
        self.assertEqual(set(fields.values()), {tuple(sorted(PAYLOAD_FIELDS))}, fields)

    def test_every_entry_in_every_condition_has_the_same_fields(self):
        for name, p in self.conditions().items():
            self.assertTrue(p["neighbors"], name)
            for entry in p["neighbors"]:
                self.assertEqual(tuple(sorted(entry.keys())), tuple(sorted(ENTRY_FIELDS)), name)

    def test_no_condition_carries_a_line_range_or_metadata_anywhere(self):
        for name, p in self.conditions().items():
            text = json.dumps(p)
            self.assertNotIn("line_range", text, name)
            self.assertNotIn("metadata", text, name)
            self.assertNotIn("depth", text, name)

    def test_every_condition_reports_the_same_seeds(self):
        seeds = {name: p["seeds"] for name, p in self.conditions().items()}
        self.assertEqual(len({json.dumps(s) for s in seeds.values()}), 1, seeds)
        self.assertEqual([s["name"] for s in seeds["B"]], ["run", "Base"])

    def test_each_entry_carries_the_source_of_its_own_entity(self):
        for name, p in self.conditions().items():
            for entry in p["neighbors"]:
                self.assertEqual(entry["source"], entity_source(self.graph, entry["id"], 40), name)

    def test_graph_condition_reaches_the_caller_in_another_file(self):
        names = {e["id"] for e in self.payload(CONDITION_GRAPH)["neighbors"]}
        self.assertIn("app/child.py::class::Child", names)

    def test_random_other_files_never_returns_the_seed_files(self):
        paths = {e["relative_path"] for e in self.conditions()["Cx"]["neighbors"]}
        self.assertNotIn("pkg/engine.py", paths)

    def test_random_matches_the_graph_type_mix_under_the_same_walk(self):
        from collections import Counter
        b = Counter(e["type"] for e in self.payload(CONDITION_GRAPH, prefer_cross_file=True)["neighbors"])
        cx = Counter(e["type"] for e in self.payload(CONDITION_RANDOM, seed=2, prefer_cross_file=True)["neighbors"])
        self.assertEqual(b, cx)


@unittest.skipUnless(_AVAILABLE, "graph service deps not installed")
class DiffSeedTests(unittest.TestCase):
    DIFF = src("""
        diff --git a/pkg/engine.py b/pkg/engine.py
        --- a/pkg/engine.py
        +++ b/pkg/engine.py
        @@ -13,3 +13,3 @@ def run(values):
             total = len(values)
        -    for v in values:
        +    for v in reversed(values):
                 total += u.helper(v)
        diff --git a/pkg/util.py b/pkg/util.py
        --- a/pkg/util.py
        +++ b/pkg/util.py
        @@ -5,2 +5,2 @@
         def shared():
        -    return 1
        +    return 3
    """)

    def test_changed_ranges_are_read_from_the_new_file_side(self):
        self.assertEqual(changed_ranges(self.DIFF), {"pkg/engine.py": [(13, 15)], "pkg/util.py": [(5, 6)]})

    def test_seeds_are_the_entities_the_diff_changes_and_ignore_the_ground_truth(self):
        graph = graph_from_sources(REPO)
        task = SimpleNamespace(diff=self.DIFF, defects=[SimpleNamespace(path="app/child.py", line=6)])
        self.assertEqual(seed_queries(task, graph),
                         ["pkg/engine.py::function::run", "pkg/util.py::function::shared"])

    def test_a_changed_file_without_a_matching_entity_seeds_its_file_node(self):
        graph = graph_from_sources(REPO)
        diff = self.DIFF.replace("@@ -13,3 +13,3 @@ def run(values):", "@@ -1,1 +1,1 @@")
        task = SimpleNamespace(diff=diff, defects=[])
        self.assertEqual(seed_queries(task, graph)[0], "pkg/engine.py")

    def test_every_condition_gets_the_same_seed_string(self):
        graph = graph_from_sources(REPO)
        task = SimpleNamespace(diff=self.DIFF, defects=[])
        seeds = "\n".join(seed_queries(task, graph))
        found = set()
        for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL):
            tools = build_tools(graph, "/tmp", condition=condition, budget_tokens=4000, entity_types=ENTITY_TYPES)
            found.add(json.dumps(json.loads(tools[0].invoke({"node": seeds}))["seeds"]))
        self.assertEqual(len(found), 1)


@unittest.skipUnless(_AVAILABLE, "graph service deps not installed")
class ModelTextTests(unittest.TestCase):
    def test_the_model_never_sees_the_condition_or_the_budget(self):
        graph = graph_from_sources(REPO)
        for condition in (CONDITION_GRAPH, CONDITION_RANDOM, CONDITION_LEXICAL):
            tools = build_tools(graph, "/tmp", condition=condition, budget_tokens=4000, entity_types=ENTITY_TYPES)
            raw = tools[0].invoke({"node": "pkg/engine.py::function::run"})
            text, meta = split_payload(raw)
            shown = json.loads(text)
            self.assertNotIn("condition", shown)
            self.assertNotIn("budget", shown)
            self.assertEqual(meta["condition"], condition)
            self.assertIn("used_tokens", meta["budget"])
            self.assertEqual(shown["neighbors"], json.loads(raw)["neighbors"])


class KnownPathsTests(unittest.TestCase):
    def test_only_listed_paths_are_requested_and_the_files_fetched_are_the_same(self):
        from experiments.sparse import collect_sources
        files = {"pkg/a.py": "from pkg.b import f\nfrom pkg.c import g\n", "pkg/b.py": "def f():\n    pass\n"}
        requested = []

        def opener(url):
            path = url.split("/", 6)[-1]
            requested.append(path)
            if path in files:
                return files[path]
            raise urllib.error.HTTPError(url, 404, "nope", {}, None)

        diff = "diff --git a/pkg/a.py b/pkg/a.py\n"
        guessed = collect_sources("o/r", "c", diff, opener=opener, import_hops=1, workers=1)
        guessed_requests = list(requested); requested.clear()
        listed = collect_sources("o/r", "c", diff, opener=opener, import_hops=1, workers=1,
                                 known_paths=set(files))
        self.assertEqual(guessed, listed)
        self.assertEqual(set(requested), set(files))
        self.assertGreater(len(guessed_requests), len(requested))


if __name__ == "__main__":
    unittest.main()
