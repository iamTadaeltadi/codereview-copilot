#!/usr/bin/env python3
"""Post hoc, descriptive only (not pre-registered): deepseek-v3.2 reply length in run F.

    python3 experiments/posthoc_reply_length.py results/v3-roc-deepseek results/v3-roc-deepseek-auth

During run 2 the deepseek replies changed from thousands of output tokens per call to under two
hundred, at about the same point in all six shards; run 4 was short throughout. The records do not
name the provider, so the cause is not known. This prints (1) mean output tokens per quarter of
each shard file, in the order the calls were made, and (2) per arm, for items whose replies were
long (median output tokens of the item's replies >= 500) and short, the hunk-rating AUC and the
binary H and F. Point estimates only; no intervals, no test.
"""
import glob
import json
import statistics
import sys
from collections import defaultdict

ARMS = ("1-diff", "7-random", "2b-snippets", "5-attributed")


def auc(d, t):
    return sum((x > y) + 0.5 * (x == y) for x in d for y in t) / (len(d) * len(t)) if d and t else float("nan")


for folder in sys.argv[1:]:
    print(f"### {folder}")
    rows = []
    print("  mean output tokens per call, by quarter of each shard file (call order):")
    for p in sorted(glob.glob(f"{folder}/structure-*-shard*.jsonl")):
        rs = [json.loads(l) for l in open(p) if l.strip()]
        rows += rs
        q = len(rs) // 4
        print(f"    {p.split('/')[-1]:<32}" + "".join(
            f"{sum(r['usage']['output_tokens'] for r in rs[i * q:(i + 1) * q]) / q:>7.0f}" for i in range(4)))
    tokens = defaultdict(list)
    for r in rows:
        tokens[r["task_id"]].append(r["usage"]["output_tokens"])
    mode = {k: "long" if statistics.median(v) >= 500 else "short" for k, v in tokens.items()}
    print(f"  items: long {sum(m == 'long' for m in mode.values())}, short {sum(m == 'short' for m in mode.values())}")
    print(f"  {'replies':<7} {'arm':<13} {'nD':>4} {'nT':>4} {'hunk AUC':>9} {'H%':>6} {'F%':>6}")
    for m in ("long", "short"):
        for a in ARMS:
            v = [r for r in rows if r["arm"] == a and mode[r["task_id"]] == m]
            s = [r for r in v if r.get("hunk_score") is not None]
            if not s:
                continue
            d = [r["hunk_score"] for r in s if r["is_defect"]]
            t = [r["hunk_score"] for r in s if not r["is_defect"]]
            b = [r for r in v if r.get("correct") is not None]
            bd = [r["hit"] for r in b if r["is_defect"]]
            bt = [r["hit"] for r in b if not r["is_defect"]]
            print(f"  {m:<7} {a:<13} {len(d):>4} {len(t):>4} {auc(d, t):>9.3f} "
                  f"{100 * sum(bd) / len(bd):>6.1f} {100 * sum(bt) / len(bt):>6.1f}")
    print()
