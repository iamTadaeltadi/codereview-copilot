#!/usr/bin/env python3
"""Condition E (paper/PREREG-E.md): E - Cx, E - B and E - A on both models.

    .venv/bin/python experiments/analyse_ccrab_cis.py [results/ccrab-cis]

E records: results/ccrab-cis/<model>/E-outcomes.jsonl. Comparators are frozen: A, B and Cx from
results/ccrab-final (gpt-4o-mini, run 4) and results/ccrab-deepseek (deepseek-v3.2). Each
difference is paired on defects present in both conditions, with the repository-clustered and
task-clustered percentile bootstraps of analyse_ccrab.py (6,000 trials, seed 0).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.analyse_ccrab import TRIALS, bootstrap, load, rate  # noqa: E402

MODELS = (("gpt-4o-mini", ROOT / "results" / "ccrab-final"),
          ("deepseek-v3.2", ROOT / "results" / "ccrab-deepseek"))
SUBSET = ROOT / "results" / "ccrab-final" / "primary-subset.txt"
PAIRS = (("Cx", "E − Cx (primary)"), ("B", "E − B"), ("A", "E − A"))


def cell(E, other, keys):
    keys = sorted(set(E) & set(other) & keys)
    d = rate(E, keys) - rate(other, keys)
    lo, hi = bootstrap(E, other, keys, by_repo=True)
    tlo, thi = bootstrap(E, other, keys, by_repo=False)
    return len(keys), rate(E, keys), rate(other, keys), d, lo, hi, tlo, thi


def main(outdir="results/ccrab-cis", e_name="E-outcomes.jsonl", e_dirs=None):
    outdir = Path(outdir)
    subset_ids = {l.strip() for l in SUBSET.open() if l.strip()}
    lines = ["Condition E (CIS context) on c-CRAB, paper/PREREG-E.md",
             f"paired bootstrap, {TRIALS} trials, seed 0; repo-clustered interval decides, task-clustered beside it",
             ""]
    decision = {}
    for model, frozen in MODELS:
        e_path = Path(e_dirs[model]) if e_dirs else outdir / model / e_name
        if not e_path.is_file():
            lines += [f"=== {model}: no E records at {e_path} ===", ""]
            continue
        for exact in (False, True):
            E = load(e_path, exact)
            comps = {c: load(frozen / f"{c}-outcomes.jsonl", exact) for c in ("A", "B", "Cx")}
            for subset_name in ("all paired defects", "pre-registered subset"):
                if subset_name == "all paired defects":
                    keys = set(E)
                else:
                    keys = {k for k in E if k[1] in subset_ids}
                tol = "exact line" if exact else "tolerance 5"
                lines.append(f"=== {model}, {tol}, {subset_name} ===")
                for c, label in PAIRS:
                    n, re_, ro, d, lo, hi, tlo, thi = cell(E, comps[c], keys)
                    verdict = ("above zero" if lo > 0 else "below zero" if hi < 0 else "spans zero")
                    lines.append(f"  {label:<18} n={n:<4} E {re_:6.1%}  {c:<2} {ro:6.1%}  diff {d:+6.1%}  "
                                 f"repo [{lo:+.1%}, {hi:+.1%}]  task [{tlo:+.1%}, {thi:+.1%}]  {verdict}")
                    if c == "Cx":
                        decision[(model, exact, subset_name)] = verdict
                lines.append("")
    lines.append("Decision rule: E beats Cx only if E − Cx is above zero on BOTH models in the decision cell")
    lines.append("(tolerance 5, pre-registered subset). Other cells are reported under the same rule.")
    for exact in (False, True):
        for subset_name in ("pre-registered subset", "all paired defects"):
            v = [decision.get((m, exact, subset_name)) for m, _ in MODELS]
            tol = "exact line" if exact else "tolerance 5"
            tag = " (DECISION CELL)" if (not exact and subset_name == "pre-registered subset") else ""
            if None in v:
                outcome = "incomplete: a model has no E records"
            elif all(x == "above zero" for x in v):
                outcome = "E beats Cx on both models"
            elif all(x == "below zero" for x in v):
                outcome = "E worse than Cx on both models"
            else:
                outcome = "no detectable gain (" + ", ".join(f"{m}: {x}" for (m, _), x in zip(MODELS, v)) + ")"
            lines.append(f"  {tol}, {subset_name}{tag}: {outcome}")
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
