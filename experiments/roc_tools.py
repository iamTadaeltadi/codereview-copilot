#!/usr/bin/env python3
"""Helpers for run F (paper/PREREG-F.md), called by experiments/roc_run.sh.

    roc_tools.py prep                     item shards and the 3 smoke items under runs/roc-items/
    roc_tools.py smoke RUN                OK, NOREPLY or FAIL <reason> for runs/RUN/structure.jsonl
    roc_tools.py project RUN N CAP        OVER or WITHIN: smoke cost per call x N calls against CAP
    roc_tools.py remaining                $4.00 minus the recorded cost of every runs/roc-* run
    roc_tools.py cost GLOB [GLOB ...]     summed recorded cost of structure and manipulation records
    roc_tools.py balance                  OpenRouter balance in dollars (the key is never printed)
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "runs" / "roc-items"


def prep():
    sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "services" / "graph"))
    from experiments.benchmark import load_crossfile
    from experiments.evidence import evidence_for, sources_for
    ITEMS.mkdir(parents=True, exist_ok=True)
    for name in ("crossfile-v3", "crossfile-v3-twins"):
        lines = [l for l in (ROOT / "data" / f"{name}.jsonl").read_text().splitlines() if l.strip()]
        for s in range(3):
            (ITEMS / f"{name}-shard{s}.jsonl").write_text("\n".join(l for i, l in enumerate(lines) if i % 3 == s) + "\n")
    lines = [l for l in (ROOT / "data" / "crossfile-v3.jsonl").read_text().splitlines() if l.strip()]
    tasks = load_crossfile(str(ROOT / "data" / "crossfile-v3.jsonl"))
    smoke = []
    for line, task in zip(lines, tasks):
        if task.metadata.get("kind") != "default_flip":
            continue
        ev = evidence_for(task, sources_for(task))
        if ev is not None and len(ev.snippets) >= 3:
            smoke.append(line)
        if len(smoke) == 3:
            break
    (ITEMS / "smoke3.jsonl").write_text("\n".join(smoke) + "\n")
    print(f"prep: shards written; smoke items {len(smoke)}")


def smoke(run):
    """paper/PREREG-F.md, Amendment 1: the run does not start if any of the 3 replies fails to
    parse, lacks a valid rating for any hunk, or rates a line that is not a hunk header. A missing
    per-finding confidence (now secondary) is reported on stderr but does not stop the run."""
    path = ROOT / "runs" / run / "structure.jsonl"
    rows = [json.loads(l) for l in path.open() if l.strip()] if path.is_file() else []
    if not rows:
        print("NOREPLY"); return
    bad, notes = [], []
    for r in rows:
        tid = r["task_id"][-60:]
        if r.get("parse_failed") or r.get("json_failed"):
            bad.append(f"{tid} reply did not parse")
            continue
        if not r.get("hunk_ratings_on"):
            bad.append(f"{tid} record has no hunk ratings (flag missing)")
            continue
        if r.get("hunks_rated") != r.get("hunks_total") or r.get("ratings_ambiguous"):
            bad.append(f"{tid} rated {r.get('hunks_rated')} of {r.get('hunks_total')} hunks"
                       + (f", ambiguous {r['ratings_ambiguous']}" if r.get("ratings_ambiguous") else ""))
        if r.get("unmatched_rating_lines") or r.get("invalid_rating_entries"):
            bad.append(f"{tid} rated non-header lines {r.get('unmatched_rating_lines')}"
                       f" / invalid entries {r.get('invalid_rating_entries')}")
        for f in r.get("finding_scores") or []:
            if f.get("confidence") is None:
                notes.append(f"{tid} finding without valid confidence")
    if len(rows) < 3:
        bad.append(f"only {len(rows)} of 3 replies")
    if notes:
        print("smoke note (does not stop the run): " + "; ".join(notes), file=sys.stderr)
    print("OK" if not bad else "FAIL " + "; ".join(bad))


def project(run, calls, cap):
    """Projected cost of a run: mean recorded cost per smoke reply x the run's calls."""
    path = ROOT / "runs" / run / "structure.jsonl"
    rows = [json.loads(l) for l in path.open() if l.strip()] if path.is_file() else []
    per = sum((r.get("usage") or {}).get("cost_usd") or 0 for r in rows) / max(len(rows), 1)
    projected = per * int(calls)
    print(("OVER" if projected > float(cap) else "WITHIN") + f" projected {projected:.4f} "
          f"({per:.6f} per call x {calls}) cap {float(cap):.4f}")


def total():
    t = 0.0
    for d in glob.glob(str(ROOT / "runs" / "roc-*")):
        for name in ("structure.jsonl", "manipulation.jsonl"):
            p = Path(d) / name
            if p.is_file():
                for l in p.open():
                    if l.strip():
                        r = json.loads(l)
                        t += ((r.get("usage") or {}).get("cost_usd") if "usage" in r else r.get("cost")) or 0
    return t


def remaining():
    print(f"{4.0 - total():.4f}")


def cost(*patterns):
    total = 0.0
    for pattern in patterns:
        for d in glob.glob(str(ROOT / "runs" / pattern)):
            for name in ("structure.jsonl", "manipulation.jsonl"):
                p = Path(d) / name
                if p.is_file():
                    for l in p.open():
                        if l.strip():
                            r = json.loads(l)
                            total += ((r.get("usage") or {}).get("cost_usd") if "usage" in r else r.get("cost")) or 0
    print(f"{total:.4f}")


def balance():
    import urllib.request
    try:
        key = next(l.split("=", 1)[1].strip().strip("\"'") for l in (ROOT / ".env").open()
                   if l.startswith("OPENROUTER_API_KEY="))
        r = json.load(urllib.request.urlopen(urllib.request.Request(
            "https://openrouter.ai/api/v1/credits", headers={"Authorization": f"Bearer {key}"}), timeout=60))["data"]
        print(f"{r['total_credits'] - r['total_usage']:.4f}")
    except Exception:
        print("nan")


if __name__ == "__main__":
    {"prep": prep, "smoke": smoke, "project": project, "remaining": remaining, "cost": cost,
     "balance": balance}[sys.argv[1]](*sys.argv[2:])
