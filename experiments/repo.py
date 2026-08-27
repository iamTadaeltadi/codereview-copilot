"""Fetch a repository at one commit and build its code graph, one at a time.

Nothing is kept that is not needed. A source tree is downloaded, parsed into a
graph, the graph is cached, and the tree is deleted. Peak disk stays near the
size of the largest single repository rather than the sum of 259 of them, which
is what makes the study runnable on a laptop.

GitHub's codeload tarball endpoint is used rather than git clone: a clone of
pandas or ansible at a single commit still transfers far more than the tree.
"""

from __future__ import annotations

import os
import pickle
import time
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


CODELOAD = "https://codeload.github.com/{repo}/tar.gz/{commit}"
SUPPORTED_EXTENSIONS = {".py", ".js", ".java", ".c"}
DEFAULT_CACHE = Path(".repo-cache")
DEFAULT_ATTEMPTS = 4
MAX_FILES = 4000


class RepoError(RuntimeError):
    pass


@dataclass
class GraphInfo:
    nodes: int
    edges: int
    files: int
    cached: bool


def _cache_path(cache_dir, repo: str, commit: str) -> Path:
    safe = repo.replace("/", "__")
    return Path(cache_dir) / f"{safe}@{commit[:12]}.pkl"


def download_tree(repo: str, commit: str, destination, token: str = "",
                  attempts: int = DEFAULT_ATTEMPTS) -> Path:
    url = CODELOAD.format(repo=repo, commit=commit)
    headers = {"User-Agent": "codereview-copilot-experiments"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    archive = Path(destination) / "src.tar.gz"

    last_error = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=300) as response, archive.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            if archive.stat().st_size > 0:
                break
            last_error = "empty archive"
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 404):
                raise RepoError(f"{repo}@{commit[:8]}: HTTP {error.code}") from error
            last_error = f"HTTP {error.code}"
        except Exception as error:
            last_error = error
        archive.unlink(missing_ok=True)
        time.sleep(min(20, 2 ** attempt))
    else:
        raise RepoError(f"{repo}@{commit[:8]}: gave up after {attempts} attempts: {last_error}")

    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(destination, filter="data")
    archive.unlink()

    roots = [p for p in Path(destination).iterdir() if p.is_dir()]
    if not roots:
        raise RepoError(f"{repo}@{commit[:8]}: archive contained no directory")
    return roots[0]


def build_graph_from_tree(root, max_files: int = MAX_FILES):
    from codecontext.construct_graph import CodeGraph

    root = Path(root)
    all_paths, code_paths = [], []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv"}]
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), root)
            all_paths.append(rel)
            if os.path.splitext(name)[1] in SUPPORTED_EXTENSIONS:
                code_paths.append(rel)

    code_paths.sort()
    truncated = code_paths[:max_files]

    builder = CodeGraph(root=str(root))
    builder.all_source_files = [p for p in all_paths if os.path.splitext(p)[1]]
    tags = []
    for rel in truncated:
        try:
            with open(root / rel, encoding="utf-8", errors="ignore") as handle:
                tags.extend(builder.parse_code_string(handle.read(), rel))
        except Exception:
            continue
    return builder.tag_to_graph(tags), len(truncated)


def graph_for(repo: str, commit: str, cache_dir=DEFAULT_CACHE, token: str = "",
              max_files: int = MAX_FILES):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = _cache_path(cache_dir, repo, commit)

    if cached.is_file():
        with cached.open("rb") as handle:
            graph = pickle.load(handle)
        return graph, GraphInfo(len(graph.nodes), len(graph.edges), 0, cached=True)

    workdir = tempfile.mkdtemp(prefix="repo-")
    try:
        root = download_tree(repo, commit, workdir, token=token)
        graph, files = build_graph_from_tree(root, max_files=max_files)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    with cached.open("wb") as handle:
        pickle.dump(graph, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return graph, GraphInfo(len(graph.nodes), len(graph.edges), files, cached=False)


def evict(cache_dir=DEFAULT_CACHE, keep_bytes: int = 2_000_000_000) -> int:
    """Drop the oldest cached graphs once the cache exceeds keep_bytes."""
    cache_dir = Path(cache_dir)
    if not cache_dir.is_dir():
        return 0
    entries = sorted(cache_dir.glob("*.pkl"), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in entries)
    removed = 0
    for path in entries:
        if total <= keep_bytes:
            break
        size = path.stat().st_size
        path.unlink()
        total -= size
        removed += 1
    return removed
