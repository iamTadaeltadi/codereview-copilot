#!/usr/bin/env python3
import requests
import os
import sys
import json
import re

from codecontext.construct_graph import CodeGraph

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = None  # Set your token here if needed

# Headers for optional authentication
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def extract_repo_details(repo_url):
    """
    Extract owner and repo name from a GitHub URL.
    Example: https://github.com/user/repo -> ("user", "repo")
    """
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)", repo_url)
    if not match:
        print("Invalid GitHub URL format. Expected format: https://github.com/owner/repo")
        sys.exit(1)
    return match.group(1), match.group(2)

def get_default_branch(owner, repo):
    """
    Fetch the default branch (e.g., 'main' or 'master') for a repository.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    try:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json().get("default_branch", "master")  # Default to master if missing
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching default branch: {e}")
        sys.exit(1)

def list_repo_files(owner, repo, branch):
    """
    Fetch all file paths from the GitHub repository tree.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 404:
        print(f"Error: Repository '{owner}/{repo}' or branch '{branch}' not found.")
        sys.exit(1)
    resp.raise_for_status()
    data = resp.json()
    return [item["path"] for item in data.get("tree", []) if item["type"] == "blob"]

def fetch_file_content(owner, repo, branch, path):
    """
    Fetch the raw content of a file from GitHub.
    """
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    resp = requests.get(raw_url, headers=HEADERS)
    resp.raise_for_status()
    return resp.text

def main():
    if len(sys.argv) < 2:
        print("Usage: python online_script.py <github_repo_url> [branch]")
        sys.exit(1)

    repo_url = sys.argv[1]
    owner, repo = extract_repo_details(repo_url)

    # Get branch if provided, otherwise fetch default branch
    branch = sys.argv[2] if len(sys.argv) >= 3 else get_default_branch(owner, repo)

    print(f"Processing GitHub Repository: {owner}/{repo} (Branch: {branch})")

    # 1) Get all files in the repo
    all_paths = list_repo_files(owner, repo, branch)

    # 2) Filter code files by extensions
    valid_exts = {".py", ".js", ".java", ".c"}
    code_paths = [p for p in all_paths if os.path.splitext(p)[1] in valid_exts]

    # 3) Initialize CodeGraph
    code_graph = CodeGraph(root=".")

    all_tags = []

    # 4) Fetch file content and parse
    for path in code_paths:
        try:
            code_string = fetch_file_content(owner, repo, branch, path)
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching content for {path}: {e}")
            continue

        rel_fname = path
        file_tags = code_graph.parse_code_string(code_string, rel_fname)
        all_tags.extend(file_tags)

    # 5) Convert to graph structure
    G = code_graph.tag_to_graph(all_tags)

    # 6) Print graph statistics
    print("---------------------------------")
    print(f"Constructed code graph for: {repo_url} (branch: {branch})")
    print(f"   Number of nodes: {len(G.nodes())}")
    print(f"   Number of edges: {len(G.edges())}")
    print("---------------------------------")

    # 7) Generate metadata JSON
    final_nodes = []
    for node_id in G.nodes:
        data = G.nodes[node_id]
        node_type = data["type"]

        out = {
            "Node_id": node_id,
            "Node_type": node_type,
            "name": data["name"],
            "filepath": data["relative_path"],
            "start_line": data["line_range"][0],
