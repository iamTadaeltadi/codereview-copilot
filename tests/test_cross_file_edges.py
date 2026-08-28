import unittest

try:
    from experiments.sparse import graph_from_sources

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


SOURCES = {
    "pkg/util.py": "def shout(text):\n    return text.upper()\n\n\ndef helper():\n    return 1\n",
    "pkg/app.py": "from pkg.util import shout\n\n\nclass Runner:\n    def go(self, text):\n        return shout(text)\n",
    "pkg/base.py": "class Base:\n    def run(self):\n        return 1\n",
    "pkg/child.py": "from pkg.base import Base\n\n\nclass Child(Base):\n    def run(self):\n        return 2\n",
}


def cross_file_edges(graph):
    out = []
    for u, v in graph.edges():
        pu = graph.nodes[u].get("relative_path")
        pv = graph.nodes[v].get("relative_path")
        if pu and pv and pu != pv:
            out.append((graph.nodes[u].get("name"), graph.nodes[v].get("name")))
    return out


@unittest.skipUnless(_AVAILABLE, "graph service deps not installed")
class CrossFileResolutionTests(unittest.TestCase):
    """A repository graph with no edges between files is not a repository graph.

    Node keys are namespaced by file, and callees were looked up in the
    caller's own file, so every call and inheritance edge stayed inside one
    file: 8,596 edges across 14 files in a real graph, none of them between
    files. The graph could not supply the cross-file context it exists to
    supply, and any measurement of "graph retrieval" was measuring same-file
    retrieval.
    """

    def setUp(self):
        self.graph = graph_from_sources(SOURCES)
        self.cross = cross_file_edges(self.graph)

    def test_a_call_reaches_a_function_defined_in_another_file(self):
        self.assertIn(("go", "shout"), self.cross)

    def test_inheritance_reaches_a_class_defined_in_another_file(self):
        self.assertIn(("Child", "Base"), self.cross)

    def test_the_graph_has_edges_between_files_at_all(self):
        self.assertGreater(len(self.cross), 0)

    def test_a_local_definition_still_wins_over_an_imported_one(self):
        sources = dict(SOURCES)
        sources["pkg/app.py"] = (
            "from pkg.util import shout\n\n\n"
            "def shout(text):\n    return text\n\n\n"
            "def go(text):\n    return shout(text)\n"
        )
        graph = graph_from_sources(sources)
        edges = [
            (u, v) for u, v in graph.edges()
            if graph.nodes[u].get("name") == "go" and graph.nodes[v].get("name") == "shout"
        ]
        self.assertTrue(edges)
        for _, v in edges:
            self.assertEqual(graph.nodes[v]["relative_path"], "pkg/app.py")

    def test_an_ambiguous_name_is_not_linked_across_files_by_guessing(self):
        sources = {
            "a/one.py": "def process():\n    return 1\n",
            "b/two.py": "def process():\n    return 2\n",
            "c/caller.py": "def run():\n    return process()\n",
        }
        graph = graph_from_sources(sources)
        for name_u, name_v in cross_file_edges(graph):
            self.assertNotEqual((name_u, name_v), ("run", "process"))

    def test_an_unresolved_callee_does_not_crash_the_build(self):
        graph = graph_from_sources({"a.py": "def run():\n    return nowhere_at_all()\n"})
        self.assertGreater(len(graph.nodes), 0)


if __name__ == "__main__":
    unittest.main()
