"""Load review-benchmark tasks into one shape the runner can consume.

Two sources, deliberately unequal:

* c-CRAB (arXiv 2603.23448, CC BY 4.0) carries the headline result. Its ground
  truth is executable tests that fail before the fix and pass after, so no
  human judgement enters the measurement. It is Python only.
* AACR-Bench (arXiv 2601.19494) supplies the multi-language check, restricted
  to the four languages the graph parser can read. 73% of its ground truth is
  LLM-generated, so it is reported as secondary evidence and never mixed into
  the primary numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_LANGUAGES = {
    "python": ".py",
    "javascript": ".js",
    "java": ".java",
    "c": ".c",
}

SOURCE_CCRAB = "c-crab"
SOURCE_AACR = "aacr-bench"


@dataclass(frozen=True)
class GroundTruthDefect:
    """One defect a review is expected to find. The unit of analysis."""

    defect_id: str
    path: str
    line: int | None
    text: str
    diff_hunk: str = ""
    start_line: int | None = None

    @property
    def has_location(self) -> bool:
        return bool(self.path) and self.line is not None


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    source: str
    repo: str
    language: str
    base_commit: str
    diff: str
    defects: tuple[GroundTruthDefect, ...] = field(default_factory=tuple)
    problem_statement: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def defect_count(self) -> int:
        return len(self.defects)


def _normalise_language(value: str) -> str:
    return (value or "").strip().lower()


def is_supported_language(value: str) -> bool:
    return _normalise_language(value) in SUPPORTED_LANGUAGES


def _ccrab_defects(instance: dict) -> tuple[GroundTruthDefect, ...]:
    defects = []
    for index, comment in enumerate(instance.get("reference_review_comments") or []):
        line = comment.get("line")
        if line is None:
            line = comment.get("original_line")
        defects.append(
            GroundTruthDefect(
                defect_id=f"{instance.get('instance_id')}#{index}",
                path=comment.get("path") or "",
                line=int(line) if line is not None else None,
                text=comment.get("text") or "",
                diff_hunk=comment.get("diff_hunk") or "",
                start_line=comment.get("start_line") or comment.get("original_start_line"),
            )
        )
    return tuple(defects)


def load_ccrab(path, languages=None, require_located_defects: bool = True) -> list[BenchmarkTask]:
    wanted = {_normalise_language(l) for l in (languages or SUPPORTED_LANGUAGES)}
    tasks = []
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            instance = json.loads(raw)
            language = _normalise_language(instance.get("language"))
            if language not in wanted:
                continue
            defects = _ccrab_defects(instance)
            if require_located_defects:
                defects = tuple(d for d in defects if d.has_location)
            if not defects:
                continue
            tasks.append(
                BenchmarkTask(
                    task_id=instance.get("instance_id") or "",
                    source=SOURCE_CCRAB,
                    repo=instance.get("repo") or "",
                    language=language,
                    base_commit=instance.get("base_commit") or "",
                    diff=instance.get("merged_patch") or "",
                    defects=defects,
                    problem_statement=instance.get("problem_statement") or "",
                    metadata=instance.get("metadata") or {},
                )
            )
    return tasks


def oracle_targets(task: BenchmarkTask) -> list[dict]:
    """The answer key, in the shape build_oracle_context_tool expects.

    Only condition F may ever be given this.
    """
    return [{"path": d.path, "line": d.line} for d in task.defects if d.has_location]


def summarise(tasks) -> dict:
    languages = {}
    repos = set()
    defects = 0
    for task in tasks:
        languages[task.language] = languages.get(task.language, 0) + 1
        repos.add(task.repo)
        defects += task.defect_count
    return {
        "tasks": len(tasks),
        "defects": defects,
        "repos": len(repos),
        "languages": dict(sorted(languages.items())),
        "defects_per_task": round(defects / len(tasks), 2) if tasks else 0.0,
    }
