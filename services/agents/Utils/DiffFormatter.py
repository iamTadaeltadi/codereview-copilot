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
                    current_chunk["new_line"] += 1
                elif line.startswith("-"):
                    current_chunk["changes"].append(
                        {
                            "type": "deletion",
                            "content": line[1:],
                            "old_line_number": current_chunk["old_line"],
                        }
                    )
                    current_chunk["old_line"] += 1
                elif line.startswith("\\"):
                    # Handle "No newline at end of file" cases
                    continue
                else:  # Context line
                    current_chunk["changes"].append(
                        {
                            "type": "context",
                            "content": line[1:] if line.startswith(" ") else line,
                            "old_line_number": current_chunk["old_line"],
                            "new_line_number": current_chunk["new_line"],
                        }
                    )
                    current_chunk["old_line"] += 1
                    current_chunk["new_line"] += 1

        if current_file:
            self.formatted_files.append(current_file)

        return self.format_for_agent()

    def _extract_file_path(self, diff_header):
        """Extract the file path from diff header line."""
        parts = diff_header.split(" ")
        path = parts[-1]
        if path.startswith("a/") or path.startswith("b/"):
            return path[2:]
        return path

    def _parse_chunk_header(self, header):
        """Parse the @@ line to get the line numbers."""
        # Example: @@ -1,7 +1,6 @@
        parts = header.split(" ")
        old_start = int(parts[1].split(",")[0].lstrip("-"))
        new_start = int(parts[2].split(",")[0].lstrip("+"))

        return {
            "header": header,
            "old_start": old_start,
            "new_start": new_start,
            "old_line": old_start,
            "new_line": new_start,
            "changes": [],
        }

    def format_for_agent(self):
        """Format the parsed diff in a clear, AI-friendly format."""
        formatted_output = []
        final_output = []
        id = 0
        for file in self.formatted_files:
            file_info = f"\nFile: {file['file_path']}\n"
            if "metadata" in file:
                file_info += f"Metadata: {file['metadata']}\n"
            formatted_output.append(file_info)

            for chunk in file["chunks"]:
                formatted_output.append(f"\nChunk {chunk['header']}")
                max_line_number_length = max(
                    [
                        len(str(change["new_line_number"]))
                        for change in chunk["changes"]
                        if change["type"] != "deletion"
                    ]
                )
                for change in chunk["changes"]:
                    if change["type"] == "addition":
                        line_info = f"+ {change['new_line_number']}"
                        line_info = line_info.rjust(max_line_number_length + 2)
                    elif change["type"] == "deletion":
                        line_info = " "
                        line_info = "-" + line_info.rjust(max_line_number_length + 1)
                    else:
                        line_info = f" {change['new_line_number']}"
                        line_info = line_info.rjust(max_line_number_length + 2)
                    # spaces = ' ' * (15 - len(line_info))
                    spaces = ""
                    formatted_output.append(f"{line_info}{spaces}: {change['content']}")
            final_output.append({
                "id": id,
                "file_path": file["file_path"],
                "content":"\n".join(formatted_output)
                })
            id += 1
            formatted_output = []
        return final_output

    def get_structured_diff(self):
        """Return the structured diff data for programmatic use."""
        return self.formatted_files

def get_pr_diff(owner: str, repo: str, pull_number: str, user_github_token: t.Optional[str] = None) -> str:
    """
    Get .diff data for a github PR.

    :param owner: Name of the owner of the repository.
    :param repo: Name of the repository.
    :param pull_number: Pull request number to retrive the diff for.
    :param thought: Thought to be used for the request.

    :return diff: .diff content for give pull request.
    """
    user_github_token = user_github_token if user_github_token else Config.GITHUB_TOKEN
    diff_text = requests.get(
        DIFF_URL.format(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
        ),
        headers= {        
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {user_github_token}" if user_github_token else ""
            }
    ).text
    return DiffFormatter(diff_text).parse_and_format()

def get_pr_metadata(owner: str, repo: str, pull_number: str, user_github_token: t.Optional[str] = None) -> t.Dict:
    """
    Get metadata for a github PR.

    :param owner: Name of the owner of the repository.
    :param repo: Name of the repository.
    :param pull_number: Pull request number to retrive the diff for.
    :param thought: Thought to be used for the request.

    :return metadata: Metadata for give pull request.
    """
    user_github_token = user_github_token if user_github_token else Config.GITHUB_TOKEN
    data = requests.get(
        PR_URL.format(
