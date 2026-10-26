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
import random
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


_CALLED = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _called_names(source: str) -> set:
    """Every identifier immediately followed by `(` in a file, computed once.

    find_defects asked, for every function, whether every other file calls
    its name, with a regex search over the whole file each time: quadratic in
    files and linear in functions, which was eleven minutes per repository on
    a 300-file pool. One pass per file and a set lookup per function instead.
    """
    return set(_CALLED.findall(source))


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
    """Swap a returned pair, where a caller unpacks it into two names.

    The swap uses the syntax tree's column spans for the two elements, not a
    regular expression. The first version split the line at its first comma,
    so `return (host, port)` became `return port), (host` and `return a, f(x, y)`
    was cut inside the call. Five of forty hand-checked messages were the
    model correctly reporting a syntax error the generator had introduced.
    """
    for node in _returns(fn):
        value = node.value
        if not (isinstance(value, ast.Tuple) and len(value.elts) == 2):
            continue
        a, b = value.elts
        if not all(getattr(e, "lineno", None) == node.lineno == getattr(e, "end_lineno", None) for e in (a, b)):
            continue
        before = _line(lines, node.lineno)
        a_src = before[a.col_offset:a.end_col_offset]
        b_src = before[b.col_offset:b.end_col_offset]
        after = before[:a.col_offset] + b_src + before[a.end_col_offset:b.col_offset] + a_src + before[b.end_col_offset:]
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


def _distract_quote_style_reverse(line):
    """`'text'` -> `"text"`, the mirror of the rewrite above, so a diff is not
    a one-way stream of double-to-single changes."""
    match = re.search(r"'([^'\\{}]*)'", line)
    if match and '"' not in match.group(1) and match.group(1):
        return line[: match.start()] + '"' + match.group(1) + '"' + line[match.end():]
    return None


def _distract_parenthesise_return(line):
    """`return x + y` -> `return (x + y)`; the tree is unchanged."""
    match = re.match(r"^(\s*return )([^(#][^#]*?)\s*$", line)
    if match and not match.group(2).endswith(":"):
        return f"{match.group(1)}({match.group(2)})"
    return None


def _distract_parenthesise_rhs(line):
    """`x = a + b` -> `x = (a + b)` for a plain assignment; the tree is unchanged."""
    match = re.match(r"^(\s*[A-Za-z_][\w.]*\s*=\s*)([^=(#\s][^#]*?)\s*$", line)
    if match and "==" not in line and not match.group(2).endswith((":", "\\", ",")):
        return f"{match.group(1)}({match.group(2)})"
    return None


DISTRACTORS = (
    _distract_quote_style,
    _distract_parenthesise_return,
    _distract_quote_style_reverse,
    _distract_parenthesise_rhs,
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


AST_NEUTRAL = (_distract_quote_style, _distract_quote_style_reverse, _distract_parenthesise_return,
               _distract_parenthesise_rhs, _distract_redundant_parens, _distract_spacing)


def _same_ast(lines, index, replacement):
    """Apply one rewrite to a copy of the file and require an identical syntax
    tree, so the rewrite cannot change behaviour. Parse-checking alone let a
    quote-style rewrite through when it merged or split a string."""
    trial = list(lines)
    trial[index] = replacement
    try:
        return ast.dump(ast.parse("\n".join(trial))) == ast.dump(ast.parse("\n".join(lines)))
    except (SyntaxError, ValueError, RecursionError):
        return False


def _distract_one(lines, index, order):
    original = lines[index]
    stripped = original.strip()
    if not stripped or stripped.startswith("#") or '"""' in original or "'''" in original:
        return None
    for rewrite in order:
        changed = rewrite(original)
        if not changed or changed == original:
            continue
        ok = _same_ast(lines, index, changed) if rewrite in AST_NEUTRAL else _still_parses(lines, index, changed)
        if ok:
            return Change(index + 1, original, changed, is_defect=False)
    return None


def find_distractors(lines, exclude_line, wanted=3, window=60, seed=""):
    """Harmless rewrites on other lines near the defect.

    Each rewrite must leave the file's syntax tree unchanged (quote style,
    parentheses, spacing) or, for the two idiom swaps, still parse. They are
    placed on both sides of the defect with a seeded split, so the defect is
    not predictably the last change in the diff; the first version scanned
    upward from sixty lines above and the defect came last in 62% of tasks.
    The rewrite tried first rotates per line, so one kind does not dominate.
    """
    rng = random.Random(seed or str(exclude_line))
    above, below = [], []
    for distance in range(1, window + 1):
        for lineno, bucket in ((exclude_line - distance, above), (exclude_line + distance, below)):
            if len(bucket) >= wanted or not (1 <= lineno <= len(lines)):
                continue
            k = lineno % len(DISTRACTORS)
            order = DISTRACTORS[k:] + DISTRACTORS[:k]
            change = _distract_one(lines, lineno - 1, order)
            if change:
                bucket.append(change)
        if len(above) >= wanted and len(below) >= wanted:
            break
    k_above = min(len(above), rng.randint(0, wanted))
    k_below = min(len(below), wanted - k_above)
    k_above = min(len(above), wanted - k_below)
    chosen = above[:k_above] + below[:k_below]
    return tuple(sorted(chosen, key=lambda c: c.line))


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


def _module_of(path: str) -> str:
    """Dotted module name of a repository-relative file path."""
    mod = path[:-3] if path.endswith(".py") else path
    if mod.endswith("/__init__"):
        mod = mod[: -len("/__init__")]
    return mod.replace("/", ".")


def _absolute_import(module, level: int, importer_path: str) -> str:
    """The dotted module an import statement names, with relative dots resolved
    against the importing file. Unknown importer: the dots are dropped and the
    name is matched by suffix, which is weaker but never wrong by prefix."""
    module = module or ""
    if not level:
        return module
    if not importer_path:
        return module
    package = _module_of(importer_path).split(".")
    if not importer_path.endswith("__init__.py"):
        package = package[:-1]
    base = package[: len(package) - (level - 1)] if level > 1 else package
    return ".".join([*base, module] if module else base)


def _module_matches(imported: str, definition_path: str) -> bool:
    """`imported` names the definition module exactly, or by a suffix that
    accounts for a `src/` or `lib/` prefix in the repository path."""
    if not imported:
        return False
    target = _module_of(definition_path)
    return target == imported or target.endswith("." + imported)


def _package_init(sources, imported: str):
    """The `__init__.py` of the package `imported` names, if it is in the pool."""
    if not sources or not imported:
        return None
    tail = imported.replace(".", "/") + "/__init__.py"
    for path in sources:
        if path == tail or path.endswith("/" + tail):
            return path
    return None


def _reexports(sources, imported: str, name: str, definition_path: str, depth: int = 3) -> bool:
    """Does package `imported` re-export `name` from the definition module?

    `from scipy.stats import skew` is only evidence about `scipy/stats/_stats_py.py`
    if `scipy/stats/__init__.py` imports `skew` from there. The first version
    accepted any `from X import name`, whatever X was, so a caller using a
    different function of the same name was recorded as depending on the
    mutated one."""
    if depth <= 0:
        return False
    init = _package_init(sources, imported)
    if init is None:
        return False
    try:
        tree = ast.parse(sources[init])
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if not any(a.name in (name, "*") for a in node.names):
            continue
        target = _absolute_import(node.module, node.level, init)
        if _module_matches(target, definition_path):
            return True
        if _reexports(sources, target, name, definition_path, depth - 1):
            return True
    return False


def _resolves(tree, name, definition_path, importer_path: str = "", sources=None):
    """Does this module import `name` from the module that defines it, or that
    module itself?

    Returns the alias under which the module is bound when it is imported as a
    module, True for a bare-name import that resolves to the definition, or
    None. A `from X import name` counts only when X is the definition module
    or a package in the pool that re-exports `name` from it.
    """
    stem = _module_of(definition_path).split(".")[-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported = _absolute_import(node.module, node.level, importer_path)
            if any(a.name == name for a in node.names):
                if _module_matches(imported, definition_path) or _reexports(sources, imported, name, definition_path):
                    return True
                continue
            if any(a.name == "*" for a in node.names) and _module_matches(imported, definition_path):
                return True
            if any(a.name == stem for a in node.names) and _module_matches(
                    f"{imported}.{stem}" if imported else stem, definition_path):
                return next(a.asname or a.name for a in node.names if a.name == stem)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if _module_matches(a.name, definition_path):
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
    # The first version returned the enclosing function's `def` line for a
    # comprehension (ast.comprehension has no lineno), so the evidence line
    # named a signature rather than the iteration; and it missed list(x),
    # which raises on None just as a for loop does.
    hits = []
    for node in ast.walk(owner):
        if isinstance(node, (ast.For, ast.comprehension)) and is_result(node.iter):
            hits.append((node.lineno if isinstance(node, ast.For) else node.iter.lineno, "iterates"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args and is_result(node.args[0]):
            if node.func.id == "len":
                hits.append((node.lineno, "len"))
            elif node.func.id in ("list", "tuple", "set", "sorted", "frozenset"):
                hits.append((node.lineno, "iterates"))
    return min(hits) if hits else None


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


def find_evidence(caller_tree, caller_lines, fn, name, definition_path, kind, detail,
                  caller_path: str = "", sources=None):
    """The line in the caller that demonstrates the dependency, verified on
    the syntax tree. Returns (lineno, text, argument) or None."""
    bound = _resolves(caller_tree, name, definition_path, caller_path, sources)
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
    called = {path: _called_names(text) for path, (_, _, text) in parsed.items()}
    texts = {path: text for path, (_, _, text) in parsed.items()}

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
                if other != path and not is_test_path(other) and fn.name in called[other]
            ]
            if not candidates:
                continue
            for kind in kinds:
                result = MUTATIONS[kind](fn, lines)
                if not result:
                    continue
                lineno, before, after, why, _pattern = result
                if not _still_parses(lines, lineno - 1, after):
                    continue
                detail = _detail(kind, fn, before, after)
                if detail is None:
                    continue
                for caller_path, caller_tree, caller_lines in candidates:
                    evidence = find_evidence(caller_tree, caller_lines, fn, fn.name, path, kind, detail,
                                             caller_path, texts)
                    if not evidence:
                        continue
                    distractors = find_distractors(lines, lineno, seed=f"{path}:{lineno}")
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


def find_robust_caller(caller_tree, caller_lines, fn, name, definition_path, kind, detail,
                       caller_path: str = "", sources=None):
    bound = _resolves(caller_tree, name, definition_path, caller_path, sources)
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
    called = {path: _called_names(text) for path, (_, _, text) in parsed.items()}
    texts = {path: text for path, (_, _, text) in parsed.items()}
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
                if other != path and not is_test_path(other) and fn.name in called[other]
            ]
            if not candidates:
                continue
            for kind in kinds:
                result = MUTATIONS[kind](fn, lines)
                if not result:
                    continue
                lineno, before, after, why, _ = result
                if not _still_parses(lines, lineno - 1, after):
                    continue
                detail = _detail(kind, fn, before, after)
                if detail is None:
                    continue
                if _dependent_call_anywhere(parsed, texts, fn, fn.name, path, kind, detail):
                    continue
                for caller_path, caller_tree, caller_lines in candidates:
                    robust = find_robust_caller(caller_tree, caller_lines, fn, fn.name, path, kind, detail,
                                                caller_path, texts)
                    if not robust:
                        continue
                    distractors = find_distractors(lines, lineno, seed=f"{path}:{lineno}")
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


def _dependent_call_anywhere(parsed, texts, fn, name, path, kind, detail):
    """Any call in the pool that the mutation would break: in another file
    through a resolved import, in the definition's own file, or through an
    attribute `x.name(...)` whose receiver cannot be resolved and is therefore
    assumed to be this function. Finding one makes the twin a defect, so the
    candidate is dropped. The first version checked only resolved cross-file
    callers; same-file calls and `module.f()` calls were invisible, and a
    reviewer that flagged such a twin was right."""
    verify = VERIFIERS[kind]
    for other, (tree, lines, _) in parsed.items():
        if is_test_path(other):
            continue
        bound = True if other == path else _resolves(tree, name, path, other, texts)
        calls = list(_calls(tree, name, bound)) if bound is not None else []
        seen = set(map(id, calls))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == name and id(node) not in seen:
                calls.append(node)
        if not calls:
            continue
        parents = _parents(tree)
        for call in calls:
            if verify(fn, call, parents, lines, detail):
                return other, call.lineno
    return None


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
    called = {path: _called_names(text) for path, (_, _, text) in parsed.items()}
    texts = {path: text for path, (_, _, text) in parsed.items()}
    found = []
    for path, (tree, lines, text) in parsed.items():
        if is_test_path(path):
            continue
        for fn in _functions(tree, lines):
            if fn.name.startswith("_") or fn.name in {"__init__", "main"}:
                continue
            mids = [(o, ot, ol) for o, (ot, ol, otx) in parsed.items()
                    if o != path and not is_test_path(o) and fn.name in called[o]]
            if not mids:
                continue
            for kind in kinds:
                result = MUTATIONS[kind](fn, lines)
                if not result:
                    continue
                lineno, before, after, why, _ = result
                if not _still_parses(lines, lineno - 1, after):
                    continue
                detail = _detail(kind, fn, before, after)
                if detail is None:
                    continue
                hit = None
                for mid_path, mid_tree, mid_lines in mids:
                    bound = _resolves(mid_tree, fn.name, path, mid_path, texts)
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
                            if o not in (path, mid_path) and not is_test_path(o) and g_name in called[o]]
                    for end_path, end_tree, end_lines in ends:
                        ev = find_evidence(end_tree, end_lines, g_fn, g_name, mid_path, kind, detail,
                                           end_path, texts)
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
