from typing import TypedDict, Annotated
class CheckerSubState(TypedDict, total=False):
    issues: list
    tool_calls_made: list
    tool_call_count: int

class AnalysisState(TypedDict):
    messages: Annotated[list, lambda old, new: new]
    issues: Annotated[list, lambda old, new: new]
    current_diff: Annotated[dict, lambda old, new: new]
    total_tool_calls: Annotated[int, lambda old, new: new]
    instruction: Annotated[str, lambda old, new: new]
    repo_summary: Annotated[dict, lambda old, new: new]
    bug_state: Annotated[CheckerSubState, lambda old, new: old if new is None else new]
    vuln_state: Annotated[CheckerSubState, lambda old, new: old if new is None else new]
from .error_analysis_summarizer import ErrorAnalysisSummarizer
from .error_checker import CheckerAgent
from .bug_checker import BugChecker
from .vulnerability_checker import VulnerabilityAgent
from .base import ErrorAnalysisAgent