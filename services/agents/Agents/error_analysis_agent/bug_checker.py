from . import AnalysisState,CheckerAgent
import json
from langchain_core.utils.function_calling import convert_to_openai_function
from Utils import LLMResponseParser
from Prompts import BUG_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_EXCEEDED,\
    BUG_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_NOT_EXCEEDED
class BugChecker(CheckerAgent):
    def __init__(self, llm, tools, max_tool_calls=3):
        super().__init__(llm, tools, analysis_type="bug", max_tool_calls=max_tool_calls)

    def analyze(self, state: AnalysisState):
        # Work on the bug substate
        sub_state = state.get("bug_state", {"issues": [], "tool_calls_made": [], "tool_call_count": 0})
        tool_call_count = sub_state.get("tool_call_count", 0)
        if tool_call_count >= self.max_tool_calls:
            prompt = BUG_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_EXCEEDED.format(
                diff_content=state['current_diff']['content'],
                repo_summary=state["repo_summary"],
                max_tool_calls=self.max_tool_calls,
                additional_instructions=state.get("instruction", ""),)
        else:
            prompt = BUG_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_NOT_EXCEEDED.format(
                diff_content=state['current_diff']['content'],
                repo_summary=state["repo_summary"],
                tool_calls_made=sub_state.get("tool_calls_made"),
                additional_instructions=state.get("instruction", ""),)
        messages = (sub_state.get("issues", [])[-(2*self.max_tool_calls):] if sub_state.get("issues") else []) + [{"role": "user", "content": prompt}]
        response = self.llm.invoke(messages, functions=[convert_to_openai_function(tool) for tool in self.tools])
        parsed = LLMResponseParser.parse_response(response.content)
        response.content = json.dumps(parsed)
        sub_state.setdefault("issues", []).append(response)
        state["bug_state"] = sub_state
        return state