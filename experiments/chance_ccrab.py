"""Chance baseline for a c-CRAB run: the same number of findings as the model, on
uniformly random new-file lines of the diff's hunks, scored by the same matcher.

Usage: python experiments/chance_ccrab.py results/ccrab-v2 [draws=500] [header] [conds=A,B,C,Cx,D]

For every (task, condition) with a raw record, k = the model's finding count. Each
draw places k findings on lines sampled uniformly (with replacement) from the
union of the diff's hunk ranges on the new-file side, then runs
experiments.matcher.match_review exactly as the run did. A defect's chance rate
is its hit frequency over the draws. Three scores: tolerance 5, exact line, and
top-1 (the model's first finding alone against one random line, tolerance 5).
Differences are model minus chance, paired by defect, percentile bootstrap over
repositories (6,000 trials, seed 0) and, beside it, over tasks.
"""
import json, random, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.benchmark import load_ccrab
from experiments.matcher import ReportedFinding, match_review
from experiments.run import DEFAULT_ARCHIVE, DEFAULT_DATA, changed_ranges

TRIALS, SEED, CONDS = 6000, 0, ["A", "B", "C", "Cx", "D"]
FILES = {"A": "main", "B": "main", "D": "main", "C": "C", "Cx": "Cx"}


def tasks_like_the_run(limit=400, max_diff=40000):
    tasks = load_ccrab(DEFAULT_DATA, testgen_archive=DEFAULT_ARCHIVE, confirmed_only=True,
                       supported_source_only=True)
    tasks = [t for t in tasks if len(t.diff) <= max_diff]
    return sorted(tasks, key=lambda t: t.task_id)[:limit]


def hunk_lines(diff):
    out = []
    for path, spans in changed_ranges(diff).items():
        for a, b in spans:
            out.extend((path, n) for n in range(a, b + 1))
    return out


def model_findings(results):
    """(task, cond) -> list of ReportedFinding, from the raw records."""
    out = {}
    for cond, name in FILES.items():
        if not Path(results, f"{name}-raw.jsonl").exists():
            continue
        for line in Path(results, f"{name}-raw.jsonl").open():
            if not line.strip():
                continue
            r = json.loads(line)
            if name == "main" and r["condition"] != cond:
                continue
            out[(r["task_id"], cond)] = [ReportedFinding(f["finding_id"], f["path"], f.get("line"), "")
                                         for f in r["findings"]]
    return out


def hits(task, cond, findings, tol):
    rep = match_review(task.task_id, cond, task.defects, findings, tol)
    return {o.defect_id: o.hit for o in rep.outcomes}


def bootstrap(diffs, group_of):
    groups = defaultdict(list)
    for k, d in diffs.items():
        groups[group_of(k)].append(d)
    names = sorted(groups); rng = random.Random(SEED); out = []
    for _ in range(TRIALS):
        pick = [names[rng.randrange(len(names))] for _ in names]
        vals = [d for g in pick for d in groups[g]]
        out.append(sum(vals) / len(vals))
    out.sort()
    return out[int(0.025 * TRIALS)], out[int(0.975 * TRIALS) - 1]


def main(results="results/ccrab-v2", draws=500, header=None, conds=None):
    draws = int(draws); conds = conds.split(",") if conds else CONDS
    tasks = {t.task_id: t for t in tasks_like_the_run()}
    found = model_findings(results)
    scores = {"tolerance 5": (5, False), "exact line": (0, False), "top-1, tolerance 5": (5, True)}
    model = {s: defaultdict(dict) for s in scores}   # score -> cond -> defect -> bool
    chance = {s: defaultdict(dict) for s in scores}  # score -> cond -> defect -> rate
    covered = total = 0
    for tid, task in tasks.items():
        lines = hunk_lines(task.diff)
        inside = {(d.path, d.line) for d in task.defects} & set(lines)
        covered += len(inside); total += len(task.defects)
        for cond in conds:
            if (tid, cond) not in found or not lines:
                continue
            fs = found[(tid, cond)]
            rng = random.Random(f"{SEED}:{tid}:{cond}")
            for s, (tol, top1) in scores.items():
                mf = fs[:1] if top1 else fs
                for did, h in hits(task, cond, mf, tol).items():
                    model[s][cond][(tid, did)] = h
                k = 1 if top1 else len(fs)
                acc = defaultdict(int)
                for _ in range(draws):
                    rf = [ReportedFinding(f"r{i}", *rng.choice(lines), "") for i in range(k)]
                    for did, h in hits(task, cond, rf, tol).items():
                        acc[(tid, did)] += h
                for key, n in acc.items():
                    chance[s][cond][key] = n / draws
    lines_out = [header or f"chance baseline for {results}: same finding count as the model, "
                           f"uniform over the diff's hunk lines, same matcher; {draws} draws per task and condition",
                 f"defects whose line lies inside a hunk of their file: {covered}/{total} "
                 f"({covered / total:.1%}); a finding outside the hunks can still hit within the tolerance", ""]
    for s in scores:
        keys = sorted(set.intersection(*[set(model[s][c]) for c in conds]))
        lines_out += [f"=== {s} ===  paired defects: {len(keys)}",
                      f"  {'cond':<5}{'model':>8}{'chance':>9}{'diff':>8}  repo-clustered 95%      task-clustered 95%"]
        for c in conds:
            m = sum(model[s][c][k] for k in keys) / len(keys)
            ch = sum(chance[s][c][k] for k in keys) / len(keys)
            d = {k: int(model[s][c][k]) - chance[s][c][k] for k in keys}
            lo, hi = bootstrap(d, lambda k: k[0].split("-")[0])
            tlo, thi = bootstrap(d, lambda k: k[0])
            verdict = "model above chance" if lo > 0 else ("model below chance" if hi < 0 else "spans zero")
            lines_out.append(f"  {c:<5}{m:>8.1%}{ch:>9.1%}{m - ch:>+8.1%}  [{lo:+.1%}, {hi:+.1%}]"
                             f"{'':8}[{tlo:+.1%}, {thi:+.1%}]  {verdict}")
        lines_out.append("")
    text = "\n".join(lines_out) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
