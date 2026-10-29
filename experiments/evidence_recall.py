"""Evidence recall: did the delivered context contain what the comment names?

Usage: python experiments/evidence_recall.py results/ccrab-final [A,B,C,Cx,D]

For every ground-truth defect, the names in its review comment are the file
paths it mentions (tokens ending in a source suffix) and the identifiers it
quotes (backticks, single or double quotes) or writes in snake_case or
CamelCase, at least 3 characters, not a Python keyword. A name is 'outside the
diff' when it does not occur in the diff text. Per condition, the share of
defects (and of tasks) whose context text contains at least one named thing,
and the same restricted to names outside the diff. Needs `context_text` in the
raw records (runs with --plain-context).
"""
import json, keyword, re, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.chance_ccrab import FILES, tasks_like_the_run

PATH = re.compile(r"[\w./-]+\.(?:py|js|ts|tsx|jsx|go|java|rb|rs|c|cc|cpp|h|hpp|cs)\b")
QUOTED = re.compile(r"`([^`\n]{3,80})`|'([^'\n]{3,80})'|\"([^\"\n]{3,80})\"")
SNAKE = re.compile(r"\b[A-Za-z]\w*_\w+\b")
CAMEL = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b")
URL = re.compile(r"https?://\S+")


def names_in(comment):
    text = URL.sub(" ", comment or "")
    paths = set(PATH.findall(text))
    idents = set()
    for m in QUOTED.findall(text):
        tok = next(t for t in m if t)
        if re.fullmatch(r"[A-Za-z_][\w.]*(\(\))?", tok):
            idents.add(tok.rstrip("()"))
    idents |= set(SNAKE.findall(text)) | set(CAMEL.findall(text))
    idents = {i for i in idents if len(i) >= 3 and not keyword.iskeyword(i)}
    return paths, idents


def main(results="results/ccrab-final", conds="A,B,C,Cx,D"):
    conds = conds.split(",")
    tasks = {t.task_id: t for t in tasks_like_the_run()}
    ctx = defaultdict(dict)
    for cond, name in FILES.items():
        f = Path(results, f"{name}-raw.jsonl")
        if cond not in conds or not f.exists():
            continue
        for line in f.open():
            if line.strip():
                r = json.loads(line)
                if name == "main" and r["condition"] != cond:
                    continue
                ctx[cond][r["task_id"]] = r.get("context_text") or ""
    out = [f"evidence recall, {results}: share of defects whose comment names a file or identifier that the delivered context contains", ""]
    out.append(f"  {'cond':<5}{'defects':>8}{'named':>7}{'recall':>8}{'outside-diff named':>20}{'recall':>8}{'tasks named':>13}{'task recall':>13}")
    for cond in conds:
        n_named = n_hit = n_out = n_out_hit = 0; t_named = set(); t_hit = set()
        for tid, task in tasks.items():
            if tid not in ctx[cond]:
                continue
            text = ctx[cond][tid]
            for d in task.defects:
                paths, idents = names_in(d.text)
                names = {p for p in paths} | idents
                if not names:
                    continue
                n_named += 1; t_named.add(tid)
                hit = any(n in text for n in names)
                n_hit += hit
                if hit: t_hit.add(tid)
                outside = {n for n in names if n not in task.diff}
                if outside:
                    n_out += 1; n_out_hit += any(n in text for n in outside)
        if n_named:
            out.append(f"  {cond:<5}{sum(len(t.defects) for tid, t in tasks.items() if tid in ctx[cond]):>8}{n_named:>7}{n_hit / n_named:>8.1%}"
                       f"{n_out:>20}{(n_out_hit / n_out if n_out else 0):>8.1%}{len(t_named):>13}{len(t_hit) / len(t_named):>13.1%}")
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main(*sys.argv[1:])
