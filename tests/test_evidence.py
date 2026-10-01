import unittest

try:
    from experiments.evidence import (
        ARM_ATTRIBUTED, ARM_CORRUPTED, ARM_EVIDENCE, ARM_HEADER, ARM_TOPOLOGY, ARM_TYPED,
        ARMS, ENCODINGS, EVIDENCE_ARMS, FLAT, PROSE, TAG,
        Evidence, Relation, Snippet, _relation_for, metadata_block, random_evidence,
    )
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def evidence():
    return Evidence(
        snippets=(
            Snippet("a/_text.py", 240, 264, "def to_text():\n    raise ValueError('x')", "_text:253"),
            Snippet("a/ec2.py", 620, 644, "try:\n    to_text(v)\nexcept TypeError:\n    pass", "ec2:632"),
            Snippet("a/_text.py", 157, 181, "def other():\n    return 1", "_text:169"),
        ),
        relations=(Relation("ec2:632", "_text:253", "catches", "TypeError"),),
    )


def block(arm, encoding=FLAT, seed="seed-1"):
    return metadata_block(evidence(), arm, encoding, seed)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ArmContentTests(unittest.TestCase):
    def test_topology_states_a_link_without_naming_its_kind(self):
        out = block(ARM_TOPOLOGY)
        self.assertIn("ec2:632", out); self.assertIn("_text:253", out)
        self.assertNotIn("catches", out); self.assertNotIn("TypeError", out)

    def test_typed_names_the_kind_but_not_the_argument(self):
        out = block(ARM_TYPED)
        self.assertIn("catches", out); self.assertNotIn("TypeError", out)

    def test_only_the_attributed_arm_can_leak_the_answer(self):
        for arm in (ARM_EVIDENCE, ARM_TOPOLOGY, ARM_TYPED, ARM_HEADER):
            with self.subTest(arm=arm):
                self.assertNotIn("TypeError", block(arm))
        self.assertIn("TypeError", block(ARM_ATTRIBUTED))

    def test_the_diff_only_arm_receives_no_metadata(self):
        self.assertEqual(metadata_block(evidence(), "1-diff", FLAT, "s"), "")

    def test_the_header_arm_carries_the_same_block_as_the_control(self):
        self.assertEqual(block(ARM_HEADER), block(ARM_EVIDENCE))
        self.assertIn(ARM_HEADER, ARMS)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class DensityControlTests(unittest.TestCase):
    """Arm 2 must carry nothing true while matching the attributed arm's shape.

    The first version kept line numbers, so a number inside a snippet's range
    identified the snippet and the topology was recoverable; and it kept the
    relation kind, so it stated a true relation between recoverable endpoints.
    """

    def test_the_control_preserves_edge_syntax_and_length(self):
        self.assertIn("-->", block(ARM_EVIDENCE))
        self.assertLess(abs(len(block(ARM_EVIDENCE)) - len(block(ARM_ATTRIBUTED))), 4)

    def test_the_control_destroys_the_endpoints_including_line_numbers(self):
        out = block(ARM_EVIDENCE)
        for true_token in ("ec2:632", "_text:253", ":632", ":253"):
            self.assertNotIn(true_token, out)

    def test_the_control_destroys_the_relation_kind(self):
        self.assertNotIn("catches", block(ARM_EVIDENCE))

    def test_scrambled_line_numbers_keep_their_digit_count(self):
        import re
        nums = re.findall(r":(\d+)", block(ARM_EVIDENCE))
        self.assertEqual([len(n) for n in nums], [3, 3])

    def test_the_control_is_deterministic_for_a_seed(self):
        self.assertEqual(block(ARM_EVIDENCE, seed="x"), block(ARM_EVIDENCE, seed="x"))


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class CorruptionTests(unittest.TestCase):
    def test_corruption_points_somewhere_real_but_wrong(self):
        target = block(ARM_CORRUPTED).split("--> ")[1].strip()
        self.assertEqual(target, "_text:169")

    def test_corruption_preserves_kind_argument_count_and_length(self):
        out = block(ARM_CORRUPTED)
        self.assertIn("catches", out); self.assertIn("TypeError", out)
        self.assertEqual(len(out.splitlines()), len(block(ARM_ATTRIBUTED).splitlines()))
        self.assertLess(abs(len(out) - len(block(ARM_ATTRIBUTED))), 4)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class RelationKindTests(unittest.TestCase):
    """Every verified mutation kind yields a typed relation with an argument,
    so the typed and attributed arms differ on every task rather than on the
    eight exception tasks of the first benchmark."""

    def test_each_verified_kind_has_a_relation_and_takes_the_recorded_argument(self):
        for kind, arg in (("exception_type", "TypeError"), ("none_sentinel", "None"),
                          ("default_flip", "strict"), ("tuple_order", "a,b"), ("empty_to_none", "iterates")):
            with self.subTest(kind=kind):
                rel, got = _relation_for(kind, arg)
                self.assertNotEqual(rel, "depends-on"); self.assertEqual(got, arg)

    def test_a_missing_argument_falls_back_to_the_handler_regex(self):
        self.assertEqual(_relation_for("exception_type", "", "except KeyError:")[1], "KeyError")


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ForeignRandomTests(unittest.TestCase):
    def test_random_evidence_never_comes_from_the_benchmark_files(self):
        out = random_evidence(None, {}, evidence(), seed="t")
        if out is evidence():
            self.skipTest("foreign pool absent")
        self.assertEqual(len(out.snippets), 3)
        for s in out.snippets:
            self.assertNotIn(s.path, {"a/_text.py", "a/ec2.py"})
        self.assertEqual(out.relations, ())


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class EncodingAndOrderingTests(unittest.TestCase):
    def test_all_three_encodings_carry_both_endpoints(self):
        for enc in ENCODINGS:
            out = block(ARM_ATTRIBUTED, enc)
            self.assertIn("ec2:632", out); self.assertIn("_text:253", out)

    def test_snippets_render_in_canonical_order(self):
        r = evidence().rendered()
        self.assertLess(r.index("_text.py:157"), r.index("_text.py:240"))
        self.assertLess(r.index("_text.py:240"), r.index("ec2.py:620"))


if __name__ == "__main__":
    unittest.main()
