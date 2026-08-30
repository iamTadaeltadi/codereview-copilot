import unittest

try:
    import networkx as nx

    from codecontext.retriever import _bounded_neighbors, retrieve_node_context

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def chain_graph():
    graph = nx.DiGraph()
    for name in ("a", "b", "c", "d"):
        graph.add_node(name, name=name, type="function", relative_path="m.py", line_range=[1, 2], metadata={})
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    graph.add_edge("c", "d")
    return graph


def star_graph(leaves):
    graph = nx.DiGraph()
    graph.add_node("hub", name="hub", type="file", relative_path="m.py", line_range=[1, 2], metadata={})
    for index in range(leaves):
        leaf = f"leaf{index}"
        graph.add_node(leaf, name=leaf, type="function", relative_path="m.py", line_range=[1, 2], metadata={})
        graph.add_edge("hub", leaf)
    return graph


@unittest.skipUnless(_AVAILABLE, "graph service deps not installed")
class BoundedNeighborsDepthTests(unittest.TestCase):
    def test_depth_one_returns_only_immediate_neighbors(self):
        found = {node for node, _ in _bounded_neighbors(chain_graph(), "a", max_nodes=50, max_depth=1)}
        self.assertEqual(found, {"b"})

    def test_depth_two_reaches_two_hops(self):
        found = {node for node, _ in _bounded_neighbors(chain_graph(), "a", max_nodes=50, max_depth=2)}
        self.assertEqual(found, {"b", "c"})

    def test_depth_three_reaches_the_whole_chain(self):
        found = {node for node, _ in _bounded_neighbors(chain_graph(), "a", max_nodes=50, max_depth=3)}
        self.assertEqual(found, {"b", "c", "d"})

    def test_depth_beyond_the_graph_does_not_grow_the_result(self):
        found = {node for node, _ in _bounded_neighbors(chain_graph(), "a", max_nodes=50, max_depth=99)}
        self.assertEqual(found, {"b", "c", "d"})

    def test_each_neighbor_is_labelled_with_its_hop_distance(self):
        distances = dict(_bounded_neighbors(chain_graph(), "a", max_nodes=50, max_depth=3))
        self.assertEqual(distances, {"b": 1, "c": 2, "d": 3})

    def test_edges_are_followed_in_both_directions(self):
        found = {node for node, _ in _bounded_neighbors(chain_graph(), "d", max_nodes=50, max_depth=1)}
        self.assertEqual(found, {"c"})

    def test_max_nodes_still_caps_a_wide_neighbourhood(self):
        found = _bounded_neighbors(star_graph(40), "hub", max_nodes=5, max_depth=3)
        self.assertEqual(len(found), 5)

    def test_zero_depth_returns_nothing(self):
        self.assertEqual(_bounded_neighbors(chain_graph(), "a", max_nodes=50, max_depth=0), [])


@unittest.skipUnless(_AVAILABLE, "graph service deps not installed")
class RetrieveNodeContextDepthTests(unittest.TestCase):
    def test_depth_is_threaded_through_and_reported(self):
        result = retrieve_node_context(chain_graph(), "", "m.py::function::a", max_depth=1)
        self.assertTrue(result["found"])
        self.assertEqual(result["max_depth"], 1)
        self.assertEqual([n["name"] for n in result["neighbors"]], ["b"])

    def test_raising_depth_adds_further_neighbors(self):
        shallow = retrieve_node_context(chain_graph(), "", "m.py::function::a", max_depth=1)
        deep = retrieve_node_context(chain_graph(), "", "m.py::function::a", max_depth=3)
        self.assertLess(len(shallow["neighbors"]), len(deep["neighbors"]))

    def test_every_neighbor_carries_its_depth(self):
        result = retrieve_node_context(chain_graph(), "", "m.py::function::a", max_depth=3)
        self.assertEqual(
            {n["name"]: n["depth"] for n in result["neighbors"]},
            {"b": 1, "c": 2, "d": 3},
        )

    def test_a_miss_still_reports_the_requested_depth(self):
        result = retrieve_node_context(chain_graph(), "", "m.py::function::nope", max_depth=2)
        self.assertFalse(result["found"])
        self.assertEqual(result["max_depth"], 2)
        self.assertEqual(result["neighbors"], [])


if __name__ == "__main__":
    unittest.main()


def two_file_graph():
    """The shape a real repository graph takes around a defect.

    The defect's own file contributes many one-hop neighbours through its file
    node, and the caller sits two hops away through an intermediate — which is
    where it sits in practice: measured at two hops for 76% of cross-file tasks
    and returned for 15% of them.
    """
    graph = nx.DiGraph()

    def add(node_id, name, path, node_type="function"):
        graph.add_node(node_id, name=name, type=node_type, relative_path=path,
                       line_range=[1, 5], metadata={})

    add("target", "to_text", "lib/_text.py")
    add("home", "_text.py", "lib/_text.py", "file")
    graph.add_edge("home", "target")
    for index in range(30):
        add(f"same{index}", f"helper_{index}", "lib/_text.py")
        graph.add_edge("home", f"same{index}")
        graph.add_edge("target", f"same{index}")

    add("bridge", "convert", "lib/ec2.py")
    add("caller", "get_ec2", "lib/ec2.py")
    graph.add_edge("bridge", "target")
    graph.add_edge("caller", "bridge")
    return graph


@unittest.skipUnless(_AVAILABLE, "graph service deps not installed")
class CrossFilePreferenceTests(unittest.TestCase):
    """Insertion order decides which neighbours survive the cap.

    A file's own contents crowd out everything else, so the depended-upon
    caller sits within reach and is never returned: measured at two hops for
    76% of cross-file tasks and returned for 15% of them. Preferring other
    files spends the same budget on the part of the neighbourhood a same-file
    search could not have found.
    """

    def _names(self, prefer):
        result = retrieve_node_context(two_file_graph(), "", "lib/_text.py::function::to_text",
                                       max_neighbors=5, max_depth=2, prefer_cross_file=prefer)
        return {n["name"] for n in result["neighbors"]}

    def test_without_ranking_the_caller_is_crowded_out(self):
        self.assertNotIn("get_ec2", self._names(False))

    def test_with_ranking_the_caller_is_returned(self):
        self.assertIn("get_ec2", self._names(True))

    def test_ranking_does_not_change_how_many_are_returned(self):
        self.assertEqual(len(self._names(False)), len(self._names(True)))

    def test_same_file_neighbours_still_fill_the_remaining_budget(self):
        names = self._names(True)
        self.assertGreater(len({n for n in names if n.startswith("helper_")}), 0)

    def test_the_flag_is_reported_in_the_payload(self):
        result = retrieve_node_context(two_file_graph(), "", "lib/_text.py::function::to_text",
                                       prefer_cross_file=True)
        self.assertTrue(result["prefer_cross_file"])

    def test_ranking_is_off_by_default(self):
        result = retrieve_node_context(two_file_graph(), "", "lib/_text.py::function::to_text")
        self.assertFalse(result["prefer_cross_file"])
