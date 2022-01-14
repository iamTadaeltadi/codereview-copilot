import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def ensure_stub_modules():
    if 'langchain.tools' not in sys.modules:
        langchain_module = types.ModuleType('langchain')
        tools_module = types.ModuleType('langchain.tools')

        def tool(fn):
            fn.name = fn.__name__
            return fn

        tools_module.tool = tool
        sys.modules['langchain'] = langchain_module
        sys.modules['langchain.tools'] = tools_module

    if 'codecontext.retriever' not in sys.modules:
        codecontext_module = types.ModuleType('codecontext')
        retriever_module = types.ModuleType('codecontext.retriever')

        def retrieve_node_context(graph, graph_path, node):
            return {'graph_path': graph_path, 'node': node, 'found': True}

        retriever_module.retrieve_node_context = retrieve_node_context
        sys.modules['codecontext'] = codecontext_module
        sys.modules['codecontext.retriever'] = retriever_module


def load_tool_organizer_module():
    ensure_stub_modules()
    spec = importlib.util.spec_from_file_location(
        'tool_organizer_module', ROOT / 'agent_runtime/Utils/ToolOrganizer.py'
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ToolOrganizerModule = load_tool_organizer_module()


class ToolOrganizerTests(unittest.TestCase):
    def test_build_retrieve_graph_tool_serializes_retriever_output(self):
        graph = object()
        with patch.object(
            ToolOrganizerModule,
            'retrieve_node_context',
            return_value={'found': True, 'node': {'name': 'process'}},
        ) as mock_retrieve:
            tool_fn = ToolOrganizerModule.build_retrieve_graph_tool(graph, '/tmp/graph-cache')

            payload = json.loads(tool_fn('src/file.py::function::process'))

        self.assertTrue(payload['found'])
        self.assertEqual(payload['node']['name'], 'process')
        mock_retrieve.assert_called_once_with(graph, '/tmp/graph-cache/graph.pkl', 'src/file.py::function::process')

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
