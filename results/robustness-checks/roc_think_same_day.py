import sys, time, collections
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from roc_multiplicity import boot, q, R
from experiments.analyse_roc import load
rows = load(R/"v3-roc-deepseek-think-complete")
import os
UTC_PLUS_3 = 3 * 3600  # UTC+3: the clock of the machine that ran the calls
day = {}
for r in rows:
    if r["arm"] in ("1-diff","5-attributed"):
        day.setdefault(r["task_id"], set()).add(time.strftime("%a", time.gmtime(r["called_at"] + UTC_PLUS_3)))
cnt = collections.Counter(tuple(sorted(v)) for v in day.values()); print("item day pattern (diff+attr):", cnt)
wed = {t for t,v in day.items() if v == {"Wed"}}; tue = {t for t,v in day.items() if v == {"Tue"}}
for name, s in (("Tue items", tue), ("Wed items", wed)):
    sub = [r for r in rows if r["task_id"] in s]
    nd = sum(1 for r in sub if r["arm"]=="1-diff" and r["is_defect"]); nt = sum(1 for r in sub if r["arm"]=="1-diff" and not r["is_defect"])
    print(f"## {name}: defects {nd} twins {nt}")
    arms = ("1-diff","7-random","5-attributed")
    o = boot(None, arms=arms, rows=sub)
    for a in arms: print(f"   {a:<13} AUC {o[a][0]:.3f}")
    for x,y in (("5-attributed","1-diff"),("5-attributed","7-random"),("7-random","1-diff")):
        d = o[x][1]-o[y][1]; lo,hi = q(d,.025,.975)
        print(f"   {x}-{y}: {o[x][0]-o[y][0]:+.3f} [{lo:+.3f},{hi:+.3f}]")
    # binary F
    for a in arms:
        tw = [r for r in sub if r["arm"]==a and not r["is_defect"] and r.get("correct") is not None]
        df = [r for r in sub if r["arm"]==a and r["is_defect"] and r.get("correct") is not None]
        print(f"   {a:<13} H {100*sum(r['hit'] for r in df)/len(df):.1f}  F {100*sum(r['hit'] for r in tw)/len(tw):.1f}")
