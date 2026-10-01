#!/usr/bin/env python3
"""Judge whether a finding states the specific mechanism, blind to arm.

    python experiments/judge_mechanism.py runs/<name>/structure.jsonl [--model deepseek/deepseek-v3.2]

The keyword rubric turned out to pass boilerplate. A diff-only reviewer writes
"may lead to unexpected behavior if the caller expects a None return value",
which contains the dependency token and a reference to the caller, and so
counts as naming the mechanism without having seen the caller. It also fails
genuine explanations phrased as "the calling code expects ... when the key is
not found", because `calling` is not `caller`.

This asks a third model, from a family used by neither reviewer, a single
question per message: does the finding state the same specific reason the
generator recorded, as opposed to a generic warning that callers might be
affected? The judge sees the changed line, the generator's reason, and the
message. It never sees the arm, the snippets or the metadata.

The verdict is validated against a hand-labelled sample before use; the
sample and its labels are released with the run.
"""
from __future__ import annotations

import argparse, json, os, sys, time
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "services", "graph")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.benchmark import load_crossfile
from experiments.llm import LLMError, client_from_env, load_env

PROMPT = """A code change and a review comment about it.

Changed line (before -> after):
{before}
->
{after}

The actual reason this change is a defect:
{why}

Review comment on that line:
{message}

Does the review comment name a CONCRETE fact about the calling code — the specific value, order, exception type or parameter the caller relies on — such that the comment could only have been written by someone who looked at the caller?

Answer NO if the comment only says the change "may lead to unexpected behavior", "may break callers", "may affect existing code" or similar, even if it mentions the changed value. Answer NO if it reports a different problem (formatting, syntax, documentation). Answer YES only if it states what the caller specifically expects or does.

Answer with exactly one word: YES or NO."""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--model", default="deepseek/deepseek-v3.2")
    ap.add_argument("--strict", action="store_true", help="(prompt is now strict by default; flag kept for file naming)")
    ap.add_argument("--benchmark", default=str(Path(_ROOT) / "data" / "crossfile-v2.jsonl"))
    a = ap.parse_args()

    tasks = {t.task_id: t for t in load_crossfile(a.benchmark)}
    rows = [json.loads(l) for l in open(a.path) if l.strip()]
    out_path = Path(a.path).with_name("structure-judged.jsonl")
    if a.strict:
        out_path = Path(a.path).with_name("structure-judged-strict.jsonl")
    done = {}
    if out_path.is_file():
        for l in open(out_path):
            if l.strip():
                r = json.loads(l); done[(r["task_id"], r["arm"], r.get("encoding"), r.get("model"))] = r.get("mechanism_judge")

    client = client_from_env(load_env())
    spent = 0.0; n_yes = n_judged = 0
    with open(out_path, "w") as h:
        for r in rows:
            key = (r["task_id"], r["arm"], r.get("encoding"), r.get("model"))
            t = tasks.get(r["task_id"])
            if key in done:
                r["mechanism_judge"] = done[key]
            elif t is None or not r.get("hit") or not r.get("message"):
                r["mechanism_judge"] = False if r.get("hit") else None
            else:
                before = t.diff.split("\n")
                bl = next((l[1:] for l in before if l.startswith("-") and not l.startswith("---") and
                           t.metadata.get("distractor_lines") is not None), "")
                prompt = PROMPT.format(before=_defect_line(t, "-"), after=_defect_line(t, "+"),
                                       why=t.problem_statement, message=r["message"][:600])
                try:
                    c = client.complete(model=a.model, messages=[{"role": "user", "content": prompt}],
                                        max_tokens=4, temperature=0)
                    spent += c.usage.cost_usd
                    r["mechanism_judge"] = (c.text or "").strip().upper().startswith("YES")
                except LLMError as e:
                    r["mechanism_judge"] = None
            if r["mechanism_judge"] is not None:
                n_judged += 1; n_yes += bool(r["mechanism_judge"])
            h.write(json.dumps(r) + "\n")
    print(f"{len(rows)} rows -> {out_path}   judged {n_judged}, YES {n_yes}   ${spent:.4f}")
    return 0


def _defect_line(task, sign):
    """The defect's own hunk line, located by the defect line number."""
    lines = task.diff.split("\n")
    target = f"@@ -{task.defects[0].line},1 +{task.defects[0].line},1 @@"
    for i, l in enumerate(lines):
        if l == target:
            for j in range(i + 1, min(i + 3, len(lines))):
                if lines[j].startswith(sign):
                    return lines[j][1:].strip()
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
