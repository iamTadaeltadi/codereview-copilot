"""Construct code-review tasks whose defect cannot be seen in the diff.

Every confirmed defect in the review-comment benchmarks sits on a line the
diff changed — 213 of 218 in c-CRAB — because a GitHub review comment can only
be anchored to a diff line. Such a benchmark cannot measure whether repository
context helps, since it contains no defect that requires any.

This module builds tasks that do. Each one mutates a definition in one file so
that it violates an assumption a *different* file demonstrably makes about it.
The diff shows only the mutation, and the mutation is chosen to be locally
plausible: reading it alone, there is nothing to object to. The defect exists
only in the relationship between the two files.

Ground truth is by construction, not by annotation. A mutation is emitted only
when a caller is found whose source shows it depending on the behaviour being
changed — checking `is None`, unpacking a fixed-width tuple, catching a
specific exception, and so on. If no such caller exists the change is not a
defect and is discarded.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Change:
    """One line in the diff. Exactly one of them is the defect."""

    line: int
    before: str
    after: str
    is_defect: bool


@dataclass(frozen=True)
class CrossFileDefect:
    defect_id: str
    kind: str
    definition_path: str
    definition_name: str
    definition_line: int
    caller_path: str
    caller_name: str
    caller_line: int
    before: str
    after: str
    why: str
    evidence: str
    distractors: tuple = field(default_factory=tuple)

    @property
    def path(self) -> str:
        return self.definition_path

    @property
    def line(self) -> int:
        return self.definition_line


def _functions(tree, source_lines):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _returns(fn):
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and node.value is not None:
            yield node


TEST_PATH = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*$|_test\.py$|conftest\.py$")


def is_test_path(path: str) -> bool:
    """Test files are excluded as the depended-upon caller.

    A test that omits an argument or catches an exception is evidence that the
    behaviour matters, but a defect whose only victim is a test is a weaker
    defect: the production code is unaffected, and a reviewer could reasonably
    decline to flag it. Requiring a non-test caller keeps every task one where
    shipping the change actually breaks something.
    """
    return bool(TEST_PATH.search(path or ""))


def _calls_name(source, name):
    return re.search(rf"\b{re.escape(name)}\s*\(", source) is not None


def _line(source_lines, lineno):
    return source_lines[lineno - 1] if 0 < lineno <= len(source_lines) else ""


def _indent(text):
    return text[: len(text) - len(text.lstrip())]


# --- mutation families -----------------------------------------------------
# Each returns (before_line, after_line, why, evidence_regex_on_caller) or None.


def _mutate_none_sentinel(fn, lines):
    """return None -> return -1 where a caller tests `is None`.

    -1 is a valid index in Python, so the caller's guard silently stops firing
    and an out-of-range lookup silently returns the last element instead of
    raising. Nothing about the changed line looks wrong.
    """
    for node in _returns(fn):
        if isinstance(node.value, ast.Constant) and node.value.value is None:
            before = _line(lines, node.lineno)
            if "return None" not in before:
                continue
            after = before.replace("return None", "return -1")
            return (
                node.lineno,
                before,
                after,
                "the function no longer returns None to signal absence, so a caller "
                "guarding on `is None` stops detecting the failure case; -1 is a "
                "valid index, so the lookup silently returns the last element",
                r"is\s+None|is\s+not\s+None|==\s*None",
            )
    return None


def _mutate_tuple_order(fn, lines):
    """Swap a returned pair, where a caller unpacks it into two names."""
    for node in _returns(fn):
        if isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2:
            before = _line(lines, node.lineno)
            match = re.search(r"return\s+(.+?),\s*(.+?)\s*$", before)
            if not match:
                continue
            after = before.replace(
                match.group(0), f"return {match.group(2).strip()}, {match.group(1).strip()}"
            )
            if after == before:
                continue
            return (
                node.lineno,
                before,
                after,
                "the two returned values are swapped; both remain valid values of "
                "their own types, so nothing fails at the boundary and the caller "
                "silently binds each name to the other's value",
                r"=\s*\w+\s*\([^)]*\)\s*$",
            )
    return None


def _mutate_boundary(fn, lines):
    """Tighten an inclusive comparison, where a caller relies on the edge."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Compare) and node.ops:
            op = node.ops[0]
            before = _line(lines, node.lineno)
            if isinstance(op, ast.LtE) and "<=" in before:
                after = before.replace("<=", "<", 1)
            elif isinstance(op, ast.GtE) and ">=" in before:
                after = before.replace(">=", ">", 1)
            else:
                continue
            return (
                node.lineno,
                before,
                after,
                "an inclusive bound becomes exclusive, so the boundary value is "
                "now rejected; every other input behaves identically, which is "
                "why the change reads as a simplification",
                r"len\s*\(|range\s*\(|\[\s*-?\d+\s*\]|\.append\(",
            )
    return None


def _mutate_shared_mutable(fn, lines):
    """Return the container itself where a copy was returned."""
    for node in _returns(fn):
        before = _line(lines, node.lineno)
        match = re.search(r"return\s+(list|dict|set)\(([\w.\[\]]+)\)", before)
        if match:
            after = before.replace(match.group(0), f"return {match.group(2)}")
            return (
                node.lineno,
                before,
                after,
                "the defensive copy is removed, so the caller now receives the "
                "internal container itself and any mutation it performs leaks "
                "back into this object's state",
                r"\.append\(|\.extend\(|\.pop\(|\.update\(|\.add\(|\.remove\(|\.clear\(",
            )
    return None


def _mutate_exception_type(fn, lines):
    """Change the raised exception, where a caller catches the old one."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            func = node.exc.func
            name = getattr(func, "id", None)
            if name not in {"ValueError", "KeyError", "TypeError", "IndexError"}:
                continue
            replacement = {
                "ValueError": "TypeError",
                "KeyError": "ValueError",
                "TypeError": "ValueError",
                "IndexError": "KeyError",
            }[name]
            before = _line(lines, node.lineno)
            if name not in before:
                continue
            after = before.replace(name, replacement, 1)
            return (
                node.lineno,
                before,
                after,
                f"the raised type changes from {name} to {replacement}, so a caller "
                f"catching {name} stops catching it and the error escapes as an "
                "unhandled exception instead of being recovered from",
                rf"except\s+{name}|except\s*\(\s*[^)]*{name}",
            )
    return None



def _mutate_default_flip(fn, lines):
    """Flip a boolean default, where a caller relies on it by omitting the argument.

    The signature still reads sensibly and every explicit caller is unaffected.
    Only callers that took the default change behaviour, and they change
    silently, because nothing at the call site mentions the parameter at all.
    """
    defaults = fn.args.defaults or []
    if not defaults:
        return None
    names = [a.arg for a in fn.args.args][-len(defaults):] if defaults else []
    for name, default in zip(names, defaults):
        if not (isinstance(default, ast.Constant) and isinstance(default.value, bool)):
            continue
        before = _line(lines, fn.lineno)
        old, new = (f"{name}=True", f"{name}=False") if default.value else (f"{name}=False", f"{name}=True")
        if old not in before:
            continue
        return (
            fn.lineno,
            before,
            before.replace(old, new, 1),
            f"the default for `{name}` is inverted, so every caller that omits it "
            "silently changes behaviour while every caller that passes it "
            "explicitly is unaffected; nothing at those call sites mentions the "
            "parameter, so there is nothing there to notice",
            rf"\b{re.escape(fn.name)}\s*\((?![^)]*{re.escape(name)})",
        )
    return None


def _mutate_empty_to_none(fn, lines):
    """Return None where an empty container was returned.

    Both are falsy, so a truthiness check still behaves. A caller that iterates
    the result, or takes its length, now raises TypeError instead.
    """
    for node in _returns(fn):
        if isinstance(node.value, (ast.List, ast.Dict)) and not getattr(node.value, "elts", None) \
                and not getattr(node.value, "keys", None):
            before = _line(lines, node.lineno)
            match = re.search(r"return\s+(\[\]|\{\})", before)
            if not match:
                continue
            return (
                node.lineno,
                before,
                before.replace(match.group(0), "return None", 1),
                "an empty container becomes None; both are falsy so a truthiness "
                "check still passes, but a caller that iterates the result or "
                "takes its length now raises TypeError",
                rf"for\s+\w+\s+in\s+.*{re.escape(fn.name)}|len\s*\(\s*.*{re.escape(fn.name)}|\.join\(",
            )
    return None


def _mutate_normalisation(fn, lines):
    """Drop a normalising call from a returned value.

    The function still returns a string of the same type. Only a caller that
    compares the result against a normalised constant changes behaviour.
    """
    for node in _returns(fn):
        before = _line(lines, node.lineno)
        for call in (".strip()", ".lower()", ".rstrip()", ".lstrip()"):
            if call in before and "return" in before:
                return (
                    node.lineno,
                    before,
                    before.replace(call, "", 1),
                    f"the {call} normalisation is dropped from the returned value; "
                    "the type is unchanged and most inputs are unaffected, but a "
                    "caller comparing against a normalised constant now fails on "
                    "any input with different case or surrounding whitespace",
                    r"""==\s*["']|\bin\s*\(|\bin\s*\[|\.get\(""",
                )
    return None


def _mutate_slice_bound(fn, lines):
    """Shift a slice bound, where a caller depends on the length or last element."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            before = _line(lines, node.lineno)
            for old, new in (("[:-1]", "[:]"), ("[1:]", "[:]"), ("[:1]", "[:2]")):
                if old in before:
                    return (
                        node.lineno,
                        before,
                        before.replace(old, new, 1),
                        f"the slice bound changes from {old} to {new}, so the result "
                        "gains or loses one element; the type and shape are "
                        "unchanged, so only a caller that depends on the exact "
                        "length or on the final element is affected",
                        r"\[-1\]|\[0\]|len\s*\(|zip\s*\(",
                    )
    return None


MUTATIONS = {
    "none_sentinel": _mutate_none_sentinel,
    "tuple_order": _mutate_tuple_order,
    "boundary": _mutate_boundary,
    "shared_mutable": _mutate_shared_mutable,
    "exception_type": _mutate_exception_type,
    "default_flip": _mutate_default_flip,
    "empty_to_none": _mutate_empty_to_none,
    "normalisation": _mutate_normalisation,
    "slice_bound": _mutate_slice_bound,
}



# --- distractors -----------------------------------------------------------
# A diff containing a single changed line makes the task trivial: the reviewer
# flags the only change and is right by default, which measured 97% for the
# no-context arm. Real review diffs carry several changes and most are fine, so
# each task carries harmless edits alongside the defect and the reviewer has to
# say which one is wrong.
#
# Every distractor is a rewrite that cannot change behaviour. They are the kind
# of tidying that appears in real pull requests and that a reviewer reads past.

def _distract_quote_style(line):
    match = re.search(r'"([^"\\{}]*)"', line)
    if match and "'" not in match.group(1):
        return line[: match.start()] + "'" + match.group(1) + "'" + line[match.end():]
    return None


def _distract_none_comparison(line):
    if "== None" in line:
        return line.replace("== None", "is None", 1)
    if "!= None" in line:
        return line.replace("!= None", "is not None", 1)
    return None


def _distract_empty_literal(line):
    for old, new in (("dict()", "{}"), ("list()", "[]"), ("tuple()", "()")):
        if old in line:
            return line.replace(old, new, 1)
    return None


def _distract_redundant_parens(line):
    match = re.search(r"return \((\w+)\)\s*$", line)
    if match:
        return line.replace(match.group(0), "return " + match.group(1))
    return None


DISTRACTORS = (
    _distract_quote_style,
    _distract_none_comparison,
    _distract_empty_literal,
    _distract_redundant_parens,
)


def find_distractors(lines, exclude_line, wanted=3, window=60):
    """Harmless rewrites on other lines near the defect."""
    out = []
    lo = max(0, exclude_line - window)
    hi = min(len(lines), exclude_line + window)
    for index in range(lo, hi):
        lineno = index + 1
        if lineno == exclude_line:
            continue
        original = lines[index]
        if not original.strip() or original.strip().startswith("#"):
            continue
        for rewrite in DISTRACTORS:
            changed = rewrite(original)
            if changed and changed != original:
                out.append(Change(lineno, original, changed, is_defect=False))
                break
        if len(out) >= wanted:
            break
    return tuple(out)


def find_defects(sources, max_per_repo: int = 3):
    """Yield defects where a mutation in one file breaks a demonstrated
    assumption made in another."""
    parsed = {}
    for path, text in sources.items():
        if not path.endswith(".py"):
            continue
        try:
            parsed[path] = (ast.parse(text), text.split("\n"), text)
        except SyntaxError:
            continue

    found = []
    for path, (tree, lines, text) in parsed.items():
        if is_test_path(path):
            continue
        for fn in _functions(tree, lines):
            if fn.name.startswith("_") or fn.name in {"__init__", "main"}:
                continue

            callers = [
                (other, otext)
                for other, (_, _, otext) in parsed.items()
                if other != path and not is_test_path(other) and _calls_name(otext, fn.name)
            ]
            if not callers:
                continue

            for kind, mutate in MUTATIONS.items():
                result = mutate(fn, lines)
                if not result:
                    continue
                lineno, before, after, why, evidence_pattern = result

                for caller_path, caller_text in callers:
                    evidence = _find_evidence(caller_text, fn.name, evidence_pattern)
                    if not evidence:
                        continue
                    found.append(
                        CrossFileDefect(
                            defect_id=f"{path}::{fn.name}::{kind}",
                            kind=kind,
                            definition_path=path,
                            definition_name=fn.name,
                            definition_line=lineno,
                            caller_path=caller_path,
                            caller_name=fn.name,
                            caller_line=evidence[0],
                            before=before,
                            after=after,
                            why=why,
                            evidence=evidence[1].strip(),
                            distractors=find_distractors(lines, lineno),
                        )
                    )
                    break
                if len(found) >= max_per_repo:
                    return found
    return found


def _find_evidence(caller_text, name, pattern):
    """Locate the line in the caller that demonstrates the dependency."""
    lines = caller_text.split("\n")
    call_lines = [i for i, l in enumerate(lines) if re.search(rf"\b{re.escape(name)}\s*\(", l)]
    if not call_lines:
        return None
    for anchor in call_lines:
        window = range(max(0, anchor - 3), min(len(lines), anchor + 8))
        for i in window:
            if re.search(pattern, lines[i]):
                return (i + 1, lines[i])
    return None


def build_diff(defect: CrossFileDefect) -> str:
    """A unified diff of the defect and its distractors, in line order.

    The defect is not marked and is not placed first: nothing about its
    position distinguishes it from the harmless changes around it.
    """
    changes = list(defect.distractors) + [
        Change(defect.definition_line, defect.before, defect.after, is_defect=True)
    ]
    changes.sort(key=lambda c: c.line)

    header = (
        f"diff --git a/{defect.definition_path} b/{defect.definition_path}\n"
        f"--- a/{defect.definition_path}\n"
        f"+++ b/{defect.definition_path}\n"
    )
    body = []
    for change in changes:
        body.append(f"@@ -{max(1, change.line - 2)},5 +{max(1, change.line - 2)},5 @@")
        body.append(f"-{change.before}")
        body.append(f"+{change.after}")
    return header + "\n".join(body) + "\n"
