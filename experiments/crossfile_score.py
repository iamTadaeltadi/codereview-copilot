"""Score the cross-file benchmark, where harmless lines are known.

Two things are possible here that are not possible on an annotated benchmark.

The defect's line is known exactly, because the mutation was applied to it, so
matching does not need a tolerance window. On c-CRAB a tolerance is necessary —
a human comment approximates the location — but here it only lets a reviewer
that flagged something else take credit.

And the harmless changes are known. A finding on a distractor line is a
*confirmed* false positive: that line was rewritten in a way that cannot change
behaviour, so there is nothing there to report. On an annotated benchmark an
unmatched finding may simply have found a defect the annotators missed, so
precision can only ever be a lower bound. Here it is exact.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.matcher import normalise_path


@dataclass(frozen=True)
class CrossFileOutcome:
    task_id: str
    condition: str
    hit: bool
    flagged_distractors: int
    findings: int
    kind: str

    @property
    def precise(self) -> bool:
        """Found the defect and flagged nothing known to be harmless."""
        return self.hit and self.flagged_distractors == 0


def score_review(task, condition, findings, tolerance: int = 0) -> CrossFileOutcome:
    defect = task.defects[0]
    distractors = set(task.metadata.get("distractor_lines") or [])

    hit = False
    flagged = 0
    for finding in findings:
        if finding.line is None:
            continue
        if not normalise_path(finding.path).endswith(normalise_path(defect.path).split("/")[-1]):
            continue
        if abs(finding.line - defect.line) <= tolerance:
            hit = True
        elif any(abs(finding.line - d) <= tolerance for d in distractors):
            flagged += 1

    return CrossFileOutcome(
        task_id=task.task_id,
        condition=condition,
        hit=hit,
        flagged_distractors=flagged,
        findings=len(findings),
        kind=task.metadata.get("kind", ""),
    )


def summarise(outcomes):
    """Recall, confirmed precision, and the strict 'exactly right' rate."""
    if not outcomes:
        return {}
    n = len(outcomes)
    hits = sum(1 for o in outcomes if o.hit)
    precise = sum(1 for o in outcomes if o.precise)
    flagged = sum(o.flagged_distractors for o in outcomes)
    reported = sum(o.findings for o in outcomes)
    return {
        "tasks": n,
        "recall": hits / n,
        "precise_rate": precise / n,
        "confirmed_false_positives": flagged,
        "findings_reported": reported,
        "confirmed_precision": hits / (hits + flagged) if (hits + flagged) else 0.0,
    }
