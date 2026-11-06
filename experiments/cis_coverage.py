#!/usr/bin/env python3
"""Condition E coverage report (paper/PREREG-E.md), written before any model call.

    .venv/bin/python experiments/cis_coverage.py [results/ccrab-cis]

Counts tasks indexed, failed (with reasons), with seeds, with raw hits and with delivered context,
and compares the delivered context size in tokens (tiktoken cl100k_base of the text the model
sees) for E with B, D and Cx from run 4.
"""
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
RUN4 = ROOT / "results" / "ccrab-final"
ENC = tiktoken.get_encoding("cl100k_base")


def open_records(outdir):
    """context-E-records.jsonl, or its committed .gz."""
    import gzip
    plain = outdir / "context-E-records.jsonl"
    return plain.open() if plain.is_file() else gzip.open(str(plain) + ".gz", "rt")


def tokens(text):
    return len(ENC.encode(text)) if text else 0


def run4_sizes():
    sizes = {"B": {}, "D": {}, "Cx": {}}
    kept = {"B": {}, "D": {}, "Cx": {}}
    for name, conds in (("main-raw.jsonl", {"B": "B", "D": "D"}), ("Cx-raw.jsonl", {"C": "Cx"})):
        for line in (RUN4 / name).open():
            r = json.loads(line)
            c = conds.get(r["condition"])
            if c:
                sizes[c][r["task_id"]] = tokens(r.get("context_text") or "")
                kept[c][r["task_id"]] = ((r.get("retrieval") or {}).get("budget") or {}).get("entries_kept", 0)
    return sizes, kept


def med(values):
    values = list(values)
    return statistics.median(values) if values else float("nan")


def main(outdir="results/ccrab-cis"):
    outdir = Path(outdir)
    recs = [json.loads(l) for l in open_records(outdir) if l.strip()]
    delivered = json.loads((outdir / "context-E-delivered.json").read_text())
    n = len(recs)
    failed = [r for r in recs if r.get("error")]
    indexed = [r for r in recs if r.get("boot") == "ok" and r.get("index_status")]
    reasons = Counter((r["error"] or "").split(";")[0][:90] for r in failed)
    with_seeds = [r for r in recs if r.get("seeds")]
    with_hits = [r for r in recs if r.get("hits")]
    e_tok = {t: tokens(v["context_text"]) for t, v in delivered.items()}
    e_kept = {t: (v["retrieval"].get("budget") or {}).get("entries_kept", 0) for t, v in delivered.items()}
    nonempty = [t for t, k in e_kept.items() if k > 0]
    sizes, kept = run4_sizes()
    parse_err = sum(1 for r in indexed if (r["index_status"] or {}).get("parse_error_count"))
    lines = [
        "Condition E (CIS) coverage, before any model call (paper/PREREG-E.md)",
        f"CIS 4ea4bfe9e37b, cisd --mcp, python-ast + body-sqlite; files = run-4 cached sources per task",
        "",
        f"tasks                                   {n}",
        f"indexed OK                              {len(indexed)}",
        f"failed to index or query                {len(failed)}",
    ]
    for reason, count in reasons.most_common():
        lines.append(f"    {count:>3}  {reason}")
    lines += [
        f"indexed with a parse error reported     {parse_err}",
        f"tasks with at least one seed            {len(with_seeds)}",
        f"tasks with at least one raw CIS hit     {len(with_hits)}",
        f"tasks with at least one entity delivered {len(nonempty)}",
        f"tasks run with no entity (header only or empty) {n - len(nonempty)}",
        "",
        f"raw hits, all tasks                     {sum(len(r.get('hits') or []) for r in recs)}",
        f"raw hits per task, median               {med(len(r.get('hits') or []) for r in recs)}",
        f"candidates offered after filter, median {med(v['retrieval'].get('offered', 0) for v in delivered.values())}",
        "",
        "delivered context, tokens of the text the model sees (tiktoken cl100k_base)",
        "                 median all tasks   median non-empty   median entities kept   tasks",
    ]
    for name, tok, kp in (("E (CIS)", e_tok, e_kept), ("B (graph)", sizes["B"], kept["B"]),
                          ("D (lexical)", sizes["D"], kept["D"]), ("Cx (random other files)", sizes["Cx"], kept["Cx"])):
        lines.append(f"  {name:<24}{med(tok.values()):>10}{med(v for v in tok.values() if v):>18}"
                     f"{med(kp.values()):>20}{len(tok):>10}")
    text = "\n".join(lines) + "\n"
    (outdir / "coverage.txt").write_text(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main(*sys.argv[1:])
