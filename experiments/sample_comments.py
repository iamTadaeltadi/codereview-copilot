"""Draw a random sample of review comments from a c-CRAB run for hand labelling.

Usage: python experiments/sample_comments.py results/ccrab-v2 50 0 out.csv

Pools every finding in the run's raw records (all conditions), draws n with
random.Random(seed), and writes one row per finding: the task, condition, repo,
the comment's path and line, the comment, whether the line lies in a changed
hunk, the distance to the nearest ground-truth defect in that file (blank if
none), the hunk that contains the line (or the file's hunks if none does), the
full diff, and empty label and note columns.
"""
import csv, json, random, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.chance_ccrab import FILES, tasks_like_the_run
from experiments.matcher import paths_match
from experiments.run import changed_ranges

HUNK = re.compile(r"^@@ .*$", re.M)


def hunks_of(diff, path):
    """[(first, last, text)] of the new-file hunks of one file in the diff."""
    out = []
    for block in re.split(r"(?=^diff --git )", diff, flags=re.M):
        m = re.match(r"diff --git a/(\S+) b/(\S+)", block)
        if not m or not paths_match(m.group(2), path):
            continue
        starts = list(HUNK.finditer(block))
        for i, h in enumerate(starts):
            text = block[h.start(): starts[i + 1].start() if i + 1 < len(starts) else len(block)]
            mm = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", h.group(0))
            a = int(mm.group(1)); n = int(mm.group(2)) if mm.group(2) else 1
            out.append((a, max(a, a + n - 1), text))
    return out


def main(results="results/ccrab-v2", n=50, seed=0, out="results/ccrab-v2/hand-label-sample.csv"):
    n, seed = int(n), int(seed)
    tasks = {t.task_id: t for t in tasks_like_the_run()}
    pool = []
    for cond, name in FILES.items():
        for line in Path(results, f"{name}-raw.jsonl").open():
            if not line.strip():
                continue
            r = json.loads(line)
            if name == "main" and r["condition"] != cond:
                continue
            for f in r["findings"]:
                pool.append((r["task_id"], cond, f))
    pool.sort(key=lambda x: (x[0], x[1], x[2]["finding_id"]))
    sample = random.Random(seed).sample(pool, n)
    with open(out, "w", newline="") as h:
        w = csv.writer(h)
        w.writerow(["sample_id", "task_id", "condition", "repo", "path", "line", "comment", "line_in_hunk",
                    "nearest_defect_distance", "hunk", "diff", "label", "note"])
        for i, (tid, cond, f) in enumerate(sample, 1):
            t = tasks[tid]; path, ln = f["path"], f.get("line")
            ranges = [(a, b) for p, spans in changed_ranges(t.diff).items() if paths_match(p, path) for a, b in spans]
            in_hunk = ln is not None and any(a <= ln <= b for a, b in ranges)
            dists = [abs(ln - d.line) for d in t.defects if ln is not None and d.line is not None and paths_match(d.path, path)]
            hs = hunks_of(t.diff, path)
            hunk = next((txt for a, b, txt in hs if ln is not None and a <= ln <= b), "\n".join(txt for _, _, txt in hs))
            w.writerow([i, tid, cond, t.repo, path, ln, f.get("message", ""), in_hunk,
                        min(dists) if dists else "", hunk, t.diff, "", ""])
    print(f"pool {len(pool)} findings; wrote {n} rows to {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
