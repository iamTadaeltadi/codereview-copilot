#!/usr/bin/env python3
"""Compare an agent that can search against an agent handed the call graph.

    python experiments/run_agent.py --limit 40 --model google/gemini-2.5-flash

Three arms:

  AGENT       tools, no supplied context. It can find the caller itself.
  AGENT_GRAPH tools, plus the graph neighbourhood supplied up front.
  ONESHOT     no tools, no context. The floor.

The number the study turns on is how often AGENT searches at all. A cross-file
defect looks correct on its own, so an agent has no prompt to go looking; an
ability it never exercises is worth nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "services", "agents"), os.path.join(_ROOT, "services", "graph")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.agent import review_with_agent
from experiments.benchmark import load_crossfile
from experiments.crossfile_score import score_review, summarise
from experiments.llm import client_from_env, load_env
from experiments.review import review_once
from experiments.sparse import collect_sources


def graph_context(task, sources, budget_tokens=1500):
    from Utils.ToolOrganizer import build_tools
    from experiments.sparse import graph_from_sources

    graph = graph_from_sources(sources)
    tools = build_tools(graph, "/tmp", condition="B", max_depth=2,
                        max_neighbors=80, budget_tokens=budget_tokens)
    return tools[0].invoke({"node": task.defects[0].path})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(Path(_ROOT) / "data" / "crossfile.jsonl"))
    parser.add_argument("--model", default="google/gemini-2.5-flash")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--arms", default="ONESHOT,AGENT,AGENT_GRAPH")
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--name", default="agent")
    parser.add_argument("--hops", type=int, default=3)
    args = parser.parse_args()

    tasks = load_crossfile(args.data)[: args.limit]
    arms = [a.strip().upper() for a in args.arms.split(",") if a.strip()]
    env = load_env()
    client = client_from_env(env)
    token = env.get("GITHUB_TOKEN", "")

    outdir = Path(_ROOT) / "runs" / args.name
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "agent.jsonl"
    done = set()
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                done.add((row["task_id"], row["condition"]))
        print(f"resuming: {len(done)} already recorded")

    print(f"model : {args.model}")
    print(f"arms  : {arms}")
    print(f"tasks : {len(tasks)}\n")

    spent = 0.0
    for index, task in enumerate(tasks, 1):
        if all((task.task_id, arm) in done for arm in arms):
            continue
        try:
            sources = collect_sources(task.repo, task.review_commit, task.diff,
                                      token=token, max_files=120, import_hops=args.hops)
        except Exception as error:
            print(f"  [{index}/{len(tasks)}] {task.task_id[:44]:<44} SKIP {error}")
            continue
        if not sources:
            continue

        for arm in arms:
            if (task.task_id, arm) in done:
                continue
            started = time.time()
            if arm == "ONESHOT":
                out = review_once(client, args.model, task, "A")
                record = {
                    "task_id": task.task_id, "condition": arm, "model": args.model,
                    "findings": [asdict(f) for f in out.findings],
                    "usage": out.usage.as_dict(), "tool_calls": 0, "searches": 0,
                    "reads": 0, "searched_at_all": False, "found_the_caller": False,
                    "turns": 1, "error": out.error, "kind": task.metadata.get("kind"),
                }
                cost = out.usage.cost_usd
            else:
                context = ""
                if arm == "AGENT_GRAPH":
                    try:
                        context = graph_context(task, sources)
                    except Exception as error:
                        print(f"      graph failed: {error}")
                result = review_with_agent(
                    client, args.model, task, sources, condition=arm,
                    preloaded_context=context, max_turns=args.max_turns,
                )
                record = {
                    "task_id": task.task_id, "condition": arm, "model": args.model,
                    "findings": [asdict(f) for f in result.findings],
                    "usage": result.usage.as_dict(), "tool_calls": result.tool_calls,
                    "searches": result.searches, "reads": result.reads,
                    "searched_at_all": result.searched_at_all,
                    "found_the_caller": result.found_the_caller,
                    "turns": result.turns, "error": result.error,
                    "kind": task.metadata.get("kind"),
                }
                cost = result.usage.cost_usd

            spent += cost
            with path.open("a") as handle:
                handle.write(json.dumps(record) + "\n")
            print(f"  [{index}/{len(tasks)}] {task.task_id[:38]:<38} {arm:<12} "
                  f"tools={record['tool_calls']:>2} found={len(record['findings']):>2} "
                  f"caller={'Y' if record['found_the_caller'] else 'n'} "
                  f"${cost:.5f} {time.time()-started:.1f}s")

    print(f"\ntotal cost: ${spent:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
