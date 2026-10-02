#!/usr/bin/env python3
"""Score a filled labelling sheet against both judges.

    python experiments/score_labels.py paper/JUDGE-LABELS-TO-FILL.csv [second_person.csv]

Reads YES/NO from the last column, joins on id via results/judge-labelling-key.json,
and reports agreement and kappa for J1 and J2, overall and per arm; with two
sheets it also reports inter-rater kappa.
"""
import csv, json, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def read(path):
    out = {}
    for row in csv.DictReader(open(path, newline="")):
        v = (list(row.values())[-1] or "").strip().upper()
        if v in ("YES", "NO"): out[int(row["id"])] = v == "YES"
    return out

def kappa(pairs):
    n = len(pairs); a = sum(x == y for x, y in pairs) / n
    px = sum(x for x, _ in pairs) / n; py = sum(y for _, y in pairs) / n
    pe = px * py + (1 - px) * (1 - py)
    return a, (a - pe) / (1 - pe) if pe < 1 else float("nan")

def main():
    human = read(sys.argv[1]); key = {k["id"]: k for k in json.load(open(ROOT / "results" / "judge-labelling-key.json"))}
    verdicts = {}
    for run in sorted({k["run"] for k in key.values()}):
        for suffix, name in (("strict", "J1"), ("gemini", "J2")):
            f = ROOT / "results" / run / f"structure-judged-{suffix}.jsonl"
            if not f.exists(): continue
            for l in open(f):
                r = json.loads(l); verdicts[(run, r["task_id"], r["arm"], name)] = r.get("mechanism_judge")
    print(f"labelled: {len(human)} of {len(key)}")
    for name in ("J1", "J2"):
        pairs = []; per = collections.defaultdict(list)
        for i, h in human.items():
            k = key[i]; j = verdicts.get((k["run"], k["task_id"], k["arm"], name))
            if j is None: continue
            pairs.append((bool(j), h)); per[k["arm"]].append((bool(j), h))
        if not pairs: print(name, "no verdicts"); continue
        a, kp = kappa(pairs); print(f"{name}: agreement {a:.0%}, kappa {kp:.2f}, n={len(pairs)}, judge YES {sum(x for x,_ in pairs)}, human YES {sum(y for _,y in pairs)}")
        for arm in sorted(per):
            a2, k2 = kappa(per[arm]); print(f"   {arm:<14} agreement {a2:.0%}  n={len(per[arm])}")
    if len(sys.argv) > 2:
        other = read(sys.argv[2]); pairs = [(human[i], other[i]) for i in human if i in other]
        a, kp = kappa(pairs); print(f"inter-rater: agreement {a:.0%}, kappa {kp:.2f}, n={len(pairs)}")

if __name__ == "__main__":
    main()
