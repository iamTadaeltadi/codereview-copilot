import json
import unittest
from unittest.mock import patch

try:
    from Utils import ToolOrganizer as ToolOrganizerModule

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


@unittest.skipUnless(_AVAILABLE, "agent runtime deps not installed")
class ToolOrganizerTests(unittest.TestCase):
    def test_build_retrieve_graph_tool_serializes_retriever_output(self):
        graph = object()
        with patch.object(
            ToolOrganizerModule,
            'retrieve_node_context',
            return_value={'found': True, 'node': {'name': 'process'}, 'neighbors': []},
        ) as mock_retrieve:
            tool_fn = ToolOrganizerModule.build_retrieve_graph_tool(graph, '/tmp/graph-cache')

            payload = json.loads(tool_fn.invoke({'node': 'src/file.py::function::process'}))

        self.assertTrue(payload['found'])
        self.assertEqual(payload['node']['name'], 'process')
        mock_retrieve.assert_called_once_with(
            graph,
            '/tmp/graph-cache/graph.pkl',
            'src/file.py::function::process',
            max_neighbors=ToolOrganizerModule.DEFAULT_MAX_NEIGHBORS,
            max_depth=ToolOrganizerModule.DEFAULT_MAX_DEPTH,
            prefer_cross_file=False,
        )

    def test_the_tool_reports_its_budget_alongside_the_payload(self):
        with patch.object(
            ToolOrganizerModule,
            'retrieve_node_context',
            return_value={'found': True, 'node': {'name': 'process'}, 'neighbors': []},
        ):
            tool_fn = ToolOrganizerModule.build_retrieve_graph_tool(object(), '/tmp/cache', budget_tokens=250)
            payload = json.loads(tool_fn.invoke({'node': 'src/file.py::function::process'}))

        self.assertEqual(payload['budget']['budget_tokens'], 250)
        self.assertEqual(payload['condition'], ToolOrganizerModule.CONDITION_GRAPH)

    def test_build_tools_returns_single_retrieve_graph_tool(self):
        tools = ToolOrganizerModule.build_tools(object(), '/tmp/cache')

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, 'retrieve_graph')

    def test_legacy_retrieve_graph_tool_alias_still_works(self):
        tool_fn = ToolOrganizerModule.retrieve_graph_tool(object(), '/tmp/cache')
        self.assertEqual(tool_fn.name, 'retrieve_graph')

    def test_legacy_tool_organizer_alias_still_works(self):
        tools = ToolOrganizerModule.toolOrganizer(object(), '/tmp/cache')
        self.assertEqual(len(tools), 1)


if __name__ == '__main__':
    unittest.main()


class RandomOtherFilesOnlyTests(unittest.TestCase):
    """With prefer_cross_file, the random arm draws only from other files, so a
    comparison against the graph arm separates retrieval through the graph
    from retrieval from another file."""

    def _graph(self):
        import networkx as nx
        g = nx.DiGraph()
        for i in range(6):
            g.add_node(f"home{i}", name=f"h{i}", type="function", relative_path="a/home.py", line_range=[i, i + 1], metadata={})
        for i in range(6):
            g.add_node(f"other{i}", name=f"o{i}", type="function", relative_path="b/other.py", line_range=[i, i + 1], metadata={})
        g.add_node("target", name="t", type="function", relative_path="a/home.py", line_range=[50, 60], metadata={})
        for i in range(6):
            g.add_edge("target", f"home{i}")
        return g

    def test_other_files_only_never_returns_the_home_file(self):
        import json
        from Utils import ToolOrganizer as T
        tool = T.build_random_context_tool(self._graph(), "/tmp", seed=1, max_neighbors=4, budget_tokens=2000, other_files_only=True)
        out = json.loads(tool.invoke({"node": "a/home.py::function::t"}))
        self.assertTrue(out["neighbors"])
        self.assertTrue(all(n["relative_path"] == "b/other.py" for n in out["neighbors"]))

    def test_default_random_may_return_the_home_file(self):
        import json
        from Utils import ToolOrganizer as T
        tool = T.build_random_context_tool(self._graph(), "/tmp", seed=1, max_neighbors=4, budget_tokens=2000)
        out = json.loads(tool.invoke({"node": "a/home.py::function::t"}))
        self.assertTrue(out["neighbors"])
