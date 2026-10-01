"""The generator's second version verifies evidence on the caller's syntax tree.

The first version located evidence by regular expression within eight lines of
any call to a same-named function. These tests pin the cases that version got
wrong: an unresolved name, a handler that also catches the new type, a None
check on an unrelated variable, a keyword the caller passes explicitly, and a
distractor that broke the file.
"""
import ast
import unittest

try:
    from experiments.crossfile import (
        VERIFIED_KINDS, find_defects, find_distractors, find_evidence, _detail,
    )
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


DEF = '''
def to_text(obj, errors="strict"):
    if obj is None:
        return None
    if not isinstance(obj, str):
        raise TypeError("obj must be a string type")
    return obj

def lookup(key, strict=True):
    """Find a thing."""
    data = dict()
    if key == None:
        return None
    return data.get(key)

def split_pair(value):
    head, tail = value.split(":", 1)
    return head, tail

def items(source):
    if not source:
        return []
    return list(source)
'''


def _fn(name):
    tree = ast.parse(DEF)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def _caller(src):
    return ast.parse(src), src.split("\n")


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ResolutionTests(unittest.TestCase):
    def test_unimported_name_is_not_evidence(self):
        tree, lines = _caller("def f(x):\n    try:\n        to_text(x)\n    except TypeError:\n        pass\n")
        self.assertIsNone(find_evidence(tree, lines, _fn("to_text"), "to_text", "lib/_text.py",
                                        "exception_type", {"old": "TypeError", "new": "ValueError"}))

    def test_bare_import_resolves(self):
        tree, lines = _caller("from lib._text import to_text\ndef f(x):\n    try:\n        to_text(x)\n    except TypeError:\n        pass\n")
        ev = find_evidence(tree, lines, _fn("to_text"), "to_text", "lib/_text.py",
                           "exception_type", {"old": "TypeError", "new": "ValueError"})
        self.assertEqual(ev[0], 5)
        self.assertIn("except TypeError", ev[1])
        self.assertEqual(ev[2], "TypeError")

    def test_module_import_resolves_attribute_call(self):
        tree, lines = _caller("from lib import _text\ndef f(x):\n    try:\n        _text.to_text(x)\n    except (ValueError, TypeError):\n        pass\n")
        ev = find_evidence(tree, lines, _fn("to_text"), "to_text", "lib/_text.py",
                           "exception_type", {"old": "TypeError", "new": "ValueError"})
        self.assertIsNone(ev, "the handler also catches the new type, so nothing breaks")

    def test_attribute_call_on_unrelated_object_is_not_a_call(self):
        tree, lines = _caller("from lib._text import to_text\ndef f(h):\n    try:\n        h.to_text()\n    except TypeError:\n        pass\n")
        self.assertIsNone(find_evidence(tree, lines, _fn("to_text"), "to_text", "lib/_text.py",
                                        "exception_type", {"old": "TypeError", "new": "ValueError"}))


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class KindVerifierTests(unittest.TestCase):
    def test_none_sentinel_needs_a_check_on_the_result(self):
        tree, lines = _caller("from lib.m import lookup\ndef f(k):\n    v = lookup(k)\n    if v is None:\n        return 0\n    return v\n")
        ev = find_evidence(tree, lines, _fn("lookup"), "lookup", "lib/m.py", "none_sentinel", {})
        self.assertEqual((ev[0], ev[2]), (4, "None"))

    def test_none_sentinel_rejects_a_check_on_another_variable(self):
        tree, lines = _caller("from lib.m import lookup\ndef f(k, w):\n    v = lookup(k)\n    if w is None:\n        return 0\n    return v\n")
        self.assertIsNone(find_evidence(tree, lines, _fn("lookup"), "lookup", "lib/m.py", "none_sentinel", {}))

    def test_default_flip_needs_the_keyword_omitted(self):
        fn = _fn("lookup")
        detail = _detail("default_flip", fn, "def lookup(key, strict=True):", "def lookup(key, strict=False):")
        self.assertEqual(detail, {"param": "strict", "index": 1})
        tree, lines = _caller("from lib.m import lookup\ndef f(k):\n    return lookup(k)\n")
        self.assertEqual(find_evidence(tree, lines, fn, "lookup", "lib/m.py", "default_flip", detail)[0], 3)
        tree, lines = _caller("from lib.m import lookup\ndef f(k):\n    return lookup(k, strict=True)\n")
        self.assertIsNone(find_evidence(tree, lines, fn, "lookup", "lib/m.py", "default_flip", detail))
        tree, lines = _caller("from lib.m import lookup\ndef f(k):\n    return lookup(k, True)\n")
        self.assertIsNone(find_evidence(tree, lines, fn, "lookup", "lib/m.py", "default_flip", detail))

    def test_tuple_order_needs_an_unpacking_assignment(self):
        tree, lines = _caller("from lib.m import split_pair\ndef f(v):\n    a, b = split_pair(v)\n    return a\n")
        ev = find_evidence(tree, lines, _fn("split_pair"), "split_pair", "lib/m.py", "tuple_order", {})
        self.assertEqual((ev[0], ev[2]), (3, "a,b"))
        tree, lines = _caller("from lib.m import split_pair\ndef f(v):\n    pair = split_pair(v)\n    return pair\n")
        self.assertIsNone(find_evidence(tree, lines, _fn("split_pair"), "split_pair", "lib/m.py", "tuple_order", {}))

    def test_empty_to_none_needs_iteration_or_len(self):
        tree, lines = _caller("from lib.m import items\ndef f(s):\n    for x in items(s):\n        print(x)\n")
        ev = find_evidence(tree, lines, _fn("items"), "items", "lib/m.py", "empty_to_none", {})
        self.assertEqual((ev[0], ev[2]), (3, "iterates"))
        tree, lines = _caller("from lib.m import items\ndef f(s):\n    return items(s)\n")
        self.assertIsNone(find_evidence(tree, lines, _fn("items"), "items", "lib/m.py", "empty_to_none", {}))


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class DistractorTests(unittest.TestCase):
    def test_docstring_lines_are_never_rewritten(self):
        lines = DEF.split("\n")
        out = find_distractors(lines, exclude_line=99, wanted=10, window=200)
        for change in out:
            self.assertNotIn('"""', change.before)

    def test_every_distractor_leaves_the_file_parseable(self):
        lines = DEF.split("\n")
        for change in find_distractors(lines, exclude_line=99, wanted=10, window=200):
            trial = list(lines); trial[change.line - 1] = change.after
            ast.parse("\n".join(trial))

    def test_a_rewrite_that_breaks_the_file_is_rejected(self):
        from experiments.crossfile import _still_parses
        lines = ["def f():", "    return dict()", ""]
        self.assertTrue(_still_parses(lines, 1, "    return {}"))
        self.assertFalse(_still_parses(lines, 1, "    return {"))
        self.assertFalse(_still_parses(lines, 0, "def f(:"))


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class EndToEndTests(unittest.TestCase):
    def test_only_verified_kinds_are_generated_and_ids_carry_the_line(self):
        caller = ("from pkg.m import to_text, lookup, split_pair, items\n"
                  "def g(x, k, v, s):\n"
                  "    try:\n        to_text(x)\n    except TypeError:\n        pass\n"
                  "    r = lookup(k)\n    if r is None:\n        return\n"
                  "    a, b = split_pair(v)\n"
                  "    for i in items(s):\n        pass\n")
        found = find_defects({"pkg/m.py": DEF, "pkg/c.py": caller}, max_per_repo=20)
        self.assertTrue(found)
        for d in found:
            self.assertIn(d.kind, VERIFIED_KINDS)
            self.assertEqual(d.defect_id.count("::"), 3)
            self.assertTrue(d.argument)
            self.assertGreaterEqual(len(d.distractors), 2)
        self.assertEqual(len({d.defect_id for d in found}), len(found))


if __name__ == "__main__":
    unittest.main()
