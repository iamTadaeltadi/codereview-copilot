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

import re
import time
import urllib.error
import urllib.request
from pathlib import Path


RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"
SUPPORTED_EXTENSIONS = {".py", ".js", ".java", ".c"}
DEFAULT_ATTEMPTS = 3
DEFAULT_TIMEOUT = 45
MAX_FILES = 60

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

    for attempt in range(attempts):
        try:
            if opener is not None:
                return opener(url)
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 404):
                return None
        except Exception:
            pass
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


def collect_sources(repo: str, commit: str, diff: str, token: str = "",
                    max_files: int = MAX_FILES, import_hops: int = 1, opener=None):
    """Return {relative_path: source} for the diff's files and their imports."""
    sources = {}
    # A path that returned nothing must be remembered too, or the next hop asks
    # for it again. On a slow link every wasted request costs seconds.
    attempted = set()

    def fetch(path):
        if path in attempted:
            return None
        attempted.add(path)
        return fetch_file(repo, commit, path, token=token, opener=opener)

    for path in paths_in_diff(diff)[:max_files]:
        text = fetch(path)
        if text is not None:
            sources[path] = text

    roots = sorted({p.split("/")[0] for p in sources if "/" in p})
    frontier = list(sources.items())
    for _ in range(max(0, import_hops)):
        if len(sources) >= max_files:
            break
        candidates = []
        for path, text in frontier:
            candidates.extend(imported_paths(text, path, roots))
        frontier = []
        for candidate in dict.fromkeys(candidates):
            if len(sources) >= max_files:
                break
            if candidate in attempted or Path(candidate).suffix not in SUPPORTED_EXTENSIONS:
                continue
            text = fetch(candidate)
            if text is not None:
                sources[candidate] = text
                frontier.append((candidate, text))
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
