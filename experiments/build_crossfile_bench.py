#!/usr/bin/env python3
"""Generate the cross-file benchmark and write it as tasks.

    python experiments/build_crossfile_bench.py --repos 60 --out data/crossfile.jsonl

Walks the repositories the review benchmark already covers, fetches a wider
import neighbourhood than a review needs, and emits every mutation whose
cross-file dependency is demonstrated in a caller's source.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "services", "graph")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.benchmark import load_ccrab
from experiments.crossfile import build_diff, find_defects
from experiments.sparse import collect_sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos", type=int, default=60)
    parser.add_argument("--max-files", type=int, default=120)
    parser.add_argument("--hops", type=int, default=3)
    parser.add_argument("--per-repo", type=int, default=6)
    parser.add_argument("--out", default=str(Path(_ROOT) / "data" / "crossfile.jsonl"))
    args = parser.parse_args()

    tasks = load_ccrab(
        str(Path(_ROOT) / "data" / "stage3_testgen_verified.jsonl"),
        testgen_archive=str(Path(_ROOT) / "data" / "testgen_combined.zip"),
        confirmed_only=True, supported_source_only=True,
    )
    seen, picked = set(), []
    for t in tasks:
        if t.repo in seen:
            continue
        seen.add(t.repo)
        picked.append(t)
        if len(picked) >= args.repos:
            break

    out = Path(args.out)
    done = set()
    if out.is_file():
        for line in out.read_text().splitlines():
            if line.strip():
                done.add(json.loads(line)["repo"])
        print(f"resuming: {len(done)} repositories already processed")

    total = 0
    with out.open("a") as handle:
        for index, task in enumerate(picked, 1):
            if task.repo in done:
                continue
            try:
                sources = collect_sources(
                    task.repo, task.review_commit, task.diff,
                    max_files=args.max_files, import_hops=args.hops,
                )
            except Exception as error:
                print(f"  [{index}/{len(picked)}] {task.repo:<34} fetch failed: {error}")
                continue

            defects = find_defects(sources, max_per_repo=args.per_repo)
            for defect in defects:
                handle.write(json.dumps({
                    "task_id": f"xf::{task.repo.replace('/', '__')}::{defect.defect_id}",
                    "repo": task.repo,
                    "commit": task.review_commit,
                    "kind": defect.kind,
                    "diff": build_diff(defect),
                    "defect_path": defect.definition_path,
                    "defect_line": defect.definition_line,
                    "caller_path": defect.caller_path,
                    "caller_line": defect.caller_line,
                    "before": defect.before,
                    "after": defect.after,
                    "why": defect.why,
                    "evidence": defect.evidence,
                    "distractor_lines": [c.line for c in defect.distractors],
                }) + "\n")
            handle.flush()
            total += len(defects)
            print(f"  [{index}/{len(picked)}] {task.repo:<34} {len(sources):>3} files -> "
                  f"{len(defects)} defects (running total {total})")

    print(f"\nwrote {total} new cross-file defects to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
