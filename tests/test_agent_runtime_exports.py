"""Import and surface-level tests for agent runtime packages.

These exercise the package ``__init__`` modules (which wire up the public agent
exports), the prompt template module, and the pure helper on ``CustomLLM`` that
formats tool descriptions without requiring a live model.
"""

import unittest

try:
    import Agents  # noqa: F401

    _AGENT_RUNTIME_AVAILABLE = True
except Exception:  # pragma: no cover - agent runtime deps absent in this env
    _AGENT_RUNTIME_AVAILABLE = False


@unittest.skipUnless(_AGENT_RUNTIME_AVAILABLE, "agent runtime deps not installed")
class AgentPackageExportTests(unittest.TestCase):
    def test_agents_package_exposes_public_agents(self):
        import Agents

        for name in (
            "CodeFixAgent",
            "CodeReviewerAgent",
            "CodeSummarizerAgent",
            "RepoSummarizerAgent",
            "StandardCheckerAgent",
            "SyntaxCheckerAgent",
            "GuardrailCheckerAgent",
            "SufficiencyCheckerAgent",
        ):
            self.assertTrue(hasattr(Agents, name), f"missing export: {name}")

    def test_error_analysis_package_imports(self):
        from Agents.error_analysis_agent import ErrorAnalysisAgent

        self.assertTrue(callable(ErrorAnalysisAgent))

    def test_support_packages_import(self):
        import LLM  # noqa: F401
        import Memory  # noqa: F401
        import Prompts  # noqa: F401
        import Tools  # noqa: F401
        import Utils  # noqa: F401


@unittest.skipUnless(_AGENT_RUNTIME_AVAILABLE, "agent runtime deps not installed")
class PromptTemplateTests(unittest.TestCase):
    def test_prompt_templates_are_non_empty_strings(self):
        from Prompts import prompts

        for name in (
            "STANDARD_CHECKER_PROMPT_TEMPLATE",
            "SYNTAX_CHECKER_PROMPT_TEMPLATE",
            "CODE_REVIEWER_PROMPT_TEMPLATE",
            "CODE_FIX_PROMPT_TEMPLATE",
            "GUARDRAIL_CHECKER_PROMPT_TEMPLATE",
        ):
            template = getattr(prompts, name)
            self.assertIsInstance(template, str)
            self.assertTrue(template.strip())

    def test_code_summarizer_template_has_expected_placeholders(self):
        from Prompts import prompts

        self.assertIn("{file_path}", prompts.CODE_SUMMARIZER_PROMPT_TEMPLATE)
        self.assertIn("{diff_content}", prompts.CODE_SUMMARIZER_PROMPT_TEMPLATE)


@unittest.skipUnless(_AGENT_RUNTIME_AVAILABLE, "agent runtime deps not installed")
class CustomLLMHelperTests(unittest.TestCase):
    def test_generate_functions_description_formats_each_function(self):
        from LLM.CustomLLM import CustomLLM

        functions = [
            {"name": "search", "description": "find things", "parameters": {"q": "string"}},
            {"name": "fetch", "description": "get a node", "parameters": {"id": "int"}},
        ]
        # The helper does not touch instance state, so it can be called unbound.
        description = CustomLLM._generate_functions_description(None, functions)

        self.assertIn("Name: search", description)
        self.assertIn("Description: find things", description)
        self.assertIn("Name: fetch", description)


if __name__ == "__main__":
    unittest.main()
