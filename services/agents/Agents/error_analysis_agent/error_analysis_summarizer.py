import json
from Utils import LLMResponseParser
from Prompts import ERROR_SUMMARIZER_PROMPT_TEMPLATE
class ErrorAnalysisSummarizer:
    def __init__(self, llm):
        self.llm = llm
        
    def summarize(self, results: list):
        summary_prompt = ERROR_SUMMARIZER_PROMPT_TEMPLATE.format(results=json.dumps(results))
        response = self.llm.invoke(summary_prompt)
        result = LLMResponseParser.parse_response(response.content)
        return result