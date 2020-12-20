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
