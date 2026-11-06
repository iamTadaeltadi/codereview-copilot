#!/usr/bin/env python3
"""Condition E (paper/PREREG-E.md): raw CIS hits -> the context the model sees.

    .venv/bin/python experiments/cis_context.py [results/ccrab-cis]

Reads context-E-records.jsonl (written by cis_extract.py) and writes
  context-E.json            {task_id: [{path, start_line, end_line, relation, text}]}, every raw hit
                            in CIS's order, before any filter or budget;
  context-E-delivered.json  {task_id: {context_text, retrieval}}, after the pre-registered filter,
                            order, 80-candidate cap, 40-line cut and the same _budgeted function and
                            render_context as B, C, Cx and D in run 4. The header line naming the
                            entities that overlap the diff is B's own, from B's run-4 seeds.
"""
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# As in run.py: experiments/ first on sys.path lets experiments/config.py shadow the agents' config.
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).resolve().parent]
for extra in (ROOT, ROOT / "services" / "agents", ROOT / "services" / "graph"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from codecontext.retriever import is_test_path, stripped_entry  # noqa: E402
from Utils.ToolOrganizer import _budgeted  # noqa: E402
from experiments.run import render_context  # noqa: E402

BUDGET_TOKENS = 3000
CANDIDATE_CAP = 80
ENTITY_LINES = 40
KEEP_KINDS = {"function", "class"}
CACHE = ROOT / ".repo-cache"
RUN4_B = ROOT / "results" / "ccrab-final" / "main-raw.jsonl"


def open_records(outdir):
    """context-E-records.jsonl, or its committed .gz."""
    import gzip
    plain = outdir / "context-E-records.jsonl"
    return plain.open() if plain.is_file() else gzip.open(str(plain) + ".gz", "rt")


def cut(text, max_lines=ENTITY_LINES):
    """The 40-line cut of entity_source, with the same marker."""
    lines = (text or "").splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"    # ... {len(lines) - max_lines} more lines"]
    return "\n".join(lines)


def b_seeds():
    """B's run-4 seeds per task: the query lines and the delivered seed ids."""
    out = {}
    for line in RUN4_B.open():
        r = json.loads(line)
        if r["condition"] == "B":
            ret = r.get("retrieval") or {}
            out[r["task_id"]] = (ret.get("seed_queries") or [], ret.get("delivered_seeds") or [])
    return out


def b_seed_entries(graph_key, seed_ids):
    path = CACHE / graph_key
    if not path.is_file() or not seed_ids:
        return []
    with path.open("rb") as handle:
        graph = pickle.load(handle)
    return [stripped_entry(graph, s) for s in seed_ids if graph.has_node(s)]


def kind(hit):
    return str(hit.get("kind") or "").lower()


def deliver(rec, queries, seed_entries):
    seed_paths = {s.get("file_path") for s in rec.get("seeds") or []}
    seed_ids = {s.get("identity_id_hex") for s in rec.get("seeds") or []}
    groups = {"caller": [], "expand": []}
    for h in rec.get("hits") or []:
        qn, path = h.get("qualified_name") or "", h.get("path")
        if not path or "::" not in qn or qn == path:          # file hubs and modules
            continue
        if kind(h) and kind(h) not in KEEP_KINDS:
            continue
        if h.get("identity_id") in seed_ids or is_test_path(path) or not h.get("text"):
            continue
        groups[h["group"]].append(h)
    ordered, seen = [], set()
    for g in ("caller", "expand"):
        # cross-file first within a group (B's run-4 rule); ties keep CIS's order.
        for h in sorted(groups[g], key=lambda h: h.get("path") in seed_paths):
            key = h.get("identity_id") or h.get("qualified_name")
            if key in seen:
                continue
            seen.add(key)
            ordered.append(h)
    ordered = ordered[:CANDIDATE_CAP]
    entries = [{"id": h["qualified_name"], "name": h["qualified_name"].split("::", 1)[1].split(".")[-1],
                "type": kind(h) or "function", "relative_path": h["path"], "source": cut(h["text"])}
               for h in ordered]
    payload = {"query": "\n".join(queries), "found": bool(seed_entries),
               "node": seed_entries[0] if seed_entries else None, "seeds": seed_entries,
               "condition": "CIS"}
    raw = _budgeted(payload, entries, BUDGET_TOKENS)
    payload = json.loads(raw)
    budget = payload.get("budget") or {}
    # B's code path: no seed query -> no context at all; otherwise the rendered payload, header
    # included, even when no entity survives.
    text = render_context(payload) if queries else ""
    return text, {"budget": budget, "delivered_ids": [e["id"] for e in payload.get("neighbors") or []],
                  "offered": len(entries), "cis_seeds": [s.get("qualified_name") for s in rec.get("seeds") or []]}


def main(outdir="results/ccrab-cis"):
    outdir = Path(outdir)
    records = [json.loads(l) for l in open_records(outdir) if l.strip()]
    seeds = b_seeds()
    raw, delivered = {}, {}
    for rec in records:
        tid = rec["task_id"]
        raw[tid] = [{"path": h.get("path"), "start_line": h.get("start_line"), "end_line": h.get("end_line"),
                     "relation": h.get("relation"), "text": h.get("text")} for h in rec.get("hits") or []]
        queries, seed_ids = seeds.get(tid, ([], []))
        entries = b_seed_entries(rec.get("graph_cache") or "", seed_ids)
        text, retrieval = deliver(rec, queries, entries)
        delivered[tid] = {"context_text": text, "retrieval": retrieval}
    (outdir / "context-E.json").write_text(json.dumps(raw))
    (outdir / "context-E-delivered.json").write_text(json.dumps(delivered))
    print(f"tasks {len(records)}  raw hits {sum(len(v) for v in raw.values())}  "
          f"non-empty delivered {sum(1 for v in delivered.values() if v['context_text'])}")


if __name__ == "__main__":
    main(*sys.argv[1:])
