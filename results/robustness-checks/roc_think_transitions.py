"""Twin flag transitions in the reasoning-on run (results/v3-roc-deepseek-think-complete).

For each twin (is_defect = False) that has both the diff-only arm (1-diff) and the attributed
arm (5-attributed), compare the binary flag (`hit`) between the two arms: how many twins the
attributed caller cleared (flagged with the diff only, not flagged with the caller) and how many
it newly flagged. Same for defects. No API calls; reads the committed records only.
"""
import sys
ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from experiments.analyse_roc import load

rows = load(ROOT / "results" / "v3-roc-deepseek-think-complete")
flag = {}
for r in rows:
    if r["arm"] in ("1-diff", "5-attributed") and r.get("hit") is not None:
        flag.setdefault((r["task_id"], bool(r["is_defect"])), {})[r["arm"]] = bool(r["hit"])
for is_def, name in ((False, "twins"), (True, "defects")):
    pairs = [v for (t, d), v in flag.items() if d == is_def and len(v) == 2]
    a = sum(v["1-diff"] for v in pairs); b = sum(v["5-attributed"] for v in pairs)
    cleared = sum(v["1-diff"] and not v["5-attributed"] for v in pairs)
    new = sum(v["5-attributed"] and not v["1-diff"] for v in pairs)
    n = len(pairs)
    print(f"{name}: n={n}  flagged diff-only {a} ({100*a/n:.1f}%)  flagged attributed {b} ({100*b/n:.1f}%)  "
          f"flag -> no flag {cleared}  no flag -> flag {new}")
