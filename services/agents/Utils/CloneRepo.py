import os
from git import Repo
import uuid
def clone_repository(git_url: str,branch_name:str, destination_path: str) -> None:
    """
    Clones a Git repository from the given URL into the specified local folder.
    """
    # Prepare environment for the Git command to prevent interactive prompts
    git_env = os.environ.copy()
    git_env["GIT_TERMINAL_PROMPT"] = "0"
    if not os.path.exists(destination_path):
        os.makedirs(destination_path, exist_ok=True)
    Repo.clone_from(git_url, destination_path,branch=branch_name,env=git_env)
    print(f"Repository cloned to: {destination_path}")

# Example usage:
if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")
    user = "abdissa-png"
    repo = "Evolve-startup-incubator"
    branch_name = "master"
    repo_url = "https://{github_token}@github.com/{user}/{repo}.git"
    folder_path = f"./tmp/repo/{repo}-{branch_name}-{uuid.uuid4()}"
    clone_repository(repo_url.format(github_token=github_token,user=user,repo=repo), branch_name, folder_path)