#!/usr/bin/env python3
"""Control CxE (paper/PREREG-E.md, second amendment): Cx's random code from other files, cut per
task to the size of E's delivered context.

    .venv/bin/python experiments/cxe_context.py [results/ccrab-cis]

For each task this repeats run 4's Cx sampler step by step (build_random_context_tool in
services/agents/Utils/ToolOrganizer.py with run 4's settings: other files only, test files
excluded, the type mix of B's walk, seed 0, 80-candidate cap, 40-line cut, the same seeds) and
checks that the 3,000-token Cx context it gives is identical to the frozen run-4 Cx context.

CxE's candidate order is Cx's own draw, followed by the other-file function and class entities
Cx did not draw, in a seeded random order (random.Random(f"0:{query}:CxE")), with the same
test-file and other-file rules and the 80-candidate cap. CxE keeps the prefix of that order whose
rendered text, counted with tiktoken cl100k_base, is closest to E's delivered text for the same
task (ties go to the shorter prefix). The match is on the text the model sees, so the 3,000-token
budget on the serialised payload is not applied to CxE: where E and Cx both fill that budget, E's
fewer, larger entities carry less JSON overhead and show more code, and CxE then goes past Cx's
3,000-token cut, still within Cx's own draw. How often CxE's payload is above 3,000 tokens is
reported. A task where E's context is empty gets an empty CxE context.

Writes context-CxE-delivered.json ({task_id: {context_text, retrieval}}) and cxe-matching.txt.
"""
import json
import random
import statistics
from collections import Counter
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).resolve().parent]
for extra in (ROOT, ROOT / "services" / "agents", ROOT / "services" / "graph"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import tiktoken  # noqa: E402
from experiments.cis_extract import tasks_of_run4  # noqa: E402
from experiments.config import RunMatrix  # noqa: E402
from experiments.run import ENTITY_TYPES, graph_cache_get, render_context, seed_queries  # noqa: E402
from Utils.ContextBudget import estimate_tokens  # noqa: E402
from Utils.ToolOrganizer import (_budgeted, _node_entry, _payload, _pool, is_test_path,  # noqa: E402
                                 retrieve_node_context)

ENC = tiktoken.get_encoding("cl100k_base")
CACHE = ROOT / ".repo-cache"
FROZEN_CX = {"gpt-4o-mini": ROOT / "results/ccrab-final/Cx-raw.jsonl",
             "deepseek-v3.2": ROOT / "results/ccrab-deepseek/Cx-raw.jsonl"}


def tokens(text):
    return len(ENC.encode(text)) if text else 0


def frozen(path):
    out = {}
    for line in path.open():
        r = json.loads(line)
        if r["condition"] == "C":
            out[r["task_id"]] = r.get("context_text") or ""
    return out


def cx_draw(task, matrix):
    """Run 4's Cx sampler, step by step: (envelope, Cx's draw, the rest of the pool in a seeded
    random order). None when the task has no cached graph; {} when it has no seed query."""
    key = f"{task.repo.replace('/', '__')}@{task.review_commit[:12]}-sparse-h3-v2.pkl"
    if not (CACHE / key).is_file():
        return None
    graph, _ = graph_cache_get(task, str(CACHE), "", True, 3, 60)
    seeds = seed_queries(task, graph, drop_class_seeds=True)
    if not seeds:
        return {}
    node = "\n".join(seeds)
    payload, seed_ids = _payload(graph, "C", node)
    if not seed_ids:
        return {"payload": payload, "picked": [], "rest": []}
    # build_random_context_tool(other_files_only=True, match_types=True, exclude_tests=True,
    # prefer_cross_file=True, callers_first=True), line for line.
    rng = random.Random(f"{matrix.seeds[0]}:{node}")
    pool = _pool(graph, seed_ids, ENTITY_TYPES)
    pool = [n for n in pool if not is_test_path(graph.nodes[n].get("relative_path"))] or pool
    homes = {graph.nodes[s].get("relative_path") for s in seed_ids}
    pool = [n for n in pool if graph.nodes[n].get("relative_path") not in homes] or pool
    reference = retrieve_node_context(graph, "", node, max_neighbors=matrix.candidate_cap, max_depth=3,
                                      prefer_cross_file=True, entity_types=ENTITY_TYPES,
                                      exclude_tests=True, callers_first=True)
    wanted = Counter(n.get("type") for n in reference["neighbors"])
    by_type = {}
    for candidate in pool:
        by_type.setdefault(graph.nodes[candidate].get("type"), []).append(candidate)
    picked = []
    for node_type, count in wanted.items():
        bucket = by_type.get(node_type, [])
        rng.shuffle(bucket)
        picked.extend(bucket[:count])
    rng.shuffle(picked)
    taken = set(picked)
    rest = sorted(n for n in pool if n not in taken)
    random.Random(f"{matrix.seeds[0]}:{node}:CxE").shuffle(rest)
    entry = lambda n: _node_entry(graph, n, matrix.entity_lines)  # noqa: E731
    return {"payload": payload, "picked": [entry(n) for n in picked],
            "rest": [entry(n) for n in rest[: max(0, matrix.candidate_cap - len(picked))]]}


def fit(payload, entries, budget):
    return json.loads(_budgeted(dict(payload), list(entries), budget))


def main(outdir="results/ccrab-cis"):
    outdir = ROOT / outdir
    e = json.loads((outdir / "context-E-delivered.json").read_text())
    cx_frozen = {m: frozen(p) for m, p in FROZEN_CX.items()}
    matrix = RunMatrix(budget_tokens=3000)
    out, rows = {}, []
    for task in tasks_of_run4():
        tid = task.task_id
        e_text = (e.get(tid) or {}).get("context_text") or ""
        e_tok = tokens(e_text)
        draw = cx_draw(task, matrix)
        payload = None
        cx_text, neighbors = "", []
        if draw:
            cx = fit(draw["payload"], draw["picked"], matrix.budget_tokens)
            cx_text = render_context(cx)
            neighbors = cx.get("neighbors") or []
            # CxE's order: Cx's draw, then the rest of the pool; matched on rendered size below.
            payload = dict(draw["payload"])
        same = {m: (cx_text == f[tid]) if tid in f else None for m, f in cx_frozen.items()}
        order = ((draw["picked"] + draw["rest"])[: matrix.candidate_cap]) if draw else []
        if not e_text or not payload:
            k, text = 0, ""
        else:
            sizes = []
            for k in range(len(order) + 1):
                size = tokens(render_context({**payload, "neighbors": order[:k]}))
                sizes.append((abs(size - e_tok), k))
                if size > e_tok:
                    break
            k = min(sizes)[1]
            text = render_context({**payload, "neighbors": order[:k]})
        c_tok = tokens(text)
        json_tok = estimate_tokens(json.dumps({**payload, "neighbors": order[:k]})) if payload else 0
        out[tid] = {"context_text": text, "retrieval": {
            "matched_to": "CIS", "e_tokens": e_tok, "cxe_tokens": c_tok, "cx_tokens": tokens(cx_text),
            "cx_entries": len(neighbors), "entries_kept": k,
            "beyond_cx_draw": max(0, k - len(draw["picked"])) if draw else 0,
            "beyond_cx_cut": max(0, k - len(neighbors)), "payload_tokens": json_tok,
            "delivered_ids": [n.get("id") for n in order[:k]],
            "header_same_as_E": (text.split("\n", 1)[0] == e_text.split("\n", 1)[0]) if text and e_text else None}}
        rows.append((tid, e_tok, c_tok, tokens(cx_text), len(neighbors), k, same, bool(e_text), bool(payload)))
    (outdir / "context-CxE-delivered.json").write_text(json.dumps(out))

    def med(xs):
        xs = list(xs)
        return statistics.median(xs) if xs else float("nan")
    ran = [r for r in rows if r[8]]
    lines = ["CxE: run 4's Cx draw, cut per task to E's delivered size (paper/PREREG-E.md, second amendment)",
             "", f"tasks                                              {len(rows)}"]
    for m in FROZEN_CX:
        checked = [r for r in rows if r[6][m] is not None]
        lines.append(f"Cx rerun identical to the frozen {m} Cx context  {sum(1 for r in checked if r[6][m])} of {len(checked)}")
    both = [r for r in rows if r[7]]
    lines += [
        f"tasks with a non-empty E context                   {len(both)}",
        f"tasks with no cached graph (CxE empty, like E)     {sum(1 for r in rows if not r[8])}",
        f"CxE header line identical to E's                   {sum(1 for v in out.values() if v['retrieval']['header_same_as_E'])} of {sum(1 for v in out.values() if v['retrieval']['header_same_as_E'] is not None)}",
        "",
        "delivered context, tokens of the text the model sees (tiktoken cl100k_base), all tasks",
        f"  median E    {med(r[1] for r in rows)}",
        f"  median CxE  {med(r[2] for r in rows)}",
        f"  median Cx   {med(r[3] for r in rows)}",
        f"  median CxE minus E, per task            {med(r[2] - r[1] for r in rows)}",
        f"  median |CxE minus E|, per task          {med(abs(r[2] - r[1]) for r in rows)}",
        f"  tasks where CxE is larger than E        {sum(1 for r in rows if r[2] > r[1])}",
        f"  tasks where CxE is smaller than E       {sum(1 for r in rows if r[2] < r[1])}",
        f"  tasks where CxE equals E                {sum(1 for r in rows if r[2] == r[1])}",
        f"  tasks where Cx's 3,000-token context is smaller than E's   {sum(1 for r in rows if r[1] and r[3] < r[1])}",
        f"  tasks where CxE goes past Cx's 3,000-token cut (within Cx's draw)  {sum(1 for v in out.values() if v['retrieval']['beyond_cx_cut'] and not v['retrieval']['beyond_cx_draw'])}",
        f"  tasks where CxE goes beyond Cx's own draw       {sum(1 for v in out.values() if v['retrieval']['beyond_cx_draw'])}",
        f"  tasks where CxE's payload, with at least one entity, is above 3,000 tokens  {sum(1 for v in out.values() if v['retrieval']['entries_kept'] and v['retrieval']['payload_tokens'] > 3000)}",
        f"  max CxE payload tokens with at least one entity  {max(v['retrieval']['payload_tokens'] for v in out.values() if v['retrieval']['entries_kept'])}",
        f"  tasks with no entity in CxE (header only or empty)  {sum(1 for v in out.values() if not v['retrieval']['entries_kept'])}",
        f"  tasks where CxE is a prefix of Cx's delivered context  {sum(1 for r in rows if r[8] and r[5] <= r[4])}",
        f"  median entities, Cx {med(r[4] for r in ran)}  CxE {med(r[5] for r in ran)}",
    ]
    text = "\n".join(lines) + "\n"
    (outdir / "cxe-matching.txt").write_text(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main(*sys.argv[1:])
