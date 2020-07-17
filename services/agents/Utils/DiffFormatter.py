import typing as t

import requests
from config import Config

DIFF_URL = "https://github.com/{owner}/{repo}/pull/{pull_number}.diff"
PR_URL = "https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"
GITHUB_API_BASE_URL = "https://api.github.com"

def get_repo_default_branch(owner: str, repo: str, user_github_token: t.Optional[str] = None) -> str:
    """
    Get the default branch name for a given repository.
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if user_github_token:
        headers["Authorization"] = f"Bearer {user_github_token}"
    
    response = requests.get(url, headers=headers)
    response.raise_for_status() # Raise an exception for HTTP errors
    repo_data = response.json()
    default_branch = repo_data.get("default_branch")
    if not default_branch:
        raise ValueError(f"Could not determine default branch for {owner}/{repo}")
    return default_branch
class DiffFormatter:
    def __init__(self, diff_text):
        self.diff_text = diff_text
        self.formatted_files = []

    def parse_and_format(self):
        """Parse the diff and return a structured format suitable for an AI review agent."""
        current_file = None
        current_chunk = None
        lines = self.diff_text.split("\n")
        for line in lines:
            # New file
            if line.startswith("diff --git"):
                if current_file:
                    self.formatted_files.append(current_file)
                current_file = {
                    "file_path": self._extract_file_path(line),
                    "chunks": [],
                }

            # File metadata (index, mode changes etc)
            elif (
                line.startswith("index ")
                or line.startswith("new file")
                or line.startswith("deleted file")
            ):
                if current_file:
                    current_file["metadata"] = line

            # Chunk header
            elif line.startswith("@@"):
                if current_file:
                    current_chunk = self._parse_chunk_header(line)
                    current_file["chunks"].append(current_chunk)

            # Content lines
            elif current_chunk is not None and current_file is not None:
                if line.startswith("+"):
                    current_chunk["changes"].append(
                        {
                            "type": "addition",
                            "content": line[1:],
                            "new_line_number": current_chunk["new_line"],
                        }
                    )
