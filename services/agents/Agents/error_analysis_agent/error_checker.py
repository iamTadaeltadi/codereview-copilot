import json
from typing import Any, Union
from langgraph.graph import StateGraph
from langchain_core.messages import ToolMessage,AIMessage
from pydantic import BaseModel
from Tools import BasicToolNode
from . import AnalysisState  # our new state definition

class CheckerAgent:
    def __init__(self, llm, tools, analysis_type: str, max_tool_calls: int):
        """
        analysis_type: should be either "bug" or "vulnerability"
        """
        self.llm = llm
        self.tools = tools
        self.analysis_type = analysis_type
        self.max_tool_calls = max_tool_calls

    def build_graph(self):
        builder = StateGraph(AnalysisState)
        builder.add_node("analyze", self.analyze)
        builder.add_node("handle_tools", self.handle_tools)
        builder.add_conditional_edges("analyze", self.tools_condition)
        builder.add_edge("handle_tools", "analyze")
        builder.set_entry_point("analyze")
        return builder.compile()

    def tools_condition(self, state: Union[list[Any], dict[str, Any], BaseModel], messages_key: str = None) -> str:
        # Use the appropriate substate key for this checker:
        key = "bug_state" if self.analysis_type == "bug" else "vuln_state"
        sub_state = state.get(key, {})
        messages = sub_state.get("issues", [])
        if not messages:
            raise ValueError(f"No messages found in {key}: {state}")
        ai_message = messages[-1]
        if isinstance(ai_message.content, str) and (
            (ai_message.content.startswith("```json") and ai_message.content.endswith("```"))
            or ("tool_calls" in ai_message.content)
        ):
            json_str = ai_message.content.strip("```json\n").strip("\n```")
            try:
                tool_call_data = json.loads(json_str)
                if isinstance(tool_call_data, dict) and "tool_calls" in tool_call_data:
                    tool_calls = tool_call_data["tool_calls"]
                    if isinstance(tool_calls, list) and len(tool_calls) > 0:
                        return "handle_tools"
            except json.JSONDecodeError:
                print("Failed to parse tool calls JSON in", key)
        return "__end__"

    def handle_tools(self, state: AnalysisState):
        # Use a separate tool node for this analysis type:
        key = "bug_state" if self.analysis_type == "bug" else "vuln_state"
        tool_node = BasicToolNode(tools=self.tools)
        state[key] = tool_node(state[key])
        # Reset the substate's tool calls and update its count.
        sub_state = state.get(key, {})
        sub_state["tool_calls_made"] = []
        count = 0
        for message in sub_state.get("issues", []):
            if isinstance(message, ToolMessage):
                count += 1
            if isinstance(message, AIMessage) and "tool_calls" in message.content:
                sub_state["tool_calls_made"].append(message.content)
        sub_state["tool_call_count"] = len(sub_state["tool_calls_made"])
        state[key] = sub_state
        return state

    def analyze(self, state: AnalysisState):
        raise NotImplementedError("Subclasses must implement the analyze method.")
