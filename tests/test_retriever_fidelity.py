import unittest

try:
    import networkx as nx

    from codecontext.retriever import _bounded_neighbors, retrieve_node_context

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def sample_graph():
    graph = nx.DiGraph()

    def add(node_id, name, node_type, path):
        graph.add_node(node_id, name=name, type=node_type, relative_path=path, line_range=[1, 5], metadata={})

    add("c:Order", "Order", "class", "orders.py")
    add("fn:total", "total", "function", "orders.py")
    add("fn:tax", "tax", "function", "tax.py")
    add("fn:round_cents", "round_cents", "function", "money.py")
    add("fn:caller", "checkout", "function", "views.py")

    graph.add_edge("c:Order", "fn:total")
    graph.add_edge("fn:total", "fn:tax")
    graph.add_edge("fn:tax", "fn:round_cents")
    graph.add_edge("fn:caller", "c:Order")
    return graph


@unittest.skipUnless(_AVAILABLE, "graph service deps not installed")
class EgoGraphSemanticsTests(unittest.TestCase):
    """RepoGraph retrieves an ego-graph centred on a matched entity.

    These pin the properties that make this retriever a faithful ego-graph
    retrieval rather than an arbitrary walk. If a result in the paper is
    negative, it has to be attributable to graph retrieval as a technique and
    not to a private deviation in this implementation.
    """

    def test_the_centre_node_is_never_returned_as_its_own_neighbour(self):
        result = retrieve_node_context(sample_graph(), "", "orders.py::class::Order", max_depth=3)
        self.assertNotIn("Order", [n["name"] for n in result["neighbors"]])

    def test_retrieval_follows_incoming_edges_as_well_as_outgoing(self):
        found = {n for n, _ in _bounded_neighbors(sample_graph(), "c:Order", max_nodes=50, max_depth=1)}
        self.assertIn("fn:total", found)
        self.assertIn("fn:caller", found)

    def test_depth_one_is_exactly_the_direct_neighbourhood(self):
        graph = sample_graph()
        found = {n for n, _ in _bounded_neighbors(graph, "c:Order", max_nodes=50, max_depth=1)}
        expected = set(graph.predecessors("c:Order")) | set(graph.successors("c:Order"))
        self.assertEqual(found, expected)

    def test_depth_k_equals_the_set_of_nodes_within_k_undirected_hops(self):
        graph = sample_graph()
        undirected = graph.to_undirected()
        for depth in (1, 2, 3):
            with self.subTest(depth=depth):
                found = {n for n, _ in _bounded_neighbors(graph, "c:Order", max_nodes=500, max_depth=depth)}
                expected = {
                    node
                    for node, distance in nx.single_source_shortest_path_length(
                        undirected, "c:Order", cutoff=depth
                    ).items()
                    if node != "c:Order"
                }
                self.assertEqual(found, expected)

    def test_the_reported_depth_is_the_true_shortest_path_length(self):
        graph = sample_graph()
        undirected = graph.to_undirected()
        truth = nx.single_source_shortest_path_length(undirected, "c:Order")
        for node, depth in _bounded_neighbors(graph, "c:Order", max_nodes=500, max_depth=4):
            with self.subTest(node=node):
                self.assertEqual(depth, truth[node])

    def test_retrieval_crosses_file_boundaries(self):
        result = retrieve_node_context(
            sample_graph(), "", "orders.py::class::Order", max_neighbors=50, max_depth=3
        )
        self.assertIn("tax.py", {n["relative_path"] for n in result["neighbors"]})

    def test_a_disconnected_node_returns_an_empty_neighbourhood(self):
        graph = sample_graph()
        graph.add_node("c:Alone", name="Alone", type="class", relative_path="alone.py", line_range=[1, 2], metadata={})
        result = retrieve_node_context(graph, "", "alone.py::class::Alone", max_depth=3)
        self.assertTrue(result["found"])
        self.assertEqual(result["neighbors"], [])

    def test_retrieval_is_deterministic_for_the_same_graph_and_query(self):
        first = retrieve_node_context(sample_graph(), "", "orders.py::class::Order", max_depth=2)
        second = retrieve_node_context(sample_graph(), "", "orders.py::class::Order", max_depth=2)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
