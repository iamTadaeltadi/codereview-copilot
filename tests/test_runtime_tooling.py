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
