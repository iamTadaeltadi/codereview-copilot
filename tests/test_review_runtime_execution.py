import importlib.util
import json
import os
import subprocess
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


def build_basic_tool_node_module():
    messages_module = types.ModuleType("langchain_core.messages")

    class FakeToolMessage:
        def __init__(self, content, name, tool_call_id):
            self.content = content
            self.name = name
            self.tool_call_id = tool_call_id

    messages_module.ToolMessage = FakeToolMessage
    langchain_core_module = types.ModuleType("langchain_core")
    return load_module(
        "basic_tool_node_module",
        "agent_runtime/Tools/BasicToolNode.py",
        {
            "langchain_core": langchain_core_module,
            "langchain_core.messages": messages_module,
        },
    )


def build_clone_repo_module():
    git_module = types.ModuleType("git")
    git_module.Repo = types.SimpleNamespace(clone_from=Mock())
    return load_module(
        "clone_repo_module",
        "agent_runtime/Utils/CloneRepo.py",
        {"git": git_module},
    )


def build_repository_module():
    utils_package = types.ModuleType("Utils")
    utils_package.__path__ = []
    utils_package.clone_repository = Mock()
    config_module = types.ModuleType("config")

    class FakeConfig:
        GITHUB_TOKEN = "default-token"

    config_module.Config = FakeConfig
    return load_module(
        "Utils.Repository",
