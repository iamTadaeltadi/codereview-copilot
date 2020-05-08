from typing import List
from Utils import LLMResponseParser
from Prompts import REREVIEW_PLANNER_PROMPT_TEMPLATE, REVIEW_STRUCTURE_PROMPT_TEMPLATE
class ReReviewPlannerAgent:
    def __init__(self, llm):
        self.llm = llm

    def re_review_planner(self, feedback:str, episodic_context: List[str] = None):
        episodic_context_str = "\n".join(episodic_context) if episodic_context else "No previous context available."
        prompt= REREVIEW_PLANNER_PROMPT_TEMPLATE.format(
            feedback=feedback,
            review_structure=REVIEW_STRUCTURE_PROMPT_TEMPLATE,
            episodic_context = episodic_context_str)
        response = self.llm.invoke(prompt).content
        re_run_plan = LLMResponseParser.parse_response(response)
        return re_run_plan