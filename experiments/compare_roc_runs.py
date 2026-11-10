#!/usr/bin/env python3
"""Between-run comparison on the same items (paper/PREREG-F.md, Amendment 4, secondary).

    python3 experiments/compare_roc_runs.py results/v3-roc-deepseek-think results/v3-roc-deepseek-ctrl \
        > results/v3-roc-deepseek-think/compare-2c.txt

Run A is the first folder (2t, reasoning on), run B the second (2c, reasoning off); only arms
1-diff and 5-attributed are read. The statistic is the difference of differences in hunk-rating AUC,
(5-attributed - 1-diff in A) - (5-attributed - 1-diff in B), each cell over its scored items, as in
analyse_roc.py. Percentile bootstrap over repositories (second field of the task id): the
repositories with a scored item in all four cells, 6,000 draws, seed 0 (the draws are built as in
analyse_roc.py), one draw applied to all four cells, so both runs resample the same repositories.
95% interval. Also: per run and arm H, F, d', c from the binary hit (parse failures dropped;
signal_detection.stats), the change from B to A per arm, and dc (5-attributed - 1-diff) per run and
its difference between runs, with 95% intervals from the same draws; and, descriptive, the
difference of differences on the items scored in all four cells.
"""
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.analyse_roc import auc_from_hist, ci, load, repo  # noqa: E402
from experiments.signal_detection import stats  # noqa: E402

TRIALS, SEED, ARMS = 6000, 0, ("1-diff", "5-attributed")


def main(folder_a, folder_b):
    runs = {"A": [r for r in load(folder_a) if r["arm"] in ARMS], "B": [r for r in load(folder_b) if r["arm"] in ARMS]}
    cells = [(x, a) for x in runs for a in ARMS]
    scored = {(x, a): [r for r in runs[x] if r["arm"] == a and r.get("hunk_score") is not None] for x, a in cells}
    repos = sorted(set.intersection(*[{repo(r) for r in scored[c]} for c in cells]))
    index = {g: i for i, g in enumerate(repos)}
    rng = random.Random(SEED)
    draws = [[repos[rng.randrange(len(repos))] for _ in repos] for _ in range(TRIALS)]
    mult = np.zeros((TRIALS, len(repos)))
    for t, pick in enumerate(draws):
        for g in pick:
            mult[t, index[g]] += 1

    def auc(rows):
        hd, ht = np.zeros((len(repos), 101)), np.zeros((len(repos), 101))
        for r in rows:
            if repo(r) in index:
                (hd if r["is_defect"] else ht)[index[repo(r)], r["hunk_score"]] += 1
        return float(auc_from_hist(hd.sum(0), ht.sum(0))), auc_from_hist(mult @ hd, mult @ ht), int(hd.sum()), int(ht.sum())

    res = {c: auc(scored[c]) for c in cells}
    common = set.intersection(*[{r["task_id"] for r in scored[c]} for c in cells])
    res_c = {c: auc([r for r in scored[c] if r["task_id"] in common]) for c in cells}

    def did(rs):
        point = (rs["A", ARMS[1]][0] - rs["A", ARMS[0]][0]) - (rs["B", ARMS[1]][0] - rs["B", ARMS[0]][0])
        boot = (rs["A", ARMS[1]][1] - rs["A", ARMS[0]][1]) - (rs["B", ARMS[1]][1] - rs["B", ARMS[0]][1])
        return point, ci(boot, 0.95)

    out = [f"Between-run comparison (paper/PREREG-F.md, Amendment 4, secondary)",
           f"A = {folder_a}", f"B = {folder_b}",
           f"arms {', '.join(ARMS)}; repositories with a scored item in all four cells: {len(repos)}; "
           f"bootstrap over repositories, {TRIALS} draws, seed {SEED}, the same draw for both runs", "",
           "1. Hunk-rating AUC per run and arm (each cell over its scored items)",
           f"  {'run':<5}{'arm':<15}{'defects':>8}{'twins':>7}{'AUC':>8}  95%"]
    for x, a in cells:
        p, b, nd, nt = res[x, a]
        lo, hi = ci(b, 0.95)
        out.append(f"  {x:<5}{a:<15}{nd:>8}{nt:>7}{p:>8.3f}  [{lo:.3f}, {hi:.3f}]")
    out += ["", "2. dAUC (5-attributed - 1-diff) per run, and the difference between runs"]
    for x in runs:
        d = res[x, ARMS[1]][1] - res[x, ARMS[0]][1]
        lo, hi = ci(d, 0.95)
        out.append(f"  {x}: {res[x, ARMS[1]][0] - res[x, ARMS[0]][0]:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    p, (lo, hi) = did(res)
    out += [f"  difference of differences, A - B: {p:+.3f} [{lo:+.3f}, {hi:+.3f}]  "
            + ("(95% interval above 0)" if lo > 0 else "(95% interval below 0)" if hi < 0 else "(95% interval includes 0)"),
            f"  descriptive, the {len(common)} items scored in all four cells "
            f"({sum(1 for r in scored['A', ARMS[0]] if r['task_id'] in common and r['is_defect'])} defects, "
            f"{sum(1 for r in scored['A', ARMS[0]] if r['task_id'] in common and not r['is_defect'])} twins): "
            f"{did(res_c)[0]:+.3f} [{did(res_c)[1][0]:+.3f}, {did(res_c)[1][1]:+.3f}]", ""]

    by = {c: {g: [] for g in repos} for c in cells}
    for x, a in cells:
        for r in runs[x]:
            if r["arm"] == a and r.get("correct") is not None and repo(r) in index:
                by[x, a][repo(r)].append((bool(r["is_defect"]), bool(r["hit"])))
    sp = {c: stats([v for g in repos for v in by[c][g]]) for c in cells}
    sb = {c: [stats([v for g in pick for v in by[c][g]]) for pick in draws] for c in cells}
    names = ("H%", "F%", "d'", "c")
    scale = (100, 100, 1, 1)

    def fmt(k, point, boot):
        lo, hi = ci([b for b in boot if b is not None], 0.95)
        f = "+.1f" if scale[k] == 100 else "+.2f"
        return f"{scale[k] * point:{f}} [{scale[k] * lo:{f}}, {scale[k] * hi:{f}}]"

    out += ["3. Binary hit (parse failures dropped): H, F, d', c per run and arm",
            f"  {'run':<5}{'arm':<15}{'nD':>5}{'nT':>5}{'H%':>7}{'F%':>7}{'d-prime':>9}{'c':>7}"]
    for x, a in cells:
        H, F, dp, c = sp[x, a]
        nd = sum(1 for g in repos for v in by[x, a][g] if v[0]); nt = sum(1 for g in repos for v in by[x, a][g] if not v[0])
        out.append(f"  {x:<5}{a:<15}{nd:>5}{nt:>5}{100 * H:>7.1f}{100 * F:>7.1f}{dp:>9.2f}{c:>7.2f}")
    out += ["", "4. Change from B to A per arm (A - B) [95%]",
            f"  {'arm':<15}" + "".join(f"{n:>24}" for n in names)]
    for a in ARMS:
        row = []
        for k in range(4):
            boot = [x[k] - y[k] if x and y else None for x, y in zip(sb["A", a], sb["B", a])]
            row.append(fmt(k, sp["A", a][k] - sp["B", a][k], boot))
        out.append(f"  {a:<15}" + "".join(f"{v:>24}" for v in row))
    out += ["", "5. Change from 1-diff to 5-attributed per run, and its difference between runs [95%]",
            f"  {'':<15}" + "".join(f"{n:>24}" for n in ("dH%", "dF%", "dd'", "dc"))]

    def delta(x, k):
        return [b5[k] - b1[k] if b5 and b1 else None for b5, b1 in zip(sb[x, ARMS[1]], sb[x, ARMS[0]])]
    for x in runs:
        out.append(f"  {'run ' + x:<15}" + "".join(
            f"{fmt(k, sp[x, ARMS[1]][k] - sp[x, ARMS[0]][k], delta(x, k)):>24}" for k in range(4)))
    row = []
    for k in range(4):
        point = (sp["A", ARMS[1]][k] - sp["A", ARMS[0]][k]) - (sp["B", ARMS[1]][k] - sp["B", ARMS[0]][k])
        boot = [p - q if p is not None and q is not None else None for p, q in zip(delta("A", k), delta("B", k))]
        row.append(fmt(k, point, boot))
    out.append(f"  {'A - B':<15}" + "".join(f"{v:>24}" for v in row))
    out += ["", "Secondary and post hoc (Amendment 4): one comparison of two runs, read with the primary result of",
            "each run; no correction for multiplicity."]
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
