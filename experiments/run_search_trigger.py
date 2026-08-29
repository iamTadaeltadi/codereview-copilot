#!/usr/bin/env python3
"""Does anything in a code review cause an agent to search?

The agent arm of the earlier study made zero tool calls across 145 records. A
result that far from the literature — which reports agents inspecting 8-12x
more files than necessary — is an instrument fault until shown otherwise.

This isolates the question. Same model, same tools, same repository, same diff.
Only the framing changes:

  NEUTRAL  the review prompt as used in the study
  PRIMED   the same, plus one sentence saying the defect can only be recognised
           from another file

If NEUTRAL searches rarely and PRIMED searches often, the tools work and the
absence of search is behaviour rather than breakage: the agent does not lack
the ability, it lacks a trigger. A diff that looks correct supplies none.
"""

from __future__ import annotations

import argparse, json, os, sys, time
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "services", "graph")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.agent import TOOLS, run_read, run_search
from experiments.benchmark import load_crossfile
from experiments.llm import LLMError, client_from_env, load_env
from experiments.sparse import collect_sources

SYSTEM = (
    "You are an experienced code reviewer examining a pull request. You have "
    "tools for searching and reading the repository. Use them when the diff "
    "alone does not tell you whether something is correct."
)

PRIME = (
    "\n\nThe defect in this diff can only be recognised by examining code in "
    "another file that depends on what changed. Find that code before answering."
)

CONTRACT = '\n\nReply with JSON only: {"findings": [{"path": "...", "line": 0, "message": "..."}]}'


def turn(client, model, task, sources, primed, max_turns=6):
    user = (f"Repository: {task.repo}\n\nPull request diff:\n```diff\n{task.diff}\n```"
            + (PRIME if primed else "") + CONTRACT)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    searches = reads = 0
    reached = False
    caller = (task.metadata or {}).get("caller_path", "")
    cost = 0.0

    for _ in range(max_turns):
        try:
            c = client.complete(model=model, messages=messages, tools=TOOLS,
                                max_tokens=1024, temperature=0.1)
        except LLMError as e:
            return {"error": str(e), "searches": searches, "reads": reads,
                    "reached_caller": reached, "cost": cost}
        cost += c.usage.cost_usd
        if not c.tool_calls:
            break
        messages.append({"role": "assistant", "content": c.text or None,
                         "tool_calls": c.tool_calls})
        for call in c.tool_calls:
            fn = call.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            if fn.get("name") == "search_code":
                searches += 1
                out = run_search(sources, args.get("query", ""))
                if caller and caller in out:
                    reached = True
            else:
                reads += 1
                path = args.get("path", "")
                out = run_read(sources, path)
                if caller and (path.endswith(caller) or caller.endswith(path)):
                    reached = True
            messages.append({"role": "tool", "tool_call_id": call.get("id"),
                             "name": fn.get("name"), "content": out[:6000]})
    return {"error": "", "searches": searches, "reads": reads,
            "reached_caller": reached, "cost": cost}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--model", default="google/gemini-2.5-flash")
    ap.add_argument("--name", default="search-trigger")
    a = ap.parse_args()

    tasks = load_crossfile(str(Path(_ROOT) / "data" / "crossfile.jsonl"))[: a.limit]
    env = load_env(); client = client_from_env(env); token = env.get("GITHUB_TOKEN", "")
    out = Path(_ROOT) / "runs" / a.name; out.mkdir(parents=True, exist_ok=True)
    path = out / "trigger.jsonl"
    done = {(json.loads(l)["task_id"], json.loads(l)["arm"])
            for l in path.read_text().splitlines() if l.strip()} if path.is_file() else set()

    print(f"model: {a.model}\ntasks: {len(tasks)}\n")
    spent = 0.0
    for i, t in enumerate(tasks, 1):
        if all((t.task_id, arm) in done for arm in ("NEUTRAL", "PRIMED")):
            continue
        try:
            src = collect_sources(t.repo, t.review_commit, t.diff, token=token,
                                  max_files=80, import_hops=2)
        except Exception as e:
            print(f"  [{i}] SKIP {e}"); continue
        if not src:
            continue
        for arm, primed in (("NEUTRAL", False), ("PRIMED", True)):
            if (t.task_id, arm) in done:
                continue
            r = turn(client, a.model, t, src, primed)
            spent += r["cost"]
            with path.open("a") as h:
                h.write(json.dumps({"task_id": t.task_id, "arm": arm,
                                    "files": len(src), **r}) + "\n")
            print(f"  [{i}/{len(tasks)}] {arm:<8} searches={r['searches']} "
                  f"reads={r['reads']} caller={'Y' if r['reached_caller'] else 'n'} "
                  f"${r['cost']:.5f}")
    print(f"\ntotal cost: ${spent:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
