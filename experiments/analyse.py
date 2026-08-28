#!/usr/bin/env python3
"""Read a run directory and print the numbers the paper reports.

    python experiments/analyse.py runs/full-gpt4omini
    python experiments/analyse.py runs/full-gpt4omini --latex

Only tasks scored under every condition are compared, so a task that failed
to fetch in one arm cannot inflate another.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from experiments.config import BUDGETED_CONDITIONS, CONDITION_LABELS, REFERENCE_CONDITIONS
from experiments.matcher import Outcome
from experiments.metrics import compare, summarise_condition, table


def load(run_dir: Path):
    outcomes = [Outcome(**json.loads(l)) for l in (run_dir / "outcomes.jsonl").read_text().splitlines() if l.strip()]
    raw = [json.loads(l) for l in (run_dir / "raw.jsonl").read_text().splitlines() if l.strip()]
    return outcomes, raw


def balance(outcomes, conditions):
    """Keep only tasks scored under every condition."""
    seen = collections.defaultdict(set)
    for outcome in outcomes:
        seen[outcome.task_id].add(outcome.condition)
    complete = {task for task, got in seen.items() if set(conditions) <= got}
    return [o for o in outcomes if o.task_id in complete], complete


def false_positives_by_condition(raw, outcomes):
    """Findings that matched no ground-truth defect.

    A review reporting 1,018 findings against 218 defects is mostly reporting
    things the benchmark does not confirm. Some are real defects the benchmark
    never recorded and some are wrong; the benchmark cannot tell them apart, so
    this is an upper bound on false positives and precision computed from it is
    a lower bound.
    """
    matched = collections.Counter()
    for outcome in outcomes:
        if outcome.hit:
            matched[outcome.condition] += 1
    reported = collections.Counter()
    for row in raw:
        reported[row["condition"]] += len(row["findings"])
    return {c: max(0, reported[c] - matched[c]) for c in reported}


def usage_by_condition(raw):
    usage = collections.defaultdict(
        lambda: {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    )
    context = collections.defaultdict(list)
    reported = collections.Counter()
    parse_failures = collections.Counter()
    for row in raw:
        condition = row["condition"]
        usage[condition]["input_tokens"] += row["usage"]["input_tokens"]
        usage[condition]["output_tokens"] += row["usage"]["output_tokens"]
        usage[condition]["cost_usd"] += row["usage"]["cost_usd"]
        context[condition].append(row["context_chars"])
        reported[condition] += len(row["findings"])
        parse_failures[condition] += int(bool(row.get("parse_failed")))
    return usage, context, reported, parse_failures


def latex(summaries, comparisons) -> str:
    lines = [
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"& Context & Defects & Recall & 95\% CI & Precision & \$/finding \\",
        r"\midrule",
    ]
    for s in summaries:
        cost = f"{s.cost_per_true_finding:.4f}" if s.cost_per_true_finding is not None else "--"
        lines.append(
            f"{s.condition} & {CONDITION_LABELS.get(s.condition, '')} & {s.defects} & "
            f"{s.recall:.1%} & [{s.recall_low:.1%}, {s.recall_high:.1%}] & "
            f"{s.precision:.1%} & {cost} \\\\".replace("%", r"\%")
        )
    lines += [r"\bottomrule", r"\end{tabular}", "", r"\begin{tabular}{lrr}", r"\toprule",
              r"Comparison & Difference & 95\% CI \\", r"\midrule"]
    for c in comparisons:
        lines.append(
            f"{c.treatment} vs {c.baseline} & {c.lift:+.1%} & "
            f"[{c.lift_low:+.1%}, {c.lift_high:+.1%}] \\\\".replace("%", r"\%")
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--baseline", default="A")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--latex", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    outcomes, raw = load(run_dir)
    conditions = sorted({o.condition for o in outcomes})
    balanced, complete = balance(outcomes, conditions)

    usage, context, reported, parse_failures = usage_by_condition(raw)

    print(f"run        : {run_dir}")
    print(f"conditions : {conditions}")
    print(f"tasks      : {len(complete)} scored under every condition "
          f"(of {len({o.task_id for o in outcomes})} seen)")
    print(f"defects    : {len(balanced) // max(1, len(conditions))} per condition")
    print()

    print("=== context delivered ===")
    for condition in conditions:
        values = context.get(condition) or [0]
        tag = " (reference, unbudgeted)" if condition in REFERENCE_CONDITIONS else ""
        print(f"  {condition}: mean {sum(values)//len(values):>7} chars   "
              f"min {min(values):>6}  max {max(values):>7}   n={len(values)}{tag}")
    # Parity is a claim about the budgeted arms only. E and F are reference
    # points and are unbudgeted by design, so including them would report a
    # spread of ~99% and say nothing about whether the comparison is fair.
    # F is budgeted but is a ceiling, not a competitor: it returns only the
    # entities covering the answer key, which is legitimately less than the
    # budget allows. Parity is a claim about the arms compared to each other.
    comparable = [
        c for c in BUDGETED_CONDITIONS
        if c not in REFERENCE_CONDITIONS and c != "A"
    ]
    matched = [
        sum(context[c]) / len(context[c])
        for c in comparable
        if context.get(c) and sum(context[c])
    ]
    if len(matched) > 1:
        spread = (max(matched) - min(matched)) / max(matched)
        verdict = "parity holds" if spread <= 0.10 else "PARITY BROKEN"
        print(f"  spread across budgeted arms: {spread:.1%}  <- {verdict}")
    print()

    unmatched = false_positives_by_condition(raw, balanced)
    summaries = [
        summarise_condition(
            c, balanced, false_positives=unmatched.get(c, 0),
            usage=usage[c], bootstrap=args.bootstrap,
        )
        for c in conditions
    ]
    print(table(summaries))
    print()

    print("=== reported findings and parse failures ===")
    for condition in conditions:
        print(f"  {condition}: {reported[condition]:>5} findings reported, "
              f"{unmatched.get(condition, 0):>5} matched no confirmed defect, "
              f"{parse_failures[condition]} parse failures")
    print("  (precision below is a lower bound: the benchmark confirms only a")
    print("   subset of real defects, so an unmatched finding may still be right)")
    print()

    comparisons = []
    print(f"=== against baseline {args.baseline} ===")
    for condition in conditions:
        if condition == args.baseline:
            continue
        c = compare(balanced, condition, args.baseline, bootstrap=args.bootstrap)
        comparisons.append(c)
        print("  " + c.verdict())

    if "B" in conditions and "D" in conditions:
        print()
        print("=== the paper's question: graph against lexical, same budget ===")
        c = compare(balanced, "B", "D", bootstrap=args.bootstrap)
        comparisons.append(c)
        print("  " + c.verdict())

    total = sum(u["cost_usd"] for u in usage.values())
    print(f"\ntotal cost: ${total:.4f}")

    if args.latex:
        print("\n" + latex(summaries, comparisons))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
