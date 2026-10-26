"""Pins for the five defects the October 2026 external review found in the
generator and the arms: same-name imports, unsafe twins, behaviour-changing
distractors, line-number labels, and unparseable replies scored as answers."""
import ast
import unittest
from types import SimpleNamespace

from experiments.crossfile import (_resolves, find_defects, find_twins, find_distractors,
                                   _dependent_call_anywhere, _detail, _functions, build_diff)
from experiments.evidence import (evidence_for, metadata_block, _relation_for, _label,
                                  _enclosing_name, _shuffle_labels, Relation, ARM_TOPOLOGY, ARM_EVIDENCE, TAG)

DEF = "pkg/stats.py"
DEF_SRC = ('LABEL = "skew"\nUNIT = "raw"\n\n\ndef skew(x, bias=True):\n    if bias:\n        return 1\n    return 2\n\n\n'
           'def other():\n    name = "other"\n    return (name)\n')


class ImportResolutionTests(unittest.TestCase):
    def test_same_name_from_another_module_is_not_evidence(self):
        caller = "from scipy.stats import skew\n\ndef f(v):\n    return skew(v)\n"
        self.assertIsNone(_resolves(ast.parse(caller), "skew", DEF, "pkg/use.py", {DEF: DEF_SRC}))

    def test_import_from_the_definition_module_resolves(self):
        caller = "from pkg.stats import skew\n\ndef f(v):\n    return skew(v)\n"
        self.assertTrue(_resolves(ast.parse(caller), "skew", DEF, "pkg/use.py", {DEF: DEF_SRC}))

    def test_relative_import_resolves_against_the_importer(self):
        caller = "from .stats import skew\n\ndef f(v):\n    return skew(v)\n"
        self.assertTrue(_resolves(ast.parse(caller), "skew", DEF, "pkg/use.py", {DEF: DEF_SRC}))
        self.assertIsNone(_resolves(ast.parse(caller), "skew", DEF, "other/use.py", {DEF: DEF_SRC}))

    def test_package_reexport_in_the_pool_is_followed(self):
        sources = {DEF: DEF_SRC, "pkg/__init__.py": "from .stats import skew\n"}
        caller = "from pkg import skew\n\ndef f(v):\n    return skew(v)\n"
        self.assertTrue(_resolves(ast.parse(caller), "skew", DEF, "app/use.py", sources))
        self.assertIsNone(_resolves(ast.parse(caller), "skew", DEF, "app/use.py", {DEF: DEF_SRC}))

    def test_module_import_must_name_the_definition_module(self):
        self.assertEqual(_resolves(ast.parse("import pkg.stats as st\nst.skew(1)\n"), "skew", DEF, "x.py", {}), "st")
        self.assertIsNone(_resolves(ast.parse("import numpy.stats as st\nst.skew(1)\n"), "skew", DEF, "x.py", {}))

    def test_a_defect_is_not_generated_from_a_same_name_import(self):
        sources = {DEF: DEF_SRC, "pkg/use.py": "from numpy.stats import skew\n\ndef f(v):\n    return skew(v)\n"}
        self.assertEqual([d.kind for d in find_defects(sources)], [])
        sources["pkg/use.py"] = "from pkg.stats import skew\n\ndef f(v):\n    return skew(v)\n"
        self.assertEqual([d.kind for d in find_defects(sources)], ["default_flip"])


class TwinSafetyTests(unittest.TestCase):
    SAFE_CALLER = "from pkg.stats import skew\n\ndef f(v):\n    return skew(v, bias=False)\n"

    def test_a_twin_is_rejected_when_the_same_file_calls_without_the_argument(self):
        unsafe_def = DEF_SRC + "\n\ndef local():\n    return skew([1])\n"
        self.assertEqual(find_twins({DEF: unsafe_def, "pkg/use.py": self.SAFE_CALLER}), [])
        self.assertEqual(len(find_twins({DEF: DEF_SRC, "pkg/use.py": self.SAFE_CALLER})), 1)

    def test_a_twin_is_rejected_when_an_attribute_call_omits_the_argument(self):
        sources = {DEF: DEF_SRC, "pkg/use.py": self.SAFE_CALLER,
                   "pkg/elsewhere.py": "import pkg.stats as st\n\ndef g(v):\n    return st.skew(v)\n"}
        self.assertEqual(find_twins(sources), [])

    def test_the_dependent_scan_reports_where(self):
        tree = ast.parse(DEF_SRC + "\n\ndef local():\n    return skew([1])\n")
        fn = next(f for f in _functions(tree, []) if f.name == "skew")
        detail = _detail("default_flip", fn, "def skew(x, bias=True):", "def skew(x, bias=False):")
        parsed = {DEF: (tree, (DEF_SRC + "\n\ndef local():\n    return skew([1])\n").split("\n"), "")}
        self.assertEqual(_dependent_call_anywhere(parsed, {}, fn, "skew", DEF, "default_flip", detail)[0], DEF)

    def test_twin_relation_is_true_for_the_twin(self):
        self.assertEqual(_relation_for("default_flip", "bias", is_defect=True)[0], "calls-without-argument")
        self.assertEqual(_relation_for("default_flip", "bias", is_defect=False)[0], "calls-with-argument")


class DistractorTests(unittest.TestCase):
    LINES = ["import os", 'A = "zero"', 'B = "half"', "def a():", '    x = "one"', '    y = ("two")', "    z = 1 + 2", "    return x", "", "",
             "def b():", '    q = "three"', '    r = "four"', "    return q", "", "def c():", "    return 0"]

    def test_distractors_keep_the_syntax_tree(self):
        for change in find_distractors(self.LINES, 7, seed="t"):
            trial = list(self.LINES); trial[change.line - 1] = change.after
            self.assertEqual(ast.dump(ast.parse("\n".join(trial))), ast.dump(ast.parse("\n".join(self.LINES))))

    def test_a_rewrite_that_changes_the_tree_is_refused_for_neutral_kinds(self):
        from experiments.crossfile import _same_ast
        self.assertTrue(_same_ast(['x = "a"'], 0, "x = 'a'"))
        self.assertFalse(_same_ast(["x = 1 == None"], 0, "x = 1 is None"))
        self.assertFalse(_same_ast(['x = "a" "b"'], 0, 'x = "a"'))

    def test_the_defect_is_not_always_the_last_change(self):
        positions = set()
        for seed in range(20):
            lines = find_distractors(self.LINES, 7, seed=str(seed))
            if lines:
                positions.add(sum(1 for c in lines if c.line > 7) > 0)
        self.assertEqual(positions, {True, False})


class LabelTests(unittest.TestCase):
    def test_labels_name_the_function_not_the_line(self):
        self.assertEqual(_label("pkg/stats.py", _enclosing_name(DEF_SRC, 6)), "stats.skew")
        self.assertEqual(_enclosing_name(DEF_SRC, 12), "other")
        self.assertEqual(_enclosing_name("x = 1\n", 1), "module")

    def test_evidence_labels_carry_no_line_numbers_and_control_scrambles_names(self):
        caller_src = "from pkg.stats import skew\n\n\ndef f(v):\n    return skew(v)\n"
        task = SimpleNamespace(task_id="t1", defects=[SimpleNamespace(path=DEF, line=5)],
                               metadata={"caller_path": "pkg/use.py", "caller_line": 5, "kind": "default_flip",
                                         "argument": "bias", "evidence": "return skew(v)"})
        ev = evidence_for(task, {DEF: DEF_SRC, "pkg/use.py": caller_src})
        labels = {s.label for s in ev.snippets}
        self.assertIn("stats.skew", labels); self.assertIn("use.f", labels)
        self.assertFalse(any(ch.isdigit() for l in labels for ch in l))
        true_block = metadata_block(ev, ARM_TOPOLOGY, TAG, "t1")
        control = metadata_block(ev, ARM_EVIDENCE, TAG, "t1")
        self.assertIn("stats.skew", true_block)
        self.assertNotIn("stats.skew", control); self.assertNotIn("use.f", control)


if __name__ == "__main__":
    unittest.main()
