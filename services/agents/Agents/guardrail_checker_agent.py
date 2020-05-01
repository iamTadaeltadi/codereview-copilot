from Utils import LLMResponseParser
from Prompts import GUARDRAIL_CHECKER_PROMPT_TEMPLATE
class GuardrailCheckerAgent:
    def __init__(self, llm):
        self.llm = llm
    def guardrail_checker(self, feedback:str):
        prompt = GUARDRAIL_CHECKER_PROMPT_TEMPLATE.format(feedback=feedback)
        response = self.llm.invoke(prompt).content
        result = LLMResponseParser.parse_response(response)
        return result
    