import json
from Prompts import CODE_SUMMARIZER_PROMPT_TEMPLATE,CODE_SUMMARY_MERGER_PROMPT_TEMPLATE
class CodeSummarizerAgent:
    def __init__(self, llm):
        self.llm = llm

    def summarize_pr(self, diffs: list):
        # Summarize each diff independently
        individual_summaries = []
        for diff in diffs:
            summary = self.summarize_diff(diff)
            individual_summaries.append(summary)

        # Merge the individual summaries
        merged_summary = self.merge_summaries(individual_summaries)
        return merged_summary

    def summarize_diff(self, diff: dict):
        summary_prompt = CODE_SUMMARIZER_PROMPT_TEMPLATE.format(file_path=diff['file_path'],diff_content=diff['content'])
        return self.llm.invoke(summary_prompt).content

    def merge_summaries(self, summaries: list):
        merge_prompt = CODE_SUMMARY_MERGER_PROMPT_TEMPLATE.format(summaries=json.dumps(summaries))
        return self.llm.invoke(merge_prompt).content
