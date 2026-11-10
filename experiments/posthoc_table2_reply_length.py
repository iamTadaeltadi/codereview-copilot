#!/usr/bin/env python3
"""Post hoc, descriptive only (paper/PREREG-F.md, Amendment 3): Table 2's deepseek records by reply length.

    python3 experiments/posthoc_table2_reply_length.py > results/twins-kind-matched/posthoc-reply-length.txt

The same records and filters as experiments/sdt_kind_matched.py for deepseek-v3.2 (defect and twin
shards 0-2, default flips, parsed replies, repositories present in every arm). A record is "long"
when its call billed more than 1,500 output tokens (hidden reasoning), else "short"; the split is
per record, so an item can be long in one arm and short in another. Per arm: the share of long
records among defects and among twins, then n, H, F, d' and c for all records, long and short
(1/(2n) clamping as in sdt_kind_matched.py). No intervals, no test.
"""
import collections
import json
from pathlib import Path
from statistics import NormalDist

Z = NormalDist().inv_cdf
ROOT = Path(__file__).resolve().parent.parent / "results"
DEFS = [ROOT / f"v3-neutral-deepseek/structure-shard{i}.jsonl" for i in range(3)]
TWINS = [ROOT / f"v3twins-neutral-deepseek/structure-shard{i}.jsonl" for i in range(3)]
LONG = 1500


def load(paths, kind="default_flip"):
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in paths:
        for line in open(p):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("correct") is None or r["kind"] != kind:
                continue
            by[r["arm"]][r["task_id"].split("::")[1]].append(
                (bool(r["is_defect"]), bool(r["hit"]), (r.get("usage") or {}).get("output_tokens") or 0))
    return by


def stats(items):
    d = [h for isd, h, _ in items if isd]
    t = [h for isd, h, _ in items if not isd]
    if not d or not t:
        return len(d), len(t), None
    H = min(max(sum(d) / len(d), 1 / (2 * len(d))), 1 - 1 / (2 * len(d)))
    F = min(max(sum(t) / len(t), 1 / (2 * len(t))), 1 - 1 / (2 * len(t)))
    return len(d), len(t), (H, F, Z(H) - Z(F), -(Z(H) + Z(F)) / 2)


by = load(DEFS)
for arm, reps in load(TWINS).items():
    for repo, xs in reps.items():
        by[arm][repo].extend(xs)
arms = sorted(by)
repos = sorted(set.intersection(*[set(by[a]) for a in arms]))
rows = {a: [x for r in repos for x in by[a][r]] for a in arms}

print("POST HOC, DESCRIPTIVE (paper/PREREG-F.md, Amendment 3). Table 2 deepseek-v3.2 records "
      "(default-flip defects vs twins, neutral prompt),")
print(f"split by billed output tokens per call: long > {LONG}, short <= {LONG}. Repositories {len(repos)}. "
      "No intervals.\n")
print("Share of long records per arm")
print(f"  {'arm':<14}{'defects long':>16}{'twins long':>16}{'all long':>14}")
tot = [0, 0, 0, 0]
for a in arms:
    d = [x for x in rows[a] if x[0]]
    t = [x for x in rows[a] if not x[0]]
    dl = sum(x[2] > LONG for x in d)
    tl = sum(x[2] > LONG for x in t)
    tot = [tot[0] + dl, tot[1] + len(d), tot[2] + tl, tot[3] + len(t)]
    print(f"  {a:<14}{dl:>5}/{len(d):<3} {100 * dl / len(d):5.1f}%{tl:>6}/{len(t):<3} {100 * tl / len(t):5.1f}%"
          f"{(dl + tl):>5}/{len(d) + len(t):<3} {100 * (dl + tl) / (len(d) + len(t)):5.1f}%")
print(f"  {'all arms':<14}{tot[0]:>5}/{tot[1]:<3} {100 * tot[0] / tot[1]:5.1f}%{tot[2]:>6}/{tot[3]:<3} "
      f"{100 * tot[2] / tot[3]:5.1f}%{tot[0] + tot[2]:>5}/{tot[1] + tot[3]:<4}{100 * (tot[0] + tot[2]) / (tot[1] + tot[3]):5.1f}%")

print("\nSignal detection per arm and split")
print(f"  {'arm':<14}{'split':<7}{'nD':>5}{'nT':>5}{'H%':>7}{'F%':>7}{'d':>7}{'c':>7}")
for a in arms:
    for split, keep in (("all", lambda x: True), ("long", lambda x: x[2] > LONG), ("short", lambda x: x[2] <= LONG)):
        nd, nt, s = stats([x for x in rows[a] if keep(x)])
        if s is None:
            print(f"  {a:<14}{split:<7}{nd:>5}{nt:>5}{'-':>7}{'-':>7}{'-':>7}{'-':>7}")
        else:
            H, F, dp, c = s
            print(f"  {a:<14}{split:<7}{nd:>5}{nt:>5}{100 * H:>7.1f}{100 * F:>7.1f}{dp:>7.2f}{c:>7.2f}")
