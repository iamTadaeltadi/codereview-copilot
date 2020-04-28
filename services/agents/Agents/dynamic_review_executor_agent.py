from Agents.syntax_checker_agent import SyntaxCheckerAgent
from Agents.standard_checker_agent import StandardCheckerAgent
from Agents.error_analysis_agent import ErrorAnalysisAgent
from Agents.code_fix_agent import CodeFixAgent
from Agents.code_reviewer_agent import CodeReviewerAgent

class DynamicReviewExecutorAgent:
    def __init__(self, llm, standards, tools, metrics, max_tool_calls):
        self.llm = llm
        self.standards = standards
        self.tools = tools
        self.metrics = metrics
        self.max_tool_calls = max_tool_calls
        # Initialize agents
        self.syntax_checker = SyntaxCheckerAgent(llm)
        self.standards_checker = StandardCheckerAgent(llm,self.standards)
        self.error_analysis_agent = ErrorAnalysisAgent(llm,self.tools,self.max_tool_calls)
        self.code_fix_agent = CodeFixAgent(llm)
        self.code_reviewer_agent = CodeReviewerAgent(llm,self.metrics)

    def execute_review(self, re_run_plan:dict, instructions:dict, reviews:dict, fixes:dict, diff_map:dict, repo_summary:dict, original_review:dict):
        for file, steps in re_run_plan.items():
            if file in diff_map:
                idx, diff = diff_map[file]
                for step in steps:
                    instruction_data = instructions.get(file, {}).get(step, {})
                    instruction = instruction_data.get("instruction", "")
                    if step == "syntax":
                        checker = SyntaxCheckerAgent(self.llm)
                        reviews["syntax"][idx] = checker.analyze(diff, additional_instructions=instruction)
                    elif step == "standards":
                        checker = StandardCheckerAgent(self.llm, self.standards)
                        reviews["standards"][idx] = checker.check_compliance(diff, additional_instructions=instruction)
                    elif step == "error_analysis":
                        agent = ErrorAnalysisAgent(self.llm, self.tools, max_tool_calls=self.max_tool_calls)
                        result = agent.graph.invoke({
                            "messages": [],
                            "issues": [],
                            "current_diff": diff,
                            "total_tool_calls": 0,
                            "repo_summary": repo_summary,
                            "instructions": instruction,
                            "bug_state": {"issues": [], "tool_calls_made": [], "tool_call_count": 0},
                            "vuln_state": {"issues": [], "tool_calls_made": [], "tool_call_count": 0},
                        })
                        reviews["error_analysis"][idx] = {
