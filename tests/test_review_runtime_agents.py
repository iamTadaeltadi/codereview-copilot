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
