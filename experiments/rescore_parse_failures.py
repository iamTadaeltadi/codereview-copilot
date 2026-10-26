"""Re-score frozen structure runs so that an unparseable reply is not an answer.

    python experiments/rescore_parse_failures.py results/v2twins-tag-deepseek

Writes <run>/structure-rescored.jsonl with `correct` and `correct_precise` set
to null where `parse_failed` is true, and prints how many rows changed. The
original file is left as the record of what was scored at the time.
"""
import json, sys
from pathlib import Path

for run in sys.argv[1:]:
    src = Path(run) / "structure.jsonl"
    dst = Path(run) / "structure-rescored.jsonl"
    changed = 0
    with src.open() as f, dst.open("w") as g:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("parse_failed"):
                if r.get("correct") is not None or r.get("correct_precise") is not None:
                    changed += 1
                r["correct"] = None; r["correct_precise"] = None
            g.write(json.dumps(r) + "\n")
    print(f"{run}: {changed} rows rescored -> {dst}")
