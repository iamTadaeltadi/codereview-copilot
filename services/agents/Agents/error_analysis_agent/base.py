from langgraph.graph import StateGraph
from langchain_core.messages import AIMessage
from . import ErrorAnalysisSummarizer
from . import VulnerabilityAgent
from . import BugChecker
from . import AnalysisState  # Add a set to track tool calls
class ErrorAnalysisAgent:
    def __init__(self, llm, tools,max_tool_calls: int=3):
        self.llm = llm
        self.tools = tools
        self.vuln_checker = VulnerabilityAgent(llm, tools,max_tool_calls=max_tool_calls)
        self.bug_checker = BugChecker(llm, tools,max_tool_calls=max_tool_calls)
        self.summarizer = ErrorAnalysisSummarizer(llm)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AnalysisState)

        # Add subgraphs
        builder.add_node("start", self.start)
        builder.add_node("vulnerability_analysis", self.vuln_checker.build_graph())
        builder.add_node("bug_analysis", self.bug_checker.build_graph())
        builder.add_node("aggregate_results", self.aggregate_results)
        # Create join node
        builder.add_node("merge_1", lambda state: state)

        # Define the flow
        builder.add_edge("start", "vulnerability_analysis")
        builder.add_edge("start", "bug_analysis")
        builder.add_edge(["bug_analysis", "vulnerability_analysis"],"merge_1")
        builder.add_edge("merge_1", "aggregate_results")
        builder.set_entry_point("start")

        return builder.compile()
    def start(self, state: AnalysisState):
        return state
    def aggregate_results(self, state: AnalysisState):
        issues = {
            "bug":[],
            "vulnerability":[]
        }
        for msg in state["vuln_state"]["issues"]:
            if isinstance(msg,AIMessage):
                if not "tool_calls" in msg.content: 
                    issues["vulnerability"].append(msg.content)
        for msg in state["bug_state"]["issues"]:
            if isinstance(msg,AIMessage):
                if not "tool_calls" in msg.content:
                    issues["bug"].append(msg.content)
        summarized_results = self.summarizer.summarize(issues)
        state["total_tool_calls"] = state["vuln_state"]["tool_call_count"] + state["bug_state"]["tool_call_count"]
        aggregated_results = {
            "messages": [f"Analysis complete for {state['current_diff']['file_path']}"],
            "issues": summarized_results,
            "total_tool_calls": state["total_tool_calls"]
        }
        return aggregated_results