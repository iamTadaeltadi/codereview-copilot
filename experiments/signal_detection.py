"""Signal detection on a structure run with twins: per arm, H = hit rate on defects,
F = flag rate on safe twins (any finding), d' = z(H) - z(F), c = -(z(H) + z(F)) / 2.

Usage: python experiments/signal_detection.py defects.jsonl twins.jsonl [more.jsonl ...]

Rows whose reply could not be parsed are dropped (correct is null), as in
analyse_structure. Rates of exactly 0 or 1 are moved by 1/(2n) before z. Intervals:
percentile bootstrap over repositories (the second field of the task id), 6,000
trials, seed 0, resampling defects and twins of a repository together; the paired
difference against the diff-only arm (1-diff) uses the same draws.
"""
import json, random, sys
from collections import defaultdict
from statistics import NormalDist

TRIALS, SEED, BASE = 6000, 0, "1-diff"
Z = NormalDist().inv_cdf


def load(paths):
    rows = defaultdict(lambda: defaultdict(list))  # arm -> repo -> [(is_defect, hit)]
    for p in paths:
        for line in open(p):
            if line.strip():
                r = json.loads(line)
                if r.get("correct") is None:
                    continue
                rows[r["arm"]][r["task_id"].split("::")[1]].append((bool(r["is_defect"]), bool(r["hit"])))
    return rows


def stats(items):
    d = [h for isd, h in items if isd]; t = [h for isd, h in items if not isd]
    if not d or not t:
        return None
    H = min(max(sum(d) / len(d), 1 / (2 * len(d))), 1 - 1 / (2 * len(d)))
    F = min(max(sum(t) / len(t), 1 / (2 * len(t))), 1 - 1 / (2 * len(t)))
    return H, F, Z(H) - Z(F), -(Z(H) + Z(F)) / 2


def main(*paths):
    rows = load(paths)
    arms = sorted(rows)
    repos = sorted(set.intersection(*[set(rows[a]) for a in arms]))
    rng = random.Random(SEED)
    draws = [[repos[rng.randrange(len(repos))] for _ in repos] for _ in range(TRIALS)]
    point, boots = {}, {}
    for a in arms:
        point[a] = stats([x for r in repos for x in rows[a][r]])
        boots[a] = [stats([x for r in pick for x in rows[a][r]]) for pick in draws]
    def ci(vals):
        v = sorted(x for x in vals if x is not None)
        return v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]
    out = [f"signal detection: {' '.join(paths)}",
           f"repositories: {len(repos)}; defects: {sum(sum(1 for isd, _ in rows[BASE][r] if isd) for r in repos)}; "
           f"twins: {sum(sum(1 for isd, _ in rows[BASE][r] if not isd) for r in repos)}; "
           f"bootstrap over repositories, {TRIALS} trials, seed {SEED}", "",
           f"  {'arm':<14}{'H':>7}{'F':>7}{'d-prime':>9}  95%                {'c':>7}  95%                "
           f"d'-d'(diff) 95%        c-c(diff) 95%"]
    for a in arms:
        H, F, dp, c = point[a]
        dlo, dhi = ci([b[2] for b in boots[a]]); clo, chi = ci([b[3] for b in boots[a]])
        dd = dp - point[BASE][2]; dc = c - point[BASE][3]
        ddlo, ddhi = ci([x[2] - y[2] for x, y in zip(boots[a], boots[BASE]) if x and y])
        dclo, dchi = ci([x[3] - y[3] for x, y in zip(boots[a], boots[BASE]) if x and y])
        out.append(f"  {a:<14}{H:>7.3f}{F:>7.3f}{dp:>9.2f}  [{dlo:+.2f}, {dhi:+.2f}]  {c:>7.2f}  [{clo:+.2f}, {chi:+.2f}]  "
                   f"{dd:+.2f} [{ddlo:+.2f}, {ddhi:+.2f}]  {dc:+.2f} [{dclo:+.2f}, {dchi:+.2f}]")
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
