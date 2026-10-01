import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from experiments.analyse_structure import (
    all_cells,
    holm,
    load,
    main,
    mcnemar,
    mcnemar_exact_p,
    paired_bootstrap,
    pairs,
    repo_of,
    report,
    table,
)

ARMS = ("1-diff", "2-evidence", "3-topology")


def task_id(repo: str, i: int) -> str:
    return f"xf::{repo}::src/mod_{i}.py::fn_{i}::none_sentinel"


def row(task: str, arm: str, precise: bool, hit=None, **extra) -> dict:
    base = {
        "task_id": task,
        "arm": arm,
        "encoding": "tag",
        "model": "openai/gpt-4o-mini",
        "kind": "none_sentinel",
        "prompt_chars": 1000 + len(arm) * 100,
        "hit": precise if hit is None else hit,
        "precise": precise,
        "flagged_distractors": 0,
        "findings": 1,
        "parse_failed": False,
        "usage": {"input_tokens": 400, "output_tokens": 50, "cost_usd": 0.0001, "calls": 1},
    }
    base.update(extra)
    return base


def write_jsonl(directory: Path, rows, name="structure.jsonl") -> Path:
    path = directory / name
    with open(path, "w", encoding="utf-8") as handle:
        for r in rows:
            handle.write(json.dumps(r) + "\n")
    return path


def paired_rows(spec, arms=ARMS):
    """spec: list of (task_id, {arm: precise}) -> rows for every arm in `arms`."""
    out = []
    for task, values in spec:
        for arm in arms:
            out.append(row(task, arm, values[arm]))
    return out


class _TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class LoadTests(_TempDirCase):
    def test_dedup_keeps_first_occurrence_and_counts_dropped(self):
        t = task_id("acme__widgets", 1)
        rows = [row(t, a, True) for a in ARMS]
        rows.append(row(t, "1-diff", False))  # re-run after resume: must be ignored
        rows.append(row(t, "1-diff", False))
        rows.append(row(t, "2-evidence", False))
        data = load(write_jsonl(self.dir, rows))
        self.assertEqual(data.dropped_duplicates, 3)
        self.assertTrue(data[t]["1-diff"]["precise"])
        self.assertTrue(data[t]["2-evidence"]["precise"])
        self.assertEqual(len(data), 1)

    def test_incomplete_tasks_are_dropped_and_counted(self):
        complete = task_id("acme__widgets", 1)
        partial = task_id("acme__widgets", 2)
        rows = [row(complete, a, True) for a in ARMS]
        rows += [row(partial, a, True) for a in ARMS[:2]]  # never ran under 3-topology
        data = load(write_jsonl(self.dir, rows))
        self.assertEqual(data.dropped_incomplete, 1)
        self.assertEqual(set(data), {complete})
        self.assertEqual(data.arms, sorted(ARMS))

    def test_arms_are_discovered_from_the_file_not_hardcoded(self):
        t = task_id("acme__widgets", 1)
        arms = ("0-header", "2-evidence")
        rows = [row(t, a, True) for a in arms]
        data = load(write_jsonl(self.dir, rows))
        self.assertEqual(data.arms, ["0-header", "2-evidence"])
        self.assertEqual(len(data), 1)


class RepoOfTests(unittest.TestCase):
    def test_repo_of_returns_owner_and_repo_segment(self):
        self.assertEqual(
            repo_of("xf::OpenMined__PySyft::src/syft/lib/torch/module.py::get::none_sentinel"),
            "OpenMined__PySyft",
        )
        self.assertEqual(repo_of("xf::scipy__scipy::scipy/stats/x.py::fit::tuple_order"), "scipy__scipy")

    def test_repo_of_rejects_malformed_id(self):
        with self.assertRaises(ValueError):
            repo_of("no-separators-here")


class BootstrapTests(_TempDirCase):
    def _mixed(self):
        spec = []
        pattern = [(True, False), (True, True), (False, True), (True, False), (False, False), (True, False)]
        for repo in ("r1__a", "r2__b", "r3__c"):
            for i, (a, b) in enumerate(pattern):
                spec.append((task_id(repo, i), {"1-diff": b, "2-evidence": b, "3-topology": a}))
        return load(write_jsonl(self.dir, paired_rows(spec)))

    def test_point_estimate_is_direct_difference_and_interval_contains_it(self):
        data = self._mixed()
        paired, _ = pairs(data, "3-topology", "2-evidence", "precise")
        direct = sum(a for _, a, _ in paired) / len(paired) - sum(b for _, _, b in paired) / len(paired)
        for cluster in ("repo", "task"):
            point, lo, hi = paired_bootstrap(data, "3-topology", "2-evidence", "precise", trials=500, cluster=cluster)
            self.assertAlmostEqual(point, direct)
            self.assertLessEqual(lo, point)
            self.assertGreaterEqual(hi, point)

    def test_identical_arms_interval_contains_zero_and_mcnemar_p_is_one(self):
        data = self._mixed()
        point, lo, hi = paired_bootstrap(data, "1-diff", "2-evidence", "precise", trials=300)
        self.assertEqual(point, 0.0)
        self.assertLessEqual(lo, 0.0)
        self.assertGreaterEqual(hi, 0.0)
        mc = mcnemar(data, "1-diff", "2-evidence", "precise")
        self.assertEqual((mc["b"], mc["c"]), (0, 0))
        self.assertEqual(mc["p"], 1.0)

    def test_strong_effect_excludes_zero_and_p_is_tiny(self):
        spec = [(task_id(f"r{i % 4}__x", i), {"1-diff": True, "2-evidence": False, "3-topology": False}) for i in range(20)]
        data = load(write_jsonl(self.dir, paired_rows(spec)))
        for cluster in ("repo", "task"):
            point, lo, hi = paired_bootstrap(data, "1-diff", "2-evidence", "precise", trials=300, cluster=cluster)
            self.assertEqual(point, 1.0)
            self.assertGreater(lo, 0.0)
        mc = mcnemar(data, "1-diff", "2-evidence", "precise")
        self.assertEqual((mc["b"], mc["c"], mc["n"]), (20, 0, 20))
        self.assertAlmostEqual(mc["p"], 2 * 0.5 ** 20)
        self.assertLess(mc["p"], 1e-5)

    def test_repo_clustering_is_wider_than_task_clustering_when_effect_sits_in_one_repo(self):
        spec = []
        for i in range(10):  # repo A: topology wins every task
            spec.append((task_id("alpha__a", i), {"1-diff": False, "2-evidence": False, "3-topology": True}))
        for i in range(10):  # repo B: no difference at all
            spec.append((task_id("beta__b", i), {"1-diff": False, "2-evidence": False, "3-topology": False}))
        data = load(write_jsonl(self.dir, paired_rows(spec)))
        p_repo, lo_repo, hi_repo = paired_bootstrap(data, "3-topology", "2-evidence", "precise", trials=2000, cluster="repo")
        p_task, lo_task, hi_task = paired_bootstrap(data, "3-topology", "2-evidence", "precise", trials=2000, cluster="task")
        self.assertEqual(p_repo, p_task)
        self.assertEqual(p_repo, 0.5)
        self.assertGreaterEqual(hi_repo - lo_repo, hi_task - lo_task)
        # With two repositories the repo bootstrap can draw {B, B}, so it must reach zero.
        self.assertLessEqual(lo_repo, 0.0)
        self.assertGreater(lo_task, 0.0)

    def test_bootstrap_is_deterministic_for_a_seed(self):
        data = self._mixed()
        one = paired_bootstrap(data, "3-topology", "2-evidence", "precise", trials=200, seed=7)
        two = paired_bootstrap(data, "3-topology", "2-evidence", "precise", trials=200, seed=7)
        self.assertEqual(one, two)

    def test_unknown_cluster_is_rejected(self):
        data = self._mixed()
        with self.assertRaises(ValueError):
            paired_bootstrap(data, "3-topology", "2-evidence", "precise", trials=10, cluster="kind")


class McNemarTests(unittest.TestCase):
    def test_exact_p_for_b5_c0(self):
        self.assertAlmostEqual(mcnemar_exact_p(5, 0), 0.0625)
        self.assertAlmostEqual(mcnemar_exact_p(0, 5), 0.0625)

    def test_exact_p_is_one_when_discordant_pairs_balance_or_are_absent(self):
        self.assertEqual(mcnemar_exact_p(0, 0), 1.0)
        self.assertEqual(mcnemar_exact_p(4, 4), 1.0)

    def test_exact_p_for_asymmetric_counts_matches_binomial_tail(self):
        # b=1, c=6: m=7, k=1 -> 2 * (C(7,0)+C(7,1)) / 2**7 = 16/128
        self.assertAlmostEqual(mcnemar_exact_p(1, 6), 16 / 128)


class HolmTests(unittest.TestCase):
    def test_holm_adjustment_ordering(self):
        raw = [0.01, 0.04, 0.03]
        adjusted = holm(raw)
        self.assertEqual(len(adjusted), 3)
        self.assertAlmostEqual(adjusted[0], 0.03)  # smallest p * 3
        self.assertAlmostEqual(adjusted[2], 0.06)  # 0.03 * 2
        self.assertAlmostEqual(adjusted[1], 0.06)  # 0.04 * 1 = 0.04, lifted to keep monotone
        # Adjusted values are never below raw and are ordered like the raw p-values.
        for r, a in zip(raw, adjusted):
            self.assertGreaterEqual(a, r)
        order_raw = sorted(range(3), key=lambda i: raw[i])
        self.assertEqual([adjusted[i] for i in order_raw], sorted(adjusted))

    def test_holm_caps_at_one_and_handles_empty(self):
        self.assertEqual(holm([]), [])
        self.assertEqual(holm([0.9, 0.8]), [1.0, 1.0])


class MissingMetricTests(_TempDirCase):
    def test_missing_mechanism_key_skips_rows_with_a_count_instead_of_crashing(self):
        spec = [(task_id("acme__w", i), {"1-diff": True, "2-evidence": False, "3-topology": True}) for i in range(6)]
        rows = paired_rows(spec)
        # Two tasks carry the future `mechanism` field, four do not; one of the two is null.
        for r in rows:
            if r["task_id"] == task_id("acme__w", 0):
                r["mechanism"] = True
                r["message"] = "ok"
            if r["task_id"] == task_id("acme__w", 1):
                r["mechanism"] = None
        data = load(write_jsonl(self.dir, rows))
        paired, skipped = pairs(data, "3-topology", "2-evidence", "mechanism")
        self.assertEqual(len(paired), 1)
        self.assertEqual(skipped, 5)
        mc = mcnemar(data, "3-topology", "2-evidence", "mechanism")
        self.assertEqual(mc["skipped"], 5)
        self.assertEqual(mc["n"], 1)
        rows_out = {r["arm"]: r for r in table(data, "mechanism")}
        self.assertEqual(rows_out["3-topology"]["n_metric"], 1)
        self.assertEqual(rows_out["3-topology"]["metric_missing"], 5)
        text = report(data.path, metric="mechanism", trials=50)
        self.assertIn("skipped=5", text)

    def test_metric_entirely_absent_yields_nan_interval_not_crash(self):
        spec = [(task_id("acme__w", i), {"1-diff": True, "2-evidence": False, "3-topology": True}) for i in range(3)]
        data = load(write_jsonl(self.dir, paired_rows(spec)))
        point, lo, hi = paired_bootstrap(data, "3-topology", "2-evidence", "mechanism", trials=10)
        self.assertTrue(point != point and lo != lo and hi != hi)  # all NaN
        text = report(data.path, metric="mechanism", trials=10)
        self.assertIn("no interval (no paired rows)", text)


class TableAndCellsTests(_TempDirCase):
    def _data(self):
        spec = [
            (task_id("acme__w", 0), {"1-diff": False, "2-evidence": True, "3-topology": True}),
            (task_id("acme__w", 1), {"1-diff": False, "2-evidence": False, "3-topology": True}),
            (task_id("zen__z", 2), {"1-diff": True, "2-evidence": False, "3-topology": False}),
        ]
        rows = paired_rows(spec)
        rows[0]["findings"] = 3
        rows[0]["flagged_distractors"] = 2
        rows[0]["parse_failed"] = True
        return load(write_jsonl(self.dir, rows))

    def test_table_has_one_row_per_arm_with_expected_columns(self):
        rows = table(self._data(), "precise")
        self.assertEqual([r["arm"] for r in rows], sorted(ARMS))
        diff = rows[0]
        self.assertEqual(diff["n"], 3)
        self.assertAlmostEqual(diff["mean_metric"], 1 / 3)
        self.assertAlmostEqual(diff["mean_findings"], (3 + 1 + 1) / 3)
        self.assertAlmostEqual(diff["mean_flagged_distractors"], 2 / 3)
        self.assertEqual(diff["parse_failed"], 1)
        self.assertAlmostEqual(diff["mean_prompt_chars"], 1000 + len("1-diff") * 100)
        topo = rows[2]
        self.assertAlmostEqual(topo["mean_metric"], 2 / 3)

    def test_all_cells_covers_every_pair_and_adds_holm(self):
        data = self._data()
        wanted = [("3-topology", "2-evidence"), ("1-diff", "2-evidence"), ("3-topology", "1-diff")]
        cells = all_cells(data, "precise", wanted, trials=100)
        self.assertEqual([(c["arm_a"], c["arm_b"]) for c in cells], wanted)
        for c in cells:
            self.assertIn("p_holm", c)
            self.assertGreaterEqual(c["p_holm"], c["p"])
            self.assertIn("repo_ci", c)
            self.assertIn("task_ci", c)
        self.assertEqual(cells[0]["b"], 1)
        self.assertEqual(cells[0]["c"], 0)


class ReportTests(_TempDirCase):
    def _path(self):
        spec = [(task_id(f"repo{i % 3}__r", i), {"1-diff": i % 2 == 0, "2-evidence": i % 3 == 0, "3-topology": True}) for i in range(12)]
        rows = paired_rows(spec)
        rows.append(row(task_id("repo0__r", 0), "1-diff", False))  # one duplicate
        rows.append(row(task_id("lonely__l", 99), "1-diff", True))  # one incomplete task
        return write_jsonl(self.dir, rows)

    def test_report_states_counts_and_never_says_significant(self):
        text = report(self._path(), metric="precise", trials=100,
                      primary=("3-topology", "2-evidence"), secondary=("1-diff", "2-evidence"))
        self.assertNotIn("significant", text.lower())
        self.assertIn("duplicates dropped:   1", text)
        self.assertIn("incomplete dropped:   1", text)
        self.assertIn("tasks compared:       12", text)
        self.assertIn("openai/gpt-4o-mini", text)
        self.assertIn("encoding:             tag", text)
        self.assertIn("primary: 3-topology minus 2-evidence", text)
        self.assertIn("secondary: 1-diff minus 2-evidence", text)
        self.assertIn("repo-clustered 95% CI", text)
        self.assertIn("task-clustered 95% CI", text)
        self.assertIn("McNemar b=", text)
        self.assertIn("Holm-adjusted p=", text)
        self.assertTrue("interval excludes zero" in text or "interval spans zero" in text)
        for arm in ARMS:
            self.assertIn(arm, text)

    def test_report_names_an_arm_that_is_absent_instead_of_crashing(self):
        text = report(self._path(), metric="precise", trials=50, secondary=("6-corrupted", "2-evidence"))
        self.assertIn("arm(s) absent from file: 6-corrupted", text)
        self.assertIn("primary: 3-topology minus 2-evidence", text)

    def test_cli_main_prints_the_report(self):
        path = self._path()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            returned = main([str(path), "--metric", "hit", "--trials", "50",
                             "--secondary", "1-diff", "2-evidence", "--pair", "3-topology", "1-diff"])
        printed = buffer.getvalue()
        self.assertEqual(printed, returned)
        self.assertIn("metric:               hit", printed)
        self.assertIn("extra 1: 3-topology minus 1-diff", printed)
        self.assertIn("comparisons (3 in the Holm family)", printed)


if __name__ == "__main__":
    unittest.main()


class BalancedViewTests(unittest.TestCase):
    def test_balanced_separates_defects_from_twins(self):
        import json, tempfile, os
        from experiments.analyse_structure import load, balanced
        rows = []
        for i in range(4):
            for arm in ("1-diff", "2-evidence"):
                rows.append({"task_id": f"xf::o__r::p.py::f::k::{i}", "arm": arm, "is_defect": True,
                             "correct": True, "hit": True, "precise": True})
            for arm in ("1-diff", "2-evidence"):
                rows.append({"task_id": f"xf::o__r::p.py::f::k::{i}::safe", "arm": arm, "is_defect": False,
                             "correct": arm == "2-evidence", "hit": arm == "1-diff", "precise": False})
        d = tempfile.mkdtemp(); path = os.path.join(d, "s.jsonl")
        with open(path, "w") as h:
            for r in rows: h.write(json.dumps(r) + "\n")
        b = balanced(load(path), "correct")
        self.assertEqual(b["1-diff"]["n_defect"], 4); self.assertEqual(b["1-diff"]["n_twin"], 4)
        self.assertAlmostEqual(b["1-diff"]["balanced"], 0.5)
        self.assertAlmostEqual(b["2-evidence"]["balanced"], 1.0)
