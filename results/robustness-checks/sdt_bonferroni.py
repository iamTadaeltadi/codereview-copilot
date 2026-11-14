import sys, json, random, collections
ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from pathlib import Path
from experiments.signal_detection import stats, load as load_pooled
R = ROOT / "results"
def q(v, lo, hi):
    v = sorted(x for x in v if x is not None)
    return v[int(lo*len(v))], v[int(hi*len(v))-1]
alpha = 0.05/8
def run(rows, label):
    arms = sorted(rows)
    repos = sorted(set.intersection(*[set(rows[a]) for a in arms]))
    rng = random.Random(0)
    draws = [[repos[rng.randrange(len(repos))] for _ in repos] for _ in range(6000)]
    pt = {a: stats([x for r in repos for x in rows[a][r]]) for a in arms}
    bs = {a: [stats([x for r in pk for x in rows[a][r]]) for pk in draws] for a in arms}
    print("##", label, "repos", len(repos))
    for a in arms:
        if a == "1-diff": continue
        dc = [x[3]-y[3] for x, y in zip(bs[a], bs["1-diff"]) if x and y]
        dd = [x[2]-y[2] for x, y in zip(bs[a], bs["1-diff"]) if x and y]
        lo, hi = q(dc, alpha/2, 1-alpha/2); l2, h2 = q(dd, alpha/2, 1-alpha/2)
        print(f"  {a:<13} dc {pt[a][3]-pt['1-diff'][3]:+.2f} bonf99.375 [{lo:+.2f},{hi:+.2f}] {'EXCL' if hi<0 or lo>0 else 'incl'}   dd {pt[a][2]-pt['1-diff'][2]:+.2f} [{l2:+.2f},{h2:+.2f}]")
# pooled (pre-registered)
g = load_pooled([R/"v3-neutral-gpt4omini/structure.jsonl", R/"v3twins-neutral-gpt4omini/structure.jsonl"])
run(g, "gpt-4o-mini pooled")
d = load_pooled([R/f"v3-neutral-deepseek/structure-shard{i}.jsonl" for i in range(3)] + [R/f"v3twins-neutral-deepseek/structure-shard{i}.jsonl" for i in range(3)])
run(d, "deepseek pooled")
# kind matched
def load_km(paths):
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in paths:
        for line in open(p):
            if not line.strip(): continue
            r = json.loads(line)
            if r.get("correct") is None or r["kind"] != "default_flip": continue
            by[r["arm"]][r["task_id"].split("::")[1]].append((bool(r["is_defect"]), bool(r["hit"])))
    return by
run(load_km([R/"v3-neutral-gpt4omini/structure.jsonl", R/"v3twins-neutral-gpt4omini/structure.jsonl"]), "gpt-4o-mini kind-matched")
run(load_km([R/f"v3-neutral-deepseek/structure-shard{i}.jsonl" for i in range(3)] + [R/f"v3twins-neutral-deepseek/structure-shard{i}.jsonl" for i in range(3)]), "deepseek kind-matched")
