import json
from Prompts import CODE_FIX_PROMPT_TEMPLATE
class CodeFixAgent:
    def __init__(self, llm):
        self.llm = llm
        
    def generate_fix(self, diff: dict, issues: list, repo_summary: dict, additional_instructions: str = ""):
        fix_prompt = CODE_FIX_PROMPT_TEMPLATE.format(issues=json.dumps(issues), file_path=diff['file_path'], diff_content=diff['content'], repo_summary=repo_summary,additional_instructions=additional_instructions)
        return self.llm.invoke(fix_prompt).content