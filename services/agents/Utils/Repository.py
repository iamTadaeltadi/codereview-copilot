import subprocess
from typing import Dict, Optional
import uuid
from config import Config
from . import clone_repository
import os
import shutil 

def clone_repo(user: str, repo: str, branch_name:str, user_github_token: Optional[str] = None, commit_hash: Optional[str] = None):
    github_token = user_github_token if user_github_token else Config.GITHUB_TOKEN
    repo_url = f"https://{github_token}@github.com/{user}/{repo}.git"

    repo_identifier = f"{repo}-{branch_name}"
    if commit_hash:
        repo_identifier = f"{repo}-{commit_hash[:7]}" # Use short commit hash for uniqueness

    repo_folder_path = os.path.join(".", "tmp", "repo", f"{repo_identifier}-{uuid.uuid4()}")
    
    # If commit_hash is specified, we need to clone the default branch first, then checkout.
    clone_repository(repo_url, branch_name, repo_folder_path)

    if commit_hash:
        try:
            # Checkout the specific commit
            subprocess.run(["git", "checkout", commit_hash], cwd=repo_folder_path, check=True, capture_output=True)
            print(f"Checked out commit {commit_hash} in {repo_folder_path}")
        except subprocess.CalledProcessError as e:
            print(f"Error checking out commit {commit_hash}: {e.stderr.decode()}")
            raise ValueError(f"Failed to checkout commit {commit_hash}: {e.stderr.decode()}") from e
            
    return repo_folder_path

def setup_local_repo_from_files(files_content: Dict[str, str], base_tmp_dir: str = "./tmp/local_repos") -> str:
    """
    Creates a temporary local repository structure from a dictionary of file paths and content.
    Returns the path to the created repository root.
    """
    repo_name = f"local-repo-{uuid.uuid4()}"
    repo_root_path = os.path.join(base_tmp_dir, repo_name)
    
    if os.path.exists(repo_root_path):
        shutil.rmtree(repo_root_path) # Clean up if exists, though uuid should make it unique
    os.makedirs(repo_root_path, exist_ok=True)
    
    for file_path, content in files_content.items():
        full_file_path = os.path.join(repo_root_path, file_path)
        os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
        with open(full_file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
    return repo_root_path