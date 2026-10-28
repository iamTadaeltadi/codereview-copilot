"""Build a code graph from only the files a diff touches, plus one import hop.

Downloading whole repositories is not possible on every connection: the tasks
here span repositories of 100-200MB and there are 259 of them. This module
fetches individual files over raw.githubusercontent instead, which turns a
150MB transfer into tens of kilobytes.

The cost is honest and must be stated in the paper: the graph covers the
changed files and their immediate imports rather than the whole repository, so
condition B retrieves from a neighbourhood rather than from everything. One
import hop is kept deliberately, because cross-file structure is the only thing
a graph offers that a text search does not, and a graph of the diff alone would
have no cross-file edges left to test.
"""

from __future__ import annotations

import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request
from pathlib import Path


RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"
SUPPORTED_EXTENSIONS = {".py", ".js", ".java", ".c"}
DEFAULT_ATTEMPTS = 3
DEFAULT_TIMEOUT = 45
MAX_FILES = 60
DEFAULT_WORKERS = 12

DIFF_PATH = re.compile(r"^diff --git a/(?P<a>.+?) b/(?P<b>.+)$", re.M)
PY_FROM = re.compile(r"^\s*from\s+([.\w]*)\s+import\s+(.+)$", re.M)
PY_IMPORT = re.compile(r"^\s*import\s+([.\w]+)", re.M)
JS_IMPORT = re.compile(r"""(?:from|require\()\s*['"]([^'"]+)['"]""")


def paths_in_diff(diff: str):
    seen, out = set(), []
    for match in DIFF_PATH.finditer(diff or ""):
        for path in (match.group("b"), match.group("a")):
            if path in seen or path == "/dev/null":
                continue
            seen.add(path)
            if Path(path).suffix in SUPPORTED_EXTENSIONS:
                out.append(path)
    return out


def fetch_file(repo: str, commit: str, path: str, token: str = "",
               attempts: int = DEFAULT_ATTEMPTS, timeout: int = DEFAULT_TIMEOUT,
               opener=None):
    url = RAW.format(repo=repo, commit=commit, path=path)
    headers = {"User-Agent": "codereview-copilot-experiments"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    debug = os.environ.get("SPARSE_DEBUG")
    started = time.time()
    for attempt in range(attempts):
        status = "?"
        try:
            if opener is not None:
                return opener(url)
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8", errors="ignore")
            if debug:
                print(f"    fetch {path} 200 {len(text)}b {time.time()-started:.1f}s", file=sys.stderr, flush=True)
            return text
        except urllib.error.HTTPError as error:
            status = error.code
            if error.code in (401, 403, 404):
                if debug:
                    print(f"    fetch {path} {status} {time.time()-started:.1f}s", file=sys.stderr, flush=True)
                return None
        except Exception as error:
            status = type(error).__name__
        if debug:
            print(f"    fetch {path} attempt {attempt+1} {status} {time.time()-started:.1f}s", file=sys.stderr, flush=True)
        if attempt + 1 < attempts:
            time.sleep(min(8, 2 ** attempt))
    return None


def _module_candidates(module: str, extension: str):
    if not module:
        return []
    parts = module.lstrip(".").split(".")
    if not parts or not parts[0]:
        return []
    stem = "/".join(parts)
    if extension == ".py":
        return [f"{stem}.py", f"{stem}/__init__.py"]
    return [f"{stem}{extension}", f"{stem}/index{extension}"]


def imported_paths(source: str, path: str, roots):
    """Guess repository-relative paths for the imports in one file."""
    extension = Path(path).suffix
    out = []
    base = str(Path(path).parent)

    if extension == ".py":
        for module, names in PY_FROM.findall(source or ""):
            if module.startswith("."):
                # "from . import sibling" names the module; "from .pkg import x"
                # names the package. Both resolve against this file's directory.
                stem = module.lstrip(".").replace(".", "/")
                targets = [stem] if stem else [
                    n.strip().split(" as ")[0].strip()
                    for n in names.replace("(", "").replace(")", "").split(",")
                    if n.strip() and n.strip() != "*"
                ]
                for target in targets:
                    if not target:
                        continue
                    prefix = f"{base}/{target}".lstrip("/")
                    out.append(f"{prefix}.py")
                    out.append(f"{prefix}/__init__.py")
            elif module:
                for candidate in _module_candidates(module, extension):
                    out.append(candidate)
                    for root in roots:
                        out.append(f"{root}/{candidate}")
        for module in PY_IMPORT.findall(source or ""):
            for candidate in _module_candidates(module, extension):
                out.append(candidate)
                for root in roots:
                    out.append(f"{root}/{candidate}")
    elif extension == ".js":
        for module in JS_IMPORT.findall(source or ""):
            if module.startswith("@"):
                continue
            if module.startswith("."):
                prefix = str((Path(base) / module).as_posix()).lstrip("/")
                out.append(f"{prefix}{extension}")
                out.append(f"{prefix}/index{extension}")
                continue
            for candidate in _module_candidates(module, extension):
                out.append(candidate)
                for root in roots:
                    out.append(f"{root}/{candidate}")

    return list(dict.fromkeys(out))


TREES = "https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"


def repo_tree(repo: str, commit: str, token: str = "", cache_dir=None, attempts: int = 3):
    """The set of file paths in the repository at the commit, or None.

    One request per task replaces the hundreds of guessed import paths that
    do not exist: an import like `from a.b import c` yields candidates under
    every root prefix, and on a slow link each miss costs a full round trip.
    The result is the same set of files, fetched without the misses. The
    listing is cached on disk. Without a token the API allows 60 requests an
    hour, and the call waits for the reset when the quota is spent; a listing
    the API truncates (very large repositories) is treated as unavailable so
    the caller falls back to guessing.
    """
    import json
    cache = None
    if cache_dir is not None:
        cache = Path(cache_dir) / "trees" / f"{repo.replace('/', '__')}@{commit[:12]}.json"
        if cache.is_file():
            data = json.loads(cache.read_text())
            return set(data) if data is not None else None
    headers = {"User-Agent": "codereview-copilot-experiments", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    result = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(TREES.format(repo=repo, commit=commit), headers=headers)
            with urllib.request.urlopen(request, timeout=90) as response:
                body = json.load(response)
            if body.get("truncated"):
                result = None
            else:
                result = sorted(e["path"] for e in body.get("tree", []) if e.get("type") == "blob")
            break
        except urllib.error.HTTPError as error:
            if error.code in (403, 429) and error.headers.get("X-RateLimit-Remaining") == "0":
                reset = int(error.headers.get("X-RateLimit-Reset") or 0)
                wait = max(5, min(3700, reset - int(time.time()) + 2))
                print(f"  github api quota spent; waiting {wait}s for the reset", flush=True)
                time.sleep(wait)
                continue
            if error.code in (401, 404, 422):
                break
            time.sleep(min(30, 5 * 2 ** attempt))
        except Exception:
            time.sleep(min(30, 5 * 2 ** attempt))
    if cache is not None and result is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result))
    return set(result) if result is not None else None


def collect_sources(repo: str, commit: str, diff: str, token: str = "",
                    max_files: int = MAX_FILES, import_hops: int = 1, opener=None,
                    workers: int = DEFAULT_WORKERS, known_paths=None):
    """Return {relative_path: source} for the diff's files and their imports.

    Requests within a hop are issued concurrently. On a link where a single
    file takes seconds, fetching a hop's candidates one at a time is what makes
    a task cost minutes rather than seconds; the requests are independent, and
    most of the wall time is latency rather than bandwidth. With known_paths
    (the repository's file listing) candidates that do not exist are never
    requested; the files fetched are the same.
    """
    sources = {}
    # A path that returned nothing must be remembered too, or the next hop asks
    # for it again. On a slow link every wasted request costs seconds.
    attempted = set()

    def fetch_many(paths):
        wanted = [p for p in paths if p not in attempted]
        attempted.update(wanted)
        if not wanted:
            return []
        if workers <= 1 or len(wanted) == 1:
            results = [fetch_file(repo, commit, p, token=token, opener=opener) for p in wanted]
        else:
            with ThreadPoolExecutor(max_workers=min(workers, len(wanted))) as pool:
                results = list(
                    pool.map(
                        lambda p: fetch_file(repo, commit, p, token=token, opener=opener),
                        wanted,
                    )
                )
        return [(p, text) for p, text in zip(wanted, results) if text is not None]

    first = paths_in_diff(diff)
    if known_paths is not None:
        first = [p for p in first if p in known_paths]
    for path, text in fetch_many(first[:max_files]):
        sources[path] = text

    roots = sorted({p.split("/")[0] for p in sources if "/" in p})
    frontier = list(sources.items())
    for _ in range(max(0, import_hops)):
        if len(sources) >= max_files:
            break
        candidates = []
        for path, text in frontier:
            candidates.extend(imported_paths(text, path, roots))
        wanted = [
            c
            for c in dict.fromkeys(candidates)
            if c not in attempted and Path(c).suffix in SUPPORTED_EXTENSIONS
            and (known_paths is None or c in known_paths)
        ][: max(0, max_files - len(sources))]
        frontier = fetch_many(wanted)
        for path, text in frontier:
            sources[path] = text
    return sources


def graph_from_sources(sources):
    from codecontext.construct_graph import CodeGraph
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="sparse-"))
    for path, text in sources.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", errors="ignore")

    builder = CodeGraph(root=str(root))
    builder.all_source_files = list(sources)
    tags = []
    for path, text in sources.items():
        try:
            tags.extend(builder.parse_code_string(text, path))
        except Exception:
            continue
    return builder.tag_to_graph(tags)
