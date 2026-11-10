#!/usr/bin/env python3
"""ROC per arm on kind-matched default flips (paper/PREREG-F.md, Amendment 1).

    python3 experiments/analyse_roc.py results/v3-roc-gpt4omini [> .../analysis-roc.txt]

Reads every structure*.jsonl in the folder (records of run_structure.py --confidence
--hunk-ratings; the smoke/ subfolder is not read). Arms are those present, in the order
1-diff, 7-random, 2b-snippets, 5-attributed.

Primary item score: the defect_probability (0-100) the reply gives the hunk whose header line is
the mutated line. Replies with no JSON object, and replies without a single valid rating for that
hunk (rating missing), are counted and left out; they are never scored 0.
AUC per arm = P(defect score > twin score) + 0.5 P(tie), over all defect-twin pairs of the arm.
dAUC = arm - 1-diff; the primary comparison is 5-attributed - 1-diff. Percentile bootstrap over
repositories (second field of the task id), 6,000 draws, seed 0, defects and twins of a
repository resampled together, the same draws for every arm (as signal_detection.py); 95% and
90% intervals. Reading, at the smallest effect of interest 0.10 (primary) and at 0.05
(secondary): equivalence if the 90% interval lies inside the margin; gain if the 95% interval
lies above 0; both: gain and equivalence; otherwise inconclusive.
Surface-match gate: the 1-diff AUC and its 95% interval; if the interval excludes 0.5, twins are
distinguishable from the diff alone for this model and dAUC is read relative to that baseline.
Secondary: the binary AUC (1 + H - F)/2 from the hit (parse failures dropped); the censored
confidence AUC (PREREG-F's original item score: highest confidence among hits, else 0); H, F,
d', c and their changes (signal_detection.stats), beside Table 2's values for the same model
and arm (results/twins-kind-matched/analysis.txt) where the prompt differs only in the output
contract. Descriptive: tie fraction, distinct values, a histogram of item scores, zROC slope.
"""
import collections
import json
import random
import statistics
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.signal_detection import stats  # noqa: E402

TRIALS, SEED, BASE, PRIMARY, MARGINS = 6000, 0, "1-diff", "5-attributed", (0.10, 0.05)
ORDER = ("1-diff", "7-random", "2b-snippets", "5-attributed")
LABEL = {"1-diff": "1 diff only", "7-random": "7 foreign code", "2b-snippets": "2b caller, no block",
         "5-attributed": "5 attributed"}
BINS = [(0, 0)] + [(1, 9)] + [(10 * k, 10 * k + 9) for k in range(1, 10)] + [(100, 100)]
Z = NormalDist().inv_cdf


def load(folder):
    rows = []
    for p in sorted(Path(folder).glob("structure*.jsonl")):
        rows += [json.loads(l) for l in p.open() if l.strip()]
    return [r for r in rows if r.get("arm") in ORDER and r.get("kind", "default_flip") == "default_flip"]


def repo(r):
    return r["task_id"].split("::")[1]


def ci(values, level):
    v = sorted(x for x in values if x is not None and not np.isnan(x))
    lo = (1 - level) / 2
    return v[int(lo * len(v))], v[int((1 - lo) * len(v)) - 1]


def auc_from_hist(hd, ht):
    """hd, ht: (..., k) counts of defect and twin scores by ascending value; ties count half."""
    nd, nt = hd.sum(-1), ht.sum(-1)
    below = np.cumsum(ht, -1) - ht
    with np.errstate(invalid="ignore", divide="ignore"):
        return (hd * (below + 0.5 * ht)).sum(-1) / (nd * nt)


def reading(lo95, lo90, hi90, margin):
    eq, gain = -margin < lo90 and hi90 < margin, lo95 > 0
    return ("gain and equivalence" if gain and eq else "gain" if gain
            else "equivalence" if eq else "inconclusive")


def zroc_slope(hd, ht):
    """Least-squares slope of z(H) on z(F) over thresholds 1..100 with both rates inside (0, 1)."""
    nd, nt = hd.sum(), ht.sum()
    pts = set()
    for t in range(1, len(hd)):
        H, F = hd[t:].sum() / nd, ht[t:].sum() / nt
        if 0 < H < 1 and 0 < F < 1:
            pts.add((Z(F), Z(H)))
    if len({x for x, _ in pts}) < 3:
        return None, len(pts)
    x, y = np.array(sorted(pts)).T
    return float(np.polyfit(x, y, 1)[0]), len(pts)


def table2(model):
    """Table 2's rows (old contract, neutral prompt) for this model: arm -> (H%, F%, d', c)."""
    path, key, out, on = ROOT / "results" / "twins-kind-matched" / "analysis.txt", model.split("/")[-1], {}, False
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        if line.startswith("### "):
            on = line[4:].split(":")[0] == key
        elif on and line.split() and line.split()[0] in ORDER:
            f = line.split()
            out[f[0]] = (float(f[3]), float(f[4]), float(f[5]), float(f[6]))
    return out


def cost_of(paths):
    total = 0.0
    for p in paths:
        for l in p.open():
            if l.strip():
                r = json.loads(l)
                total += ((r.get("usage") or {}).get("cost_usd") if "usage" in r else r.get("cost")) or 0
    return total


def main(folder):
    folder = Path(folder)
    rows = load(folder)
    arms = [a for a in ORDER if any(r["arm"] == a for r in rows)]
    models = sorted({r.get("model") or "" for r in rows})
    authoritative = sorted({bool(r.get("authoritative")) for r in rows})
    scored = [r for r in rows if r.get("hunk_score") is not None]
    repos = sorted(set.intersection(*[{repo(r) for r in scored if r["arm"] == a} for a in arms]))
    index = {g: i for i, g in enumerate(repos)}
    rng = random.Random(SEED)
    draws = [[repos[rng.randrange(len(repos))] for _ in repos] for _ in range(TRIALS)]
    mult = np.zeros((TRIALS, len(repos)))
    for t, pick in enumerate(draws):
        for g in pick:
            mult[t, index[g]] += 1

    def hists(arm, value, k):
        hd, ht = np.zeros((len(repos), k)), np.zeros((len(repos), k))
        for r in rows:
            v = value(r) if r["arm"] == arm and repo(r) in index else None
            if v is not None:
                (hd if r["is_defect"] else ht)[index[repo(r)], v] += 1
        return hd, ht

    measures = {
        "hunk": (lambda r: r.get("hunk_score"), 101),
        "binary": (lambda r: None if r.get("correct") is None else int(bool(r["hit"])), 2),
        "censored": (lambda r: r.get("item_score"), 101),
    }
    point, boot, pooled = {}, {}, {}
    for m, (value, k) in measures.items():
        for a in arms:
            hd, ht = hists(a, value, k)
            pooled[m, a] = (hd.sum(0), ht.sum(0))
            point[m, a] = float(auc_from_hist(*pooled[m, a]))
            boot[m, a] = auc_from_hist(mult @ hd, mult @ ht)

    smoke = list((folder / "smoke").glob("structure.jsonl"))
    manip = sorted(folder.glob("manipulation*.jsonl"))
    out = [f"ROC on kind-matched default flips (paper/PREREG-F.md, Amendment 1): {folder}",
           f"model: {', '.join(m for m in models if m)}; arms: {', '.join(arms)}; authoritative: "
           f"{'/'.join(map(str, authoritative))}; hunk ratings on in every record: "
           f"{all(r.get('hunk_ratings_on') for r in rows)}",
           *([f"settings (Amendment 3): reasoning {rows[0].get('request_reasoning')}; provider "
               f"{rows[0].get('request_provider')}; served by "
               f"{dict(collections.Counter(str(r.get('served_provider')) for r in rows))}; max reasoning tokens "
               f"{max((r.get('reasoning_tokens') or 0) for r in rows)}; max output tokens "
               f"{max((r.get('usage') or {}).get('output_tokens') or 0 for r in rows)}"]
             if any(r.get("request_provider") for r in rows) else []),
           f"records: {len(rows)}; recorded cost: reviews ${cost_of(sorted(folder.glob('structure*.jsonl'))):.4f}, "
           f"manipulation checks ${cost_of(manip):.4f}, smoke ${cost_of(smoke):.4f}",
           f"repositories with a scored item in every arm: {len(repos)}; bootstrap over repositories, "
           f"{TRIALS} draws, seed {SEED}, defects and twins of a repository resampled together",
           "item score = the defect_probability of the mutated line's hunk; no-JSON replies and missing",
           "ratings are left out and counted, never scored 0", ""]

    if BASE in arms:
        lo, hi = ci(boot["hunk", BASE], 0.95)
        out += ["1. Surface-match gate (diff only)",
                f"  AUC {point['hunk', BASE]:.3f} [{lo:.3f}, {hi:.3f}]: " +
                ("excludes 0.5: twins are distinguishable from the diff alone for this model; dAUC is read "
                 "relative to this baseline" if lo > 0.5 or hi < 0.5 else "includes 0.5"), ""]

    out += ["2. Per arm, primary score (hunk rating)",
            f"  {'arm':<21}{'def att/sc':>11}{'twin att/sc':>12}{'no JSON d/t':>12}{'missing d/t':>12}"
            f"{'ambig':>6}{'unmat':>6}{'all rated':>10}{'ties':>7}{'values':>7}{'AUC':>7}  95%"]
    for a in arms:
        ar = [r for r in rows if r["arm"] == a]
        att = [sum(1 for r in ar if bool(r["is_defect"]) == d) for d in (True, False)]
        nj = [sum(1 for r in ar if r.get("json_failed") and bool(r["is_defect"]) == d) for d in (True, False)]
        ms = [sum(1 for r in ar if r.get("rating_missing") and bool(r["is_defect"]) == d) for d in (True, False)]
        amb = sum(1 for r in ar if r.get("ratings_ambiguous"))
        unm = sum(1 for r in ar if r.get("unmatched_rating_lines") or r.get("invalid_rating_entries"))
        parsed = [r for r in ar if r.get("json_failed") is False]
        full = sum(1 for r in parsed if r.get("hunks_rated") == r.get("hunks_total"))
        hd, ht = pooled["hunk", a]
        ties = float((hd * ht).sum() / (hd.sum() * ht.sum())) if hd.sum() and ht.sum() else float("nan")
        lo, hi = ci(boot["hunk", a], 0.95)
        out.append(f"  {LABEL[a]:<21}{att[0]:>6}/{int(hd.sum()):<4}{att[1]:>7}/{int(ht.sum()):<4}"
                   f"{nj[0]:>7}/{nj[1]:<4}{ms[0]:>7}/{ms[1]:<4}{amb:>6}{unm:>6}"
                   f"{(100 * full / len(parsed) if parsed else float('nan')):>9.1f}%{ties:>7.3f}"
                   f"{int(((hd + ht) > 0).sum()):>7}{point['hunk', a]:>7.3f}  [{lo:.3f}, {hi:.3f}]")
    out += ["  att/sc: attempted / scored in the bootstrap repositories; ambig: replies rating a hunk twice with",
            "  different values; unmat: replies with entries for non-header lines or invalid entries; all rated:",
            "  share of parsed replies rating every hunk; ties: share of defect-twin pairs with equal scores;",
            "  values: distinct item scores", ""]

    out += ["3. AUC by score, per arm (primary hunk rating beside the secondary scores)",
            f"  {'arm':<21}{'hunk':>7}{'binary (1+H-F)/2':>18}{'censored confidence':>21}"]
    for a in arms:
        out.append(f"  {LABEL[a]:<21}{point['hunk', a]:>7.3f}{point['binary', a]:>18.3f}{point['censored', a]:>21.3f}")
    out.append("")

    if BASE in arms:
        out += ["4. dAUC vs 1-diff, hunk rating (primary: 5-attributed - 1-diff)",
                f"  {'arm':<21}{'dAUC':>8}  {'95%':<18}{'90%':<18}{'reading at 0.10':<23}reading at 0.05"]
        for a in arms:
            if a == BASE:
                continue
            d = boot["hunk", a] - boot["hunk", BASE]
            lo95, hi95 = ci(d, 0.95); lo90, hi90 = ci(d, 0.90)
            tag = "PRIMARY " if a == PRIMARY else "secondary "
            out.append(f"  {LABEL[a]:<21}{point['hunk', a] - point['hunk', BASE]:>+8.3f}  "
                       f"[{lo95:+.3f}, {hi95:+.3f}]  [{lo90:+.3f}, {hi90:+.3f}]  "
                       f"{tag + reading(lo95, lo90, hi90, MARGINS[0]):<23}{reading(lo95, lo90, hi90, MARGINS[1])}")
        out += ["  equivalence: 90% interval inside the margin; gain: 95% interval above 0", "",
                "  secondary scores, dAUC vs 1-diff [95%]:",
                f"  {'arm':<21}{'binary':>26}{'censored confidence':>30}"]
        for a in arms:
            if a == BASE:
                continue
            cells = []
            for m in ("binary", "censored"):
                lo, hi = ci(boot[m, a] - boot[m, BASE], 0.95)
                cells.append(f"{point[m, a] - point[m, BASE]:+.3f} [{lo:+.3f}, {hi:+.3f}]")
            out.append(f"  {LABEL[a]:<21}{cells[0]:>26}{cells[1]:>30}")
        out.append("")

    out += ["5. Histogram of item scores (mutated hunk), defects (d) and twins (t)",
            "  " + f"{'arm':<23}" + "".join(f"{(str(lo) if lo == hi else f'{lo}-{hi}'):>6}" for lo, hi in BINS)
            + "  median  most common values (d+t)"]
    for a in arms:
        hd, ht = pooled["hunk", a]
        both = hd + ht
        top = ", ".join(f"{v}:{int(both[v])}" for v in np.argsort(-both, kind="stable")[:5] if both[v])
        for name, h in (("d", hd), ("t", ht)):
            vals = [v for v in range(101) for _ in range(int(h[v]))]
            cells = "".join(f"{int(h[lo:hi + 1].sum()):>6}" for lo, hi in BINS)
            med = f"{statistics.median(vals):>6.1f}" if vals else f"{'-':>6}"
            out.append(f"  {(LABEL[a] if name == 'd' else ''):<21}{name:>2}{cells}  {med}"
                       + (f"  {top}" if name == "d" else ""))
    out.append("")

    ref = table2(models[-1]) if models else {}
    by = {a: {g: [] for g in repos} for a in arms}
    for r in rows:
        if r.get("correct") is not None and repo(r) in index:
            by[r["arm"]][repo(r)].append((bool(r["is_defect"]), bool(r["hit"])))
    sp = {a: stats([x for g in repos for x in by[a][g]]) for a in arms}
    sb = {a: [stats([x for g in pick for x in by[a][g]]) for pick in draws] for a in arms}
    out += ["6. Secondary, binary hit (parse failures dropped), with Table 2 (old contract) for reference",
            f"  {'arm':<21}{'H%':>6}{'F%':>6}{'d-prime':>8}  {'95%':<16}{'c':>6}  {'95%':<16}"
            f"{'dd vs 1-diff':<22}{'dc vs 1-diff':<22}Table 2 H% F% d' c"]
    for a in arms:
        H, F, dp, c = sp[a]
        dlo, dhi = ci([b[2] for b in sb[a] if b], 0.95); clo, chi = ci([b[3] for b in sb[a] if b], 0.95)
        if BASE in arms:
            ddlo, ddhi = ci([x[2] - y[2] for x, y in zip(sb[a], sb[BASE]) if x and y], 0.95)
            dclo, dchi = ci([x[3] - y[3] for x, y in zip(sb[a], sb[BASE]) if x and y], 0.95)
            dd = f"{dp - sp[BASE][2]:+.2f} [{ddlo:+.2f}, {ddhi:+.2f}]"
            dc = f"{c - sp[BASE][3]:+.2f} [{dclo:+.2f}, {dchi:+.2f}]"
        else:
            dd = dc = "-"
        same_prompt = a == BASE or authoritative == [False]
        t2 = ref.get(a) if same_prompt else None
        out.append(f"  {LABEL[a]:<21}{100 * H:>6.1f}{100 * F:>6.1f}{dp:>8.2f}  [{dlo:+.2f}, {dhi:+.2f}]  "
                   f"{c:>6.2f}  [{clo:+.2f}, {chi:+.2f}]  {dd:<22}{dc:<22}"
                   + (f"{t2[0]:.1f} {t2[1]:.1f} {t2[2]:+.2f} {t2[3]:+.2f}" if t2 else "-"))
    out.append("")

    out += ["7. zROC slope of the hunk rating (descriptive; least squares of z(H) on z(F) over thresholds)"]
    for a in arms:
        slope, n = zroc_slope(*pooled["hunk", a])
        out.append(f"  {LABEL[a]:<21}" + (f"{slope:.2f} ({n} points)" if slope is not None else f"n/a ({n} points)"))
    out += ["", "8. Multiplicity: one primary comparison per run (5-attributed - 1-diff, hunk rating). Every other",
            "  comparison, measure and run is reported without correction and read as secondary."]
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
