#!/usr/bin/env python3
"""Generate safe twins from the persisted pools.

    python experiments/build_twins.py --out data/crossfile-v2-twins.jsonl
"""
from __future__ import annotations
import argparse, collections, json, os, sys
from pathlib import Path
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "services", "graph")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from experiments.crossfile import build_diff, find_twins
from experiments.rebuild_crossfile import POOL_DIR, _cache_sources


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path(_ROOT) / "data" / "crossfile-v2-twins.jsonl"))
    ap.add_argument("--per-repo", type=int, default=8)
    a = ap.parse_args()
    pools = sorted(POOL_DIR.glob("*.json")) if POOL_DIR.is_dir() else []
    done = set()
    if Path(a.out).is_file():
        done = {json.loads(l)["repo"] for l in open(a.out) if l.strip()}
    funnel = collections.Counter()
    with open(a.out, "a") as h:
        for f in pools:
            name, sha = f.stem.rsplit("@", 1); repo = name.replace("__", "/")
            if repo in done:
                continue
            sources = json.loads(f.read_text())
            twins = find_twins(sources, max_per_repo=a.per_repo)
            for d in twins:
                _cache_sources(repo, sha, d.definition_path, d.caller_path, sources)
                funnel[d.kind] += 1
                h.write(json.dumps({
                    "task_id": f"xf::{repo.replace('/', '__')}::{d.defect_id}",
                    "repo": repo, "commit": sha, "kind": d.kind, "is_defect": False,
                    "defect_path": d.definition_path, "defect_line": d.definition_line,
                    "caller_path": d.caller_path, "caller_line": d.caller_line,
                    "before": d.before, "after": d.after, "why": d.why,
                    "evidence": d.evidence, "argument": d.argument,
                    "distractor_lines": [c.line for c in d.distractors],
                    "verified": "ast", "diff": build_diff(d),
                }) + "\n")
            h.flush()
            print(f"  {repo:<34} {len(sources):>3} files  {len(twins):>2} twins", flush=True)
    print(f"\ntwins by kind: {dict(funnel)}  -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
