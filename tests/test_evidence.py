import unittest

try:
    from experiments.evidence import (
        ARM_ATTRIBUTED, ARM_CORRUPTED, ARM_EVIDENCE, ARM_TOPOLOGY, ARM_TYPED,
        ENCODINGS, EVIDENCE_ARMS, FLAT, PROSE, TAG,
        Evidence, Relation, Snippet, metadata_block,
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


def block(arm, encoding=FLAT):
    return metadata_block(evidence(), arm, encoding, "seed-1")


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ArmContentTests(unittest.TestCase):
    def test_topology_states_a_link_without_naming_its_kind(self):
        out = block(ARM_TOPOLOGY)
        self.assertIn("ec2:632", out)
        self.assertIn("_text:253", out)
        self.assertNotIn("catches", out)
        self.assertNotIn("TypeError", out)

    def test_typed_names_the_kind_but_not_the_argument(self):
        out = block(ARM_TYPED)
        self.assertIn("catches", out)
        self.assertNotIn("TypeError", out)

    def test_only_the_attributed_arm_can_leak_the_answer(self):
        """TypeError is the defect. Any arm naming it hands over the answer."""
        for arm in (ARM_EVIDENCE, ARM_TOPOLOGY, ARM_TYPED):
            with self.subTest(arm=arm):
                self.assertNotIn("TypeError", block(arm))
        self.assertIn("TypeError", block(ARM_ATTRIBUTED))

    def test_the_diff_only_arm_receives_no_metadata(self):
        self.assertEqual(metadata_block(evidence(), "1-diff", FLAT, "s"), "")


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class DensityControlTests(unittest.TestCase):
    """Arm 2 destroys topology while preserving everything else.

    A block of low-signal filler would dilute attention while a graph string is
    dense, so a win for a structured arm could be signal-to-noise rather than
    topology.
    """

    def test_the_control_preserves_edge_syntax(self):
        self.assertIn("-->", block(ARM_EVIDENCE))

    def test_the_control_preserves_length_within_a_few_characters(self):
        self.assertLess(abs(len(block(ARM_EVIDENCE)) - len(block(ARM_ATTRIBUTED))), 4)

    def test_the_control_destroys_the_real_endpoints(self):
        out = block(ARM_EVIDENCE)
        self.assertNotIn("ec2:632", out)
        self.assertNotIn("_text:253", out)

    def test_the_control_is_deterministic_for_a_seed(self):
        self.assertEqual(
            metadata_block(evidence(), ARM_EVIDENCE, FLAT, "x"),
            metadata_block(evidence(), ARM_EVIDENCE, FLAT, "x"),
        )


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class CorruptionTests(unittest.TestCase):
    def test_corruption_points_somewhere_real_but_wrong(self):
        out = block(ARM_CORRUPTED)
        target = out.split("--> ")[1].strip()
        self.assertIn(target, {"_text:169", "_text:253", "ec2:632"})
        self.assertNotEqual(target, "_text:253")

    def test_corruption_never_produces_a_self_loop(self):
        """A self-loop reads as malformed rather than as a wrong claim."""
        out = block(ARM_CORRUPTED)
        source, _, target = out.partition("--> ")
        self.assertNotEqual(source.split(" --")[0].strip(), target.strip())

    def test_corruption_preserves_relation_kind_and_argument(self):
        out = block(ARM_CORRUPTED)
        self.assertIn("catches", out)
        self.assertIn("TypeError", out)

    def test_corruption_preserves_edge_count(self):
        self.assertEqual(
            len(block(ARM_CORRUPTED).splitlines()),
            len(block(ARM_ATTRIBUTED).splitlines()),
        )

    def test_corruption_preserves_length_within_a_few_characters(self):
        self.assertLess(abs(len(block(ARM_CORRUPTED)) - len(block(ARM_ATTRIBUTED))), 4)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class EncodingTests(unittest.TestCase):
    def test_all_three_encodings_are_produced(self):
        rendered = {e: block(ARM_ATTRIBUTED, e) for e in ENCODINGS}
        self.assertEqual(len(set(rendered.values())), 3)

    def test_every_encoding_carries_both_endpoints(self):
        for encoding in ENCODINGS:
            with self.subTest(encoding=encoding):
                out = block(ARM_ATTRIBUTED, encoding)
                self.assertIn("ec2:632", out)
                self.assertIn("_text:253", out)

    def test_the_tag_encoding_is_well_formed(self):
        out = block(ARM_ATTRIBUTED, TAG)
        self.assertTrue(out.startswith("<dependency "))
        self.assertTrue(out.rstrip().endswith("/>"))


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class OrderingTests(unittest.TestCase):
    """Ordering is not harmless: GraphDO reports BFS order at 89.43% against
    random at 78.36% on identical graphs. The snippet order must therefore be
    fixed across arms, or it becomes the treatment."""

    def test_snippets_render_in_canonical_order(self):
        rendered = evidence().rendered()
        self.assertLess(rendered.index("_text.py:157"), rendered.index("_text.py:240"))
        self.assertLess(rendered.index("_text.py:240"), rendered.index("ec2.py:620"))

    def test_every_arm_receives_identical_snippet_text(self):
        text = evidence().rendered()
        for arm in EVIDENCE_ARMS:
            with self.subTest(arm=arm):
                self.assertEqual(evidence().rendered(), text)


if __name__ == "__main__":
    unittest.main()
