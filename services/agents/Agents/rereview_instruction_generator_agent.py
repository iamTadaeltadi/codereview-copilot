from typing import List
import jmespath
import json
from Utils import LLMResponseParser
from Prompts import REREVIEW_INSTRUCTION_GENERATOR_PROMPT_TEMPLATE, REVIEW_STRUCTURE_PROMPT_TEMPLATE
class ReReviewInstructionGeneratorAgent:
    def __init__(self, llm):
        self.llm = llm

    def re_review_instruction_generator(self, re_run_plan: dict, original_review: dict, feedback: str, preference_context: str, episodic_context: List[str] = None):
        instructions = {}
        files = jmespath.search("review.error_analysis[].current_diff.file_path",original_review)
        print(f"Files to re-review: {files}") # Debug: Check files to re-review

        episodic_context_str = "\n".join(episodic_context) if episodic_context else "No previous context available."

        for file, steps in re_run_plan.items():
            instructions[file] = {}
            for step in steps:
                prompt = REREVIEW_INSTRUCTION_GENERATOR_PROMPT_TEMPLATE.format(
                    feedback=feedback,
                    file=file,
                    step=step,
                    review_structure=REVIEW_STRUCTURE_PROMPT_TEMPLATE,
                    files=((i,file) for i,files in enumerate(files)),
                    preference_context=preference_context,
                    episodic_context=episodic_context_str
                )
                response = self.llm.invoke(prompt).content
                result = LLMResponseParser.parse_response(response)
                if result:
                    queries = result.get("queries", [])
                    instruction = result.get("instruction", "")
                else:
                    queries = []
                    instruction = ""
                current_section = [jmespath.search(query, original_review) for query in queries] if queries else "No current issues."
                current_section_str = json.dumps(current_section, indent=2) if queries and current_section else "No current issues."
                instructions[file][step] = {
                    "queries": queries,
                    "instruction": instruction,
                    "current_section": current_section_str
                }
        print(f"Generated instructions: {instructions.keys()}")
        return instructions   