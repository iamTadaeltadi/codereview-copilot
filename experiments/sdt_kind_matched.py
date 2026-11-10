"""Kind-matched signal detection for the twin experiment (paper Table 2).

Compares default-flip defects with default-flip twins under the neutral prompt,
per arm: hit rate H on defects, flag rate F on twins, d' = z(H) - z(F),
c = -(z(H) + z(F)) / 2, with 1/(2n) clamping, and repository-bootstrap intervals
(6000 draws, seed 0) for each arm's change from the diff-only arm. Also prints
the mean change in d' over the six caller arms. Post hoc: the pre-registered
analysis (experiments/signal_detection.py) pools mutation kinds.

Usage: python experiments/sdt_kind_matched.py > results/twins-kind-matched/analysis.txt
"""
import collections, json, random
from pathlib import Path
from statistics import NormalDist

Z = NormalDist().inv_cdf
ROOT = Path(__file__).resolve().parent.parent / "results"
SETS = {
    "gpt-4o-mini": ([ROOT / "v3-neutral-gpt4omini/structure.jsonl"],
                    [ROOT / "v3twins-neutral-gpt4omini/structure.jsonl"]),
    "deepseek-v3.2": ([ROOT / f"v3-neutral-deepseek/structure-shard{i}.jsonl" for i in range(3)],
                      [ROOT / f"v3twins-neutral-deepseek/structure-shard{i}.jsonl" for i in range(3)]),
}
CALLER = ["2-evidence", "2b-snippets", "3-topology", "4-typed", "5-attributed", "6-corrupted"]
DRAWS = 6000


def load(paths, kind="default_flip"):
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in paths:
        for line in open(p):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("correct") is None or r["kind"] != kind:
                continue
            by[r["arm"]][r["task_id"].split("::")[1]].append((bool(r["is_defect"]), bool(r["hit"])))
    return by


def stats(items):
    d = [h for isd, h in items if isd]
    t = [h for isd, h in items if not isd]
    if not d or not t:
        return None
    H = min(max(sum(d) / len(d), 1 / (2 * len(d))), 1 - 1 / (2 * len(d)))
    F = min(max(sum(t) / len(t), 1 / (2 * len(t))), 1 - 1 / (2 * len(t)))
    return H, F, Z(H) - Z(F), -(Z(H) + Z(F)) / 2, len(d), len(t)


def ci(v):
    v = sorted(x for x in v if x is not None)
    return v[int(.025 * len(v))], v[int(.975 * len(v)) - 1]


for name, (defs, twins) in SETS.items():
    by = load(defs)
    for arm, reps in load(twins).items():
        for repo, xs in reps.items():
            by[arm][repo].extend(xs)
    arms = sorted(by)
    repos = sorted(set.intersection(*[set(by[a]) for a in arms]))
    rng = random.Random(0)
    draws = [[repos[rng.randrange(len(repos))] for _ in repos] for _ in range(DRAWS)]
    pt = {a: stats([x for r in repos for x in by[a][r]]) for a in arms}
    bs = {a: [stats([x for r in pk for x in by[a][r]]) for pk in draws] for a in arms}
    print(f"\n### {name}: default-flip defects vs default-flip twins, repositories {len(repos)}")
    print(f"{'arm':<14}{'nD':>5}{'nT':>5}{'H%':>7}{'F%':>7}{'d':>7}{'c':>7}   dd[95%]            dc[95%]")
    for a in arms:
        H, F, d, c, nd, nt = pt[a]
        dd = ci([x[2] - y[2] for x, y in zip(bs[a], bs["1-diff"]) if x and y])
        dc = ci([x[3] - y[3] for x, y in zip(bs[a], bs["1-diff"]) if x and y])
        print(f"{a:<14}{nd:>5}{nt:>5}{100*H:>7.1f}{100*F:>7.1f}{d:>7.2f}{c:>7.2f}   "
              f"{d - pt['1-diff'][2]:+.2f}[{dd[0]:+.2f},{dd[1]:+.2f}]  {c - pt['1-diff'][3]:+.2f}[{dc[0]:+.2f},{dc[1]:+.2f}]")
    m = sum(pt[a][2] for a in CALLER) / len(CALLER) - pt["1-diff"][2]
    mb = [sum(bs[a][i][2] for a in CALLER) / len(CALLER) - bs["1-diff"][i][2] for i in range(DRAWS)]
    lo, hi = ci(mb)
    print(f"mean change in d' over the six caller arms: {m:+.2f} [{lo:+.2f}, {hi:+.2f}]")
