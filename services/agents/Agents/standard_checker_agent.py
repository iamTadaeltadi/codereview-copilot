from Utils import LLMResponseParser
from Prompts import STANDARD_CHECKER_PROMPT_TEMPLATE
class StandardCheckerAgent:
    def __init__(self, llm, standards: list):
        self.llm = llm
        self.standards = standards

    def check_compliance(self, diff: dict, additional_instructions: str = ""):
        # Generate standards prompt
        standards_str = "\n".join(self.standards)
        prompt = STANDARD_CHECKER_PROMPT_TEMPLATE.format(standards_str=standards_str, diff_content=diff['content'],additional_instructions=additional_instructions)
        # Call LLM and process response
        response = self.llm.invoke(prompt)
        result = LLMResponseParser.parse_response(response.content)
        return result