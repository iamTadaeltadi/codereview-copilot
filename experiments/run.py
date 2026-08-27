#!/usr/bin/env python3
"""Run the experiment: every condition against the same tasks, one budget.

    python experiments/run.py --limit 3 --conditions A,B,D
    python experiments/run.py --limit 20 --model qwen/qwen-2.5-coder-32b-instruct

Results stream to runs/<name>/outcomes.jsonl as they complete, so a run that
dies at task 200 resumes rather than restarts, and every raw model response is
kept for inspection.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Running this file as a script puts experiments/ first on sys.path, where
# config.py then shadows services/agents/config.py and breaks the agent
# runtime's own "from config import Config". Drop it: every import here is
# either absolute from the repository root or from a service directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _extra in (_ROOT, os.path.join(_ROOT, "services", "agents"), os.path.join(_ROOT, "services", "graph")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)
from dataclasses import asdict
from pathlib import Path

from experiments.benchmark import load_ccrab, oracle_targets, summarise
from experiments.config import (
    CONDITION_GRAPH,
    CONDITION_NONE,
    CONDITION_ORACLE,
    CONDITION_WHOLE_FILE,
    MODELS,
    RunMatrix,
)
from experiments.llm import Usage, client_from_env, load_env
from experiments.matcher import DEFAULT_LINE_TOLERANCE, match_review
from experiments.metrics import compare, summarise_condition, table
from experiments.repo import RepoError, evict, graph_for
from experiments.sparse import collect_sources, graph_from_sources
from experiments.review import review_once

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "stage3_testgen_verified.jsonl"
DEFAULT_ARCHIVE = ROOT / "data" / "testgen_combined.zip"

NEEDS_GRAPH = {"B", "C", "D", "G"}


def graph_cache_get(task, graph_cache, token, sparse):
    """One graph per task, cached, built sparsely when the link is too slow."""
    import pickle

    cache = Path(graph_cache)
    cache.mkdir(parents=True, exist_ok=True)
    key = f"{task.repo.replace('/', '__')}@{task.review_commit[:12]}"
    if sparse:
        key += "-sparse"
    cached = cache / f"{key}.pkl"
    if cached.is_file():
        with cached.open("rb") as handle:
            return pickle.load(handle), None

    if sparse:
        sources = collect_sources(task.repo, task.review_commit, task.diff, token=token)
        if not sources:
            raise RepoError(f"{task.repo}@{task.review_commit[:8]}: no source files fetched")
        graph = graph_from_sources(sources)
        info = len(sources)
    else:
        graph, meta = graph_for(task.repo, task.review_commit, cache_dir=graph_cache, token=token)
        info = meta.files
    with cached.open("wb") as handle:
        pickle.dump(graph, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return graph, info


def build_context(task, condition, matrix, graph_cache, token, max_depth, sparse=True):
    """Return the context payload for one condition, or '' when it has none."""
    if condition == CONDITION_NONE:
        return "", None

    if condition == CONDITION_WHOLE_FILE:
        # The reference arm for what practitioners actually do: hand over the
        # whole of every file the diff touches, unbudgeted. It is reported
        # separately from the matched arms precisely because it is not budgeted;
        # returning nothing here would have made it a silent duplicate of A.
        sources = collect_sources(
            task.repo, task.review_commit, task.diff, token=token, import_hops=0
        )
        if not sources:
            raise RepoError(f"{task.repo}@{task.review_commit[:8]}: no source files fetched")
        rendered = "\n\n".join(
            f"### {path}\n{text}" for path, text in sorted(sources.items())
        )
        return rendered, len(sources)

    from Utils.ToolOrganizer import build_tools

    graph = None
    info = None
    if condition in NEEDS_GRAPH or condition == CONDITION_ORACLE:
        graph, info = graph_cache_get(task, graph_cache, token, sparse)

    tools = build_tools(
        graph,
        str(graph_cache),
        condition=condition,
        max_depth=max_depth,
        max_neighbors=matrix.candidate_cap,
        budget_tokens=matrix.budget_tokens,
        seed=matrix.seeds[0],
        oracle_targets=oracle_targets(task) if condition == CONDITION_ORACLE else None,
    )
    if not tools:
        return "", info

    seed_query = ""
    for defect in task.defects:
        if defect.path:
            seed_query = defect.path
            break
    return tools[0].invoke({"node": seed_query}), info


def already_done(path):
    seen = set()
    if path.is_file():
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            seen.add((row.get("task_id"), row.get("condition")))
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--name", default="pilot")
    parser.add_argument("--conditions", default="A,B,D,G")
    parser.add_argument("--model", default=None)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument("--tolerance", type=int, default=DEFAULT_LINE_TOLERANCE)
    parser.add_argument("--graph-cache", default=str(ROOT / ".repo-cache"))
    parser.add_argument("--max-diff-chars", type=int, default=40000)
    parser.add_argument("--full-repo", action="store_true",
                        help="download whole repositories instead of the diff's files "
                             "and their imports; needs a fast connection")
    args = parser.parse_args()

    matrix = RunMatrix()
    if args.budget:
        matrix = RunMatrix(budget_tokens=args.budget)
    model = args.model or MODELS["secondary"].name
    conditions = [c.strip().upper() for c in args.conditions.split(",") if c.strip()]

    env = load_env()
    client = client_from_env(env)
    token = env.get("GITHUB_TOKEN", "")

    tasks = load_ccrab(
        args.data,
        testgen_archive=args.archive,
        confirmed_only=True,
        supported_source_only=True,
    )
    tasks = [t for t in tasks if len(t.diff) <= args.max_diff_chars]
    tasks = sorted(tasks, key=lambda t: t.task_id)[: args.limit]
    print(f"benchmark : {json.dumps(summarise(tasks))}")
    print(f"model     : {model}")
    print(f"conditions: {conditions}   budget={matrix.budget_tokens} depth={args.depth}")
    print(f"graph mode: {'full repository' if args.full_repo else 'sparse (diff files + 1 import hop)'}")

    outdir = ROOT / "runs" / args.name
    outdir.mkdir(parents=True, exist_ok=True)
    outcomes_path = outdir / "outcomes.jsonl"
    raw_path = outdir / "raw.jsonl"
    done = already_done(outcomes_path)
    if done:
        print(f"resuming  : {len(done)} task/condition pairs already recorded")

    all_outcomes = []
    usage_by_condition = {c: Usage() for c in conditions}
    fp_by_condition = {c: 0 for c in conditions}
    started = time.time()

    for index, task in enumerate(tasks, 1):
        for condition in conditions:
            if (task.task_id, condition) in done:
                continue
            t0 = time.time()
            try:
                context, info = build_context(
                    task, condition, matrix, args.graph_cache, token, args.depth,
                    sparse=not args.full_repo,
                )
            except RepoError as error:
                print(f"  [{index}/{len(tasks)}] {task.task_id} {condition}: SKIP {error}")
                continue

            result = review_once(client, model, task, condition, context)
            if result.error:
                print(f"  [{index}/{len(tasks)}] {task.task_id} {condition}: ERROR {result.error}")
                continue

            report = match_review(
                task.task_id, condition, task.defects, result.findings, args.tolerance
            )
            all_outcomes.extend(report.outcomes)
            usage_by_condition[condition].add(result.usage)
            fp_by_condition[condition] += len(report.false_positives)

            with outcomes_path.open("a") as handle:
                for outcome in report.outcomes:
                    handle.write(json.dumps(asdict(outcome)) + "\n")
            with raw_path.open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "task_id": task.task_id,
                            "condition": condition,
                            "model": model,
                            "context_chars": len(context),
                            "findings": [asdict(f) for f in result.findings],
                            "parse_failed": result.parse_failed,
                            "usage": result.usage.as_dict(),
                            "raw_text": result.raw_text[:8000],
                        }
                    )
                    + "\n"
                )

            print(
                f"  [{index}/{len(tasks)}] {task.task_id[:40]:<40} {condition} "
                f"ctx={len(context):>6} found={len(result.findings):>2} "
                f"hit={report.hits}/{len(report.outcomes)} "
                f"${result.usage.cost_usd:.5f} {time.time()-t0:.1f}s"
            )
        evict(args.graph_cache)

    if not all_outcomes:
        print("\nno new results")
        return 0

    print(f"\ntotal wall time: {time.time()-started:.0f}s")
    summaries = [
        summarise_condition(
            c,
            all_outcomes,
            false_positives=fp_by_condition[c],
            usage=usage_by_condition[c].as_dict() | {"cost_usd": usage_by_condition[c].cost_usd},
            bootstrap=400,
        )
        for c in conditions
    ]
    print()
    print(table(summaries))

    if CONDITION_NONE in conditions:
        print()
        for condition in conditions:
            if condition != CONDITION_NONE:
                print("  " + compare(all_outcomes, condition, CONDITION_NONE, bootstrap=400).verdict())

    total = sum(u.cost_usd for u in usage_by_condition.values())
    print(f"\ntotal cost: ${total:.4f}")
    (outdir / "config.json").write_text(
        json.dumps(
            {"model": model, "conditions": conditions, "depth": args.depth,
             "budget_tokens": matrix.budget_tokens, "tolerance": args.tolerance,
             "tasks": len(tasks), "matrix": matrix.as_dict()},
            indent=2, default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
