"""How accurately does the model report the line of the code it talks about?

Usage: python experiments/line_accuracy.py results/ccrab-v2 [A,B,C,Cx,D]

For every finding whose message quotes a token in backticks, single or double
quotes, find the
new-file lines of that finding's file in the diff (context and added lines of
its hunks) that contain the token; the finding is 'located' when at least one
such line exists. Distance = the smallest |reported line - token line|. Reports
the share at distance 0, within 5, and beyond 5, per condition and pooled.
Tokens shorter than 3 characters are ignored.
"""
import json, re, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.chance_ccrab import FILES, tasks_like_the_run
from experiments.matcher import paths_match

TOKEN = re.compile(r"`([^`\n]{3,80})`|'([^'\n]{3,80})'|\"([^\"\n]{3,80})\"")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def new_lines(diff):
    """{path: [(new_line_number, text)]} for context and added lines."""
    out = defaultdict(list); path = None; n = None
    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(\S+) b/(\S+)", line); path = m.group(2) if m else None; n = None
        elif line.startswith("@@"):
            m = HUNK.match(line); n = int(m.group(1)) if m else None
        elif n is not None and path:
            if line.startswith("+"):
                out[path].append((n, line[1:])); n += 1
            elif line.startswith("-"):
                pass
            elif not line.startswith("\\"):
                out[path].append((n, line[1:] if line.startswith(" ") else line)); n += 1
    return out


def main(results="results/ccrab-v2", conds="A,B,C,Cx,D"):
    conds = conds.split(",")
    tasks = {t.task_id: t for t in tasks_like_the_run()}
    lines_by_task = {tid: new_lines(t.diff) for tid, t in tasks.items()}
    dist = defaultdict(list); quoted = defaultdict(int); total = defaultdict(int)
    for cond in conds:
        name = FILES[cond]
        for line in Path(results, f"{name}-raw.jsonl").open():
            if not line.strip():
                continue
            r = json.loads(line)
            if name == "main" and r["condition"] != cond:
                continue
            nl = lines_by_task.get(r["task_id"], {})
            for f in r["findings"]:
                total[cond] += 1
                toks = [t for m in TOKEN.findall(f.get("message", "")) for t in m if t]
                if not toks or f.get("line") is None:
                    continue
                quoted[cond] += 1
                cand = [n for p, ls in nl.items() if paths_match(p, f["path"]) for n, t in ls if any(tok in t for tok in toks)]
                if cand:
                    dist[cond].append(min(abs(int(f["line"]) - n) for n in cand))
    out = [f"line accuracy of quoted tokens, {results}", "",
           f"  {'cond':<5}{'findings':>9}{'quoting':>9}{'located':>9}{'exact':>8}{'<=5':>8}{'>5':>8}{'median':>8}"]
    allc = []
    for cond in conds + ["all"]:
        d = dist[cond] if cond != "all" else allc
        if cond != "all":
            allc += dist[cond]
        if not d:
            continue
        d_sorted = sorted(d); n = len(d)
        out.append(f"  {cond:<5}{(total[cond] if cond != 'all' else sum(total.values())):>9}"
                   f"{(quoted[cond] if cond != 'all' else sum(quoted.values())):>9}{n:>9}"
                   f"{sum(x == 0 for x in d) / n:>8.1%}{sum(x <= 5 for x in d) / n:>8.1%}{sum(x > 5 for x in d) / n:>8.1%}"
                   f"{d_sorted[n // 2]:>8}")
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
