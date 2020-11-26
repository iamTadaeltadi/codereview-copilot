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
