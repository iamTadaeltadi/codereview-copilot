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
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_LANGUAGES = {
    "python": ".py",
    "javascript": ".js",
    "java": ".java",
    "c": ".c",
}

# The graph is built from source the parser understands. A defect reported
# against a .rst page or a .yaml config cannot be reached by any retrieval
# condition here, so scoring one would charge every arm with a miss it had no
# means of avoiding. Such defects are excluded, and the exclusion is a stated
# inclusion criterion rather than a silent skip.
SUPPORTED_SUFFIXES = frozenset(SUPPORTED_LANGUAGES.values())

SOURCE_CCRAB = "c-crab"
SOURCE_AACR = "aacr-bench"
SOURCE_CROSSFILE = "crossfile"

FUNCTIONAL = "functional"


@dataclass(frozen=True)
class GroundTruthDefect:
    """One defect a review is expected to find. The unit of analysis."""

    defect_id: str
    path: str
    line: int | None
    text: str
    diff_hunk: str = ""
    start_line: int | None = None
    comment_type: str = ""
    test_verified: bool = False

    @property
    def has_location(self) -> bool:
        return bool(self.path) and self.line is not None

    @property
    def in_supported_source(self) -> bool:
        from pathlib import PurePosixPath

        return PurePosixPath(self.path or "").suffix in SUPPORTED_SUFFIXES

    @property
    def is_confirmed_defect(self) -> bool:
        """Functional, and proven by a test that failed before and passed after.

        Everything else is a style preference, a documentation note, a
        structural suggestion, or a comment whose generated test never
        demonstrated the defect. Scoring a review against those would measure
        agreement with opinion rather than defect detection.
        """
        return self.comment_type == FUNCTIONAL and self.test_verified


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    source: str
    repo: str
    language: str
    base_commit: str
    diff: str
    head_commit: str = ""
    defects: tuple[GroundTruthDefect, ...] = field(default_factory=tuple)
    problem_statement: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def defect_count(self) -> int:
        return len(self.defects)

    @property
    def review_commit(self) -> str:
        """The commit whose code is under review.

        base_commit is where the branch started; the reviewer never sees that
        tree. head_commit is the revision the human reviewers actually
        commented on, and it is what the instance id is named after. Fetching
        sources at base_commit misses every file the pull request added, which
        is what produced "no source files fetched" skips in the pilot.
        """
        return self.head_commit or self.base_commit


def _normalise_language(value: str) -> str:
    return (value or "").strip().lower()


def is_supported_language(value: str) -> bool:
    return _normalise_language(value) in SUPPORTED_LANGUAGES


def _comment_key(text: str) -> str:
    return " ".join((text or "").split())


def load_testgen_verdicts(archive_path) -> dict:
    """Read the c-CRAB testgen archive into {(instance_id, comment_key): verdict}.

    The archive records, per comment, the comment_type the pipeline assigned and
    whether the generated test actually flipped from failing to passing. Both are
    needed to separate a demonstrated defect from a reviewer's preference.

    The join is on normalised comment text, not on comment_index. The released
    instances have had reference_review_comments reduced to the retained subset,
    so the archive's indices refer to positions in the original SWE-CARE list and
    no longer line up — joining on index silently drops 198 of the 524 confirmed
    defects and misattributes others.
    """
    verdicts = {}
    with zipfile.ZipFile(archive_path) as archive:
        for name in archive.namelist():
            if not name.endswith("result.json"):
                continue
            data = json.loads(archive.read(name))
            instance_id = data.get("instance_id")
            for entry in data.get("results") or []:
                key = (instance_id, _comment_key(entry.get("comment_text")))
                verdicts[key] = {
                    "comment_type": entry.get("comment_type") or "",
                    "test_verified": entry.get("success") is True,
                    "before_passed": entry.get("before_passed"),
                    "after_passed": entry.get("after_passed"),
                }
    return verdicts


def _ccrab_defects(instance: dict, verdicts=None) -> tuple[GroundTruthDefect, ...]:
    verdicts = verdicts or {}
    instance_id = instance.get("instance_id")
    defects = []
    for index, comment in enumerate(instance.get("reference_review_comments") or []):
        verdict = verdicts.get((instance_id, _comment_key(comment.get("text"))), {})
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
                comment_type=verdict.get("comment_type", ""),
                test_verified=bool(verdict.get("test_verified")),
            )
        )
    return tuple(defects)


def load_ccrab(
    path,
    languages=None,
    require_located_defects: bool = True,
    testgen_archive=None,
    confirmed_only: bool = False,
    supported_source_only: bool = False,
) -> list[BenchmarkTask]:
    wanted = {_normalise_language(l) for l in (languages or SUPPORTED_LANGUAGES)}
    verdicts = load_testgen_verdicts(testgen_archive) if testgen_archive else {}
    if confirmed_only and not verdicts:
        raise ValueError("confirmed_only needs testgen_archive: the verdicts live there")
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
            defects = _ccrab_defects(instance, verdicts)
            if require_located_defects:
                defects = tuple(d for d in defects if d.has_location)
            if confirmed_only:
                defects = tuple(d for d in defects if d.is_confirmed_defect)
            if supported_source_only:
                defects = tuple(d for d in defects if d.in_supported_source)
            if not defects:
                continue
            tasks.append(
                BenchmarkTask(
                    task_id=instance.get("instance_id") or "",
                    source=SOURCE_CCRAB,
                    repo=instance.get("repo") or "",
                    language=language,
                    base_commit=instance.get("base_commit") or "",
                    head_commit=(instance.get("commit_to_review") or {}).get("head_commit") or "",
                    # patch_to_review is the change the humans reviewed.
                    # merged_patch is everything that eventually landed on the
                    # branch, including work added after the review, so showing
                    # it would ask the model to find defects in code the
                    # reviewers never saw. Median 7.5k characters against 9.8k.
                    diff=(instance.get("commit_to_review") or {}).get("patch_to_review")
                    or instance.get("merged_patch")
                    or "",
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
        "confirmed": sum(1 for t in tasks for d in t.defects if d.is_confirmed_defect),
        "in_supported_source": sum(1 for t in tasks for d in t.defects if d.in_supported_source),
        "repos": len(repos),
        "languages": dict(sorted(languages.items())),
        "defects_per_task": round(defects / len(tasks), 2) if tasks else 0.0,
    }


def _distractor_lines(diff: str, defect_line: int) -> list[int]:
    """The changed lines in a generated diff other than the defect's."""
    import re

    # Each change is its own single-line hunk whose header names the line the
    # change is actually on.
    lines = [int(m.group(1)) for m in re.finditer(r"@@ -(\d+),1 ", diff or "")]
    return sorted({l for l in lines if l != defect_line})


def load_crossfile(path) -> list[BenchmarkTask]:
    """Load the generated cross-file benchmark.

    One task per defect. The diff contains only the mutated line; the file that
    makes the change wrong is never in it. A reviewer can only flag these by
    retrieving code the diff does not mention, which is what the review-comment
    benchmarks cannot ask.
    """
    tasks = []
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            row = json.loads(raw)
            from experiments.crossfile import is_test_path

            # A defect whose only victim is a test is weaker: production code is
            # unaffected and a reviewer could reasonably decline to flag it.
            if is_test_path(row.get("caller_path", "")) or is_test_path(row.get("defect_path", "")):
                continue

            # A diff with one change is free: flag the only change and be right
            # without knowing why. Measured at 97% for the no-context arm.
            changed = [
                l for l in row["diff"].split("\n")
                if l.startswith("-") and not l.startswith("---")
            ]
            if len(changed) < 2:
                continue
            defect = GroundTruthDefect(
                defect_id=row["task_id"],
                path=row["defect_path"],
                line=int(row["defect_line"]),
                text=row["why"],
                comment_type=FUNCTIONAL,
                test_verified=True,
            )
            tasks.append(
                BenchmarkTask(
                    task_id=row["task_id"],
                    source=SOURCE_CROSSFILE,
                    repo=row["repo"],
                    language="python",
                    base_commit=row["commit"],
                    head_commit=row["commit"],
                    diff=row["diff"],
                    defects=(defect,),
                    problem_statement=row["why"],
                    metadata={
                        "kind": row["kind"],
                        "caller_path": row["caller_path"],
                        "caller_line": row["caller_line"],
                        "evidence": row["evidence"],
                        "argument": row.get("argument", ""),
                        "is_defect": bool(row.get("is_defect", True)),
                        "via_path": row.get("via_path", ""), "via_line": row.get("via_line"),
                        "hops": 2 if row.get("via_path") else 1,
                        "verified": row.get("verified", "regex"),
                        # Lines the benchmark knows are harmless. Flagging one is a
                        # confirmed false positive, which no annotated benchmark can
                        # tell you: there, an unmatched finding may simply have found
                        # something the annotators missed.
                        "distractor_lines": row.get("distractor_lines")
                        or _distractor_lines(row["diff"], int(row["defect_line"])),
                    },
                )
            )
    return tasks
