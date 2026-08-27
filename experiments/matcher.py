"""Decide, per ground-truth defect, whether a review found it.

This module fixes the unit of analysis. Every ground-truth defect produces
exactly one outcome row per condition, hit or miss, and every reported finding
that matches no defect is counted as a false positive. Scoring one row per task
instead would raise the minimum detectable effect from roughly 5 points to 10
(see experiments/power.py), so the shape here is not cosmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


DEFAULT_LINE_TOLERANCE = 5


@dataclass(frozen=True)
class ReportedFinding:
    """One defect a review claims to have found."""

    finding_id: str
    path: str
    line: int | None
    message: str = ""


@dataclass(frozen=True)
class Outcome:
    """One ground-truth defect, judged under one condition."""

    defect_id: str
    task_id: str
    condition: str
    hit: bool
    matched_finding_id: str | None = None
    line_distance: int | None = None


@dataclass(frozen=True)
class MatchReport:
    outcomes: tuple[Outcome, ...]
    false_positives: tuple[str, ...]

    @property
    def hits(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.hit)

    @property
    def recall(self) -> float:
        if not self.outcomes:
            return 0.0
        return self.hits / len(self.outcomes)

    @property
    def precision(self) -> float:
        reported = self.hits + len(self.false_positives)
        if reported == 0:
            return 0.0
        return self.hits / reported

    @property
    def f1(self) -> float:
        precision, recall = self.precision, self.recall
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)


def normalise_path(path: str) -> str:
    if not path:
        return ""
    cleaned = path.strip().replace("\\", "/").lstrip("./")
    for prefix in ("a/", "b/"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    return str(PurePosixPath(cleaned))


def paths_match(left: str, right: str) -> bool:
    left_norm, right_norm = normalise_path(left), normalise_path(right)
    if not left_norm or not right_norm:
        return False
    return left_norm == right_norm


def line_distance(finding_line, defect_line) -> int | None:
    if finding_line is None or defect_line is None:
        return None
    return abs(int(finding_line) - int(defect_line))


def match_review(
    task_id: str,
    condition: str,
    defects,
    findings,
    line_tolerance: int = DEFAULT_LINE_TOLERANCE,
) -> MatchReport:
    remaining = list(findings)
    outcomes = []
    consumed = set()

    for defect in defects:
        best = None
        best_distance = None
        for finding in remaining:
            if finding.finding_id in consumed:
                continue
            if not paths_match(finding.path, defect.path):
                continue
            distance = line_distance(finding.line, defect.line)
            if distance is None or distance > line_tolerance:
                continue
            if best_distance is None or distance < best_distance:
                best, best_distance = finding, distance

        if best is None:
            outcomes.append(
                Outcome(
                    defect_id=defect.defect_id,
                    task_id=task_id,
                    condition=condition,
                    hit=False,
                )
            )
        else:
            consumed.add(best.finding_id)
            outcomes.append(
                Outcome(
                    defect_id=defect.defect_id,
                    task_id=task_id,
                    condition=condition,
                    hit=True,
                    matched_finding_id=best.finding_id,
                    line_distance=best_distance,
                )
            )

    false_positives = tuple(
        finding.finding_id for finding in remaining if finding.finding_id not in consumed
    )
    return MatchReport(outcomes=tuple(outcomes), false_positives=false_positives)
