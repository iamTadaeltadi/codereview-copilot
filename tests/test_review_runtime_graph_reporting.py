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
        code_graph = types.SimpleNamespace(parse_code_string=Mock(return_value=[{"tag": "ok"}]))

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "existing.py").write_text("print('ok')\n", encoding="utf-8")
            tags = module.parse_code_files(code_graph, tmpdir, ["existing.py", "missing.py"])

        self.assertEqual(tags, [{"tag": "ok"}])
        code_graph.parse_code_string.assert_called_once()

    def test_generate_code_tags_summarizes_file_class_function_and_variable_nodes(self):
        module = build_graph_module()
        tags = module.generate_code_tags(FakeGraph())

        file_tag = next(tag for tag in tags if tag["Node_type"] == "file")
        class_tag = next(tag for tag in tags if tag["Node_type"] == "class")
        function_tag = next(tag for tag in tags if tag["Node_type"] == "function" and tag["name"] == "run")
        variable_tag = next(tag for tag in tags if tag["Node_type"] == "variable")

        self.assertIn("src/lib.py", file_tag["Info"]["related_files"])
        self.assertEqual(class_tag["Info"]["methods"], ["run"])
        self.assertEqual(function_tag["Info"]["Parameters"], [{"name": "payload"}])
        self.assertEqual(variable_tag["Info"]["var_type"], "HttpClient")

    def test_generate_code_graph_uses_gather_parse_and_tag_pipeline(self):
        module = build_graph_module()
        fake_code_graph = types.SimpleNamespace(all_source_files=[], tag_to_graph=Mock(return_value={"built": True}))

        with patch.object(module, "gather_files", return_value=(["src/app.py", "README.md"], ["src/app.py"])), patch.object(
            module, "parse_code_files", return_value=[{"tag": "ok"}]
        ), patch.object(module, "CodeGraph", return_value=fake_code_graph), patch.object(
            module.os, "getcwd", return_value="/workspace"
        ):
            graph = module.generate_code_graph("./repo")

        self.assertEqual(graph, {"built": True})
        self.assertEqual(fake_code_graph.all_source_files, ["src/app.py", "README.md"])
        fake_code_graph.tag_to_graph.assert_called_once_with([{"tag": "ok"}])

    def test_print_graph_info_emits_summary_lines(self):
        module = build_graph_module()
        graph = types.SimpleNamespace(nodes=[1, 2, 3], edges=[("a", "b")])

        with patch("builtins.print") as mock_print:
            module.print_graph_info(graph, "./repo")

        self.assertEqual(mock_print.call_count, 5)


class HtmlReportTests(unittest.TestCase):
    def test_generate_html_report_contains_summary_counts_and_file_sections(self):
        module = build_html_report_module()
        review_data = {
            "review": {
                "final": [
                    {
                        "file": "backend/core/views.py",
                        "summary": "Main review summary",
                        "ratings": {"maintainability": "8: good"},
                        "critical_issues": ["Fix auth validation"],
                    }
                ],
                "syntax": [{"issues": [{"file": "backend/core/views.py", "location": 14, "description": "Missing colon"}]}],
                "standards": [{"issues": [{"file": "backend/core/views.py", "location": 20, "standard": "Use snake_case"}]}],
            },
            "artifacts": {"fixes": ["```diff\n+ fix\n```"], "summary": "Applied a patch"},
        }

        html = module.generate_html_report(review_data)

        self.assertIn("1 Critical Issues", html)
        self.assertIn("backend/core/views.py", html)
        self.assertIn("Missing colon", html)
        self.assertIn("Use snake_case", html)

