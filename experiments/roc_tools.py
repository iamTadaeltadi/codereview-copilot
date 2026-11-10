#!/usr/bin/env python3
"""Helpers for run F (paper/PREREG-F.md), called by experiments/roc_run.sh.

    roc_tools.py prep                     item shards and the 3 smoke items under runs/roc-items/
    roc_tools.py smoke RUN                OK, NOREPLY or FAIL <reason> for runs/RUN/structure.jsonl
    roc_tools.py project RUN N CAP        OVER or WITHIN: smoke cost per call x N calls against CAP
    roc_tools.py remaining                $4.00 minus the recorded cost of every runs/roc-* run
    roc_tools.py smoke_ctrl RUN NAME      smoke plus Amendment 3: no reasoning, < 600 output tokens, provider NAME
    roc_tools.py guard NAME GLOB [...]    OK or ABORT <reason>: Amendment 3 abort rule over every recorded call
    roc_tools.py usage GLOB [...]         raw usage object and served provider of every call (smoke display)
    roc_tools.py ctrlstats GLOB [...]     calls, providers seen, max reasoning tokens, max output tokens
    roc_tools.py cost GLOB [GLOB ...]     summed recorded cost of structure and manipulation records
    roc_tools.py balance                  OpenRouter balance in dollars (the key is never printed)

Amendment 4 (run 2t, reasoning on):
    roc_tools.py prep_think               6 shuffled mixed shards of 2c's 282 items, and 3+3 smoke items
    roc_tools.py smoke_think RUN NAME     OK, BUDGET <reason> (reasoning used up max_tokens) or FAIL <reason>
    roc_tools.py project_think RUN CAP N SMOKEGLOB [...]  mean smoke review cost x N x 1.5 + smoke cost
    roc_tools.py guard_think NAME PLANNED GLOB [...]      OK or ABORT <reason>: Amendment 4 abort rules
    roc_tools.py usage_think GLOB [...]   per call: kind, finish reason, provider, tokens, raw usage
    roc_tools.py thinkstats GLOB [...]    providers, reasoning tokens (max, median, zeros), output max, cut-offs
Amendment 5 (run 2t completed, with 7-random added):
    roc_tools.py guard_a5 NAME MAXRUNAWAY GLOB [...]   OK or ABORT <reason>: Amendment 5 abort rules
    roc_tools.py daysplit GLOB [...]      review calls per arm and calendar day (EAT), from called_at
Every reader counts failed.jsonl (calls cut off at max_tokens, billed but not scored) beside the
structure and manipulation records.
"""
import contextlib
import glob
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "runs" / "roc-items"
RECORDS = ("structure.jsonl", "manipulation.jsonl", "failed.jsonl")


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
        for name in RECORDS:
            p = Path(d) / name
            if p.is_file():
                for l in p.open():
                    if l.strip():
                        r = json.loads(l)
                        t += ((r.get("usage") or {}).get("cost_usd") if "usage" in r else r.get("cost")) or 0
    return t


def remaining():
    print(f"{4.0 - total():.4f}")


def _norm(name):
    return "".join(ch for ch in str(name).lower() if ch not in " -_")


def _calls(patterns):
    """Every recorded call (review and manipulation-check records) of the runs matching the globs."""
    out = []
    for pattern in patterns:
        for d in sorted(glob.glob(str(ROOT / "runs" / pattern))):
            for name in RECORDS:
                p = Path(d) / name
                if p.is_file():
                    out += [(Path(d).name, name, json.loads(l)) for l in p.open() if l.strip()]
    return out


def _out_tokens(r):
    return r.get("output_tokens", (r.get("usage") or {}).get("output_tokens"))


def smoke_ctrl(run, name):
    """paper/PREREG-F.md, Amendment 3: the smoke checks above, and on every call: the run's settings
    present, reasoning_tokens 0 or absent, fewer than 600 output tokens, and the served provider
    NAME (ignoring case, spaces, hyphens) or not reported."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        smoke(run)
    base = buf.getvalue().strip()
    bad = [] if base == "OK" else [base]
    for _, kind, r in _calls([run]):
        tid = f"{kind[:5]} {r['task_id'][-50:]}"
        if not r.get("request_provider") or r.get("request_reasoning") is None:
            bad.append(f"{tid} settings missing"); continue
        if r.get("reasoning_tokens"):
            bad.append(f"{tid} reasoning_tokens {r['reasoning_tokens']}")
        if (_out_tokens(r) or 0) >= 600:
            bad.append(f"{tid} output tokens {_out_tokens(r)}")
        if r.get("served_provider") is not None and _norm(r["served_provider"]) != _norm(name):
            bad.append(f"{tid} served by {r['served_provider']}")
    print("OK" if not bad else "FAIL " + "; ".join(bad))


def guard(name, *patterns):
    """Amendment 3 abort rule: any call with reasoning_tokens > 0, more than 1,500 output tokens, a
    reported provider other than NAME, or without the run's settings."""
    calls = _calls(patterns)
    for run, kind, r in calls:
        where = f"{run}/{kind} {r['task_id'][-50:]} {r.get('arm', '')}"
        if not r.get("request_provider") or r.get("request_reasoning") is None:
            print(f"ABORT settings missing: {where}"); return
        if (r.get("reasoning_tokens") or 0) > 0:
            print(f"ABORT reasoning_tokens {r['reasoning_tokens']}: {where}"); return
        if (_out_tokens(r) or 0) > 1500:
            print(f"ABORT output tokens {_out_tokens(r)}: {where}"); return
        if r.get("served_provider") is not None and _norm(r["served_provider"]) != _norm(name):
            print(f"ABORT served by {r['served_provider']}: {where}"); return
    reported = sum(1 for *_, r in calls if r.get("served_provider") is not None)
    print(f"OK {len(calls)} calls, provider reported on {reported}")


def usage(*patterns):
    for run, kind, r in _calls(patterns):
        print(f"{run}/{kind} {r['task_id'][-60:]} {r.get('arm', '')}: provider={r.get('served_provider')!r} "
              f"reasoning_tokens={r.get('reasoning_tokens')!r} output_tokens={_out_tokens(r)} "
              f"usage={json.dumps(r.get('usage_raw'), sort_keys=True)}")


def ctrlstats(*patterns):
    import collections
    calls = [r for *_, r in _calls(patterns)]
    prov = collections.Counter(str(r.get("served_provider")) for r in calls)
    rt = [r.get("reasoning_tokens") for r in calls]
    print(f"calls {len(calls)}; providers {dict(prov)}; reasoning_tokens max "
          f"{max((x for x in rt if x is not None), default=None)} (absent on {sum(x is None for x in rt)}); "
          f"output tokens max {max((_out_tokens(r) or 0 for r in calls), default=None)}")


def cost(*patterns):
    total = 0.0
    for pattern in patterns:
        for d in glob.glob(str(ROOT / "runs" / pattern)):
            for name in RECORDS:
                p = Path(d) / name
                if p.is_file():
                    for l in p.open():
                        if l.strip():
                            r = json.loads(l)
                            total += ((r.get("usage") or {}).get("cost_usd") if "usage" in r else r.get("cost")) or 0
    print(f"{total:.4f}")


THINK = {"enabled": True}
PIN = {"atlas-cloud/fp8": "AtlasCloud", "gmicloud/fp8": "GMICloud"}


def prep_think(seed="0", shards="6"):
    """Amendment 4: run 2c's 282 items (139 defects, 143 twins), shuffled together with a fixed seed
    and dealt round-robin into shards, so every shard holds defects and twins and runs them at the
    same time; plus 3 defects (smoke3.jsonl) and the first 3 default-flip twins with at least 3
    evidence snippets (the same rule as prep), alternating, for the smoke test."""
    import random
    ids = sorted({json.loads(l)["task_id"] for p in glob.glob(str(ROOT / "results" / "v3-roc-deepseek-ctrl" / "structure-*.jsonl"))
                  for l in open(p) if l.strip()})
    lines = {}
    for p in sorted(ITEMS.glob("crossfile-v3*-shard*.jsonl")):
        for l in p.read_text().splitlines():
            if l.strip():
                tid = json.loads(l)["task_id"]
                assert tid not in lines, f"duplicate item {tid}"
                lines[tid] = l
    missing = [t for t in ids if t not in lines]
    assert not missing, f"{len(missing)} items of 2c not in the item shards"
    order = list(ids)
    random.Random(int(seed)).shuffle(order)
    n = int(shards)
    for s in range(n):
        (ITEMS / f"think-mixed-shard{s}.jsonl").write_text("\n".join(lines[t] for t in order[s::n]) + "\n")
    sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "services" / "graph"))
    from experiments.benchmark import load_crossfile
    from experiments.evidence import evidence_for, sources_for
    twins = []
    raw =[l for l in (ROOT / "data" / "crossfile-v3-twins.jsonl").read_text().splitlines() if l.strip()]
    by_id = {json.loads(l)["task_id"]: l for l in raw}
    for task in load_crossfile(str(ROOT / "data" / "crossfile-v3-twins.jsonl")):
        if task.metadata.get("kind") != "default_flip" or task.task_id not in ids:
            continue
        ev = evidence_for(task, sources_for(task))
        if ev is not None and len(ev.snippets) >= 3:
            twins.append(by_id[task.task_id])
        if len(twins) == 3:
            break
    defects = [l for l in (ITEMS / "smoke3.jsonl").read_text().splitlines() if l.strip()]
    (ITEMS / "smoke6.jsonl").write_text("\n".join(x for pair in zip(defects, twins) for x in pair) + "\n")
    d = sum(1 for t in ids if json.loads(lines[t]).get("is_defect", True))
    print(f"prep_think: {len(ids)} items ({d} defects, {len(ids) - d} twins), seed {seed}, {n} shards of "
          f"{', '.join(str(len(order[s::n])) for s in range(n))}; smoke items {len(defects)} + {len(twins)}")


def _review_rows(run):
    path = ROOT / "runs" / run / "structure.jsonl"
    return [json.loads(l) for l in path.open() if l.strip()] if path.is_file() else []


def _failed_rows(run):
    path = ROOT / "runs" / run / "failed.jsonl"
    return [json.loads(l) for l in path.open() if l.strip()] if path.is_file() else []


def smoke_think(run, name):
    """Amendment 4 smoke test (6 replies, 3 defects + 3 twins x 5-attributed, plus the manipulation
    check). BUDGET when reasoning used up max_tokens: a reply cut off (finish_reason length), empty, or
    without JSON at max_tokens; the run then uses 16,000. Otherwise OK only if every reply parses with
    a rating for every hunk and no non-header lines, every call (manipulation check included) has the
    run's settings, reasoning_tokens > 0, a finish reason other than length and the served provider
    NAME (reported; ignoring case, spaces, hyphens), and the manipulation check is recorded."""
    rows, failed = _review_rows(run), _failed_rows(run)
    budget, bad = [], []
    for f in failed:
        budget.append(f"{f['call']} {f['task_id'][-40:]} cut off (finish_reason {f.get('finish_reason')!r}, "
                      f"{(f.get('usage') or {}).get('output_tokens')} output tokens)")
    for r in rows:
        tid = r["task_id"][-40:]
        if not (r.get("raw_text") or "").strip():
            budget.append(f"{tid} empty reply ({r['usage']['output_tokens']} output tokens)")
        elif r.get("json_failed") and r["usage"]["output_tokens"] >= (r.get("max_tokens") or 2048):
            budget.append(f"{tid} no JSON at max_tokens ({r['usage']['output_tokens']} output tokens)")
    if budget:
        print("BUDGET " + "; ".join(budget)); return
    for r in rows:
        tid = r["task_id"][-40:]
        if r.get("parse_failed") or r.get("json_failed"):
            bad.append(f"{tid} reply did not parse")
        elif r.get("hunks_rated") != r.get("hunks_total") or r.get("ratings_ambiguous"):
            bad.append(f"{tid} rated {r.get('hunks_rated')} of {r.get('hunks_total')} hunks")
        if r.get("unmatched_rating_lines") or r.get("invalid_rating_entries"):
            bad.append(f"{tid} non-header or invalid rating entries")
    if len(rows) < 6:
        bad.append(f"only {len(rows)} of 6 replies")
    checks = [r for *_, r in _calls([run]) if "answer" in r]
    if not checks:
        bad.append("no manipulation check recorded")
    for _, kind, r in _calls([run]):
        tid = f"{kind[:5]} {r['task_id'][-40:]}"
        if r.get("request_reasoning") != THINK or not r.get("request_provider"):
            bad.append(f"{tid} settings missing or different"); continue
        if not (r.get("reasoning_tokens") or 0) > 0:
            bad.append(f"{tid} reasoning_tokens {r.get('reasoning_tokens')!r}")
        if r.get("finish_reason") == "length":
            bad.append(f"{tid} finish_reason length")
        if r.get("served_provider") is None or _norm(r["served_provider"]) != _norm(name):
            bad.append(f"{tid} served by {r.get('served_provider')!r}")
    print("OK" if not bad else "FAIL " + "; ".join(bad))


def _cost_rows(rows):
    return sum(((r.get("usage") or {}).get("cost_usd") if "usage" in r else r.get("cost")) or 0 for r in rows)


def project_think(run, cap, calls, *smoke_globs):
    """Amendment 4: mean recorded cost of the passing smoke test's review calls x the run's calls x 1.5,
    plus the cost of every smoke test of this run so far (all providers and max_tokens values)."""
    rows = _review_rows(run)
    per = _cost_rows(rows) / max(len(rows), 1)
    spent = sum(_cost_rows([r]) for *_, r in _calls(smoke_globs))
    checks = [r for *_, r in _calls([run]) if "answer" in r]
    projected = per * int(calls) * 1.5 + spent
    print(("OVER" if projected > float(cap) else "WITHIN") + f" projected {projected:.4f} = {per:.6f} mean per "
          f"smoke review x {calls} x 1.5 + smoke cost {spent:.4f}; cap {float(cap):.2f} (for information: "
          f"manipulation check {(_cost_rows(checks) / max(len(checks), 1)):.6f} per call)")


def guard_think(name, planned, *patterns):
    """Amendment 4 abort rules over every recorded call (reviews, manipulation checks, cut-off calls):
    the run's settings missing or different; a reported provider other than NAME; any call over 40,000
    output tokens; more calls with reasoning_tokens 0 (or absent) than 2% of the larger of the
    recorded calls and PLANNED."""
    calls = _calls(patterns)
    zeros = 0
    for run, kind, r in calls:
        where = f"{run}/{kind} {r['task_id'][-50:]} {r.get('arm', '')}"
        if r.get("request_reasoning") != THINK or not r.get("request_provider"):
            print(f"ABORT settings missing or different: {where}"); return
        if r.get("served_provider") is not None and _norm(r["served_provider"]) != _norm(name):
            print(f"ABORT served by {r['served_provider']}: {where}"); return
        if (_out_tokens(r) or 0) > 40000:
            print(f"ABORT output tokens {_out_tokens(r)}: {where}"); return
        zeros += not (r.get("reasoning_tokens") or 0) > 0
    limit = 0.02 * max(len(calls), int(planned))
    if zeros > limit:
        print(f"ABORT {zeros} calls with reasoning_tokens 0, more than 2% of max({len(calls)}, {planned}) = {limit:.2f}")
        return
    reported = sum(1 for *_, r in calls if r.get("served_provider") is not None)
    print(f"OK {len(calls)} calls, provider reported on {reported}, reasoning_tokens 0 on {zeros} (limit {limit:.2f})")


def guard_a5(name, maxrun, *patterns):
    """Amendment 5 abort rules, the only ones: more than MAXRUNAWAY calls logged over the runaway limit;
    a reported provider other than NAME, or a call without the pinned settings (reasoning on, the
    provider NAME's endpoint first, no fallbacks). Calls with reasoning_tokens 0 are counted, not acted on."""
    slug = {v: k for k, v in PIN.items()}[name]
    calls = _calls(patterns)
    for run, kind, r in calls:
        where = f"{run}/{kind} {r['task_id'][-50:]} {r.get('arm', '')}"
        prov = r.get("request_provider") or {}
        if r.get("request_reasoning") != THINK or prov.get("order", [None])[0] != slug or prov.get("allow_fallbacks") is not False:
            print(f"ABORT settings missing or different: {where}"); return
        if r.get("served_provider") is not None and _norm(r["served_provider"]) != _norm(name):
            print(f"ABORT served by {r['served_provider']}: {where}"); return
    runaway = [r for *_, r in calls if r.get("runaway") is True]
    if len(runaway) > int(maxrun):
        print(f"ABORT {len(runaway)} calls over the runaway limit, more than {maxrun}"); return
    zeros = sum(1 for *_, r in calls if not (r.get("reasoning_tokens") or 0) > 0)
    reported = sum(1 for *_, r in calls if r.get("served_provider") is not None)
    print(f"OK {len(calls)} calls, provider reported on {reported}, over the runaway limit {len(runaway)}, "
          f"reasoning_tokens 0 on {zeros}")


def daysplit(*patterns):
    import collections
    import time
    n = collections.Counter()
    for _, kind, r in _calls(patterns):
        if kind == "structure.jsonl":
            day = time.strftime("%a %d %b", time.localtime(r["called_at"])) if r.get("called_at") else "unknown"
            n[r["arm"], day] += 1
    for arm in ("1-diff", "7-random", "5-attributed"):
        cells = ", ".join(f"{d} {c}" for (a, d), c in sorted(n.items()) if a == arm)
        print(f"{arm}: {cells or 'none'}")


def usage_think(*patterns):
    for run, kind, r in _calls(patterns):
        what = {"structure.jsonl": "review", "manipulation.jsonl": "check",
                "failed.jsonl": f"{'RUNAWAY' if r.get('runaway') else 'CUT-OFF'} {r.get('call')}"}[kind]
        print(f"{run} {what} {r['task_id'][-60:]} {r.get('arm', '')}: finish_reason={r.get('finish_reason')!r} "
              f"provider={r.get('served_provider')!r} reasoning_tokens={r.get('reasoning_tokens')!r} "
              f"output_tokens={_out_tokens(r)} usage={json.dumps(r.get('usage_raw'), sort_keys=True)}")


def thinkstats(*patterns):
    import collections
    import statistics
    calls = _calls(patterns)
    rs = [r for *_, r in calls]
    prov = collections.Counter(str(r.get("served_provider")) for r in rs)
    fin = collections.Counter(f"{k.split('.')[0]}:{r.get('finish_reason')}" for _, k, r in calls if "finish_reason" in r)
    rt = [r.get("reasoning_tokens") or 0 for r in rs]
    out = [_out_tokens(r) or 0 for r in rs]
    print(f"calls {len(rs)} (reviews {sum(k == 'structure.jsonl' for _, k, _ in calls)}, manipulation checks "
          f"{sum(k == 'manipulation.jsonl' for _, k, _ in calls)}, cut off "
          f"{sum(k == 'failed.jsonl' and not r.get('runaway') for _, k, r in calls)}, over the runaway limit "
          f"{sum(bool(r.get('runaway')) for _, k, r in calls)}); "
          f"providers {dict(prov)}; reasoning tokens max {max(rt, default=None)}, median "
          f"{statistics.median(rt) if rt else None}, zero on {sum(x == 0 for x in rt)}; output tokens max "
          f"{max(out, default=None)}, median {statistics.median(out) if out else None}; finish reasons {dict(fin)}")


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
     "balance": balance, "smoke_ctrl": smoke_ctrl, "guard": guard, "usage": usage, "ctrlstats": ctrlstats,
     "prep_think": prep_think, "smoke_think": smoke_think, "project_think": project_think,
     "guard_think": guard_think, "usage_think": usage_think, "thinkstats": thinkstats,
     "guard_a5": guard_a5, "daysplit": daysplit}[sys.argv[1]](*sys.argv[2:])
