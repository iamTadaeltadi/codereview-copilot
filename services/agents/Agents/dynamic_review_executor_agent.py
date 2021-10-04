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
                            "messages": result["messages"],
                            "issues": result["issues"],
                            "current_diff": diff,
                            "total_tool_calls": result["total_tool_calls"],
                            "tool_calls": result["bug_state"]["tool_calls_made"] + result["vuln_state"]["tool_calls_made"]
                        }
                current_review = {
                    "syntax": [reviews["syntax"][idx]],
                    "standards": [reviews["standards"][idx]],
                    "error_analysis": [reviews["error_analysis"][idx]]
                }
                
                # Generate a fix, applying any provided “fix” instruction
                fix_section = instructions.get(file, {}).get("fix", {})
                fix_instr = fix_section.get("instruction", "")
                
                # If a “final” instruction exists and current_review is missing any review sections,
                # complete them from the original review using the proper index.
                final_section = instructions.get(file, {}).get("final", {})
                review_instr = final_section.get("instruction", "")
                if review_instr or fix_instr:
                    for section in ["syntax", "standards", "error_analysis"]:
                        # Check if the current section is missing or its element is empty
                        if not current_review.get(section) or not current_review[section][0]:
                            orig_section = original_review["review"].get(section, [])
                            if len(orig_section) > idx:
                                current_review[section] = [orig_section[idx]]
                fix_agent = CodeFixAgent(self.llm)
                fixes[idx] = fix_agent.generate_fix(
                    diff,
                    current_review,
                    repo_summary,
                    additional_instructions=fix_instr
                )

                # Generate final review, applying any provided “final” instruction
                reviewer = CodeReviewerAgent(self.llm, self.metrics)
                final_reviews = reviewer.generate_review(
                    current_review,
                    repo_summary,
                    additional_instructions=review_instr
                )

                reviews["final"][idx] = final_reviews[0]
        return reviews,fixes