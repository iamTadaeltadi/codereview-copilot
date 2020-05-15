from Utils import LLMResponseParser
from Prompts import SYNTAX_CHECKER_PROMPT_TEMPLATE
class SyntaxCheckerAgent:
    def __init__(self, llm):
        self.llm = llm
        
    def analyze(self, diff: dict,additional_instructions: str = ""):    
        # Language detection
        language = diff['file_path'].split("\n")[0].split('.')[-1]
        
        # Generate LLM prompt
        prompt = SYNTAX_CHECKER_PROMPT_TEMPLATE.format(language=language,diff_content=diff['content'],additional_instructions=additional_instructions)
        
        # Call LLM
        response = self.llm.invoke(prompt)
        result = LLMResponseParser.parse_response(response.content)
        return result