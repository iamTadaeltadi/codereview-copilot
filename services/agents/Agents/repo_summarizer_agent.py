import os
import json
from Utils import LLMResponseParser
from Prompts import REPO_SUMMARIZER_PROMPT_TEMPLATE
class RepoSummarizerAgent:
    def __init__(self, llm):
        self.llm = llm

    def _build_file_tree(self, path: str) -> dict:
        tree = {}
        for entry in os.scandir(path):
            if entry.is_dir():
                tree[entry.name] = self._build_file_tree(entry.path)
            else:
                tree[entry.name] = "file"
        return tree

    def summarize_repository(self, repo_folder_path: str) -> dict:
        """
        Inspect the repository, construct a file tree, and use the LLM to:
        - Identify project type (frameworks, language, etc.)
        - Detect tools or libraries used
        - Describe overall architecture and setup
        """
        file_tree = self._build_file_tree(repo_folder_path)
        file_tree_json = json.dumps(file_tree, indent=2)
        prompt = REPO_SUMMARIZER_PROMPT_TEMPLATE.format(repo_folder_path=repo_folder_path, file_tree_json=file_tree_json)
        response = self.llm.invoke(prompt)
        result = LLMResponseParser.parse_response(response.content)
        return result