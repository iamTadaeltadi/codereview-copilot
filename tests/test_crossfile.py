import unittest

try:
    from experiments.crossfile import MUTATIONS, build_diff, find_defects

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def sources(**files):
    return {k.replace("__", "/") + ".py": v for k, v in files.items()}


SENTINEL = {
    "pkg/utils.py": "def find_index(items, target):\n    for i, x in enumerate(items):\n        if x == target:\n            return i\n    return None\n",
    "pkg/handlers.py": "from pkg.utils import find_index\n\n\ndef lookup(rows, key):\n    idx = find_index(rows, key)\n    if idx is None:\n        raise KeyError(key)\n    return rows[idx]\n",
}


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class HardnessGuaranteeTests(unittest.TestCase):
    """The properties that make a generated task a fair test of context.

    A task is only emitted when a *different* file demonstrably depends on the
    behaviour being changed. Without that check the mutation is not a defect at
    all, and a benchmark of non-defects measures nothing.
    """

    def test_a_defect_is_found_when_another_file_depends_on_the_behaviour(self):
        found = find_defects(SENTINEL, min_distractors=0)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].kind, "none_sentinel")

    def test_no_defect_when_nothing_calls_the_function(self):
        only = {"pkg/utils.py": SENTINEL["pkg/utils.py"]}
        self.assertEqual(find_defects(only, min_distractors=0), [])

    def test_no_defect_when_the_caller_does_not_depend_on_the_behaviour(self):
        indifferent = dict(SENTINEL)
        indifferent["pkg/handlers.py"] = (
            "from pkg.utils import find_index\n\n\n"
            "def lookup(rows, key):\n"
            "    return find_index(rows, key)\n"   # never checks for None
        )
        self.assertEqual(find_defects(indifferent, min_distractors=0), [])

    def test_no_defect_when_the_only_caller_is_in_the_same_file(self):
        same_file = {
            "pkg/utils.py": SENTINEL["pkg/utils.py"]
            + "\n\ndef lookup(rows, key):\n    idx = find_index(rows, key)\n    if idx is None:\n        raise KeyError(key)\n    return rows[idx]\n"
        }
        self.assertEqual(find_defects(same_file, min_distractors=0), [])

    def test_the_defect_and_its_caller_are_always_in_different_files(self):
        for defect in find_defects(SENTINEL, min_distractors=0):
            self.assertNotEqual(defect.definition_path, defect.caller_path)

    def test_the_evidence_line_comes_from_the_caller(self):
        defect = find_defects(SENTINEL, min_distractors=0)[0]
        caller_source = SENTINEL[defect.caller_path]
        self.assertIn(defect.evidence, caller_source)

    def test_the_diff_contains_only_the_mutated_line(self):
        defect = find_defects(SENTINEL, min_distractors=0)[0]
        body = [
            l for l in build_diff(defect).split("\n")
            if l.startswith(("-", "+")) and not l.startswith(("---", "+++"))
        ]
        self.assertEqual(len(body), 2)
        self.assertTrue(body[0].startswith("-"))
        self.assertTrue(body[1].startswith("+"))

    def test_the_caller_file_never_appears_in_the_diff(self):
        defect = find_defects(SENTINEL, min_distractors=0)[0]
        self.assertNotIn(defect.caller_path, build_diff(defect))

    def test_the_mutation_is_locally_plausible(self):
        """The changed line must be valid, ordinary-looking code on its own."""
        import ast

        defect = find_defects(SENTINEL, min_distractors=0)[0]
        ast.parse(defect.after.strip())
        self.assertNotIn("TODO", defect.after)
        self.assertNotIn("FIXME", defect.after)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class MutationFamilyTests(unittest.TestCase):
    def test_tuple_order_needs_a_caller_that_unpacks(self):
        files = {
            "m/geo.py": "def bounds(points):\n    lo = min(points)\n    hi = max(points)\n    return lo, hi\n",
            "m/use.py": "from m.geo import bounds\n\n\ndef span(points):\n    lo, hi = bounds(points)\n    return hi - lo\n",
        }
        kinds = {d.kind for d in find_defects(files, min_distractors=0)}
        self.assertIn("tuple_order", kinds)

    def test_shared_mutable_needs_a_caller_that_mutates(self):
        files = {
            "m/store.py": "class Box:\n    def items(self):\n        return list(self._items)\n",
            "m/use.py": "from m.store import Box\n\n\ndef add(box):\n    got = box.items()\n    got.append(1)\n    return got\n",
        }
        kinds = {d.kind for d in find_defects(files, min_distractors=0)}
        # No structural check exists for this kind, so it is no longer generated.
        self.assertNotIn("shared_mutable", kinds)

    def test_exception_type_needs_a_caller_that_catches_it(self):
        files = {
            "m/parse.py": "def parse(text):\n    if not text:\n        raise ValueError('empty')\n    return int(text)\n",
            "m/use.py": "from m.parse import parse\n\n\ndef safe(text):\n    try:\n        return parse(text)\n    except ValueError:\n        return 0\n",
        }
        kinds = {d.kind for d in find_defects(files, min_distractors=0)}
        self.assertIn("exception_type", kinds)

    def test_every_mutation_family_explains_why_it_is_a_defect(self):
        for defect in find_defects(SENTINEL, min_distractors=0):
            self.assertGreater(len(defect.why), 40)

    def test_all_families_are_registered(self):
        self.assertEqual(
            set(MUTATIONS),
            {
                "none_sentinel", "tuple_order", "boundary", "shared_mutable",
                "exception_type", "default_flip", "empty_to_none",
                "normalisation", "slice_bound",
            },
        )

    def test_default_flip_needs_a_caller_that_omits_the_argument(self):
        files = {
            "m/fmt.py": "def render(text, escape=True):\n    return text\n",
            "m/use.py": "from m.fmt import render\n\n\ndef show(text):\n    return render(text)\n",
        }
        self.assertIn("default_flip", {d.kind for d in find_defects(files, min_distractors=0)})

    def test_default_flip_is_rejected_when_every_caller_passes_it(self):
        files = {
            "m/fmt.py": "def render(text, escape=True):\n    return text\n",
            "m/use.py": "from m.fmt import render\n\n\ndef show(text):\n    return render(text, escape=True)\n",
        }
        self.assertNotIn("default_flip", {d.kind for d in find_defects(files, min_distractors=0)})

    def test_empty_to_none_needs_a_caller_that_iterates(self):
        files = {
            "m/q.py": "def rows(flag):\n    if flag:\n        return []\n    return [1]\n",
            "m/use.py": "from m.q import rows\n\n\ndef total(flag):\n    return sum(x for x in rows(flag))\n",
        }
        self.assertIn("empty_to_none", {d.kind for d in find_defects(files, min_distractors=0)})

    def test_normalisation_needs_a_caller_that_compares(self):
        files = {
            "m/norm.py": "def key(raw):\n    return raw.strip().lower()\n",
            "m/use.py": "from m.norm import key\n\n\ndef is_admin(raw):\n    return key(raw) == 'admin'\n",
        }
        # The first benchmark "verified" this kind with a regex for `.get(` and
        # `==`; no structural check exists for it, so it is no longer generated.
        self.assertNotIn("normalisation", {d.kind for d in find_defects(files, min_distractors=0)})


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class TestFileExclusionTests(unittest.TestCase):
    """A defect whose only victim is a test is a weaker defect.

    The production code is unaffected, so a reviewer could reasonably decline
    to flag it. Requiring a non-test caller keeps every task one where shipping
    the change actually breaks something that runs.
    """

    LIB = "def find_index(items, target):\n    for i, x in enumerate(items):\n        if x == target:\n            return i\n    return None\n"
    USE = "from pkg.utils import find_index\n\n\ndef lookup(rows, key):\n    idx = find_index(rows, key)\n    if idx is None:\n        raise KeyError(key)\n    return rows[idx]\n"

    def test_a_test_file_does_not_count_as_the_depending_caller(self):
        for caller in ("tests/test_utils.py", "pkg/tests/test_x.py", "pkg/utils_test.py", "conftest.py"):
            with self.subTest(caller=caller):
                files = {"pkg/utils.py": self.LIB, caller: self.USE}
                self.assertEqual(find_defects(files, min_distractors=0), [])

    def test_a_production_caller_still_counts(self):
        files = {"pkg/utils.py": self.LIB, "pkg/handlers.py": self.USE}
        self.assertEqual(len(find_defects(files, min_distractors=0)), 1)

    def test_a_defect_is_never_placed_in_a_test_file(self):
        files = {"tests/helpers.py": self.LIB, "pkg/handlers.py": self.USE}
        self.assertEqual(find_defects(files, min_distractors=0), [])

    def test_a_production_caller_wins_when_both_exist(self):
        files = {
            "pkg/utils.py": self.LIB,
            "tests/test_utils.py": self.USE,
            "pkg/handlers.py": self.USE,
        }
        found = find_defects(files, min_distractors=0)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].caller_path, "pkg/handlers.py")

    def test_the_path_matcher_recognises_common_layouts(self):
        from experiments.crossfile import is_test_path

        for path in ("tests/a.py", "test/a.py", "pkg/tests/a.py", "test_thing.py",
                     "pkg/test_thing.py", "thing_test.py", "conftest.py", "testing/a.py"):
            with self.subTest(path=path):
                self.assertTrue(is_test_path(path))
        for path in ("pkg/latest.py", "pkg/contest.py", "src/protest/a.py", "pkg/handlers.py"):
            with self.subTest(path=path):
                self.assertFalse(is_test_path(path))


NOISY = {
    "pkg/utils.py": (
        "import os\n\n\nDEFAULT = dict()\n\n\n"
        "def find_index(items, target):\n"
        '    label = "index"\n'
        "    if items == None:\n"
        "        return None\n"
        "    for i, x in enumerate(items):\n"
        "        if x == target:\n"
        "            return i\n"
        "    return None\n"
    ),
    "pkg/handlers.py": (
        "from pkg.utils import find_index\n\n\n"
        "def lookup(rows, key):\n"
        "    idx = find_index(rows, key)\n"
        "    if idx is None:\n"
        "        raise KeyError(key)\n"
        "    return rows[idx]\n"
    ),
}


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class DistractorTests(unittest.TestCase):
    """A one-line diff makes the task free: flag the only change and be right.

    Measured at 97% for the no-context arm before distractors existed. Real
    review diffs carry several changes and most are fine, so the reviewer has
    to say which one is wrong rather than that something is.
    """

    def setUp(self):
        self.defect = find_defects(NOISY, min_distractors=0)[0]
        self.diff = build_diff(self.defect)

    def _changed(self):
        return [
            l for l in self.diff.split("\n")
            if l.startswith(("-", "+")) and not l.startswith(("---", "+++"))
        ]

    def test_the_diff_carries_more_than_one_change(self):
        self.assertGreater(len(self._changed()) // 2, 1)

    def test_the_defect_is_one_of_several_changes(self):
        self.assertGreater(len(self.defect.distractors), 0)

    def test_the_defect_line_is_present_in_the_diff(self):
        self.assertIn(f"+{self.defect.after}", self.diff)

    def test_every_distractor_is_behaviour_preserving(self):
        for change in self.defect.distractors:
            with self.subTest(line=change.line):
                pair = {change.before.strip(), change.after.strip()}
                harmless = (
                    {"DEFAULT = dict()", "DEFAULT = {}"},
                    {'label = "index"', "label = 'index'"},
                    {"if items == None:", "if items is None:"},
                )
                self.assertTrue(any(pair == h for h in harmless), pair)

    def test_no_distractor_is_marked_as_the_defect(self):
        self.assertTrue(all(not c.is_defect for c in self.defect.distractors))

    def test_distractors_never_touch_the_defect_line(self):
        for change in self.defect.distractors:
            self.assertNotEqual(change.line, self.defect.definition_line)

    def test_changes_appear_in_line_order_not_defect_first(self):
        lines = [c.line for c in self.defect.distractors] + [self.defect.definition_line]
        rendered = [
            int(l.split(" -")[1].split(",")[0])
            for l in self.diff.split("\n") if l.startswith("@@")
        ]
        self.assertEqual(rendered, sorted(rendered))
        self.assertGreater(len(lines), 1)

    def test_the_caller_file_still_never_appears(self):
        self.assertNotIn(self.defect.caller_path, self.diff)
