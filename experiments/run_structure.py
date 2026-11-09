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
                                  sources_for, with_noise)
from experiments.llm import LLMError, client_from_env, load_env
from experiments.matcher import ReportedFinding
from experiments.review import OUTPUT_CONTRACT, SYSTEM_PROMPT, _extract_json, parse_findings

METADATA_HEADER = "Dependency information for the code above:"
METADATA_NOTE = ("Each line states a relationship between two of the snippets above. "
                 "A snippet is identified as file-stem.function, the function that "
                 "encloses it.")

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



NEUTRAL_SYSTEM_PROMPT = SYSTEM_PROMPT.replace(
    "This diff has already been reviewed by humans, and they found real problems "
    "in it. Assume there is something to find and look carefully. ",
    "The change may or may not contain a defect. If it is compatible with the "
    "code shown, say so by returning an empty list. ")
NEUTRAL_OUTPUT_CONTRACT = OUTPUT_CONTRACT.replace(
    "Report your best candidates even when you are not\n"
    "certain — a plausible defect that turns out to be wrong is more useful here than\n"
    "silence. Return an empty list only if you genuinely cannot identify anything.",
    "Report a finding only when you can say what breaks and where. Return an empty\n"
    "list when nothing is wrong; an empty list is a correct answer.")
assert NEUTRAL_SYSTEM_PROMPT != SYSTEM_PROMPT and NEUTRAL_OUTPUT_CONTRACT != OUTPUT_CONTRACT

# paper/PREREG-F.md: graded confidence per finding, for an ROC per arm. The same two changes to the
# output contract in every arm; off by default, so earlier runs are reproduced unchanged.
CONFIDENCE_SHAPE = ('"message": "what is wrong"}', '"message": "what is wrong", "confidence": 70}')
CONFIDENCE_NOTE = ('"confidence" is an integer from 0 to 100: how likely you think it is that the '
                   'finding is a real defect (0 = almost certainly not, 100 = certain).')


def with_confidence(contract: str) -> str:
    out = contract.replace(*CONFIDENCE_SHAPE).replace(
        "Never wrap the JSON in prose.", CONFIDENCE_NOTE + "\nNever wrap the JSON in prose.")
    assert out.count('"confidence": 70') == 1 and CONFIDENCE_NOTE in out, "contract changed shape"
    return out


CONFIDENCE_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*%?\s*$")


def parse_confidence(value):
    """An integer 0-100, or None. Numbers and numeric strings ("80", "80%") are accepted and
    rounded; anything else, or a value outside 0-100, is missing."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str) and CONFIDENCE_NUMBER.match(value):
        number = float(CONFIDENCE_NUMBER.match(value).group(1))
    else:
        return None
    return int(round(number)) if 0 <= number <= 100 else None


def finding_confidences(text: str):
    """Confidence per finding, in parse_findings' order (dict items of the findings list)."""
    payload = _extract_json(text)
    raw = payload.get("findings") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return []
    return [parse_confidence(item.get("confidence")) for item in raw if isinstance(item, dict)]


def score_items(task, arm, findings, confidences):
    """Per finding: line, hit on the mutated line (the existing matcher, tolerance 0) and
    confidence. Item score: the highest confidence among hits, 0 with no hit; None when a hit
    has no valid confidence (counted as confidence missing, never scored as 0)."""
    rows = []
    for f, conf in zip(findings, confidences):
        hit = score_review(task, arm, [ReportedFinding(f.finding_id, f.path, f.line, f.message)],
                           tolerance=0).hit
        rows.append({"line": f.line, "hit": hit, "confidence": conf})
    hits = [r["confidence"] for r in rows if r["hit"]]
    if any(c is None for c in hits):
        return rows, None, True
    return rows, (max(hits) if hits else 0), False


AUTHORITATIVE = ("The related code shown below is every place in the repository that uses "
                 "the changed function. Judge the change against that code only: if it is "
                 "compatible with every use shown, it is not a defect.")


def build_prompt(task, evidence, arm, encoding, seed, authoritative: bool = False,
                 neutral: bool = False, confidence: bool = False):
    parts = [f"Repository: {task.repo}", "", "Pull request diff:",
             "```diff", task.diff, "```"]
    # Without this, "safe for the shown caller" is not "safe", and a reviewer
    # that flags every exception-type change is being prudent rather than
    # wrong. With it, the shown callers are the whole truth and the twin
    # discrimination is well-posed. The instruction is identical across arms.
    if authoritative and arm != ARM_DIFF_ONLY and evidence is not None:
        parts += ["", AUTHORITATIVE]
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
    contract = NEUTRAL_OUTPUT_CONTRACT if neutral else OUTPUT_CONTRACT
    parts += ["", with_confidence(contract) if confidence else contract]
    return [{"role": "system", "content": NEUTRAL_SYSTEM_PROMPT if neutral else SYSTEM_PROMPT},
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
    ap.add_argument("--neutral-prompt", action="store_true",
                    help="drop the 'assume there is something to find' instruction and tell the "
                         "model an empty list is a correct answer; identical across arms")
    ap.add_argument("--authoritative", action="store_true",
                    help="tell the model the shown related code is every use of the changed function")
    ap.add_argument("--noise", type=int, default=0,
                    help="add this many unrelated snippets to the evidence set, identical across arms")
    ap.add_argument("--hide-evidence", action="store_true",
                    help="window the caller above the evidence line so the call is "
                         "visible and the relation is not; only exception and None kinds")
    ap.add_argument("--benchmark", default=str(Path(_ROOT) / "data" / "crossfile-v2.jsonl"))
    ap.add_argument("--confidence", action="store_true",
                    help="ask for an integer confidence 0-100 per finding (paper/PREREG-F.md) and "
                         "record it per finding with the item score; identical across arms")
    ap.add_argument("--kinds", default="",
                    help="comma-separated defect kinds to keep (e.g. default_flip); default all")
    a = ap.parse_args()

    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    tasks = load_crossfile(a.benchmark)[: a.limit]
    kinds = {k.strip() for k in a.kinds.split(",") if k.strip()}
    if kinds:
        tasks = [t for t in tasks if t.metadata.get("kind") in kinds]
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
            if ev is not None and a.noise:
                ev = with_noise(ev, a.noise, task.task_id)
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
            messages = build_prompt(task, shown, arm, a.encoding, task.task_id, authoritative=a.authoritative,
                                    neutral=a.neutral_prompt, confidence=a.confidence)
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
            # A reply that could not be parsed is not an answer: on a twin, "no
            # findings" would otherwise count as correctly staying silent (102
            # such rows in one deepseek run). None drops the row from the metric.
            correct = None if failed else (sc.hit if is_defect else not sc.hit)
            correct_precise = None if failed else (sc.precise if is_defect else (not sc.hit and sc.flagged_distractors == 0))
            mech = mechanism_correct(task.metadata.get("kind", ""), task.metadata.get("argument", ""),
                                     on_defect) if sc.hit else (False if findings else None)
            spent += c.usage.cost_usd
            extra = {}
            if a.confidence:
                per, item_score, missing = score_items(task, arm, findings,
                                                       [] if failed else finding_confidences(c.text))
                extra = {"confidence": True, "finding_scores": per,
                         "item_score": None if failed else item_score,
                         "confidence_missing": (not failed) and missing,
                         "raw_text": (c.text or "")[:6000]}
                if failed or missing:
                    print(f"  [{i}] {arm} {'PARSE FAILED' if failed else 'CONFIDENCE MISSING on a hit'}")
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
                    "hide_evidence": a.hide_evidence, "noise": a.noise, "authoritative": a.authoritative, "neutral_prompt": a.neutral_prompt, "benchmark": os.path.basename(a.benchmark),
                    "usage": c.usage.as_dict(), **extra,
                }) + "\n")
            print(f"  [{i}/{len(tasks)}] {arm:<14} hit={'Y' if sc.hit else 'n'} "
                  f"exact={'Y' if sc.precise else 'n'} mech={'Y' if mech else ('n' if mech is False else '-')} "
                  f"chars={len(messages[1]['content']):>5} "
                  f"${c.usage.cost_usd:.5f} {time.time()-t0:.1f}s")

    print(f"\ntotal cost: ${spent:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
