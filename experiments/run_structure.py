#!/usr/bin/env python3
"""Structure or content: does representing relationships help, given the code?

    python experiments/run_structure.py --limit 60
    python experiments/run_structure.py --limit 60 --encoding tag

Every arm receives the same diff. Arms 2-6 receive the same snippets, in the
same canonical order, with identical formatting; only the metadata block
differs. The primary comparison is arm 3 against arm 2 — topology against a
density-matched control carrying nothing true — and it is pre-registered as
such in paper/PLAN.md before any result is seen.

A manipulation check runs alongside. If arm 3 matches arm 2 there are two
explanations and they are not the same: structure carries no value, or the
serialisation failed to communicate structure. Asking the model to read the
relation back distinguishes them, and without it a null is uninterpretable.
"""

from __future__ import annotations

import argparse, json, os, re, sys, time
from dataclasses import asdict
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "services", "graph")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.benchmark import load_crossfile
from experiments.crossfile_score import score_review
from experiments.evidence import (ARM_DIFF_ONLY, ARM_HEADER, ARM_RANDOM, ARMS, EVIDENCE_ARMS,
                                  FLAT, evidence_for, metadata_block, random_evidence,
                                  sources_for)
from experiments.llm import LLMError, client_from_env, load_env
from experiments.matcher import ReportedFinding
from experiments.review import OUTPUT_CONTRACT, SYSTEM_PROMPT, parse_findings

METADATA_HEADER = "Dependency information for the code above:"
METADATA_NOTE = ("Each line states a relationship between two of the snippets above. "
                 "A snippet is identified as file-stem:line, where line is inside the "
                 "snippet's range.")

# Mechanism scoring. A finding on the right line for the wrong reason — "prefer
# f-strings" on the mutated line — counted as a hit in the first version, and
# the message was never read. Each kind now has a rubric: the message must
# name the thing the caller depends on, and must refer to the caller. It is a
# keyword test, mechanical and auditable, and it is stated as such.
RUBRIC = {
    "exception_type": lambda arg: [re.escape(arg.lower()), r"caller|catch|except|handl"],
    "none_sentinel": lambda arg: [r"\bnone\b", r"caller|check|guard|sentinel|is none|compar"],
    "default_flip": lambda arg: [re.escape(arg.lower()), r"caller|default|omit|pass|rel(y|ies)|without"],
    "tuple_order": lambda arg: [r"order|unpack|tuple|swap|position", r"caller|unpack|destructur|assign"],
    "empty_to_none": lambda arg: [r"\bnone\b", r"iterat|len\(|loop|caller|empty|sequence"],
}


def mechanism_correct(kind: str, argument: str, messages) -> bool | None:
    rules = RUBRIC.get(kind)
    if rules is None or not messages:
        return None
    text = " ".join(messages).lower()
    return all(re.search(pat, text) for pat in rules(argument or ""))



def build_prompt(task, evidence, arm, encoding, seed):
    parts = [f"Repository: {task.repo}", "", "Pull request diff:",
             "```diff", task.diff, "```"]
    if arm not in (ARM_DIFF_ONLY, ARM_HEADER) and evidence is not None:
        parts += ["", "Related code from the repository:", "```python",
                  evidence.rendered(), "```"]
    if arm != ARM_DIFF_ONLY and evidence is not None:
        block = metadata_block(evidence, arm, encoding, seed)
        if block:
            # Arm 8 carries the header and a scrambled block with no snippets,
            # so that "evidence vs diff only" can be separated from "the
            # presence of a dependency section vs none".
            parts += ["", METADATA_HEADER, METADATA_NOTE, block]
    parts += ["", OUTPUT_CONTRACT]
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(parts)}]


def manipulation_check(client, model, evidence, arm, encoding, seed):
    """Can the model read the relation back out of the serialisation?

    A null in the structure comparison means nothing if the answer here is no.
    """
    block = metadata_block(evidence, arm, encoding, seed)
    if not block:
        return None
    relation = evidence.relations[0]
    messages = [
        {"role": "system", "content": "Answer with a single identifier and nothing else."},
        {"role": "user", "content":
         f"{METADATA_HEADER}\n{block}\n\nAccording to that dependency information, "
         f"which identifier does {relation.source} depend on? Reply with the identifier only."},
    ]
    try:
        c = client.complete(model=model, messages=messages, max_tokens=48, temperature=0)
    except LLMError:
        return None
    return {"answer": (c.text or "").strip(), "cost": c.usage.cost_usd}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--model", default="openai/gpt-4o-mini")
    ap.add_argument("--encoding", default=FLAT)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--name", default="structure")
    ap.add_argument("--check-every", type=int, default=8)
    ap.add_argument("--hide-evidence", action="store_true",
                    help="window the caller above the evidence line so the call is "
                         "visible and the relation is not; only exception and None kinds")
    ap.add_argument("--benchmark", default=str(Path(_ROOT) / "data" / "crossfile-v2.jsonl"))
    a = ap.parse_args()

    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    tasks = load_crossfile(a.benchmark)[: a.limit]
    env = load_env(); client = client_from_env(env); token = env.get("GITHUB_TOKEN", "")

    out = Path(_ROOT) / "runs" / a.name; out.mkdir(parents=True, exist_ok=True)
    path = out / "structure.jsonl"; checks = out / "manipulation.jsonl"
    done = {(json.loads(l)["task_id"], json.loads(l)["arm"])
            for l in path.read_text().splitlines() if l.strip()} if path.is_file() else set()
    if done:
        print(f"resuming: {len(done)} already recorded")

    print(f"model    : {a.model}\nencoding : {a.encoding}\narms     : {arms}\ntasks    : {len(tasks)}\n")
    spent = 0.0
    for i, task in enumerate(tasks, 1):
        if all((task.task_id, arm) in done for arm in arms):
            continue
        try:
            src = sources_for(task, token=token)
            ev = evidence_for(task, src, hide_evidence=a.hide_evidence)
        except Exception as e:
            print(f"  [{i}] SKIP fetch: {e}"); continue
        if ev is None or len(ev.snippets) < 3:
            print(f"  [{i}] SKIP no evidence set"); continue

        if i % a.check_every == 1:
            for arm in (x for x in arms if x in EVIDENCE_ARMS):
                r = manipulation_check(client, a.model, ev, arm, a.encoding, task.task_id)
                if r:
                    spent += r["cost"]
                    with checks.open("a") as h:
                        h.write(json.dumps({"task_id": task.task_id, "arm": arm,
                                            "expected": ev.relations[0].target,
                                            **r}) + "\n")

        decoy_ev = random_evidence(task, src, ev, task.task_id)

        for arm in arms:
            if (task.task_id, arm) in done:
                continue
            t0 = time.time()
            # Arm 7 varies the evidence itself; every other arm varies only what
            # is said about it.
            shown = decoy_ev if arm == ARM_RANDOM else ev
            messages = build_prompt(task, shown, arm, a.encoding, task.task_id)
            try:
                c = client.complete(model=a.model, messages=messages,
                                    max_tokens=2048, temperature=0.1)
            except LLMError as e:
                print(f"  [{i}] {arm} ERROR {e}"); continue
            findings, failed = parse_findings(c.text, task.task_id, arm)
            reported = [ReportedFinding(f.finding_id, f.path, f.line, f.message) for f in findings]
            sc = score_review(task, arm, reported, tolerance=0)
            on_defect = [f.message for f in findings if f.line == task.defects[0].line]
            is_defect = bool(task.metadata.get("is_defect", True))
            correct = sc.hit if is_defect else not sc.hit
            correct_precise = sc.precise if is_defect else (not sc.hit and sc.flagged_distractors == 0)
            mech = mechanism_correct(task.metadata.get("kind", ""), task.metadata.get("argument", ""),
                                     on_defect) if sc.hit else (False if findings else None)
            spent += c.usage.cost_usd
            with path.open("a") as h:
                h.write(json.dumps({
                    "task_id": task.task_id, "arm": arm, "encoding": a.encoding,
                    "model": a.model, "kind": task.metadata.get("kind"),
                    "prompt_chars": len(messages[1]["content"]),
                    "hit": sc.hit, "precise": sc.precise,
                    "flagged_distractors": sc.flagged_distractors,
                    "findings": len(findings), "parse_failed": failed,
                    "mechanism": mech, "message": " | ".join(on_defect)[:600],
                    "is_defect": is_defect, "correct": correct, "correct_precise": correct_precise,
                    "finish_reason": getattr(c, "finish_reason", None),
                    "hide_evidence": a.hide_evidence, "benchmark": os.path.basename(a.benchmark),
                    "usage": c.usage.as_dict(),
                }) + "\n")
            print(f"  [{i}/{len(tasks)}] {arm:<14} hit={'Y' if sc.hit else 'n'} "
                  f"exact={'Y' if sc.precise else 'n'} mech={'Y' if mech else ('n' if mech is False else '-')} "
                  f"chars={len(messages[1]['content']):>5} "
                  f"${c.usage.cost_usd:.5f} {time.time()-t0:.1f}s")

    print(f"\ntotal cost: ${spent:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
