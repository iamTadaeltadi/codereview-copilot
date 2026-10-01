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
    argument: str = ""
    via_path: str = ""
    via_line: int = 0
    via_name: str = ""

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



def _default_token(name, value):
    """`name=True`, `name: bool = True`, `name : Optional[bool]=True` — the
    annotated forms are how typed codebases write it, and the first version
    matched only the bare form, so no default-flip task could come from a
    typed repository. Returns a compiled pattern over one source line."""
    return re.compile(rf"\b{re.escape(name)}\s*(?::\s*[^=,)]+?)?\s*=\s*{value}\b")


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
        # The default may sit on a later line of a multi-line signature.
        lineno = getattr(default, "lineno", fn.lineno)
        before = _line(lines, lineno)
        pattern = _default_token(name, default.value)
        match = pattern.search(before)
        if not match:
            continue
        after = before[: match.start()] + match.group(0).replace(str(default.value), str(not default.value)) + before[match.end():]
        return (
            lineno,
            before,
            after,
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


def _distract_spacing(line):
    """`f(a,b)` -> `f(a, b)`: whitespace after a comma that is a token, not a
    character inside a string. Whitespace outside literals cannot change
    behaviour, and this is the commonest tidy-up in real pull requests. Found
    with the tokenizer so a comma inside a string is never touched; a line
    the tokenizer cannot read on its own is left alone."""
    import io, tokenize
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(line + "\n").readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return None
    for t in toks:
        if t.type == tokenize.OP and t.string == ",":
            end = t.end[1]
            if end < len(line) and line[end] not in " \n)" and line[end] != ",":
                return line[:end] + " " + line[end:]
    return None


DISTRACTORS = (
    _distract_quote_style,
    _distract_none_comparison,
    _distract_empty_literal,
    _distract_redundant_parens,
    _distract_spacing,
)


def _still_parses(lines, index, replacement):
    """Apply one rewrite to a copy of the file and check it still parses.

    The first version of the quote-style rewrite matched the empty string
    between two of the three quotes in a docstring and produced ''" — a syntax
    error in 304 hunks across 145 of 204 tasks. A model that flagged it was
    right, and the scorer counted it as a confirmed false positive. Every
    distractor is now applied to the whole file and rejected unless the file
    still parses; a rewrite that changes behaviour cannot be excluded this way,
    but one that breaks the file can.
    """
    trial = list(lines)
    trial[index] = replacement
    try:
        ast.parse("\n".join(trial))
    except SyntaxError:
        return False
    return True


def find_distractors(lines, exclude_line, wanted=3, window=60):
    """Harmless rewrites on other lines near the defect, each parse-checked."""
    out = []
    lo = max(0, exclude_line - window)
    hi = min(len(lines), exclude_line + window)
    for index in range(lo, hi):
        lineno = index + 1
        if lineno == exclude_line:
            continue
        original = lines[index]
        stripped = original.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if '"""' in original or "'''" in original:
            continue
        for rewrite in DISTRACTORS:
            changed = rewrite(original)
            if changed and changed != original and _still_parses(lines, index, changed):
                out.append(Change(lineno, original, changed, is_defect=False))
                break
        if len(out) >= wanted:
            break
    return tuple(out)


# --- resolution and verification -------------------------------------------
# The first version located "evidence" with a regular expression within eight
# lines of any call to a function of the same name, in any file. No import was
# resolved and no structure was checked, so a mutation to `auth` was recorded
# as demonstrated by `creds = RemoteCredentials(...)`. Measured after the fact:
# the evidence line actually called the mutated function in 65 of 65
# default_flip tasks and in 18 of 139 tasks of every other kind.
#
# Every kind below is now verified on the caller's syntax tree: the call must
# resolve to the definition through an import, and the relationship the
# mutation breaks must be present as a node, not as a pattern of characters.
# Kinds for which no such check exists are not generated.

VERIFIED_KINDS = (
    "exception_type",
    "none_sentinel",
    "default_flip",
    "tuple_order",
    "empty_to_none",
)


def _parents(tree):
    out = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[child] = node
    return out


def _enclosing(node, parents, kinds=(ast.FunctionDef, ast.AsyncFunctionDef)):
    while node in parents:
        node = parents[node]
        if isinstance(node, kinds):
            return node
    return None


def _resolves(tree, name, definition_path):
    """Does this module import `name`, or the module that defines it?

    Returns the alias under which the module is bound when it is imported as a
    module, or True for a bare-name import, or None.
    """
    stem = definition_path.rsplit("/", 1)[-1].removesuffix(".py")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(a.name == name for a in node.names):
                return True
            if node.module and node.module.split(".")[-1] == stem:
                if any(a.name == "*" for a in node.names):
                    return True
                if any(a.name == stem for a in node.names):
                    return next(a.asname or a.name for a in node.names if a.name == stem)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[-1] == stem:
                    return a.asname or a.name.split(".")[-1]
    return None


def _calls(tree, name, bound):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if bound is True and isinstance(f, ast.Name) and f.id == name:
            yield node
        elif isinstance(bound, str) and isinstance(f, ast.Attribute) and f.attr == name \
                and isinstance(f.value, ast.Name) and f.value.id == bound:
            yield node


def _names_in(node):
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Tuple):
        return {e.id for e in node.elts if isinstance(e, ast.Name)}
    return set()


def _assigned_to(call, parents):
    """The variable a call's result is bound to, if it is bound to exactly one."""
    parent = parents.get(call)
    if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name):
        return parent.targets[0].id
    if isinstance(parent, (ast.AnnAssign,)) and isinstance(parent.target, ast.Name):
        return parent.target.id
    return None


def _verify_exception_type(fn, call, parents, lines, detail):
    old, new = detail["old"], detail["new"]
    node = call
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return None
        if isinstance(node, ast.Try):
            for h in node.handlers:
                caught = _names_in(h.type) if h.type is not None else set()
                if old in caught and new not in caught:
                    return h.lineno, old
            return None
    return None


def _verify_none_sentinel(fn, call, parents, lines, detail):
    owner = _enclosing(call, parents)
    if owner is None:
        return None
    var = _assigned_to(call, parents)
    for node in ast.walk(owner):
        if not isinstance(node, ast.Compare) or len(node.comparators) != 1:
            continue
        if not isinstance(node.comparators[0], ast.Constant) or node.comparators[0].value is not None:
            continue
        if not isinstance(node.ops[0], (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)):
            continue
        left = node.left
        if left is call or (var and isinstance(left, ast.Name) and left.id == var):
            return node.lineno, "None"
    return None


def _verify_default_flip(fn, call, parents, lines, detail):
    param, index = detail["param"], detail["index"]
    if any(k.arg == param for k in call.keywords):
        return None
    if any(k.arg is None for k in call.keywords) or any(isinstance(a, ast.Starred) for a in call.args):
        return None
    if len(call.args) > index:
        return None
    return call.lineno, param


def _verify_tuple_order(fn, call, parents, lines, detail):
    parent = parents.get(call)
    if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Tuple):
        names = [e.id for e in parent.targets[0].elts if isinstance(e, ast.Name)]
        if len(names) >= 2 and len(names) == len(parent.targets[0].elts):
            return parent.lineno, ",".join(names)
    return None


def _verify_empty_to_none(fn, call, parents, lines, detail):
    owner = _enclosing(call, parents)
    if owner is None:
        return None
    var = _assigned_to(call, parents)
    def is_result(node):
        return node is call or (var and isinstance(node, ast.Name) and node.id == var)
    for node in ast.walk(owner):
        if isinstance(node, (ast.For, ast.comprehension)) and is_result(node.iter):
            return node.lineno if isinstance(node, ast.For) else owner.lineno, "iterates"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len" \
                and node.args and is_result(node.args[0]):
            return node.lineno, "len"
    return None


VERIFIERS = {
    "exception_type": _verify_exception_type,
    "none_sentinel": _verify_none_sentinel,
    "default_flip": _verify_default_flip,
    "tuple_order": _verify_tuple_order,
    "empty_to_none": _verify_empty_to_none,
}


def _detail(kind, fn, before, after):
    """What the verifier needs to know about the mutation, from the lines."""
    if kind == "exception_type":
        m = re.search(r"raise\s+(\w+)", before); n = re.search(r"raise\s+(\w+)", after)
        return {"old": m.group(1), "new": n.group(1)} if m and n else None
    if kind == "default_flip":
        defaults = fn.args.defaults
        args = fn.args.args[len(fn.args.args) - len(defaults):]
        for arg, default in zip(args, defaults):
            if isinstance(default, ast.Constant) and isinstance(default.value, bool):
                if _default_token(arg.arg, default.value).search(before) and \
                        _default_token(arg.arg, not default.value).search(after):
                    return {"param": arg.arg, "index": fn.args.args.index(arg)}
        return None
    return {}


def find_evidence(caller_tree, caller_lines, fn, name, definition_path, kind, detail):
    """The line in the caller that demonstrates the dependency, verified on
    the syntax tree. Returns (lineno, text, argument) or None."""
    bound = _resolves(caller_tree, name, definition_path)
    if bound is None:
        return None
    parents = _parents(caller_tree)
    verify = VERIFIERS[kind]
    for call in _calls(caller_tree, name, bound):
        found = verify(fn, call, parents, caller_lines, detail)
        if found:
            lineno, argument = found
            return lineno, caller_lines[lineno - 1], argument
    return None


def find_defects(sources, max_per_repo: int = 3, kinds=VERIFIED_KINDS, min_distractors: int = 2):
    """Yield defects where a mutation in one file breaks an assumption that a
    different file demonstrably makes, verified on that file's syntax tree."""
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
            candidates = [
                (other, otree, olines)
                for other, (otree, olines, otext) in parsed.items()
                if other != path and not is_test_path(other) and _calls_name(otext, fn.name)
            ]
            if not candidates:
                continue
            for kind in kinds:
                result = MUTATIONS[kind](fn, lines)
                if not result:
                    continue
                lineno, before, after, why, _pattern = result
                detail = _detail(kind, fn, before, after)
                if detail is None:
                    continue
                for caller_path, caller_tree, caller_lines in candidates:
                    evidence = find_evidence(caller_tree, caller_lines, fn, fn.name, path, kind, detail)
                    if not evidence:
                        continue
                    distractors = find_distractors(lines, lineno)
                    if len(distractors) < min_distractors:
                        break
                    found.append(
                        CrossFileDefect(
                            defect_id=f"{path}::{fn.name}::{kind}::{lineno}",
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
                            distractors=distractors,
                            argument=evidence[2],
                        )
                    )
                    break
                if len(found) >= max_per_repo:
                    return found
    return found


# --- safe twins ------------------------------------------------------------
# Every task above is a defect, and the mutated line looks the same whether or
# not a caller depends on it: `return None` -> `return -1` is a defect for a
# caller that checks `is None` and harmless for one that does not. A reviewer
# that flags every such change scores at ceiling on hit without ever reading a
# caller. Measured on the rebuilt benchmark: 97% hit for the diff alone, and a
# blind judge accepted the diff-only mechanism statement 69% of the time,
# because the mechanism is inferable from the mutation kind.
#
# A twin is the same surface mutation where the shown caller is verifiably
# robust to it. The diff cannot tell the two apart; only the caller can. The
# task becomes a discrimination, which is the first form of it on which
# evidence, and therefore structure, can matter.

TWIN_KINDS = ("exception_type", "default_flip")


def _robust_exception_type(fn, call, parents, lines, detail):
    old, new = detail["old"], detail["new"]
    node = call
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return None
        if isinstance(node, ast.Try):
            for h in node.handlers:
                if h.type is None:
                    return h.lineno, "bare-except"
                caught = _names_in(h.type)
                if old in caught and new in caught:
                    return h.lineno, f"{old},{new}"
                if caught & {"Exception", "BaseException"}:
                    return h.lineno, "Exception"
            return None
    return None


def _robust_default_flip(fn, call, parents, lines, detail):
    param, index = detail["param"], detail["index"]
    if any(k.arg == param for k in call.keywords):
        return call.lineno, param
    if len(call.args) > index and not any(isinstance(a, ast.Starred) for a in call.args):
        return call.lineno, param
    return None


ROBUST = {"exception_type": _robust_exception_type, "default_flip": _robust_default_flip}


def find_robust_caller(caller_tree, caller_lines, fn, name, definition_path, kind, detail):
    bound = _resolves(caller_tree, name, definition_path)
    if bound is None:
        return None
    parents = _parents(caller_tree)
    for call in _calls(caller_tree, name, bound):
        found = ROBUST[kind](fn, call, parents, caller_lines, detail)
        if found:
            lineno, argument = found
            return lineno, caller_lines[lineno - 1], argument
    return None


def find_twins(sources, max_per_repo: int = 8, kinds=TWIN_KINDS, min_distractors: int = 2):
    """Mutations that look like the defects above but are safe for the shown
    caller, with no caller in the pool that depends on the old behaviour.

    Absence of a dependent caller is checked against the pool, not the
    repository; a dependent caller outside the pool would make the twin a
    defect. That is a stated limitation of every twin."""
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
            candidates = [
                (other, otree, olines)
                for other, (otree, olines, otext) in parsed.items()
                if other != path and not is_test_path(other) and _calls_name(otext, fn.name)
            ]
            if not candidates:
                continue
            for kind in kinds:
                result = MUTATIONS[kind](fn, lines)
                if not result:
                    continue
                lineno, before, after, why, _ = result
                detail = _detail(kind, fn, before, after)
                if detail is None:
                    continue
                if any(find_evidence(ct, cl, fn, fn.name, path, kind, detail) for _, ct, cl in candidates):
                    continue
                for caller_path, caller_tree, caller_lines in candidates:
                    robust = find_robust_caller(caller_tree, caller_lines, fn, fn.name, path, kind, detail)
                    if not robust:
                        continue
                    distractors = find_distractors(lines, lineno)
                    if len(distractors) < min_distractors:
                        break
                    found.append(CrossFileDefect(
                        defect_id=f"{path}::{fn.name}::{kind}::{lineno}::safe",
                        kind=kind, definition_path=path, definition_name=fn.name,
                        definition_line=lineno, caller_path=caller_path, caller_name=fn.name,
                        caller_line=robust[0], before=before, after=after,
                        why=f"safe for this caller: it {_robust_reason(kind, robust[2])}",
                        evidence=robust[1].strip(), distractors=distractors, argument=robust[2],
                    ))
                    break
                if len(found) >= max_per_repo:
                    return found
    return found


def _robust_reason(kind, argument):
    if kind == "exception_type":
        return {"bare-except": "catches every exception", "Exception": "catches Exception"}.get(
            argument, f"catches both {argument.replace(',', ' and ')}")
    return f"passes {argument} explicitly, so the default is never used"


# --- two-hop chains ----------------------------------------------------------
# A one-hop task gives a dependency map almost nothing to do: two snippets and
# one edge. In a chain the definition f is called by a pass-through g in a
# second file, which returns f's result unchanged, and the dependent check sits
# in h in a third file around a call to g. The map's job is to connect h's
# check to f's change through g, which is the first task here where structure
# has something to carry.

CHAIN_KINDS = ("exception_type", "none_sentinel", "tuple_order", "empty_to_none")


def _passthrough_line(tree, name, bound, parents):
    """The line in this module where a call to `name` is returned directly,
    or assigned to a variable that is then returned, and the enclosing
    function's name. None if the module does not pass the result through."""
    for call in _calls(tree, name, bound):
        owner = _enclosing(call, parents)
        if owner is None:
            continue
        parent = parents.get(call)
        if isinstance(parent, ast.Return):
            return parent.lineno, owner.name
        var = _assigned_to(call, parents)
        if var:
            for node in ast.walk(owner):
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Name) and node.value.id == var:
                    return node.lineno, owner.name
    return None


def find_chains(sources, max_per_repo: int = 8, kinds=CHAIN_KINDS, min_distractors: int = 2):
    """Defects whose dependent check is two calls away through a pass-through."""
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
            mids = [(o, ot, ol) for o, (ot, ol, otx) in parsed.items()
                    if o != path and not is_test_path(o) and _calls_name(otx, fn.name)]
            if not mids:
                continue
            for kind in kinds:
                result = MUTATIONS[kind](fn, lines)
                if not result:
                    continue
                lineno, before, after, why, _ = result
                detail = _detail(kind, fn, before, after)
                if detail is None:
                    continue
                hit = None
                for mid_path, mid_tree, mid_lines in mids:
                    bound = _resolves(mid_tree, fn.name, path)
                    if bound is None:
                        continue
                    through = _passthrough_line(mid_tree, fn.name, bound, _parents(mid_tree))
                    if not through:
                        continue
                    via_line, g_name = through
                    g_fn = next((n for n in ast.walk(mid_tree)
                                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == g_name), None)
                    if g_fn is None or g_name.startswith("_"):
                        continue
                    ends = [(o, ot, ol) for o, (ot, ol, otx) in parsed.items()
                            if o not in (path, mid_path) and not is_test_path(o) and _calls_name(otx, g_name)]
                    for end_path, end_tree, end_lines in ends:
                        ev = find_evidence(end_tree, end_lines, g_fn, g_name, mid_path, kind, detail)
                        if ev:
                            hit = (mid_path, via_line, g_name, end_path, ev)
                            break
                    if hit:
                        break
                if not hit:
                    continue
                distractors = find_distractors(lines, lineno)
                if len(distractors) < min_distractors:
                    continue
                mid_path, via_line, g_name, end_path, ev = hit
                found.append(CrossFileDefect(
                    defect_id=f"{path}::{fn.name}::{kind}::{lineno}::hop2",
                    kind=kind, definition_path=path, definition_name=fn.name, definition_line=lineno,
                    caller_path=end_path, caller_name=g_name, caller_line=ev[0],
                    before=before, after=after,
                    why=why + f"; the result reaches the caller through `{g_name}`, which returns it unchanged",
                    evidence=ev[1].strip(), distractors=distractors, argument=ev[2],
                    via_path=mid_path, via_line=via_line, via_name=g_name,
                ))
                if len(found) >= max_per_repo:
                    return found
    return found


def _find_evidence(caller_text, name, pattern):
    """The regex locator the first benchmark used. Kept only so the old
    data can be re-examined; find_defects no longer calls it."""
    lines = caller_text.split("\n")
    call_lines = [i for i, l in enumerate(lines) if re.search(rf"\b{re.escape(name)}\s*\(", l)]
    for anchor in call_lines:
        for i in range(max(0, anchor - 3), min(len(lines), anchor + 8)):
            if re.search(pattern, lines[i]):
                return (i + 1, lines[i])
    return None


def build_diff(defect: CrossFileDefect) -> str:
    """A unified diff of the defect and its distractors, in line order.

    Each change is its own single-line hunk whose header names the line the
    change is actually on. An earlier version started the header two lines
    above and then showed the changed line immediately, so every line number a
    reviewer could compute from the diff was wrong by two and no reviewer could
    ever name the defect's line exactly.

    The defect is not marked and is not placed first: nothing about its
    position distinguishes it from the harmless changes around it.
    """
    changes = list(defect.distractors) + [
        Change(defect.definition_line, defect.before, defect.after, is_defect=True)
    ]
    changes.sort(key=lambda c: c.line)

    body = [
        f"diff --git a/{defect.definition_path} b/{defect.definition_path}",
        f"--- a/{defect.definition_path}",
        f"+++ b/{defect.definition_path}",
    ]
    for change in changes:
        body.append(f"@@ -{change.line},1 +{change.line},1 @@")
        body.append(f"-{change.before}")
        body.append(f"+{change.after}")
    return "\n".join(body) + "\n"
