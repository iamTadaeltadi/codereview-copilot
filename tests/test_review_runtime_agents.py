import importlib.util
import json
import os
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


def fake_prompts_module():
    prompts = types.ModuleType("Prompts")
    prompts.CODE_FIX_PROMPT_TEMPLATE = "FIX:{file_path}|{diff_content}|{repo_summary}|{issues}|{additional_instructions}"
    prompts.CODE_REVIEWER_PROMPT_TEMPLATE = "REVIEW:{issue}|{repo_summary}|{metrics}|{ratings}|{additional_instructions}"
    prompts.CODE_SUMMARIZER_PROMPT_TEMPLATE = "SUM:{file_path}|{diff_content}"
    prompts.CODE_SUMMARY_MERGER_PROMPT_TEMPLATE = "MERGE:{summaries}"
    prompts.GUARDRAIL_CHECKER_PROMPT_TEMPLATE = "GUARD:{feedback}"
    prompts.STANDARD_CHECKER_PROMPT_TEMPLATE = "STD:{standards_str}|{diff_content}|{additional_instructions}"
    prompts.SYNTAX_CHECKER_PROMPT_TEMPLATE = "SYN:{language}|{diff_content}|{additional_instructions}"
    prompts.REPO_SUMMARIZER_PROMPT_TEMPLATE = "REPO:{repo_folder_path}|{file_tree_json}"
    prompts.REREVIEW_PLANNER_PROMPT_TEMPLATE = "PLAN:{feedback}|{review_structure}|{episodic_context}"
    prompts.REVIEW_STRUCTURE_PROMPT_TEMPLATE = "REVIEW-STRUCTURE"
    prompts.REREVIEW_INSTRUCTION_GENERATOR_PROMPT_TEMPLATE = (
        "INSTR:{feedback}|{file}|{step}|{review_structure}|{files}|{preference_context}|{episodic_context}"
    )
    prompts.SUFFICIENCY_CHECKER_PROMPT_TEMPLATE = "SUFF:{feedback}|{files}|{episodic_context}"
    prompts.ERROR_SUMMARIZER_PROMPT_TEMPLATE = "ERRSUM:{results}"
    prompts.BUG_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_EXCEEDED = "BUG-LIMIT:{diff_content}|{repo_summary}|{max_tool_calls}|{additional_instructions}"
    prompts.BUG_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_NOT_EXCEEDED = "BUG-OK:{diff_content}|{repo_summary}|{tool_calls_made}|{additional_instructions}"
    prompts.VULNERABILITY_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_EXCEEDED = "VULN-LIMIT:{diff_content}|{repo_summary}|{max_tool_calls}|{additional_instructions}"
    prompts.VULNERABILITY_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_NOT_EXCEEDED = "VULN-OK:{diff_content}|{repo_summary}|{tool_calls_made}|{additional_instructions}"
    prompts.LONG_TERM_MEMORY_PROMPT_TEMPLATE = "LTM:{interaction}|{existing_preferences}"
    return prompts


class FakeLLMResponseParser:
    @staticmethod
    def parse_response(content):
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"raw": content}
        return content


def base_utils_module():
    utils_module = types.ModuleType("Utils")
    utils_module.LLMResponseParser = FakeLLMResponseParser
    return utils_module


class Response:
    def __init__(self, content):
        self.content = content


class AgentWrapperTests(unittest.TestCase):
    def test_code_fix_agent_formats_prompt_and_returns_content(self):
        module = load_module(
            "code_fix_agent_module",
            "agent_runtime/Agents/code_fix_agent.py",
            {"Prompts": fake_prompts_module()},
        )
        llm = Mock()
        llm.invoke.return_value = Response("patch")

        result = module.CodeFixAgent(llm).generate_fix(
            {"file_path": "src/app.py", "content": "+ print('ok')"},
            [{"issue": "bug"}],
            {"repo": "summary"},
            "follow-up",
        )

        self.assertEqual(result, "patch")
        prompt = llm.invoke.call_args.args[0]
        self.assertIn("src/app.py", prompt)
        self.assertIn("follow-up", prompt)

    def test_code_reviewer_agent_generates_reviews_for_each_issue_tuple(self):
        module = load_module(
            "code_reviewer_agent_module",
            "agent_runtime/Agents/code_reviewer_agent.py",
            {"Prompts": fake_prompts_module(), "Utils": base_utils_module()},
        )
        llm = Mock()
        llm.invoke.side_effect = [
            Response('{"file": "src/app.py", "summary": "ok"}'),
            Response('{"file": "src/lib.py", "summary": "warn"}'),
        ]

        output = module.CodeReviewerAgent(llm, ["security", "clarity"]).generate_review(
            {
                "syntax": [{"file": "src/app.py"}, {"file": "src/lib.py"}],
                "standards": [{"issues": []}, {"issues": ["naming"]}],
                "error_analysis": [{"issues": {}}, {"issues": {"bug": []}}],
            },
            {"repo": "summary"},
            "extra",
        )

        self.assertEqual(len(output), 2)
        self.assertEqual(output[0]["file"], "src/app.py")
        self.assertIn("security", llm.invoke.call_args_list[0].args[0])

    def test_code_summarizer_agent_summarizes_and_merges_diffs(self):
        module = load_module(
            "code_summarizer_agent_module",
            "agent_runtime/Agents/code_summarizer_agent.py",
            {"Prompts": fake_prompts_module()},
        )
        llm = Mock()
        llm.invoke.side_effect = [Response("sum-a"), Response("sum-b"), Response("merged")]
        agent = module.CodeSummarizerAgent(llm)

        summary = agent.summarize_pr(
            [
                {"file_path": "src/a.py", "content": "+ a"},
                {"file_path": "src/b.py", "content": "+ b"},
            ]
        )

        self.assertEqual(summary, "merged")
        self.assertEqual(llm.invoke.call_count, 3)

    def test_guardrail_standard_and_syntax_agents_parse_llm_output(self):
        prompts = fake_prompts_module()
        utils = base_utils_module()
        guardrail_module = load_module(
            "guardrail_agent_module",
            "agent_runtime/Agents/guardrail_checker_agent.py",
            {"Prompts": prompts, "Utils": utils},
        )
        standard_module = load_module(
            "standard_agent_module",
            "agent_runtime/Agents/standard_checker_agent.py",
            {"Prompts": prompts, "Utils": utils},
        )
        syntax_module = load_module(
            "syntax_agent_module",
            "agent_runtime/Agents/syntax_checker_agent.py",
            {"Prompts": prompts, "Utils": utils},
        )

        llm = Mock()
        llm.invoke.side_effect = [
            Response('{"classification": "relevant"}'),
            Response('{"issues": ["snake_case"]}'),
            Response('{"issues": ["indentation"]}'),
        ]

        guardrail = guardrail_module.GuardrailCheckerAgent(llm).guardrail_checker("focus on auth")
        standards = standard_module.StandardCheckerAgent(llm, ["snake_case"]).check_compliance(
            {"content": "+ value = 1"}, "extra"
        )
        syntax = syntax_module.SyntaxCheckerAgent(llm).analyze(
            {"file_path": "src/app.py", "content": "+ print('ok')"}, "extra"
        )

        self.assertEqual(guardrail["classification"], "relevant")
        self.assertEqual(standards["issues"], ["snake_case"])
        self.assertEqual(syntax["issues"], ["indentation"])

    def test_repo_summarizer_builds_tree_and_parses_summary(self):
        module = load_module(
            "repo_summarizer_module",
            "agent_runtime/Agents/repo_summarizer_agent.py",
            {"Prompts": fake_prompts_module(), "Utils": base_utils_module()},
        )
        llm = Mock()
        llm.invoke.return_value = Response('{"project_type": "django"}')
        agent = module.RepoSummarizerAgent(llm)

        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
            Path(tmpdir, "src", "app.py").write_text("print('x')\n", encoding="utf-8")
            result = agent.summarize_repository(tmpdir)

        self.assertEqual(result["project_type"], "django")
        self.assertTrue(agent._build_file_tree(ROOT)["tests"])

    def test_rereview_planner_and_sufficiency_agents_include_episodic_context(self):
        prompts = fake_prompts_module()
        utils = base_utils_module()
        jmespath_module = types.ModuleType("jmespath")
        jmespath_module.search = lambda expr, data: ["src/app.py"]
        planner_module = load_module(
            "planner_agent_module",
            "agent_runtime/Agents/rereview_planner_agent.py",
            {"Prompts": prompts, "Utils": utils},
        )
        sufficiency_module = load_module(
            "sufficiency_agent_module",
            "agent_runtime/Agents/sufficiency_checker_agent.py",
            {"Prompts": prompts, "Utils": utils, "jmespath": jmespath_module},
        )
        llm = Mock()
        llm.invoke.side_effect = [
            Response('{"src/app.py": ["syntax", "final"]}'),
            Response('{"classification": "sufficient"}'),
        ]

        plan = planner_module.ReReviewPlannerAgent(llm).re_review_planner(
            "please re-check", ["prior note"]
        )
        sufficiency = sufficiency_module.SufficiencyCheckerAgent(llm).sufficiency_checker(
            "please re-check", {"review": {"error_analysis": []}}, "episode text"
        )

        self.assertIn("src/app.py", plan)
        self.assertEqual(sufficiency["classification"], "sufficient")

    def test_rereview_instruction_generator_builds_per_file_step_instructions(self):
        prompts = fake_prompts_module()
        utils = base_utils_module()
        jmespath_module = types.ModuleType("jmespath")

        def fake_search(expr, data):
            if expr == "review.error_analysis[].current_diff.file_path":
                return ["src/app.py"]
            if expr == "review.final[0]":
                return {"summary": "current"}
            return None

        jmespath_module.search = fake_search
        module = load_module(
            "instruction_agent_module",
            "agent_runtime/Agents/rereview_instruction_generator_agent.py",
            {"Prompts": prompts, "Utils": utils, "jmespath": jmespath_module},
        )
        llm = Mock()
        llm.invoke.return_value = Response(
            '{"queries": ["review.final[0]"], "instruction": "focus on null checks"}'
        )

        result = module.ReReviewInstructionGeneratorAgent(llm).re_review_instruction_generator(
            {"src/app.py": ["final"]},
            {"review": {"error_analysis": []}},
            "please fix",
            "prefers terse responses",
            ["old context"],
        )

        self.assertEqual(result["src/app.py"]["final"]["instruction"], "focus on null checks")
        self.assertIn("current", result["src/app.py"]["final"]["current_section"])

    def test_long_term_memory_agent_analyzes_and_updates_preferences(self):
        module = load_module(
            "memory_agent_module",
            "agent_runtime/Agents/memory_agent.py",
            {"Prompts": fake_prompts_module(), "Utils.LLMHelper": base_utils_module()},
        )
        llm = Mock()
        llm.invoke.return_value = Response('[{"preference": "concise", "confidence": 0.9}]')
        manage_tool = Mock()
        search_tool = Mock()
        agent = module.LongTermMemoryAgent(llm, manage_tool, search_tool)

        prefs = agent.analyze_preferences("feedback", [{"preference": "concise"}])
        agent.update_preferences(prefs, {"configurable": {"user": "demo"}})

        self.assertEqual(prefs[0]["preference"], "concise")
        self.assertEqual(manage_tool.invoke.call_count, 1)


class DynamicReviewExecutorTests(unittest.TestCase):
    def test_execute_review_applies_requested_steps_and_fallback_sections(self):
        class FakeSyntaxChecker:
            def __init__(self, llm):
                self.llm = llm

            def analyze(self, diff, additional_instructions=""):
                return {"syntax": diff["file_path"], "instruction": additional_instructions}

        class FakeStandardChecker:
            def __init__(self, llm, standards):
                self.llm = llm
                self.standards = standards

            def check_compliance(self, diff, additional_instructions=""):
                return {"standards": diff["file_path"], "instruction": additional_instructions}

        class FakeErrorAgent:
            def __init__(self, llm, tools, max_tool_calls):
                self.graph = Mock()
                self.graph.invoke.return_value = {
                    "messages": ["ok"],
                    "issues": {"bug": ["b"], "vulnerability": []},
                    "total_tool_calls": 2,
                    "bug_state": {"tool_calls_made": ["bug-call"]},
                    "vuln_state": {"tool_calls_made": ["vuln-call"]},
                }

        class FakeFixAgent:
            def __init__(self, llm):
                self.llm = llm

            def generate_fix(self, diff, current_review, repo_summary, additional_instructions=""):
                return f"fix:{diff['file_path']}:{additional_instructions}:{bool(current_review['syntax'])}"

        class FakeReviewer:
            def __init__(self, llm, metrics):
                self.llm = llm
                self.metrics = metrics

            def generate_review(self, current_review, repo_summary, additional_instructions=""):
                return [{"final": current_review["syntax"][0], "instruction": additional_instructions}]

        agents_pkg = types.ModuleType("Agents")
        agents_pkg.__path__ = []
        syntax_mod = types.ModuleType("Agents.syntax_checker_agent")
        syntax_mod.SyntaxCheckerAgent = FakeSyntaxChecker
        standard_mod = types.ModuleType("Agents.standard_checker_agent")
        standard_mod.StandardCheckerAgent = FakeStandardChecker
        error_mod = types.ModuleType("Agents.error_analysis_agent")
        error_mod.ErrorAnalysisAgent = FakeErrorAgent
        fix_mod = types.ModuleType("Agents.code_fix_agent")
        fix_mod.CodeFixAgent = FakeFixAgent
        review_mod = types.ModuleType("Agents.code_reviewer_agent")
        review_mod.CodeReviewerAgent = FakeReviewer

        module = load_module(
            "dynamic_review_executor_module",
            "agent_runtime/Agents/dynamic_review_executor_agent.py",
            {
                "Agents": agents_pkg,
                "Agents.syntax_checker_agent": syntax_mod,
                "Agents.standard_checker_agent": standard_mod,
                "Agents.error_analysis_agent": error_mod,
                "Agents.code_fix_agent": fix_mod,
                "Agents.code_reviewer_agent": review_mod,
            },
        )

        agent = module.DynamicReviewExecutorAgent(Mock(), ["snake_case"], ["tool"], ["quality"], 3)
        reviews = {
            "syntax": [None],
            "standards": [None],
            "error_analysis": [None],
            "final": [None],
        }
        fixes = [None]
        diff_map = {"src/app.py": (0, {"file_path": "src/app.py", "content": "+ value"})}
        original_review = {
            "review": {
                "syntax": [{"orig": "syntax"}],
                "standards": [{"orig": "std"}],
                "error_analysis": [{"orig": "err"}],
            }
        }

        updated_reviews, updated_fixes = agent.execute_review(
            {"src/app.py": ["syntax", "standards", "error_analysis"]},
            {
                "src/app.py": {
                    "syntax": {"instruction": "syntax-focus"},
                    "standards": {"instruction": "style-focus"},
                    "error_analysis": {"instruction": "bug-focus"},
                    "fix": {"instruction": "patch-it"},
                    "final": {"instruction": "summarize-it"},
                }
            },
            reviews,
            fixes,
            diff_map,
            {"repo": "summary"},
            original_review,
        )

        self.assertEqual(updated_reviews["syntax"][0]["instruction"], "syntax-focus")
        self.assertEqual(updated_reviews["final"][0]["instruction"], "summarize-it")
        self.assertIn("patch-it", updated_fixes[0])


class ErrorAnalysisAgentTests(unittest.TestCase):
    def test_error_analysis_summarizer_and_checker_variants(self):
        prompts = fake_prompts_module()
        utils = base_utils_module()
        fn_call_module = types.ModuleType("langchain_core.utils.function_calling")
        fn_call_module.convert_to_openai_function = lambda tool: {"name": tool.name}

        summarizer_module = load_module(
            "error_summarizer_module",
            "agent_runtime/Agents/error_analysis_agent/error_analysis_summarizer.py",
            {"Prompts": prompts, "Utils": utils},
        )

        llm = Mock()
        llm.invoke.return_value = Response('{"summary": "done"}')
        self.assertEqual(
            summarizer_module.ErrorAnalysisSummarizer(llm).summarize({"bug": [], "vulnerability": []})["summary"],
            "done",
        )

        agent_runtime_pkg = types.ModuleType("agent_runtime")
        agent_runtime_pkg.__path__ = []
        agents_pkg = types.ModuleType("agent_runtime.Agents")
        agents_pkg.__path__ = []
        analysis_state_module = types.ModuleType("agent_runtime.Agents.error_analysis_agent")
        analysis_state_module.__path__ = []
        analysis_state_module.AnalysisState = dict

        class FakeCheckerAgent:
            def __init__(self, llm, tools, analysis_type, max_tool_calls):
                self.llm = llm
                self.tools = tools
                self.analysis_type = analysis_type
                self.max_tool_calls = max_tool_calls

        analysis_state_module.CheckerAgent = FakeCheckerAgent

        bug_module = load_module(
            "agent_runtime.Agents.error_analysis_agent.bug_checker",
            "agent_runtime/Agents/error_analysis_agent/bug_checker.py",
            {
                "Prompts": prompts,
                "Utils": utils,
                "langchain_core.utils.function_calling": fn_call_module,
                "agent_runtime": agent_runtime_pkg,
                "agent_runtime.Agents": agents_pkg,
                "agent_runtime.Agents.error_analysis_agent": analysis_state_module,
            },
        )
        vuln_module = load_module(
            "agent_runtime.Agents.error_analysis_agent.vulnerability_checker",
            "agent_runtime/Agents/error_analysis_agent/vulnerability_checker.py",
            {
                "Prompts": prompts,
                "Utils": utils,
                "langchain_core.utils.function_calling": fn_call_module,
                "agent_runtime": agent_runtime_pkg,
                "agent_runtime.Agents": agents_pkg,
                "agent_runtime.Agents.error_analysis_agent": analysis_state_module,
            },
        )

        llm = Mock()
        llm.invoke.return_value = Response('{"tool_calls": []}')
        bug_state = {
            "current_diff": {"content": "+ bug"},
            "repo_summary": {"repo": "summary"},
            "instruction": "focus",
            "bug_state": {"issues": [], "tool_calls_made": [], "tool_call_count": 0},
        }
        vuln_state = {
            "current_diff": {"content": "+ vuln"},
            "repo_summary": {"repo": "summary"},
            "instruction": "focus",
            "vuln_state": {"issues": [], "tool_calls_made": ["prior"], "tool_call_count": 3},
        }

        bug_result = bug_module.BugChecker(llm, [types.SimpleNamespace(name="retrieve")], max_tool_calls=3).analyze(bug_state)
        vuln_result = vuln_module.VulnerabilityAgent(llm, [types.SimpleNamespace(name="retrieve")], max_tool_calls=3).analyze(vuln_state)

        self.assertEqual(len(bug_result["bug_state"]["issues"]), 1)
        self.assertEqual(len(vuln_result["vuln_state"]["issues"]), 1)

    def test_checker_agent_tools_condition_and_handle_tools(self):
        class FakeToolMessage:
            pass

        class FakeAIMessage:
            def __init__(self, content):
                self.content = content

        class FakeStateGraph:
            def __init__(self, state_type):
                self.nodes = []
                self.entry = None

            def add_node(self, name, fn):
                self.nodes.append(name)

            def add_conditional_edges(self, *args, **kwargs):
                pass

            def add_edge(self, *args, **kwargs):
                pass

            def set_entry_point(self, entry):
                self.entry = entry

            def compile(self):
                return {"entry": self.entry, "nodes": self.nodes}

        class FakeBasicToolNode:
            def __init__(self, tools):
                self.tools = tools

            def __call__(self, inputs):
                inputs["issues"].append(FakeToolMessage())
                return inputs

        tools_pkg = types.ModuleType("Tools")
        tools_pkg.BasicToolNode = FakeBasicToolNode
        graph_module = types.ModuleType("langgraph.graph")
        graph_module.StateGraph = FakeStateGraph
        messages_module = types.ModuleType("langchain_core.messages")
        messages_module.ToolMessage = FakeToolMessage
        messages_module.AIMessage = FakeAIMessage
        pydantic_module = types.ModuleType("pydantic")
        pydantic_module.BaseModel = object
        agent_runtime_pkg = types.ModuleType("agent_runtime")
        agent_runtime_pkg.__path__ = []
        agents_pkg = types.ModuleType("agent_runtime.Agents")
        agents_pkg.__path__ = []
        parent_pkg = types.ModuleType("agent_runtime.Agents.error_analysis_agent")
        parent_pkg.__path__ = []
        parent_pkg.AnalysisState = dict

        module = load_module(
            "agent_runtime.Agents.error_analysis_agent.error_checker",
            "agent_runtime/Agents/error_analysis_agent/error_checker.py",
            {
                "Tools": tools_pkg,
                "langgraph.graph": graph_module,
                "langchain_core.messages": messages_module,
                "pydantic": pydantic_module,
                "agent_runtime": agent_runtime_pkg,
                "agent_runtime.Agents": agents_pkg,
                "agent_runtime.Agents.error_analysis_agent": parent_pkg,
            },
        )

        class ConcreteChecker(module.CheckerAgent):
            def analyze(self, state):
                return state

        checker = ConcreteChecker(Mock(), ["tool"], "bug", 3)
        self.assertEqual(checker.build_graph()["entry"], "analyze")
        with self.assertRaises(ValueError):
            checker.tools_condition({"bug_state": {"issues": []}})

        handle = checker.tools_condition(
            {
                "bug_state": {
                    "issues": [FakeAIMessage('{"tool_calls": [{"function_call": {"name": "x", "args": {}}}]}')]
                }
            }
        )
        self.assertEqual(handle, "handle_tools")
        end = checker.tools_condition({"bug_state": {"issues": [FakeAIMessage("plain text")]}})
        self.assertEqual(end, "__end__")

        handled = checker.handle_tools(
            {
                "bug_state": {
                    "issues": [
                        FakeAIMessage('{"tool_calls": [{"function_call": {"name": "x", "args": {}}}]}')
                    ]
                }
            }
        )
        self.assertEqual(handled["bug_state"]["tool_call_count"], 1)

    def test_error_analysis_base_aggregate_results_filters_tool_call_messages(self):
        class FakeAIMessage:
            def __init__(self, content):
                self.content = content

        class FakeStateGraph:
            def __init__(self, state_type):
                self.state_type = state_type

            def add_node(self, *args, **kwargs):
                pass

            def add_edge(self, *args, **kwargs):
                pass

            def set_entry_point(self, *args, **kwargs):
                pass

            def compile(self):
                return "compiled"

        agent_runtime_pkg = types.ModuleType("agent_runtime")
        agent_runtime_pkg.__path__ = []
        agents_pkg = types.ModuleType("agent_runtime.Agents")
        agents_pkg.__path__ = []
        parent_module = types.ModuleType("agent_runtime.Agents.error_analysis_agent")
        parent_module.__path__ = []
        parent_module.AnalysisState = dict
        parent_module.ErrorAnalysisSummarizer = lambda llm: types.SimpleNamespace(
            summarize=lambda issues: {"summary": issues}
        )
        parent_module.VulnerabilityAgent = lambda llm, tools, max_tool_calls=3: types.SimpleNamespace(
            build_graph=lambda: "vuln-graph"
        )
        parent_module.BugChecker = lambda llm, tools, max_tool_calls=3: types.SimpleNamespace(
            build_graph=lambda: "bug-graph"
        )
        graph_module = types.ModuleType("langgraph.graph")
        graph_module.StateGraph = FakeStateGraph
        messages_module = types.ModuleType("langchain_core.messages")
        messages_module.AIMessage = FakeAIMessage

        module = load_module(
            "agent_runtime.Agents.error_analysis_agent.base",
            "agent_runtime/Agents/error_analysis_agent/base.py",
            {
                "agent_runtime.Agents.error_analysis_agent": parent_module,
                "agent_runtime": agent_runtime_pkg,
                "agent_runtime.Agents": agents_pkg,
                "langgraph.graph": graph_module,
                "langchain_core.messages": messages_module,
            },
        )

        agent = module.ErrorAnalysisAgent(Mock(), ["tool"], max_tool_calls=2)
        result = agent.aggregate_results(
            {
                "current_diff": {"file_path": "src/app.py"},
                "vuln_state": {
                    "issues": [FakeAIMessage("tool_calls"), FakeAIMessage("vulnerability found")],
                    "tool_call_count": 1,
                },
                "bug_state": {
                    "issues": [FakeAIMessage("bug found")],
                    "tool_call_count": 2,
                },
            }
        )

        self.assertEqual(result["total_tool_calls"], 3)
        self.assertIn("vulnerability", result["issues"]["summary"])
        self.assertEqual(agent.start({"ok": True}), {"ok": True})


if __name__ == "__main__":
    unittest.main()
