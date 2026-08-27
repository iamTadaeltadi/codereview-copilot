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
        "services/agents/Tools/BasicToolNode.py",
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
        "services/agents/Utils/CloneRepo.py",
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
        "services/agents/Utils/Repository.py",
        {"Utils": utils_package, "config": config_module},
    )


def build_memory_module():
    utils_package = types.ModuleType("Utils")
    utils_package.__path__ = []
    html_report_module = types.ModuleType("Utils.HTMLReport")
    html_report_module.generate_review_report = Mock()
    return load_module(
        "memory_module",
        "services/agents/Memory/memory.py",
        {"Utils": utils_package, "Utils.HTMLReport": html_report_module},
    )


def build_preprocessing_module():
    utils_module = types.ModuleType("Utils")
    utils_module.get_pr_diff = Mock()
    utils_module.get_pr_metadata = Mock()
    utils_module.clone_repo = Mock(return_value="./tmp/repo/demo-main")
    utils_module.generate_code_graph = Mock(return_value="graph-object")
    utils_module.print_graph_info = Mock()
    utils_module.save_graph = Mock()

    codecontext_package = types.ModuleType("codecontext")
    retriever_module = types.ModuleType("codecontext.retriever")
    retriever_module.retrieve_node_context = Mock()

    config_module = types.ModuleType("config")

    class FakeConfig:
        GITHUB_TOKEN = "token"

    config_module.Config = FakeConfig
    return load_module(
        "preprocessing_module",
        "services/agents/steps_before_passing_to_an_agent.py",
        {
            "Utils": utils_module,
            "codecontext": codecontext_package,
            "codecontext.retriever": retriever_module,
            "config": config_module,
        },
    )


class BasicToolNodeTests(unittest.TestCase):
    def test_appends_tool_messages_for_valid_tool_calls(self):
        module = build_basic_tool_node_module()

        class FakeTool:
            name = "retrieve_graph"

            def invoke(self, args):
                return {"ok": True, "args": args}

        node = module.BasicToolNode([FakeTool()])
        inputs = {
            "issues": [
                types.SimpleNamespace(
                    content=json.dumps(
                        {
                            "tool_calls": [
                                {
                                    "function_call": {
                                        "name": "retrieve_graph",
                                        "args": {"node": "src/app.py::function::run"},
                                    }
                                }
                            ]
                        }
                    )
                )
            ]
        }

        result = node(inputs)

        self.assertEqual(len(result["issues"]), 2)
        tool_message = result["issues"][-1]
        self.assertEqual(tool_message.name, "retrieve_graph")
        self.assertEqual(
            json.loads(tool_message.content),
            {"ok": True, "args": {"node": "src/app.py::function::run"}},
        )

    def test_raises_when_input_has_no_issues(self):
        module = build_basic_tool_node_module()
        node = module.BasicToolNode([])

        with self.assertRaises(ValueError):
            node({})

    def test_returns_original_inputs_for_invalid_json(self):
        module = build_basic_tool_node_module()
        node = module.BasicToolNode([])
        inputs = {"issues": [types.SimpleNamespace(content="not-json")]}

        result = node(inputs)

        self.assertIs(result, inputs)
        self.assertEqual(len(result["issues"]), 1)


class CloneRepositoryTests(unittest.TestCase):
    def test_clone_repository_creates_directory_and_disables_prompts(self):
        module = build_clone_repo_module()

        with patch.object(module.os.path, "exists", return_value=False), patch.object(
            module.os, "makedirs"
        ) as mock_makedirs, patch.object(
            module.os.environ, "copy", return_value={"PATH": "/tmp"}
        ), patch.object(module.Repo, "clone_from") as mock_clone_from:
            module.clone_repository(
                "https://example.com/repo.git",
                "main",
                "/tmp/repo-destination",
            )

        mock_makedirs.assert_called_once_with("/tmp/repo-destination", exist_ok=True)
        _, _, kwargs = mock_clone_from.mock_calls[0]
        self.assertEqual(kwargs["branch"], "main")
        self.assertEqual(kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")


class RepositoryUtilityTests(unittest.TestCase):
    def test_clone_repo_uses_default_token_and_checks_out_commit(self):
        module = build_repository_module()

        with patch.object(module, "clone_repository") as mock_clone_repository, patch.object(
            module.uuid, "uuid4", return_value="repo-uuid"
        ), patch.object(module.subprocess, "run") as mock_run:
            repo_path = module.clone_repo(
                user="octocat",
                repo="demo",
                branch_name="main",
                commit_hash="abcdef1234567890",
            )

        self.assertEqual(repo_path, "./tmp/repo/demo-abcdef1-repo-uuid")
        mock_clone_repository.assert_called_once_with(
            "https://default-token@github.com/octocat/demo.git",
            "main",
            "./tmp/repo/demo-abcdef1-repo-uuid",
        )
        mock_run.assert_called_once_with(
            ["git", "checkout", "abcdef1234567890"],
            cwd="./tmp/repo/demo-abcdef1-repo-uuid",
            check=True,
            capture_output=True,
        )

    def test_clone_repo_raises_clean_value_error_when_checkout_fails(self):
        module = build_repository_module()
        checkout_error = subprocess.CalledProcessError(
            1, ["git", "checkout"], stderr=b"missing commit"
        )

        with patch.object(module, "clone_repository"), patch.object(
            module.uuid, "uuid4", return_value="repo-uuid"
        ), patch.object(module.subprocess, "run", side_effect=checkout_error):
            with self.assertRaisesRegex(ValueError, "missing commit"):
                module.clone_repo(
                    user="octocat",
                    repo="demo",
                    branch_name="main",
                    commit_hash="abcdef1234567890",
                )

    def test_setup_local_repo_from_files_writes_nested_tree(self):
        module = build_repository_module()
        files = {
            "src/app.py": "print('hi')\n",
            "README.md": "# Demo\n",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(module.uuid, "uuid4", return_value="repo-uuid"):
                repo_root = module.setup_local_repo_from_files(files, base_tmp_dir=tmpdir)

            self.assertEqual(repo_root, os.path.join(tmpdir, "local-repo-repo-uuid"))
            with open(os.path.join(repo_root, "src/app.py"), "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "print('hi')\n")
            with open(os.path.join(repo_root, "README.md"), "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "# Demo\n")


class MemoryManagerTests(unittest.TestCase):
    def test_save_review_and_get_pr_state(self):
        module = build_memory_module()
        manager = module.MemoryManager()

        manager.save_review(
            "pr-12",
            {
                "review": {"final": []},
                "fixes": ["apply patch"],
                "summary": "ready",
            },
        )

        self.assertEqual(
            manager.get_pr_state("pr-12"),
            {
                "review": {"final": []},
                "status": "completed",
                "artifacts": {"fixes": ["apply patch"], "summary": "ready"},
            },
        )
        self.assertIsNone(manager.get_pr_state("missing"))

    def test_save_to_file_writes_review_json_and_calls_report_generator(self):
        module = build_memory_module()
        manager = module.MemoryManager()
        manager.pr_states["pr-9"] = {
            "review": {"final": []},
            "status": "completed",
            "artifacts": {"fixes": [], "summary": "done"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            previous_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                with patch.object(module, "generate_review_report") as mock_report:
                    output_path = manager.save_to_file("pr-9")
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(output_path.startswith("./reviews/pr-9_"))
            stored_file = os.path.join(tmpdir, output_path.removeprefix("./"))
            self.assertTrue(os.path.exists(stored_file))
            with open(stored_file, "r", encoding="utf-8") as handle:
                stored = json.load(handle)

        self.assertEqual(stored["status"], "completed")
        mock_report.assert_called_once_with(output_path, "./reviews")


class PreProcessingStepTests(unittest.TestCase):
    def test_preprocessing_clones_repo_builds_graph_and_persists_it(self):
        module = build_preprocessing_module()

        with patch.object(module.uuid, "uuid4", return_value="graph-uuid"):
            graph_folder_path, repo_folder_path = module.preProcessingStep(
                "octocat", "demo", "main"
            )

        self.assertEqual(repo_folder_path, "./tmp/repo/demo-main")
        self.assertEqual(graph_folder_path, "./tmp/graph/demo-main-graph-uuid")
        module.clone_repo.assert_called_once_with("octocat", "demo", "main")
        module.generate_code_graph.assert_called_once_with("./tmp/repo/demo-main")
        module.print_graph_info.assert_called_once_with("graph-object", "./tmp/repo/demo-main")
        module.save_graph.assert_called_once_with("./tmp/graph/demo-main-graph-uuid", "graph-object")


if __name__ == "__main__":
    unittest.main()
