import unittest

try:
    from experiments.benchmark import GroundTruthDefect
    from experiments.matcher import (
        DEFAULT_LINE_TOLERANCE,
        ReportedFinding,
        match_review,
        normalise_path,
        paths_match,
    )

    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def defect(defect_id, path, line):
    return GroundTruthDefect(defect_id=defect_id, path=path, line=line, text="x")


def finding(finding_id, path, line):
    return ReportedFinding(finding_id=finding_id, path=path, line=line)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class PathNormalisationTests(unittest.TestCase):
    def test_diff_prefixes_are_stripped(self):
        self.assertEqual(normalise_path("a/src/app.py"), "src/app.py")
        self.assertEqual(normalise_path("b/src/app.py"), "src/app.py")

    def test_leading_dot_slash_is_stripped(self):
        self.assertEqual(normalise_path("./src/app.py"), "src/app.py")

    def test_windows_separators_are_normalised(self):
        self.assertEqual(normalise_path("src\\app.py"), "src/app.py")

    def test_an_empty_path_never_matches(self):
        self.assertFalse(paths_match("", "src/app.py"))
        self.assertFalse(paths_match("src/app.py", ""))

    def test_different_files_do_not_match(self):
        self.assertFalse(paths_match("src/app.py", "src/other.py"))


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class MatchingTests(unittest.TestCase):
    def test_an_exact_hit_is_recorded(self):
        report = match_review("t1", "B", [defect("d1", "src/app.py", 10)], [finding("f1", "src/app.py", 10)])
        self.assertTrue(report.outcomes[0].hit)
        self.assertEqual(report.outcomes[0].line_distance, 0)
        self.assertEqual(report.outcomes[0].matched_finding_id, "f1")

    def test_a_nearby_line_within_tolerance_is_a_hit(self):
        report = match_review("t1", "B", [defect("d1", "src/app.py", 10)], [finding("f1", "src/app.py", 13)])
        self.assertTrue(report.outcomes[0].hit)
        self.assertEqual(report.outcomes[0].line_distance, 3)

    def test_a_line_beyond_tolerance_is_a_miss(self):
        report = match_review("t1", "B", [defect("d1", "src/app.py", 10)], [finding("f1", "src/app.py", 40)])
        self.assertFalse(report.outcomes[0].hit)

    def test_the_right_line_in_the_wrong_file_is_a_miss(self):
        report = match_review("t1", "B", [defect("d1", "src/app.py", 10)], [finding("f1", "src/other.py", 10)])
        self.assertFalse(report.outcomes[0].hit)
        self.assertEqual(report.false_positives, ("f1",))

    def test_the_closest_finding_wins(self):
        report = match_review(
            "t1",
            "B",
            [defect("d1", "src/app.py", 10)],
            [finding("f_far", "src/app.py", 14), finding("f_near", "src/app.py", 11)],
        )
        self.assertEqual(report.outcomes[0].matched_finding_id, "f_near")

    def test_one_finding_cannot_satisfy_two_defects(self):
        report = match_review(
            "t1",
            "B",
            [defect("d1", "src/app.py", 10), defect("d2", "src/app.py", 11)],
            [finding("f1", "src/app.py", 10)],
        )
        self.assertEqual([o.hit for o in report.outcomes], [True, False])

    def test_unmatched_findings_become_false_positives(self):
        report = match_review(
            "t1",
            "B",
            [defect("d1", "src/app.py", 10)],
            [finding("f1", "src/app.py", 10), finding("noise", "src/app.py", 900)],
        )
        self.assertEqual(report.false_positives, ("noise",))

    def test_a_finding_without_a_line_cannot_match(self):
        report = match_review("t1", "B", [defect("d1", "src/app.py", 10)], [finding("f1", "src/app.py", None)])
        self.assertFalse(report.outcomes[0].hit)

    def test_a_review_that_reports_nothing_misses_everything(self):
        report = match_review("t1", "A", [defect("d1", "src/app.py", 10), defect("d2", "src/b.py", 3)], [])
        self.assertEqual([o.hit for o in report.outcomes], [False, False])
        self.assertEqual(report.false_positives, ())


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class UnitOfAnalysisTests(unittest.TestCase):
    def test_one_outcome_row_per_defect_not_per_task(self):
        defects = [defect(f"d{i}", "src/app.py", i * 100) for i in range(1, 6)]
        report = match_review("t1", "B", defects, [finding("f1", "src/app.py", 100)])
        self.assertEqual(len(report.outcomes), 5)

    def test_every_outcome_carries_its_task_and_condition_for_clustering(self):
        defects = [defect("d1", "src/app.py", 10), defect("d2", "src/app.py", 50)]
        report = match_review("t7", "D", defects, [])
        for outcome in report.outcomes:
            self.assertEqual(outcome.task_id, "t7")
            self.assertEqual(outcome.condition, "D")

    def test_a_partially_solved_task_is_not_collapsed_to_a_single_verdict(self):
        report = match_review(
            "t1",
            "B",
            [defect("d1", "src/app.py", 10), defect("d2", "src/app.py", 50), defect("d3", "src/b.py", 7)],
            [finding("f1", "src/app.py", 10), finding("f2", "src/b.py", 7)],
        )
        self.assertEqual([o.hit for o in report.outcomes], [True, False, True])
        self.assertAlmostEqual(report.recall, 2 / 3)


@unittest.skipUnless(_AVAILABLE, "experiment package not importable")
class ScoreTests(unittest.TestCase):
    def test_recall_precision_and_f1_on_a_mixed_review(self):
        report = match_review(
            "t1",
            "B",
            [defect("d1", "src/app.py", 10), defect("d2", "src/app.py", 50)],
            [finding("f1", "src/app.py", 10), finding("noise", "src/z.py", 1)],
        )
        self.assertAlmostEqual(report.recall, 0.5)
        self.assertAlmostEqual(report.precision, 0.5)
        self.assertAlmostEqual(report.f1, 0.5)

    def test_a_silent_review_scores_zero_without_dividing_by_zero(self):
        report = match_review("t1", "A", [defect("d1", "src/app.py", 10)], [])
        self.assertEqual(report.recall, 0.0)
        self.assertEqual(report.precision, 0.0)
        self.assertEqual(report.f1, 0.0)

    def test_a_perfect_review_scores_one(self):
        report = match_review("t1", "F", [defect("d1", "src/app.py", 10)], [finding("f1", "src/app.py", 10)])
        self.assertEqual(report.recall, 1.0)
        self.assertEqual(report.precision, 1.0)
        self.assertEqual(report.f1, 1.0)

    def test_the_tolerance_is_configurable_and_documented(self):
        strict = match_review(
            "t1", "B", [defect("d1", "src/app.py", 10)], [finding("f1", "src/app.py", 13)], line_tolerance=1
        )
        loose = match_review(
            "t1", "B", [defect("d1", "src/app.py", 10)], [finding("f1", "src/app.py", 13)], line_tolerance=10
        )
        self.assertFalse(strict.outcomes[0].hit)
        self.assertTrue(loose.outcomes[0].hit)
        self.assertEqual(DEFAULT_LINE_TOLERANCE, 5)


if __name__ == "__main__":
    unittest.main()
