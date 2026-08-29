import unittest

try:
    from experiments.evidence_scope import SCOPE_DIFF, SCOPE_OUTSIDE, classify, is_strict

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


DIFF = (
    "diff --git a/pkg/utils.py b/pkg/utils.py\n"
    "@@ -10,3 +10,3 @@\n"
    "-    return None\n"
    "+    return -1\n"
    "     needs_resorting = True\n"
)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class DiffScopedTests(unittest.TestCase):
    """A comment resolvable from the change alone."""

    def test_a_comment_about_the_changed_line_needs_nothing_else(self):
        self.assertEqual(classify("@u: rename needs_resorting", DIFF).scope, SCOPE_DIFF)

    def test_speaker_prefixes_are_not_treated_as_identifiers(self):
        self.assertEqual(classify("@reviewer1: fine by me", DIFF).scope, SCOPE_DIFF)

    def test_an_empty_comment_is_diff_scoped(self):
        self.assertEqual(classify("", DIFF).scope, SCOPE_DIFF)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class OutsideScopedTests(unittest.TestCase):
    """A comment anchored on a changed line can still need another file.

    This is the distinction the project's first position collapsed: the anchor
    is constrained by GitHub, the evidence is not.
    """

    def test_naming_a_file_absent_from_the_diff(self):
        s = classify("@u: this breaks handlers.py which checks is None", DIFF)
        self.assertEqual(s.scope, SCOPE_OUTSIDE)
        self.assertTrue(is_strict(s))

    def test_linking_to_code_outside_the_diff(self):
        s = classify("@u: see https://github.com/o/r/blob/x/other.py#L4", DIFF)
        self.assertTrue(is_strict(s))

    def test_a_phrase_naming_code_elsewhere(self):
        for phrase in ("is called by another function", "should be consistent with the base class",
                       "defined in the parent", "look at the examples"):
            with self.subTest(phrase=phrase):
                self.assertTrue(is_strict(classify(f"@u: it {phrase}", DIFF)))

    def test_the_reason_is_recorded_so_a_reader_can_disagree(self):
        s = classify("@u: breaks handlers.py", DIFF)
        self.assertTrue(s.reasons)
        self.assertIn("handlers.py", s.reasons[0])


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class BoundTests(unittest.TestCase):
    """Strict and loose bracket the true figure rather than asserting one."""

    def test_the_identifier_rule_is_loose_only(self):
        """An assertion message is not a reference to other code."""
        s = classify("@u: fails with AssertionError: assert 95.27 == 95.270", DIFF)
        self.assertEqual(s.scope, SCOPE_OUTSIDE)
        self.assertFalse(is_strict(s))

    def test_strict_is_a_subset_of_loose(self):
        for comment in ("@u: breaks handlers.py", "@u: called by other code",
                        "@u: rename this", "@u: see http://x/y.py"):
            with self.subTest(comment=comment):
                s = classify(comment, DIFF)
                if is_strict(s):
                    self.assertTrue(s.needs_outside_evidence)

    def test_a_file_already_in_the_diff_does_not_count_as_outside(self):
        s = classify("@u: utils.py handles this", DIFF + "\n+++ b/pkg/utils.py")
        self.assertFalse(any("utils.py" in r for r in s.reasons if r.startswith("names a file")))


if __name__ == "__main__":
    unittest.main()
