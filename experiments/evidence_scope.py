"""Classify what information a review comment needs, by mechanical signal.

The anchor of a comment is not the location of the evidence that justifies it.
A reviewer can attach a note to a changed line and support it with an invariant
three files away, and the resulting benchmark row is indistinguishable from one
requiring nothing but the diff.

This measures the difference. For each confirmed defect it asks whether the
comment refers to anything the diff does not contain: a file path, a URL, an
identifier that appears nowhere in the change, or a phrase naming code
elsewhere.

The classification is deliberately mechanical rather than model-assigned. A
model-assigned label would inherit exactly the weakness this project has
criticised in benchmarks whose ground truth is model-generated, and it could
not be checked. Every rule here is a regular expression over the comment and a
membership test against the diff, so a reader can disagree with a specific
decision and see why it was made.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


SCOPE_DIFF = "diff"
SCOPE_OUTSIDE = "outside-diff"
SCOPES = (SCOPE_DIFF, SCOPE_OUTSIDE)

# A comment pointing at a file, a URL or a repository path is naming something
# the reader has to go and look at.
PATH = re.compile(r"\b[\w./-]+\.(py|js|java|c|h|ts|go|rs|rb|yml|yaml|json|md|rst|txt|cfg|toml)\b")
URL = re.compile(r"https?://\S+")

# Phrases that name code elsewhere without naming a file.
ELSEWHERE = re.compile(
    r"\b("
    r"other (file|module|place|caller|method|function)s?"
    r"|els[ew]where|the (examples?|docs?|tests?|caller|callers|base ?class|parent|interface)"
    r"|(same|similar) (thing|pattern|way|code) (in|as)"
    r"|defined in|declared in|implemented in|used in|called (from|by)"
    r"|consistent with|matches? the|as (in|we do in)"
    r"|look(ed|ing)? at the|see the|refer to the"
    r"|upstream|downstream|the rest of"
    r")\b",
    re.I,
)

# Identifiers worth checking: backticked code, dotted paths, snake_case, CamelCase.
BACKTICKED = re.compile(r"`([^`\n]{2,60})`")
IDENTIFIER = re.compile(r"\b([a-z_][a-z0-9_]{3,}(?:\.[a-z_][a-z0-9_]*)+|[A-Z][a-z]+[A-Z]\w+)\b")

# Speaker prefixes the benchmark inserts; not part of the reviewer's words.
SPEAKER = re.compile(r"@\w+:")

STOPWORDS = {
    "self", "none", "true", "false", "return", "import", "class", "def",
    "this", "that", "with", "from", "value", "values", "string", "object",
}


@dataclass(frozen=True)
class Scope:
    scope: str
    reasons: tuple
    external_identifiers: tuple

    @property
    def needs_outside_evidence(self) -> bool:
        return self.scope == SCOPE_OUTSIDE


def _diff_text(diff: str) -> str:
    """Everything the diff shows, including the paths in its headers.

    Searching only the content lines misses the file names, so a comment naming
    a file the pull request actually changed was counted as pointing outside it.
    """
    return (diff or "").lower()


def _diff_files(diff: str) -> set:
    out = set()
    for line in (diff or "").split("\n"):
        if line.startswith(("diff --git", "+++ ", "--- ")):
            for token in line.split():
                cleaned = token.lstrip("ab/").strip()
                if PATH.fullmatch(cleaned) or PATH.search(cleaned):
                    out.add(cleaned.lower())
                    out.add(cleaned.rsplit("/", 1)[-1].lower())
    return out


def _candidates(comment: str):
    body = SPEAKER.sub(" ", comment or "")
    out = []
    for match in BACKTICKED.finditer(body):
        token = match.group(1).strip()
        if 2 < len(token) < 60 and not token.startswith(("http", "/")):
            out.append(token)
    out.extend(IDENTIFIER.findall(body))
    seen, unique = set(), []
    for token in out:
        key = token.lower().strip("().,`'\"")
        if key and key not in seen and key not in STOPWORDS:
            seen.add(key)
            unique.append(token.strip("().,`'\""))
    return unique


# The identifier rule over-triggers: an assertion message or a stack trace is
# not a reference to other code. The strict reading drops it and keeps only the
# signals that unambiguously name something outside the change — a file, a link,
# or a phrase like "called by". Reporting both gives a bound rather than a
# single number resting on the loosest rule.
STRICT_REASONS = ("names a file", "links to code", "refers to code elsewhere")


def is_strict(scope: "Scope") -> bool:
    return any(r.startswith(STRICT_REASONS) for r in scope.reasons)


def classify(comment: str, diff: str, defect_path: str = "") -> Scope:
    body = SPEAKER.sub(" ", comment or "")
    haystack = _diff_text(diff)
    touched = _diff_files(diff)
    reasons, external = [], []

    for path in [m.group(0) for m in PATH.finditer(body)]:
        low = path.lower()
        if low in touched or low.rsplit("/", 1)[-1] in touched:
            continue
        if low in haystack or (defect_path and path in defect_path):
            continue
        reasons.append(f"names a file the diff does not contain: {path}")
        external.append(path)

    if URL.search(body):
        reasons.append("links to code outside the diff")

    phrase = ELSEWHERE.search(body)
    if phrase:
        reasons.append(f"refers to code elsewhere: {phrase.group(0)!r}")

    for token in _candidates(body):
        stem = token.split(".")[0].lower()
        if len(stem) < 4:
            continue
        if stem not in haystack and token.lower() not in haystack:
            reasons.append(f"names an identifier absent from the diff: {token}")
            external.append(token)

    scope = SCOPE_OUTSIDE if reasons else SCOPE_DIFF
    return Scope(scope=scope, reasons=tuple(reasons), external_identifiers=tuple(dict.fromkeys(external)))
