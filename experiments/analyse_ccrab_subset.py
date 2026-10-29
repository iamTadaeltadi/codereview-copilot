"""Paired analysis of a c-CRAB run that has only some conditions.

Usage: python experiments/analyse_ccrab_subset.py results/ccrab-gemini A,B,Cx "header" [exact]

Same loader, rates and bootstrap as analyse_ccrab (repository-clustered and
task-clustered percentile bootstrap, 6,000 trials, seed 0); every ordered pair
among the named conditions is reported, the first-named pair first.
"""
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.analyse_ccrab import bootstrap, load, rate

LABEL = {"A": "diff only", "B": "graph", "C": "random, any file", "Cx": "random, other files", "D": "lexical"}


def main(results, conds="A,B,Cx", header="", exact=False):
    conds = conds.split(",")
    exact = str(exact).lower() in ("1", "true", "exact", "yes")
    data = {c: load(Path(results, f"{c}-outcomes.jsonl"), exact) for c in conds}
    keys = sorted(set.intersection(*[set(data[c]) for c in conds]))
    lines = [header, "=== exact line (tolerance 0) ===" if exact else "=== tolerance 5 ===", f"paired defects: {len(keys)}"]
    for c in conds:
        lines.append(f"  {c:<3}{LABEL.get(c, c):<34}{rate(data[c], keys):6.1%}")
    lines.append("")
    preferred = [("B", "Cx"), ("B", "A"), ("Cx", "A"), ("B", "C"), ("B", "D"), ("C", "A"), ("D", "A")]
    pairs = [(x, y) for x, y in preferred if x in conds and y in conds]
    pairs += [(b, a) for a, b in combinations(conds, 2) if (b, a) not in pairs and (a, b) not in pairs]
    for x, y in pairs:
        d = rate(data[x], keys) - rate(data[y], keys)
        lo, hi = bootstrap(data[x], data[y], keys, by_repo=True)
        tlo, thi = bootstrap(data[x], data[y], keys, by_repo=False)
        verdict = "excludes zero" if lo > 0 or hi < 0 else "spans zero"
        lines.append(f"  {x + ' − ' + y:<12}{d:+6.1%}  repo-clustered [{lo:+.1%}, {hi:+.1%}]  task-clustered [{tlo:+.1%}, {thi:+.1%}]  {verdict}")
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
