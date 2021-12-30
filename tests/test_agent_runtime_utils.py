import importlib.util
import os
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DiffFormatterModule = load_module("diff_formatter_module", "agent_runtime/Utils/DiffFormatter.py")
LLMHelperModule = load_module("llm_helper_module", "agent_runtime/Utils/LLMHelper.py")
StorageModule = load_module("storage_module", "agent_runtime/Utils/Storage.py")

DiffFormatter = DiffFormatterModule.DiffFormatter
LLMResponseParser = LLMHelperModule.LLMResponseParser
save_graph = StorageModule.save_graph


class LLMResponseParserTests(unittest.TestCase):
    def test_parse_response_handles_direct_json(self):
        result = LLMResponseParser.parse_response('{"status": "ok", "score": 9}')
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["score"], 9)

    def test_parse_response_extracts_fenced_json(self):
        content = 'analysis\n```json\n{"issues": 2, "verdict": "warn"}\n```'
        result = LLMResponseParser.parse_response(content)
        self.assertEqual(result["issues"], 2)
        self.assertEqual(result["verdict"], "warn")

    @patch.object(LLMHelperModule, "repair_json", return_value='{"fixed": true}')
    def test_parse_response_uses_repair_for_invalid_fenced_json(self, mock_repair):
        content = '```json\n{"fixed": tru\n```'
        result = LLMResponseParser.parse_response(content)
        self.assertEqual(result, {"fixed": True})
        mock_repair.assert_called_once()


class DiffFormatterTests(unittest.TestCase):
    def test_parse_and_format_preserves_additions_deletions_and_context(self):
        diff_text = """diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
@@ -1,2 +1,3 @@
 def greet(name):
-    return \"hi\"
+    message = f\"hi {name}\"
+    return message
"""
        formatter = DiffFormatter(diff_text)

        result = formatter.parse_and_format()
        structured = formatter.get_structured_diff()

        self.assertEqual(result[0]["file_path"], "src/app.py")
        changes = structured[0]["chunks"][0]["changes"]
        self.assertEqual(changes[0]["type"], "context")
        self.assertEqual(changes[1]["type"], "deletion")
        self.assertEqual(changes[2]["type"], "addition")
        self.assertIn("message = f\"hi {name}\"", result[0]["content"])

    def test_extract_file_path_uses_new_side_path(self):
        formatter = DiffFormatter("")
        self.assertEqual(
            formatter._extract_file_path("diff --git a/backend/core.py b/backend/core.py"),
            "backend/core.py",
        )


class StorageTests(unittest.TestCase):
    def test_save_graph_writes_pickle_file(self):
        graph = {"nodes": [1, 2, 3]}
        with tempfile.TemporaryDirectory() as tmpdir:
            save_graph(tmpdir, graph)
            graph_path = os.path.join(tmpdir, "graph.pkl")
            self.assertTrue(os.path.exists(graph_path))
            with open(graph_path, "rb") as handle:
                self.assertEqual(pickle.load(handle), graph)


if __name__ == "__main__":
    unittest.main()
