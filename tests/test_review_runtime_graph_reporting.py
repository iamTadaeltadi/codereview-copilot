import importlib.util
import json
import os
import pickle
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(module_name: str, relative_path: str, stub_modules=None):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    with patch.dict(sys.modules, stub_modules or {}, clear=False):
        spec.loader.exec_module(module)
    return module


def build_graph_module():
    codecontext_package = types.ModuleType("codecontext")
    construct_graph_module = types.ModuleType("codecontext.construct_graph")

    class FakeCodeGraph:
        def __init__(self, root):
            self.root = root
            self.all_source_files = []
            self._parse_results = []

        def parse_code_string(self, code_string, path):
            return [{"path": path, "size": len(code_string)}]

        def tag_to_graph(self, tags):
            return {"graph_tags": tags, "root": self.root}

    construct_graph_module.CodeGraph = FakeCodeGraph
    return load_module(
        "graph_utils_module",
        "agent_runtime/Utils/Graph.py",
        {
            "codecontext": codecontext_package,
            "codecontext.construct_graph": construct_graph_module,
        },
    )


def build_html_report_module():
    return load_module("html_report_module", "agent_runtime/Utils/HTMLReport.py")


def build_markdown_module():
    return load_module("markdown_report_module", "agent_runtime/Utils/MDReport.py")


class FakeNodeView:
    def __init__(self, data):
        self._data = data

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, key):
        return self._data[key]


class FakeGraph:
    def __init__(self):
        self._nodes = {
            "src/app.py::file::app.py": {
                "type": "file",
                "name": "app.py",
