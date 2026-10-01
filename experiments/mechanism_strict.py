#!/usr/bin/env python3
"""Add a stricter mechanism verdict to a structure run, from the stored messages.

    python experiments/mechanism_strict.py runs/<name>/structure.jsonl

The run-time rubric asks whether the message on the defect line names what the
caller depends on. The typed, attributed and corrupted blocks contain those
tokens — `catches(TypeError)`, `calls-without-argument(strict)` — so a model
that copies the metadata into its message satisfies the rubric without having
used the snippets at all. The pre-registered primary comparison, topology
against the scrambled control, is unaffected: neither block carries a rubric
token. Every other comparison on `mechanism` is contaminated in that direction
and is read on this stricter verdict instead.

`mechanism_strict` requires, in addition, that the message name the caller by
something only the caller snippet shows: the enclosing function at the caller
line, or the caller file's stem. Arms 2 to 6 see that snippet identically; the
diff-only, random and header arms do not and cannot pass, which is correct.
"""
from __future__ import annotations

import ast, json, os, re, sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "services", "graph")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.benchmark import load_crossfile
from experiments.evidence import sources_for


def enclosing_function(source: str, line: int) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    best, span = "", None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= line <= end and (span is None or end - node.lineno < span):
                best, span = node.name, end - node.lineno
    return best


def caller_tokens(task) -> set:
    meta = task.metadata or {}
    stem = meta.get("caller_path", "").rsplit("/", 1)[-1].removesuffix(".py")
    tokens = {stem.lower()} if stem and len(stem) > 2 else set()
    try:
        src = sources_for(task).get(meta.get("caller_path", ""), "")
    except Exception:
        src = ""
    fn = enclosing_function(src, int(meta.get("caller_line") or 0)) if src else ""
    if fn and len(fn) > 2 and fn != task.task_id.split("::")[3]:
        tokens.add(fn.lower())
    return tokens


def main(path: str, benchmark: str) -> int:
    tasks = {t.task_id: t for t in load_crossfile(benchmark)}
    cache = {}
    rows = [json.loads(l) for l in open(path) if l.strip()]
    out_path = Path(path).with_name("structure-strict.jsonl")
    n_strict = n_mech = 0
    with open(out_path, "w") as h:
        for r in rows:
            t = tasks.get(r["task_id"])
            if t is None:
                continue
            if r["task_id"] not in cache:
                cache[r["task_id"]] = caller_tokens(t)
            msg = (r.get("message") or "").lower()
            strict = None
            if r.get("mechanism") is not None:
                names_caller = any(re.search(r"\b" + re.escape(tok) + r"\b", msg) for tok in cache[r["task_id"]])
                strict = bool(r.get("mechanism")) and names_caller
            r["mechanism_strict"] = strict
            n_mech += bool(r.get("mechanism")); n_strict += bool(strict)
            h.write(json.dumps(r) + "\n")
    print(f"{len(rows)} rows -> {out_path}")
    print(f"mechanism true: {n_mech}   mechanism_strict true: {n_strict}")
    return 0


if __name__ == "__main__":
    bench = sys.argv[2] if len(sys.argv) > 2 else str(Path(_ROOT) / "data" / "crossfile-v2.jsonl")
    raise SystemExit(main(sys.argv[1], bench))
