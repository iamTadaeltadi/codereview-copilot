#!/usr/bin/env python3
"""Validate the code graph's caller edges on repositories outside the c-CRAB task set.

    python experiments/validate_graph.py --old-builder /path/to/old_construct_graph.py

For each repository, up to --max-files Python files under one package prefix
are fetched at the current default-branch commit. Two graphs are built from
the same files: one with the builder as it was before the retrieval repair
(a saved copy of the old module) and one with the current builder.

The ground truth is independent of both builders: jedi's find-references
(`Script.get_references`) is run on each sampled function definition over
the same files, and a reference counts as a call when the referencing line
holds a call whose callee is that name; the caller is the function enclosing
that line. Jedi infers types, follows imports, aliases, re-exports and
inheritance on its own, so a caller it reports was not found with anything
the builders share. Targets are sampled with a fixed seed from the module-level
functions and methods in the fetched files; those with no jedi caller are
counted and set aside.

A second, grep-style check is reported for targets whose name is unique among
every definition in the fetched files: every call to that name, anywhere, is
a caller. It needs no resolution at all.

Caller recall and precision are reported per repository for the old and the
new builder. Nothing here reads a c-CRAB task; the repositories, commits and
functions are chosen without reference to the benchmark.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import random
import sys
import tempfile
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "services", "graph")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.sparse import fetch_file  # noqa: E402

REPOS = [
    # (repository, package prefix); PostHog is in c-CRAB, so it is taken at a
    # current commit and a package the benchmark's tasks do not touch.
    ("PostHog/posthog", "posthog/hogql/"),
    ("psf/requests", "src/requests/"),
    ("pallets/flask", "src/flask/"),
    ("encode/httpx", "httpx/"),
    ("Textualize/rich", "rich/"),
    ("fastapi/fastapi", "fastapi/"),
]


def gh(url):
    request = urllib.request.Request(url, headers={"User-Agent": "codereview-copilot-validation",
                                                   "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def repo_files(repo: str, prefix: str, max_files: int):
    meta = gh(f"https://api.github.com/repos/{repo}")
    branch = meta["default_branch"]
    commit = gh(f"https://api.github.com/repos/{repo}/commits/{branch}")["sha"]
    tree = gh(f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1")["tree"]
    paths = sorted(
        e["path"] for e in tree
        if e["type"] == "blob" and e["path"].startswith(prefix) and e["path"].endswith(".py")
        and "/tests/" not in e["path"] and "/test_" not in e["path"] and e.get("size", 0) <= 80_000
    )
    return commit, paths[:max_files]


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_tree(sources) -> Path:
    root = Path(tempfile.mkdtemp(prefix="validate-"))
    for path, text in sources.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", errors="ignore")
    return root


def graph_with_builder(module, sources, root):
    builder = module.CodeGraph(root=str(root))
    builder.all_source_files = list(sources)
    tags = []
    for path, text in sources.items():
        try:
            tags.extend(builder.parse_code_string(text, path))
        except Exception:
            continue
    return builder.tag_to_graph(tags)


# ------------------------------------------------------------------- targets


class Definitions:
    """Module-level functions and methods, with the position of each name, by `ast`."""

    def __init__(self, sources):
        self.sources = sources
        self.trees = {}
        self.targets = []            # (file, name, class or None, line, column)
        self.name_count = defaultdict(int)
        self.functions = defaultdict(list)   # file -> [(name, first line, last line)]
        self.call_lines = defaultdict(set)   # (file, callee name) -> {lines holding such a call}
        for path, text in sources.items():
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            self.trees[path] = tree
            lines = text.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.functions[path].append((node.name, node.lineno, node.end_lineno or node.lineno))
                if isinstance(node, ast.Call):
                    fn = node.func
                    callee = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else None
                    if callee:
                        self.call_lines[(path, callee)].add(fn.end_lineno or node.lineno)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._add(path, node, None, lines)
                elif isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("__"):
                            self._add(path, item, node.name, lines)

    def _add(self, path, node, cls, lines):
        line = lines[node.lineno - 1] if node.lineno - 1 < len(lines) else ""
        column = line.find(f"def {node.name}")
        if column < 0:
            return
        self.targets.append((path, node.name, cls, node.lineno, column + 4))
        self.name_count[node.name] += 1

    def enclosing(self, path, line):
        """The innermost function whose span holds the line, or None."""
        best = None
        for name, first, last in self.functions.get(path, ()):
            if first <= line <= last and (best is None or last - first < best[2] - best[1]):
                best = (name, first, last)
        return best[0] if best else None

    def loose_callers(self, name):
        """Every function holding a call to `name`, anywhere, regardless of resolution."""
        out = set()
        for (path, callee), lines in self.call_lines.items():
            if callee != name:
                continue
            for line in lines:
                func = self.enclosing(path, line)
                if func:
                    out.add((path, func))
        return out


def jedi_callers(root: Path, defs: Definitions, path: str, name: str, line: int, column: int):
    """{(file, enclosing function)} for every jedi reference that is a call."""
    import jedi

    project = jedi.Project(path=str(root), added_sys_path=[str(root)])
    script = jedi.Script(path=str(root / path), project=project)
    out = set()
    for ref in script.get_references(line, column, include_builtins=False):
        if ref.is_definition() or ref.module_path is None:
            continue
        try:
            rel = str(Path(ref.module_path).relative_to(root))
        except ValueError:
            continue
        if ref.line not in defs.call_lines.get((rel, name), ()):
            continue
        func = defs.enclosing(rel, ref.line)
        if func:
            out.add((rel, func))
    return out


def graph_callers(graph, target_file, name):
    key = f"{target_file}::function::{name}"
    if not graph.has_node(key):
        return None
    out = set()
    for u, _, data in graph.in_edges(key, data=True):
        if data.get("label") == "calls":
            d = graph.nodes[u]
            out.add((d.get("relative_path"), d.get("name")))
    return out


def graph_stats(graph):
    calls = [(u, v) for u, v, d in graph.edges(data=True) if d.get("label") == "calls"]
    cross = sum(1 for u, v in calls if graph.nodes[u].get("relative_path") != graph.nodes[v].get("relative_path"))
    functions = [n for n, d in graph.nodes(data=True) if d.get("type") == "function"]
    phantom = sum(1 for n in functions
                  if not any(d.get("label") == "contains" for _, _, d in graph.in_edges(n, data=True)))
    return {"calls_edges": len(calls), "cross_file_calls": cross,
            "function_nodes": len(functions), "phantom_function_nodes": phantom}


def prf(rows, label, truth_key):
    tp = fp = fn = 0
    for row in rows:
        truth = row[truth_key]
        if truth is None:
            continue
        got = set(map(tuple, row[label]["callers"]))
        want = set(map(tuple, truth))
        tp += len(got & want); fp += len(got - want); fn += len(want - got)
    return {"tp": tp, "fp": fp, "fn": fn,
            "recall": tp / (tp + fn) if tp + fn else None,
            "precision": tp / (tp + fp) if tp + fp else None}


def validate(repo, prefix, old_module, new_module, max_files, per_repo, seed, out_dir):
    commit, paths = repo_files(repo, prefix, max_files)
    sources = {}
    for path in paths:
        text = fetch_file(repo, commit, path)
        if text is not None:
            sources[path] = text
    root = write_tree(sources)
    defs = Definitions(sources)

    rng = random.Random(seed)
    candidates = list(defs.targets)
    rng.shuffle(candidates)
    sampled, without = [], 0
    for path, name, cls, line, column in candidates:
        if len(sampled) >= per_repo:
            break
        try:
            callers = jedi_callers(root, defs, path, name, line, column)
        except Exception:
            continue
        if callers:
            sampled.append((path, name, cls, sorted(callers)))
        else:
            without += 1

    graphs = {"old": graph_with_builder(old_module, sources, root),
              "new": graph_with_builder(new_module, sources, root)}
    rows = []
    for path, name, cls, callers in sampled:
        unique = defs.name_count[name] == 1
        row = {"file": path, "name": name, "class": cls, "unique_name": unique,
               "jedi_callers": callers,
               "loose_callers": sorted(defs.loose_callers(name)) if unique else None}
        for label, graph in graphs.items():
            got = graph_callers(graph, path, name)
            row[label] = {"node_present": got is not None, "callers": sorted(got or [])}
        rows.append(row)

    summary = {"repo": repo, "commit": commit, "prefix": prefix, "files": len(sources),
               "definitions": len(defs.targets), "sampled_with_callers": len(sampled),
               "sampled_without_callers": without,
               "unique_name_targets": sum(1 for r in rows if r["unique_name"])}
    for label, graph in graphs.items():
        summary[label] = {**graph_stats(graph), "jedi": prf(rows, label, "jedi_callers"),
                          "loose_unique": prf(rows, label, "loose_callers")}
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / f"{repo.replace('/', '__')}.json").write_text(json.dumps({"summary": summary, "targets": rows}, indent=1))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old-builder", required=True, help="path to a copy of construct_graph.py before the repair")
    ap.add_argument("--out", default=str(Path(_ROOT) / "results" / "graph-validation"))
    ap.add_argument("--max-files", type=int, default=80)
    ap.add_argument("--per-repo", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    import jedi
    old_module = load_module("old_construct_graph", a.old_builder)
    from codecontext import construct_graph as new_module

    summaries = []
    for repo, prefix in REPOS:
        t0 = time.time()
        s = validate(repo, prefix, old_module, new_module, a.max_files, a.per_repo, a.seed, a.out)
        summaries.append(s)
        o, n = s["old"]["jedi"], s["new"]["jedi"]
        print(f"{repo:<20} files={s['files']:>3} targets={s['sampled_with_callers']:>3} (no caller: {s['sampled_without_callers']})  "
              f"old R={o['recall'] or 0:.2f} P={o['precision'] or 0:.2f}  new R={n['recall'] or 0:.2f} P={n['precision'] or 0:.2f}  "
              f"phantom {s['old']['phantom_function_nodes']}->{s['new']['phantom_function_nodes']}  {time.time()-t0:.0f}s", flush=True)

    lines = [f"ground truth: jedi {jedi.__version__} find-references on the same files; a reference counts as a call "
             f"when its line holds a call to the name, the caller is the enclosing function",
             f"sample: up to {a.per_repo} definitions per repository with at least one jedi caller, seed {a.seed}; "
             f"files: up to {a.max_files} per package prefix, tests excluded", "",
             f"{'repository':<20}{'commit':>9}{'files':>7}{'targets':>9}{'old recall':>12}{'old prec':>10}{'new recall':>12}{'new prec':>10}"
             f"{'loose R old':>13}{'loose R new':>13}{'phantom old':>13}{'phantom new':>13}"]
    agg = {"old": [0, 0, 0], "new": [0, 0, 0]}
    for s in summaries:
        o, n = s["old"]["jedi"], s["new"]["jedi"]
        for label in ("old", "new"):
            m = s[label]["jedi"]
            for i, k in enumerate(("tp", "fp", "fn")):
                agg[label][i] += m[k]
        f = lambda v: f"{v:.2f}" if v is not None else "-"
        lines.append(f"{s['repo']:<20}{s['commit'][:7]:>9}{s['files']:>7}{s['sampled_with_callers']:>9}"
                     f"{f(o['recall']):>12}{f(o['precision']):>10}{f(n['recall']):>12}{f(n['precision']):>10}"
                     f"{f(s['old']['loose_unique']['recall']):>13}{f(s['new']['loose_unique']['recall']):>13}"
                     f"{s['old']['phantom_function_nodes']:>13}{s['new']['phantom_function_nodes']:>13}")
    for label in ("old", "new"):
        tp, fp, fn = agg[label]
        lines.append(f"pooled {label}: recall {tp/(tp+fn) if tp+fn else 0:.3f}  precision {tp/(tp+fp) if tp+fp else 0:.3f}  (tp={tp} fp={fp} fn={fn})")
    text = "\n".join(lines) + "\n"
    print("\n" + text)
    Path(a.out, "summary.txt").write_text(text)
    Path(a.out, "summaries.json").write_text(json.dumps(summaries, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
