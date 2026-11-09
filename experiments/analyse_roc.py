#!/usr/bin/env python3
"""ROC per arm on kind-matched default flips (paper/PREREG-F.md).

    python experiments/analyse_roc.py results/v3-roc-gpt4omini [> .../analysis-roc.txt]

Reads every structure*.jsonl in the folder (defect and twin records of run_structure.py
--confidence; the smoke/ subfolder is not read). Item score: the highest confidence among
findings the matcher counts as a hit on the mutated line, 0 with no hit (run_structure.py
score_items). Replies that could not be parsed, and hits without a valid confidence, are
counted and left out; they are never scored 0.

Primary: AUC per arm = P(defect score > twin score) + 0.5 P(tie), over all defect-twin pairs of
the arm. dAUC = arm - 1-diff. Percentile bootstrap over repositories (second field of the task
id), 6,000 trials, seed 0, defects and twins of a repository resampled together, the same draws
for every arm (as experiments/signal_detection.py); 95% and 90% intervals.
Reading: equivalence if the 90% interval of dAUC lies inside [-0.05, +0.05]; gain if the 95%
interval lies above 0; otherwise inconclusive.
Secondary: H, F, d', c from the binary hit, as signal_detection.py, on the same draws.
"""
import json
import random
import statistics
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.signal_detection import stats  # noqa: E402

TRIALS, SEED, BASE, MARGIN = 6000, 0, "1-diff", 0.05
ARMS = ("1-diff", "7-random", "2b-snippets", "5-attributed")
LABEL = {"1-diff": "1 diff only", "7-random": "7 foreign code", "2b-snippets": "2b caller, no block",
         "5-attributed": "5 attributed"}


def load(folder):
    rows = []
    for p in sorted(Path(folder).glob("structure*.jsonl")):
        rows += [json.loads(l) for l in p.open() if l.strip()]
    return [r for r in rows if r.get("arm") in ARMS]


def repo(r):
    return r["task_id"].split("::")[1]


def ci(values, level):
    v = sorted(x for x in values if x is not None and not np.isnan(x))
    lo = (1 - level) / 2
    return v[int(lo * len(v))], v[int((1 - lo) * len(v)) - 1]


def auc_from_hist(hd, ht):
    """hd, ht: (..., 101) counts of defect and twin scores; AUC with ties counted half."""
    nd, nt = hd.sum(-1), ht.sum(-1)
    below = np.cumsum(ht, -1) - ht
    with np.errstate(invalid="ignore", divide="ignore"):
        return (hd * (below + 0.5 * ht)).sum(-1) / (nd * nt)


def main(folder):
    rows = load(folder)
    model = sorted({r.get("model") for r in rows})
    scored = [r for r in rows if r.get("item_score") is not None]
    repos = sorted(set.intersection(*[{repo(r) for r in scored if r["arm"] == a} for a in ARMS]))
    index = {g: i for i, g in enumerate(repos)}
    rng = random.Random(SEED)
    draws = [[repos[rng.randrange(len(repos))] for _ in repos] for _ in range(TRIALS)]
    mult = np.zeros((TRIALS, len(repos)))
    for t, pick in enumerate(draws):
        for g in pick:
            mult[t, index[g]] += 1

    out = [f"ROC on kind-matched default flips (paper/PREREG-F.md): {folder}",
           f"model: {', '.join(m for m in model if m)}",
           f"records: {len(rows)}; cost of these records ${sum((r.get('usage') or {}).get('cost_usd') or 0 for r in rows):.4f}",
           f"repositories in every arm: {len(repos)}; bootstrap over repositories, {TRIALS} trials, seed {SEED}",
           "item score = highest confidence among hits on the mutated line, 0 with no hit; parse failures and",
           "hits without a valid confidence are left out and counted", ""]
    auc, boot = {}, {}
    out.append(f"  {'arm':<22}{'defects':>8}{'twins':>7}{'parse fail d/t':>16}{'conf missing d/t':>18}"
               f"{'AUC':>8}  95%")
    for a in ARMS:
        ar = [r for r in rows if r["arm"] == a]
        sc = [r for r in ar if r.get("item_score") is not None and repo(r) in index]
        hd = np.zeros((len(repos), 101)); ht = np.zeros((len(repos), 101))
        for r in sc:
            (hd if r["is_defect"] else ht)[index[repo(r)], r["item_score"]] += 1
        auc[a] = float(auc_from_hist(hd.sum(0), ht.sum(0)))
        boot[a] = auc_from_hist(mult @ hd, mult @ ht)
        pf = [sum(1 for r in ar if r.get("parse_failed") and r["is_defect"] == d) for d in (True, False)]
        cm = [sum(1 for r in ar if r.get("confidence_missing") and r["is_defect"] == d) for d in (True, False)]
        lo, hi = ci(boot[a], 0.95)
        out.append(f"  {LABEL[a]:<22}{int(hd.sum()):>8}{int(ht.sum()):>7}{pf[0]:>10}/{pf[1]:<5}{cm[0]:>12}/{cm[1]:<5}"
                   f"{auc[a]:>8.3f}  [{lo:.3f}, {hi:.3f}]")
    out += ["", f"  {'dAUC vs 1-diff':<22}{'dAUC':>8}  95%                90%                reading"]
    for a in ARMS[1:]:
        d = boot[a] - boot[BASE]
        lo95, hi95 = ci(d, 0.95); lo90, hi90 = ci(d, 0.90)
        eq = -MARGIN < lo90 and hi90 < MARGIN
        gain = lo95 > 0
        reading = ("gain and equivalence (gain below 0.05)" if gain and eq else "gain" if gain
                   else "equivalence (no discrimination gain)" if eq else "inconclusive")
        out.append(f"  {LABEL[a]:<22}{auc[a] - auc[BASE]:>+8.3f}  [{lo95:+.3f}, {hi95:+.3f}]   "
                   f"[{lo90:+.3f}, {hi90:+.3f}]   {reading}")

    out += ["", "  confidence of hits:  median   distinct values   hits with confidence 100"]
    for a in ARMS:
        hc = [f["confidence"] for r in rows if r["arm"] == a and r.get("item_score") is not None
              for f in r.get("finding_scores") or [] if f["hit"] and f["confidence"] is not None]
        out.append(f"  {LABEL[a]:<22}{statistics.median(hc) if hc else float('nan'):>6.1f}"
                   f"{len(set(hc)):>14}{sum(1 for c in hc if c == 100):>16} of {len(hc)}")

    # Secondary: the binary hit, as signal_detection.py (parse failures dropped; confidence not needed).
    by = {a: {g: [] for g in repos} for a in ARMS}
    for r in rows:
        if r.get("correct") is not None and repo(r) in index:
            by[r["arm"]][repo(r)].append((bool(r["is_defect"]), bool(r["hit"])))
    point = {a: stats([x for g in repos for x in by[a][g]]) for a in ARMS}
    sboot = {a: [stats([x for g in pick for x in by[a][g]]) for pick in draws] for a in ARMS}
    out += ["", "  secondary, binary hit:", f"  {'arm':<22}{'H':>7}{'F':>7}{'d-prime':>9}  95%              "
            f"{'c':>7}  95%              d'-d'(diff) 95%        c-c(diff) 95%"]
    for a in ARMS:
        H, F, dp, c = point[a]
        dlo, dhi = ci([b[2] for b in sboot[a] if b], 0.95); clo, chi = ci([b[3] for b in sboot[a] if b], 0.95)
        ddlo, ddhi = ci([x[2] - y[2] for x, y in zip(sboot[a], sboot[BASE]) if x and y], 0.95)
        dclo, dchi = ci([x[3] - y[3] for x, y in zip(sboot[a], sboot[BASE]) if x and y], 0.95)
        out.append(f"  {LABEL[a]:<22}{H:>7.3f}{F:>7.3f}{dp:>9.2f}  [{dlo:+.2f}, {dhi:+.2f}]  {c:>7.2f}  "
                   f"[{clo:+.2f}, {chi:+.2f}]  {dp - point[BASE][2]:+.2f} [{ddlo:+.2f}, {ddhi:+.2f}]  "
                   f"{c - point[BASE][3]:+.2f} [{dclo:+.2f}, {dchi:+.2f}]")
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
