import sys, random, json, collections
ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
import numpy as np
from pathlib import Path
from experiments.analyse_roc import load, repo, auc_from_hist
R = ROOT / "results"
def q(v, lo, hi):
    v = np.sort(v[~np.isnan(v)]); return v[int(lo*len(v))], v[int(hi*len(v))-1]
def boot(folder, arms=("1-diff","5-attributed"), score="hunk_score", rows=None, extra=None):
    rows = rows if rows is not None else load(R/folder)
    rows = [r for r in rows if r["arm"] in arms]
    scored = [r for r in rows if r.get(score) is not None]
    repos = sorted(set.intersection(*[{repo(r) for r in scored if r["arm"] == a} for a in arms]))
    idx = {g:i for i,g in enumerate(repos)}
    rng = random.Random(0)
    draws = [[repos[rng.randrange(len(repos))] for _ in repos] for _ in range(6000)]
    mult = np.zeros((6000, len(repos)))
    for t, pk in enumerate(draws):
        for g in pk: mult[t, idx[g]] += 1
    out = {}
    for a in arms:
        hd, ht = np.zeros((len(repos),101)), np.zeros((len(repos),101))
        for r in scored:
            if r["arm"] == a and repo(r) in idx:
                (hd if r["is_defect"] else ht)[idx[repo(r)], int(r[score])] += 1
        out[a] = (float(auc_from_hist(hd.sum(0), ht.sum(0))), auc_from_hist(mult@hd, mult@ht), int(hd.sum()), int(ht.sum()))
    return out
if __name__ == "__main__":
    runs = ["v3-roc-gpt4omini","v3-roc-gpt4omini-auth","v3-roc-deepseek-ctrl","v3-roc-deepseek-auth-ctrl","v3-roc-deepseek","v3-roc-deepseek-auth","v3-roc-deepseek-think-complete"]
    from statistics import NormalDist
    for f in runs:
        o = boot(f)
        d = o["5-attributed"][1]-o["1-diff"][1]; p = o["5-attributed"][0]-o["1-diff"][0]
        # one-sided bootstrap p for gain (share of draws <= 0)
        pboot = 2*min((d<=0).mean(), (d>=0).mean())
        l95 = q(d,.025,.975); l4 = q(d,.0125/2*2/2, 1-.0125/2*2/2)
        print(f"{f:<34} dAUC {p:+.3f} 95% [{l95[0]:+.3f},{l95[1]:+.3f}]  98.75% [{q(d,.00625,.99375)[0]:+.3f},{q(d,.00625,.99375)[1]:+.3f}]  99.29% [{q(d,.05/7/2,1-.05/7/2)[0]:+.3f},{q(d,.05/7/2,1-.05/7/2)[1]:+.3f}]  2-sided boot p~{pboot:.4f}")
