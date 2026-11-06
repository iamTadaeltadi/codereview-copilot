#!/usr/bin/env python3
"""What files CIS indexed for condition E, against the full repository (paper/PREREG-E.md).

    .venv/bin/python experiments/cis_file_pool.py [results/ccrab-cis]

Per task: the files in the cached run-4 graph (graph.graph["sources"], the pool every condition
drew from and the files CIS indexed), the files in the whole repository at the reviewed head
commit (the GitHub tree listing cached in .repo-cache/trees/ when run 4 built the graph), and the
files B's run-4 context actually showed (its seeds' and delivered entities' files).
Writes file-pool.txt.
"""
import json
import pickle
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".repo-cache"
SOURCE_EXT = (".py", ".js", ".java", ".c")   # SUPPORTED_EXTENSIONS of experiments/sparse.py


def med(xs):
    xs = list(xs)
    return statistics.median(xs) if xs else float("nan")


def main(outdir="results/ccrab-cis"):
    outdir = ROOT / outdir
    recs = {}
    import gzip
    plain = outdir / "context-E-records.jsonl"
    fh = plain.open() if plain.is_file() else gzip.open(str(plain) + ".gz", "rt")
    for line in fh:
        if line.strip():
            r = json.loads(line)
            recs[r["task_id"]] = r
    b = {}
    for line in (ROOT / "results/ccrab-final/main-raw.jsonl").open():
        r = json.loads(line)
        if r["condition"] == "B":
            ret = r.get("retrieval") or {}
            ids = (ret.get("delivered_ids") or []) + (ret.get("delivered_seeds") or [])
            b[r["task_id"]] = {i.split("::")[0] for i in ids if i}
    rows = []
    for tid, r in sorted(recs.items()):
        key = r.get("graph_cache") or ""
        pkl = CACHE / key
        if not key or not pkl.is_file():
            rows.append({"task": tid, "pool": None})
            continue
        with pkl.open("rb") as h:
            sources = pickle.load(h).graph.get("sources") or {}
        repo_commit = key.split("-sparse-")[0]
        tree_file = CACHE / "trees" / f"{repo_commit}.json"
        tree = json.loads(tree_file.read_text()) if tree_file.is_file() else None
        rows.append({
            "task": tid, "pool": len(sources),
            "pool_src": sum(1 for p in sources if p.endswith(SOURCE_EXT)),
            "repo_all": len(tree) if tree is not None else None,
            "repo_src": sum(1 for p in tree if p.endswith(SOURCE_EXT)) if tree is not None else None,
            "b_files": len(b.get(tid, set())),
            "b_in_pool": all(p in sources for p in b.get(tid, set())),
        })
    ok = [x for x in rows if x["pool"] is not None]
    full = [x for x in ok if x["repo_all"] is not None]
    share = [x["pool_src"] / x["repo_src"] for x in full if x["repo_src"]]
    lines = [
        "Files behind condition E: the cached run-4 pool (what CIS indexed) against the full repository",
        "",
        "The pool is built by experiments/sparse.py collect_sources: the files the diff touches, then the",
        "files they import, up to 3 import hops, at most 60 files, at the reviewed head commit. It follows",
        "imports outward only; files that import the changed files are not added unless reached that way.",
        "It is the same pool every run-4 condition drew from (B, C, Cx, D), not the files B delivered.",
        "",
        f"tasks                                         {len(rows)}",
        f"tasks with a cached pool                      {len(ok)}",
        f"tasks with a full tree listing                {len(full)}",
        "",
        "files per task                                median     min     max",
        f"  cached pool, all files                      {med(x['pool'] for x in ok):>6}  {min(x['pool'] for x in ok):>6}  {max(x['pool'] for x in ok):>6}",
        f"  cached pool, source files (.py .js .java .c){med(x['pool_src'] for x in ok):>6}  {min(x['pool_src'] for x in ok):>6}  {max(x['pool_src'] for x in ok):>6}",
        f"  full repository, all files                  {med(x['repo_all'] for x in full):>6}  {min(x['repo_all'] for x in full):>6}  {max(x['repo_all'] for x in full):>6}",
        f"  full repository, source files               {med(x['repo_src'] for x in full):>6}  {min(x['repo_src'] for x in full):>6}  {max(x['repo_src'] for x in full):>6}",
        f"  files B's run-4 context showed              {med(x['b_files'] for x in ok):>6}  {min(x['b_files'] for x in ok):>6}  {max(x['b_files'] for x in ok):>6}",
        "",
        f"pool source files as a share of the repository's source files, median  {100 * med(share):.2f}%",
        f"tasks whose pool reached the 60-file cap      {sum(1 for x in ok if x['pool'] >= 60)}",
        f"tasks whose pool is larger than B's files     {sum(1 for x in ok if x['pool'] > x['b_files'])}",
        f"tasks where every file B showed is in the pool {sum(1 for x in ok if x['b_in_pool'])}",
    ]
    text = "\n".join(lines) + "\n"
    (outdir / "file-pool.txt").write_text(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main(*sys.argv[1:])
