#!/usr/bin/env python3
"""Power analysis for the paired condition comparison.

Every condition reviews the same pull request, so a pair is one task judged
under two conditions and the right test is McNemar's on the discordant pairs.
This simulates that design to answer one question before any money is spent on
LLM calls: at the benchmark size available, what size of effect can be detected?

    python experiments/power.py
    python experiments/power.py --n 184 --base-rate 0.30
"""

from __future__ import annotations

import argparse
import random
from statistics import NormalDist


def mcnemar_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    statistic = (abs(b - c) - 1) ** 2 / n
    return 1 - _chi2_cdf_1df(statistic)


def _chi2_cdf_1df(x: float) -> float:
    if x <= 0:
        return 0.0
    return 2 * NormalDist().cdf(x ** 0.5) - 1


def simulate_power(
    n: int,
    base_rate: float,
    lift: float,
    correlation: float,
    alpha: float,
    trials: int,
    seed: int,
) -> float:
    rng = random.Random(seed)
    treated_rate = base_rate + lift
    if not 0 < treated_rate < 1:
        raise ValueError("base_rate + lift must stay inside (0, 1)")

    swap = 1 - correlation
    hits = 0
    for _ in range(trials):
        b = c = 0
        for _ in range(n):
            baseline = rng.random() < base_rate
            if rng.random() < swap:
                treated = rng.random() < treated_rate
            else:
                treated = baseline
                if not baseline and rng.random() < lift / (1 - base_rate):
                    treated = True
            if treated and not baseline:
                b += 1
            elif baseline and not treated:
                c += 1
        if mcnemar_p(b, c) < alpha:
            hits += 1
    return hits / trials


def minimum_detectable_lift(
    n: int, base_rate: float, correlation: float, alpha: float, target: float, trials: int, seed: int
) -> float | None:
    lift = 0.01
    while base_rate + lift < 0.99:
        power = simulate_power(n, base_rate, lift, correlation, alpha, trials, seed)
        if power >= target:
            return lift
        lift += 0.01
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=184)
    parser.add_argument("--base-rate", type=float, default=0.30)
    parser.add_argument("--correlation", type=float, default=0.7)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--target-power", type=float, default=0.80)
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    print(f"paired design, n={args.n} tasks, baseline pass rate {args.base_rate:.0%}")
    print(f"alpha={args.alpha}, target power={args.target_power:.0%}, "
          f"between-condition agreement={args.correlation:.0%}\n")

    print(f"{'lift':>8}  {'treated rate':>13}  {'power':>7}")
    for lift in (0.03, 0.05, 0.08, 0.10, 0.15, 0.20):
        power = simulate_power(
            args.n, args.base_rate, lift, args.correlation, args.alpha, args.trials, args.seed
        )
        print(f"{lift:>7.0%}  {args.base_rate + lift:>12.0%}  {power:>6.0%}")

    mdl = minimum_detectable_lift(
        args.n, args.base_rate, args.correlation, args.alpha, args.target_power, args.trials, args.seed
    )
    print()
    if mdl is None:
        print(f"no lift below 99% reaches {args.target_power:.0%} power at n={args.n}")
    else:
        print(f"minimum detectable lift at {args.target_power:.0%} power: "
              f"{mdl:.0%} ({args.base_rate:.0%} -> {args.base_rate + mdl:.0%})")

    print("\nIf the true effect is smaller than that, this benchmark cannot")
    print("distinguish it from noise, and the honest report is a confidence")
    print("interval rather than a significance claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
