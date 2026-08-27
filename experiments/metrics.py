"""Aggregate per-defect outcomes into the numbers the paper prints.

Two rules hold everywhere in this module.

Findings within a task are correlated: a review that understands a pull request
tends to find all of its defects, and one that does not tends to find none of
them. Treating ~1,500 defect rows as independent would understate every
standard error, so every interval here comes from a cluster bootstrap that
resamples whole tasks.

No result is reported as a bare significance verdict. At c-CRAB's size the
minimum detectable lift is a few points, so an effect below that returns "not
distinguishable at this sample size" rather than "no difference", which would be
a different and false claim.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from statistics import NormalDist


DEFAULT_BOOTSTRAP = 2000
DEFAULT_CONFIDENCE = 0.95


@dataclass(frozen=True)
class ConditionSummary:
    condition: str
    tasks: int
    defects: int
    hits: int
    recall: float
    recall_low: float
    recall_high: float
    false_positives: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def precision(self) -> float:
        reported = self.hits + self.false_positives
        return self.hits / reported if reported else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def cost_per_true_finding(self) -> float | None:
        return self.cost_usd / self.hits if self.hits else None

    @property
    def tokens_per_true_finding(self) -> float | None:
        total = self.input_tokens + self.output_tokens
        return total / self.hits if self.hits else None


@dataclass(frozen=True)
class Comparison:
    treatment: str
    baseline: str
    lift: float
    lift_low: float
    lift_high: float
    discordant_treatment_only: int
    discordant_baseline_only: int
    p_value: float

    @property
    def distinguishable(self) -> bool:
        return self.lift_low > 0 or self.lift_high < 0

    def verdict(self) -> str:
        if self.distinguishable:
            direction = "higher" if self.lift > 0 else "lower"
            return (
                f"{self.treatment} is {direction} than {self.baseline} by "
                f"{abs(self.lift):.1%} (95% CI {self.lift_low:+.1%} to {self.lift_high:+.1%})"
            )
        return (
            f"{self.treatment} vs {self.baseline}: {self.lift:+.1%} "
            f"(95% CI {self.lift_low:+.1%} to {self.lift_high:+.1%}) — "
            "not distinguishable at this sample size"
        )


def _by_task(outcomes) -> dict:
    grouped = defaultdict(list)
    for outcome in outcomes:
        grouped[outcome.task_id].append(outcome)
    return grouped


def _rate(rows) -> float:
    return sum(1 for row in rows if row.hit) / len(rows) if rows else 0.0


def _cluster_bootstrap(grouped, statistic, trials: int, confidence: float, seed: int):
    keys = list(grouped)
    if not keys:
        return 0.0, 0.0
    rng = random.Random(seed)
    samples = []
    for _ in range(trials):
        drawn = [grouped[rng.choice(keys)] for _ in keys]
        flat = [row for cluster in drawn for row in cluster]
        if flat:
            samples.append(statistic(flat))
    if not samples:
        return 0.0, 0.0
    samples.sort()
    tail = (1 - confidence) / 2
    low = samples[max(0, int(tail * len(samples)) - 1)]
    high = samples[min(len(samples) - 1, int((1 - tail) * len(samples)))]
    return low, high


def summarise_condition(
    condition: str,
    outcomes,
    false_positives: int = 0,
    usage=None,
    bootstrap: int = DEFAULT_BOOTSTRAP,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = 0,
) -> ConditionSummary:
    rows = [o for o in outcomes if o.condition == condition]
    grouped = _by_task(rows)
    low, high = _cluster_bootstrap(grouped, _rate, bootstrap, confidence, seed)
    usage = usage or {}
    return ConditionSummary(
        condition=condition,
        tasks=len(grouped),
        defects=len(rows),
        hits=sum(1 for row in rows if row.hit),
        recall=_rate(rows),
        recall_low=low,
        recall_high=high,
        false_positives=false_positives,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cost_usd=usage.get("cost_usd", 0.0),
    )


def _mcnemar_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    statistic = (abs(b - c) - 1) ** 2 / n
    if statistic <= 0:
        return 1.0
    return max(0.0, min(1.0, 2 * (1 - NormalDist().cdf(statistic ** 0.5))))


def compare(
    outcomes,
    treatment: str,
    baseline: str,
    bootstrap: int = DEFAULT_BOOTSTRAP,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = 0,
) -> Comparison:
    treated = {o.defect_id: o for o in outcomes if o.condition == treatment}
    control = {o.defect_id: o for o in outcomes if o.condition == baseline}
    shared = sorted(set(treated) & set(control))

    paired = defaultdict(list)
    only_treatment = only_baseline = 0
    for defect_id in shared:
        t, c = treated[defect_id], control[defect_id]
        paired[t.task_id].append((t.hit, c.hit))
        if t.hit and not c.hit:
            only_treatment += 1
        elif c.hit and not t.hit:
            only_baseline += 1

    def lift(rows) -> float:
        if not rows:
            return 0.0
        return sum(1 for t, _ in rows if t) / len(rows) - sum(1 for _, c in rows if c) / len(rows)

    flat = [pair for rows in paired.values() for pair in rows]
    point = lift(flat)
    low, high = _cluster_bootstrap(paired, lift, bootstrap, confidence, seed)

    return Comparison(
        treatment=treatment,
        baseline=baseline,
        lift=point,
        lift_low=low,
        lift_high=high,
        discordant_treatment_only=only_treatment,
        discordant_baseline_only=only_baseline,
        p_value=_mcnemar_p(only_treatment, only_baseline),
    )


def table(summaries) -> str:
    header = (
        f"{'cond':<6}{'tasks':>7}{'defects':>9}{'hits':>7}"
        f"{'recall':>9}{'95% CI':>18}{'prec':>8}{'F1':>7}{'$/hit':>9}"
    )
    lines = [header, "-" * len(header)]
    for s in summaries:
        cost = f"{s.cost_per_true_finding:.4f}" if s.cost_per_true_finding is not None else "-"
        interval = f"[{s.recall_low:.1%}, {s.recall_high:.1%}]"
        lines.append(
            f"{s.condition:<6}{s.tasks:>7}{s.defects:>9}{s.hits:>7}"
            f"{s.recall:>8.1%}{interval:>18}{s.precision:>8.1%}{s.f1:>7.2f}{cost:>9}"
        )
    return "\n".join(lines)
