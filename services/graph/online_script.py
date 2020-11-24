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
