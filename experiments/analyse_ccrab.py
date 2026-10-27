"""Recompute results/ccrab-today/analysis.txt from the frozen outcome files.

Usage: python experiments/analyse_ccrab.py [results/ccrab-today] [results/gpt-4o-mini]

Pairs defects across conditions, reports the localised rate per condition and the
paired differences with percentile bootstrap intervals (6,000 trials, seed 0),
resampling repositories (the unit that shares code) and, beside it, tasks.
"""
import json, random, sys
from collections import defaultdict
from pathlib import Path

TODAY = {"A": "diff only (today)", "B": "graph, repaired retrieval",
         "C": "random nodes, same budget", "D": "lexical, same budget"}
AUG = {"E": "whole changed files (Aug)", "F": "fault-location oracle (Aug)", "A": "diff only (Aug)"}
PAIRS = [("B", "A", "graph − diff only"), ("B", "C", "graph − random"), ("B", "D", "graph − lexical"),
         ("D", "A", "lexical − diff only"), ("C", "A", "random − diff only")]
PAIRS_CX = [("B", "Cx", "graph − random other files"), ("Cx", "A", "random other files − diff"),
            ("Cx", "C", "random other files − random any")]
TRIALS, SEED = 6000, 0


def load(path, exact=False):
    """hit per (task, defect); with exact, a hit is a finding on the exact line."""
    out = {}
    for line in Path(path).open():
        if line.strip():
            r = json.loads(line)
            hit = bool(r["hit"]) and (not exact or r.get("line_distance") == 0)
            out[(r["task_id"], r["defect_id"])] = hit
    return out


def repo_of(key):
    return key[0].split("-")[0]


def rate(cond, keys):
    return sum(cond[k] for k in keys) / len(keys)


def bootstrap(a, b, keys, by_repo):
    groups = defaultdict(list)
    for k in keys:
        groups[repo_of(k) if by_repo else k].append(k)
    names = sorted(groups)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(TRIALS):
        pick = [names[rng.randrange(len(names))] for _ in names]
        num = den = 0
        for g in pick:
            for k in groups[g]:
                num += int(a[k]) - int(b[k]); den += 1
        diffs.append(num / den)
    diffs.sort()
    return diffs[int(0.025 * TRIALS)], diffs[int(0.975 * TRIALS) - 1]


def section(conds, order, labels, pairs, lines, aug=None, aug_keys=None):
    keys = sorted(set.intersection(*[set(conds[c]) for c in order]))
    lines.append(f"paired defects: {len(keys)}")
    for c in order:
        lines.append(f"  {c:<3}{labels[c]:<34}{rate(conds[c], keys):6.1%}")
    if aug:
        for c, label in AUG.items():
            ks = [k for k in keys if k in aug[c]]
            if ks:
                lines.append(f"  {c:<3}{label:<34}{rate(aug[c], ks):6.1%}   (n={len(ks)})")
    lines.append("")
    for x, y, label in pairs:
        d = rate(conds[x], keys) - rate(conds[y], keys)
        lo, hi = bootstrap(conds[x], conds[y], keys, by_repo=True)
        tlo, thi = bootstrap(conds[x], conds[y], keys, by_repo=False)
        verdict = "excludes zero" if lo > 0 or hi < 0 else "spans zero"
        lines.append(f"  {label:<32}{d:+6.1%}  repo-clustered [{lo:+.1%}, {hi:+.1%}]  "
                     f"task-clustered [{tlo:+.1%}, {thi:+.1%}]  {verdict}")
    return keys


def main(today="results/ccrab-today", august="results/gpt-4o-mini", header=None, exact=False):
    today = Path(today)
    exact = str(exact).lower() in ("1", "true", "exact", "yes")
    conds = {c: load(today / f"{c}-outcomes.jsonl", exact) for c in ["A", "B", "Bs", "C", "Cx", "D"]
             if (today / f"{c}-outcomes.jsonl").exists()}
    aug = None
    if Path(august, "outcomes.jsonl").exists():
        aug = defaultdict(dict)
        for line in Path(august, "outcomes.jsonl").open():
            r = json.loads(line)
            if r["condition"] in AUG:
                aug[r["condition"]][(r["task_id"], r["defect_id"])] = bool(r["hit"])
    lines = [header or "c-CRAB, test-verified real defects, gpt-4o-mini, tolerance 5 lines, budget 1500 tokens",
             "=== exact line (tolerance 0) ===" if exact else "=== A, B, C, D run on one day ==="]
    section(conds, ["A", "B", "C", "D"], TODAY, PAIRS, lines, aug)
    if "Cx" in conds:
        lines += ["", "=== with the random-other-files control (Cx) ==="]
        labels = dict(TODAY, Cx="random, other files only")
        section(conds, ["A", "C", "Cx", "D", "B"], labels, PAIRS_CX, lines)
    if "Bs" in conds:
        lines += ["", "=== graph with the seed node stripped of line_range and metadata (Bs) ==="]
        labels = dict(TODAY, Cx="random, other files only", Bs="graph, seed stripped")
        section(conds, ["A", "Cx", "Bs", "B"], labels,
                [("B", "Bs", "graph - graph seed-stripped"), ("Bs", "A", "graph seed-stripped - diff only"),
                 ("Bs", "Cx", "graph seed-stripped - random other files")], lines)
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
