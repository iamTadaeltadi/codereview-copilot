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
        found = find_defects(SENTINEL)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].kind, "none_sentinel")

    def test_no_defect_when_nothing_calls_the_function(self):
        only = {"pkg/utils.py": SENTINEL["pkg/utils.py"]}
        self.assertEqual(find_defects(only), [])

    def test_no_defect_when_the_caller_does_not_depend_on_the_behaviour(self):
        indifferent = dict(SENTINEL)
        indifferent["pkg/handlers.py"] = (
            "from pkg.utils import find_index\n\n\n"
            "def lookup(rows, key):\n"
            "    return find_index(rows, key)\n"   # never checks for None
        )
        self.assertEqual(find_defects(indifferent), [])

    def test_no_defect_when_the_only_caller_is_in_the_same_file(self):
        same_file = {
            "pkg/utils.py": SENTINEL["pkg/utils.py"]
            + "\n\ndef lookup(rows, key):\n    idx = find_index(rows, key)\n    if idx is None:\n        raise KeyError(key)\n    return rows[idx]\n"
        }
        self.assertEqual(find_defects(same_file), [])

    def test_the_defect_and_its_caller_are_always_in_different_files(self):
        for defect in find_defects(SENTINEL):
            self.assertNotEqual(defect.definition_path, defect.caller_path)

    def test_the_evidence_line_comes_from_the_caller(self):
        defect = find_defects(SENTINEL)[0]
        caller_source = SENTINEL[defect.caller_path]
        self.assertIn(defect.evidence, caller_source)

    def test_the_diff_contains_only_the_mutated_line(self):
        defect = find_defects(SENTINEL)[0]
        body = [
            l for l in build_diff(defect).split("\n")
            if l.startswith(("-", "+")) and not l.startswith(("---", "+++"))
        ]
        self.assertEqual(len(body), 2)
        self.assertTrue(body[0].startswith("-"))
        self.assertTrue(body[1].startswith("+"))

    def test_the_caller_file_never_appears_in_the_diff(self):
        defect = find_defects(SENTINEL)[0]
        self.assertNotIn(defect.caller_path, build_diff(defect))

    def test_the_mutation_is_locally_plausible(self):
        """The changed line must be valid, ordinary-looking code on its own."""
        import ast

        defect = find_defects(SENTINEL)[0]
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
        kinds = {d.kind for d in find_defects(files)}
        self.assertIn("tuple_order", kinds)

    def test_shared_mutable_needs_a_caller_that_mutates(self):
        files = {
            "m/store.py": "class Box:\n    def items(self):\n        return list(self._items)\n",
            "m/use.py": "from m.store import Box\n\n\ndef add(box):\n    got = box.items()\n    got.append(1)\n    return got\n",
        }
        kinds = {d.kind for d in find_defects(files)}
        self.assertIn("shared_mutable", kinds)

    def test_exception_type_needs_a_caller_that_catches_it(self):
        files = {
            "m/parse.py": "def parse(text):\n    if not text:\n        raise ValueError('empty')\n    return int(text)\n",
            "m/use.py": "from m.parse import parse\n\n\ndef safe(text):\n    try:\n        return parse(text)\n    except ValueError:\n        return 0\n",
        }
        kinds = {d.kind for d in find_defects(files)}
        self.assertIn("exception_type", kinds)

    def test_every_mutation_family_explains_why_it_is_a_defect(self):
        for defect in find_defects(SENTINEL):
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
        self.assertIn("default_flip", {d.kind for d in find_defects(files)})

    def test_default_flip_is_rejected_when_every_caller_passes_it(self):
        files = {
            "m/fmt.py": "def render(text, escape=True):\n    return text\n",
            "m/use.py": "from m.fmt import render\n\n\ndef show(text):\n    return render(text, escape=True)\n",
        }
        self.assertNotIn("default_flip", {d.kind for d in find_defects(files)})

    def test_empty_to_none_needs_a_caller_that_iterates(self):
        files = {
            "m/q.py": "def rows(flag):\n    if flag:\n        return []\n    return [1]\n",
            "m/use.py": "from m.q import rows\n\n\ndef total(flag):\n    return sum(x for x in rows(flag))\n",
        }
        self.assertIn("empty_to_none", {d.kind for d in find_defects(files)})

    def test_normalisation_needs_a_caller_that_compares(self):
        files = {
            "m/norm.py": "def key(raw):\n    return raw.strip().lower()\n",
            "m/use.py": "from m.norm import key\n\n\ndef is_admin(raw):\n    return key(raw) == 'admin'\n",
        }
        self.assertIn("normalisation", {d.kind for d in find_defects(files)})


if __name__ == "__main__":
    unittest.main()
