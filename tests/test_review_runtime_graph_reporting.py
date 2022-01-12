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
                "relative_path": "src/app.py",
                "line_range": [1, 42],
                "metadata": {"dependencies": ["src/lib.py::file::lib.py"], "total_lines": 42, "language": "python"},
            },
            "src/lib.py::file::lib.py": {
                "type": "file",
                "name": "lib.py",
                "relative_path": "src/lib.py",
                "line_range": [1, 10],
                "metadata": {"dependencies": [], "total_lines": 10, "language": "python"},
            },
            "src/app.py::class::Service": {
                "type": "class",
                "name": "Service",
                "relative_path": "src/app.py",
                "line_range": [5, 25],
                "metadata": {"parent_classes": [], "variables": ["client", "client"]},
            },
            "src/app.py::function::run": {
                "type": "function",
                "name": "run",
                "relative_path": "src/app.py",
                "line_range": [10, 18],
                "metadata": {
                    "parent_class": "Service",
                    "calls": ["src/lib.py::function::helper"],
                    "parameters": [{"name": "payload"}, {"name": "payload"}],
                    "reads": {"config": {"DEBUG"}},
                    "writes": {"cache": {"SET"}},
                },
            },
            "src/lib.py::function::helper": {
                "type": "function",
                "name": "helper",
                "relative_path": "src/lib.py",
                "line_range": [1, 8],
                "metadata": {"parent_class": None, "calls": [], "parameters": [], "reads": {}, "writes": {}},
            },
            "src/app.py::variable::client": {
                "type": "variable",
                "name": "client",
                "relative_path": "src/app.py",
                "line_range": [6, 6],
                "metadata": {
                    "accessed_by": {"src/app.py::function::run"},
                    "modified_by": set(),
                    "var_type": "HttpClient",
                },
            },
        }
        self.nodes = FakeNodeView(self._nodes)
        self._successors = {"src/app.py::class::Service": ["src/app.py::function::run"]}
        self.edges = [("a", "b"), ("b", "c")]

    def successors(self, node_id):
        return iter(self._successors.get(node_id, []))


class GraphUtilityTests(unittest.TestCase):
    def test_gather_files_filters_supported_code_extensions(self):
        module = build_graph_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
            Path(tmpdir, "src", "app.py").write_text("print('hi')\n", encoding="utf-8")
            Path(tmpdir, "src", "helper.js").write_text("export const x = 1;\n", encoding="utf-8")
            Path(tmpdir, "README.md").write_text("# Demo\n", encoding="utf-8")

            all_paths, code_files = module.gather_files(tmpdir, {".py", ".js"})

        self.assertIn("src/app.py", all_paths)
        self.assertIn("src/helper.js", code_files)
        self.assertNotIn("README.md", code_files)

    def test_parse_code_files_collects_tags_and_skips_missing_files(self):
        module = build_graph_module()
