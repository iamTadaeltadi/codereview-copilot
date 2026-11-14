import sys, numpy as np
ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from pathlib import Path
from experiments.analyse_roc import load
R = ROOT / "results"
def auc(d, t):
    d = np.asarray(d)[:, None]; t = np.asarray(t)[None, :]
    return ((d > t) + 0.5*(d == t)).mean()
rng = np.random.default_rng(0)
for f in ["v3-roc-gpt4omini","v3-roc-gpt4omini-auth","v3-roc-deepseek-ctrl","v3-roc-deepseek-auth-ctrl","v3-roc-deepseek","v3-roc-deepseek-auth","v3-roc-deepseek-think-complete"]:
    rows = load(R/f)
    s = {}
    for r in rows:
        if r["arm"] in ("1-diff","5-attributed") and r.get("hunk_score") is not None:
            s.setdefault(r["task_id"], {})[r["arm"]] = (r["hunk_score"], bool(r["is_defect"]))
    items = [(v["1-diff"][0], v["5-attributed"][0], v["1-diff"][1]) for v in s.values() if len(v) == 2]
    a = np.array([x[0] for x in items], float); b = np.array([x[1] for x in items], float); isd = np.array([x[2] for x in items])
    obs = auc(b[isd], b[~isd]) - auc(a[isd], a[~isd])
    null = []
    for _ in range(4000):
        sw = rng.random(len(a)) < 0.5
        a2 = np.where(sw, b, a); b2 = np.where(sw, a, b)
        null.append(auc(b2[isd], b2[~isd]) - auc(a2[isd], a2[~isd]))
    null = np.array(null)
    p = (np.abs(null) >= abs(obs) - 1e-12).mean()
    # tie-free view: share of items with nonzero rating
    print(f"{f:<34} n={len(a)} dAUC {obs:+.3f}  item-level paired permutation p={p:.4f}")
