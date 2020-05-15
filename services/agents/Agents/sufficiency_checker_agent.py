from Utils import LLMResponseParser
import jmespath
from Prompts import SUFFICIENCY_CHECKER_PROMPT_TEMPLATE
class SufficiencyCheckerAgent:
    def __init__(self, llm):
        self.llm = llm

    def sufficiency_checker(self, feedback:str, original_review: dict, episodic_context: str):
        files = jmespath.search("review.error_analysis[].current_diff.file_path",original_review)
        prompt = SUFFICIENCY_CHECKER_PROMPT_TEMPLATE.format(feedback=feedback, files=files, episodic_context=episodic_context)
        response = self.llm.invoke(prompt).content
        result = LLMResponseParser.parse_response(response)
        return result