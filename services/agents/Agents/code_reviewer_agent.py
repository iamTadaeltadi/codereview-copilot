import json
from Utils import LLMResponseParser
from Prompts import CODE_REVIEWER_PROMPT_TEMPLATE
class CodeReviewerAgent:
    def __init__(self, llm, metrics: list):
        self.llm = llm
        self.metrics = metrics  # e.g., ["security", "readability", "performance"]
        
    def generate_review(self, issues: dict, repo_summary: dict, additional_instructions: str = ""):
        aligned_issues = list(zip(issues["syntax"], issues["standards"], issues["error_analysis"]))
        output = []
        for issue in aligned_issues:
            review_prompt = CODE_REVIEWER_PROMPT_TEMPLATE.format(issue=json.dumps(issue, indent=4), repo_summary=repo_summary, metrics=', '.join(self.metrics),ratings=', '.join([f'"{metric}": "score_value: reason_for_score"' for metric in self.metrics]),additional_instructions=additional_instructions)
            response = self.llm.invoke(review_prompt)
            result = LLMResponseParser.parse_response(response.content)
            output.append(result)
        return output