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
