#!/usr/bin/env python3
"""Analyse a structure experiment (runs/<name>/structure.jsonl) and print every comparison.

    python experiments/analyse_structure.py runs/<name>/structure.jsonl
    python experiments/analyse_structure.py runs/<name>/structure.jsonl --metric hit
    python experiments/analyse_structure.py runs/<name>/structure.jsonl \\
        --primary 3-topology 2-evidence --secondary 6-corrupted 2-evidence \\
        --pair 4-typed 2-evidence --pair 7-random 2-evidence

The file holds one JSON object per (task, arm). Re-runs after a resume append
duplicate (task_id, arm) rows; the first occurrence wins and the count of
dropped duplicates is reported. Only tasks present in every arm are compared,
so an arm that skipped a task cannot be scored on an easier set.

Uncertainty is reported two ways, side by side: a bootstrap that resamples
repositories (tasks from one repository share code, style and the model's
familiarity, so they are not independent) and a bootstrap that resamples
tasks. McNemar's exact test on the discordant pairs is given for each
comparison, with Holm-Bonferroni adjustment across the family of comparisons
so a report shows every cell rather than the one that happened to cross zero.

No third-party dependencies: only the standard library.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

DEFAULT_PRIMARY: Tuple[str, str] = ("3-topology", "2-evidence")
DEFAULT_SECONDARY: Tuple[str, str] = ("6-corrupted", "2-evidence")
DEFAULT_TRIALS = 6000
DEFAULT_SEED = 0
METRICS = ("precise", "hit", "mechanism")


class Dataset(dict):
    """task_id -> arm -> row, plus bookkeeping about what was dropped on load."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.arms: List[str] = []
        self.dropped_duplicates: int = 0
        self.dropped_incomplete: int = 0
        self.path: Optional[Path] = None

    @property
    def tasks(self) -> List[str]:
        return sorted(self.keys())


# --------------------------------------------------------------------------- load


def _read_rows(path: Path) -> Iterable[dict]:
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def load(path) -> Dataset:
    """Read a structure.jsonl file, dedupe on (task_id, arm) keeping the first row,
    and keep only tasks present in every arm that appears in the file."""
    path = Path(path)
    first: Dict[str, Dict[str, dict]] = collections.OrderedDict()
    arms_seen: List[str] = []
    duplicates = 0
    for row in _read_rows(path):
        task_id, arm = row["task_id"], row["arm"]
        if arm not in arms_seen:
            arms_seen.append(arm)
        per_task = first.setdefault(task_id, {})
        if arm in per_task:
            duplicates += 1
            continue
        per_task[arm] = row

    arms = sorted(arms_seen)
    data = Dataset()
    incomplete = 0
    for task_id, per_task in first.items():
        if all(arm in per_task for arm in arms):
            data[task_id] = per_task
        else:
            incomplete += 1
    data.arms = arms
    data.dropped_duplicates = duplicates
    data.dropped_incomplete = incomplete
    data.path = path
    return data


def repo_of(task_id: str) -> str:
    """'xf::owner__repo::path::function::kind' -> 'owner__repo'."""
    parts = task_id.split("::")
    if len(parts) < 2:
        raise ValueError(f"task_id has no repository segment: {task_id!r}")
    return parts[1]


def metric_value(row: dict, metric: str) -> Optional[bool]:
    """The metric as a bool, or None when the row does not carry it (older files
    have no `mechanism`; a null mechanism means the judge could not decide)."""
    value = row.get(metric)
    if value is None:
        return None
    return bool(value)


def pairs(data: Dataset, arm_a: str, arm_b: str, metric: str) -> Tuple[List[Tuple[str, bool, bool]], int]:
    """(task_id, value_a, value_b) for every task where both arms carry the metric,
    plus the count of tasks skipped because at least one side lacks it."""
    out: List[Tuple[str, bool, bool]] = []
    skipped = 0
    for task_id in data.tasks:
        per_task = data[task_id]
        if arm_a not in per_task or arm_b not in per_task:
            skipped += 1
            continue
        va = metric_value(per_task[arm_a], metric)
        vb = metric_value(per_task[arm_b], metric)
        if va is None or vb is None:
            skipped += 1
            continue
        out.append((task_id, va, vb))
    return out, skipped


# ---------------------------------------------------------------------- bootstrap


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    position = q * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def paired_bootstrap(
    data: Dataset,
    arm_a: str,
    arm_b: str,
    metric: str,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
    cluster: str = "repo",
) -> Tuple[float, float, float]:
    """(mean_a - mean_b, lo, hi): percentile 95% interval from a paired bootstrap.

    cluster="repo" resamples repositories with replacement and keeps every task
    of each drawn repository; cluster="task" resamples tasks. The point estimate
    is the plain difference of means over tasks, not a bootstrap average.
    """
    if cluster not in ("repo", "task"):
        raise ValueError(f"cluster must be 'repo' or 'task', got {cluster!r}")
    paired, _ = pairs(data, arm_a, arm_b, metric)
    if not paired:
        return float("nan"), float("nan"), float("nan")

    # Per-task difference is in {-1, 0, 1}; a cluster is summarised by
    # (sum of differences, number of tasks) so each trial is O(#clusters).
    groups: Dict[str, List[int]] = collections.defaultdict(lambda: [0, 0])
    for task_id, va, vb in paired:
        key = repo_of(task_id) if cluster == "repo" else task_id
        groups[key][0] += int(va) - int(vb)
        groups[key][1] += 1
    keys = sorted(groups)
    sums = [groups[k][0] for k in keys]
    counts = [groups[k][1] for k in keys]

    point = sum(sums) / sum(counts)
    rng = random.Random(seed)
    k = len(keys)
    estimates: List[float] = []
    for _ in range(trials):
        total = 0
        n = 0
        for _ in range(k):
            i = rng.randrange(k)
            total += sums[i]
            n += counts[i]
        estimates.append(total / n)
    estimates.sort()
    return point, _quantile(estimates, 0.025), _quantile(estimates, 0.975)


# ------------------------------------------------------------------------ mcnemar


def mcnemar_exact_p(b: int, c: int) -> float:
    """Exact two-sided p for discordant counts b and c under H0: P(b) = P(c) = 1/2."""
    m = b + c
    if m == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(m, i) for i in range(k + 1)) * (0.5 ** m)
    return min(1.0, 2.0 * tail)


def mcnemar(data: Dataset, arm_a: str, arm_b: str, metric: str) -> dict:
    """b = a right and b wrong, c = a wrong and b right, n = paired tasks,
    p = exact two-sided binomial p on the discordant pairs."""
    paired, skipped = pairs(data, arm_a, arm_b, metric)
    b = sum(1 for _, va, vb in paired if va and not vb)
    c = sum(1 for _, va, vb in paired if vb and not va)
    return {
        "arm_a": arm_a,
        "arm_b": arm_b,
        "metric": metric,
        "b": b,
        "c": c,
        "n": len(paired),
        "skipped": skipped,
        "p": mcnemar_exact_p(b, c),
    }


def holm(p_values: Sequence[float]) -> List[float]:
    """Holm-Bonferroni step-down adjustment, returned in the input order."""
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        candidate = min(1.0, (m - rank) * p_values[i])
        running = max(running, candidate)
        adjusted[i] = running
    return adjusted


# -------------------------------------------------------------------------- table


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def balanced(data, metric):
    """Per-arm mean of `metric` on defects and on safe twins separately, and
    their average. A reviewer that flags every mutated line scores at ceiling
    on defects and at zero on twins; the balanced mean exposes that. Rows
    without `is_defect` are treated as defects."""
    out = {}
    for arm in data.arms:
        d, t = [], []
        for task_id, arms in data.items():
            row = arms.get(arm)
            if row is None or row.get(metric) is None:
                continue
            (d if row.get("is_defect", True) else t).append(1.0 if row[metric] else 0.0)
        md = sum(d) / len(d) if d else float("nan")
        mt = sum(t) / len(t) if t else float("nan")
        bal = (md + mt) / 2 if d and t else float("nan")
        out[arm] = {"n_defect": len(d), "n_twin": len(t), "defect": md, "twin": mt, "balanced": bal}
    return out


def table(data: Dataset, metric: str) -> List[dict]:
    """One row per arm: n, mean metric (over rows that carry it), findings,
    flagged distractors, parse failures, prompt size and cost."""
    rows: List[dict] = []
    for arm in data.arms:
        arm_rows = [data[t][arm] for t in data.tasks]
        metric_values = [v for v in (metric_value(r, metric) for r in arm_rows) if v is not None]
        rows.append({
            "arm": arm,
            "n": len(arm_rows),
            "n_metric": len(metric_values),
            "metric_missing": len(arm_rows) - len(metric_values),
            "mean_metric": _mean([float(v) for v in metric_values]),
            "mean_findings": _mean([float(r.get("findings", 0) or 0) for r in arm_rows]),
            "mean_flagged_distractors": _mean([float(r.get("flagged_distractors", 0) or 0) for r in arm_rows]),
            "parse_failed": sum(1 for r in arm_rows if r.get("parse_failed")),
            "mean_prompt_chars": _mean([float(r.get("prompt_chars", 0) or 0) for r in arm_rows]),
            "mean_cost_usd": _mean([float((r.get("usage") or {}).get("cost_usd", 0) or 0) for r in arm_rows]),
        })
    return rows


# ---------------------------------------------------------------------- all cells


def cell(
    data: Dataset,
    arm_a: str,
    arm_b: str,
    metric: str,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Both bootstraps and McNemar for one comparison."""
    point, repo_lo, repo_hi = paired_bootstrap(data, arm_a, arm_b, metric, trials, seed, cluster="repo")
    _, task_lo, task_hi = paired_bootstrap(data, arm_a, arm_b, metric, trials, seed, cluster="task")
    mc = mcnemar(data, arm_a, arm_b, metric)
    return {
        "arm_a": arm_a,
        "arm_b": arm_b,
        "metric": metric,
        "point": point,
        "repo_ci": (repo_lo, repo_hi),
        "task_ci": (task_lo, task_hi),
        "repo_excludes_zero": _excludes_zero(repo_lo, repo_hi),
        "task_excludes_zero": _excludes_zero(task_lo, task_hi),
        "b": mc["b"],
        "c": mc["c"],
        "n": mc["n"],
        "skipped": mc["skipped"],
        "p": mc["p"],
    }


def all_cells(
    data: Dataset,
    metric: str,
    pairs_: Sequence[Tuple[str, str]],
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
) -> List[dict]:
    """cell() for every (arm_a, arm_b) with Holm-adjusted p across the family."""
    cells = [cell(data, a, b, metric, trials, seed) for a, b in pairs_]
    for c, p_adj in zip(cells, holm([c["p"] for c in cells])):
        c["p_holm"] = p_adj
    return cells


def _excludes_zero(lo: float, hi: float) -> Optional[bool]:
    if math.isnan(lo) or math.isnan(hi):
        return None
    return lo > 0 or hi < 0


def _zero_phrase(flag: Optional[bool]) -> str:
    if flag is None:
        return "no interval (no paired rows)"
    return "interval excludes zero" if flag else "interval spans zero"


# ------------------------------------------------------------------------- report


def _fmt(value: float, width: int = 7, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "nan".rjust(width)
    return f"{value:{width}.{digits}f}"


def _fmt_p(p: float) -> str:
    return f"{p:.2e}" if p < 1e-3 else f"{p:.4f}"


def _describe_cell(c: dict, label: str) -> List[str]:
    lines = [f"{label}: {c['arm_a']} minus {c['arm_b']}  (metric={c['metric']}, n={c['n']}, skipped={c['skipped']})"]
    lines.append(
        f"  difference {_fmt(c['point'])}   "
        f"repo-clustered 95% CI [{_fmt(c['repo_ci'][0])}, {_fmt(c['repo_ci'][1])}]   "
        f"task-clustered 95% CI [{_fmt(c['task_ci'][0])}, {_fmt(c['task_ci'][1])}]"
    )
    lines.append(f"  repo-clustered: {_zero_phrase(c['repo_excludes_zero'])}; task-clustered: {_zero_phrase(c['task_excludes_zero'])}")
    holm_part = f"  Holm-adjusted p={_fmt_p(c['p_holm'])}" if "p_holm" in c else ""
    lines.append(f"  McNemar b={c['b']} (a right, b wrong)  c={c['c']} (a wrong, b right)  exact p={_fmt_p(c['p'])}{holm_part}")
    return lines


def _fill_missing(data, metric):
    for arms in data.values():
        for row in arms.values():
            if row.get(metric) is None:
                row[metric] = False
    return data


def report(
    path,
    metric: str = "precise",
    primary: Tuple[str, str] = DEFAULT_PRIMARY,
    secondary: Tuple[str, str] = DEFAULT_SECONDARY,
    extra_pairs: Sequence[Tuple[str, str]] = (),
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
    missing_as_false: bool = False,
) -> str:
    data = load(path)
    if missing_as_false:
        _fill_missing(data, metric)
    lines: List[str] = []
    models = sorted({str(r.get("model")) for t in data.values() for r in t.values()})
    encodings = sorted({str(r.get("encoding")) for t in data.values() for r in t.values()})
    lines.append(f"file:                 {data.path}")
    lines.append(f"model:                {', '.join(models) or '-'}")
    lines.append(f"encoding:             {', '.join(encodings) or '-'}")
    lines.append(f"metric:               {metric}")
    lines.append(f"arms:                 {', '.join(data.arms)}")
    lines.append(f"tasks compared:       {len(data)}")
    lines.append(f"duplicates dropped:   {data.dropped_duplicates}  (first occurrence kept)")
    lines.append(f"incomplete dropped:   {data.dropped_incomplete}  (tasks missing from at least one arm)")
    lines.append(f"bootstrap:            {trials} trials, seed {seed}, percentile 2.5/97.5")
    lines.append("")

    header = f"{'arm':<14}{'n':>5}{'n_metric':>10}{'mean_' + metric:>14}{'findings':>10}{'distract':>10}{'parse_fail':>12}{'prompt_chars':>14}{'cost_usd':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for r in table(data, metric):
        lines.append(
            f"{r['arm']:<14}{r['n']:>5}{r['n_metric']:>10}{_fmt(r['mean_metric'], 14)}"
            f"{_fmt(r['mean_findings'], 10, 2)}{_fmt(r['mean_flagged_distractors'], 10, 2)}"
            f"{r['parse_failed']:>12}{_fmt(r['mean_prompt_chars'], 14, 0)}{_fmt(r['mean_cost_usd'], 12, 5)}"
        )
    lines.append("")

    bal = balanced(data, metric)
    if any(v["n_twin"] for v in bal.values()):
        lines.append(f"{'arm':<14}{'n_defect':>9}{'n_twin':>7}{'on defects':>12}{'on twins':>10}{'balanced':>10}")
        for arm, v in bal.items():
            lines.append(f"{arm:<14}{v['n_defect']:>9}{v['n_twin']:>7}{v['defect']:>12.3f}{v['twin']:>10.3f}{v['balanced']:>10.3f}")
        lines.append("")

    family: List[Tuple[str, Tuple[str, str]]] = [("primary", tuple(primary)), ("secondary", tuple(secondary))]
    family += [(f"extra {i + 1}", tuple(p)) for i, p in enumerate(extra_pairs)]
    present = [(label, p) for label, p in family if p[0] in data.arms and p[1] in data.arms]
    for label, p in family:
        if (label, p) not in present:
            missing = [arm for arm in p if arm not in data.arms]
            lines.append(f"{label}: {p[0]} minus {p[1]} not computed; arm(s) absent from file: {', '.join(missing)}")
    if any((label, p) not in present for label, p in family):
        lines.append("")

    cells = all_cells(data, metric, [p for _, p in present], trials, seed)
    lines.append(f"comparisons ({len(cells)} in the Holm family)")
    lines.append("")
    for (label, _), c in zip(present, cells):
        lines.extend(_describe_cell(c, label))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------- CLI


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="runs/<name>/structure.jsonl")
    parser.add_argument("--missing-as-false", action="store_true",
                        help="treat a null metric as False: a miss cannot state the mechanism, so a judge "
                             "verdict that exists only for hits must count misses as failures or arms are "
                             "compared on different task subsets")
    parser.add_argument("--metric", default="precise", help="any boolean column, e.g. precise, hit, mechanism, mechanism_judge, correct, correct_precise")
    parser.add_argument("--primary", nargs=2, metavar=("ARM_A", "ARM_B"), default=list(DEFAULT_PRIMARY))
    parser.add_argument("--secondary", nargs=2, metavar=("ARM_A", "ARM_B"), default=list(DEFAULT_SECONDARY))
    parser.add_argument("--pair", nargs=2, action="append", metavar=("ARM_A", "ARM_B"), default=[],
                        help="extra comparison; repeatable")
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> str:
    args = _parse_args(argv)
    text = report(
        args.path,
        metric=args.metric,
        primary=tuple(args.primary),
        secondary=tuple(args.secondary),
        extra_pairs=[tuple(p) for p in args.pair],
        trials=args.trials,
        seed=args.seed,
        missing_as_false=args.missing_as_false,
    )
    sys.stdout.write(text)
    return text


if __name__ == "__main__":
    main()
