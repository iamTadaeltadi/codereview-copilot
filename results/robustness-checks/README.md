# Robustness checks behind specific sentences of the paper

Re-analysis of records already committed in `results/`. No API calls. Each script reads the
committed files, uses the same repository-cluster bootstrap as the main analyses (6,000 draws,
`random.Random(0)`) unless stated, and writes nothing except its printed output, saved next to it
as `.txt`. Run any script from the repository root, e.g. `python results/robustness-checks/roc_think_transitions.py`.

These checks were added after the paper's numbers were written; they confirm the sentences below.
None of them was pre-registered.

| Script (output) | Paper sentence it backs | Key numbers |
|---|---|---|
| `sdt_bonferroni.py` (`.txt`) | Section 4, twins: "six of six and five of six also at the Bonferroni level for eight arms" | Bonferroni 99.375% intervals for Δc, kind-matched: gpt-4o-mini 6/6 caller arms exclude 0, deepseek-v3.2 5/6 (2-evidence includes 0) |
| `roc_multiplicity.py` (`.txt`) | Abstract and Table 3: "+0.08, post hoc and not robust to correction for four runs" | deepseek-v3.2 reasoning-off controlled run: ΔAUC +0.081, 98.75% (Bonferroni, 4 runs) [+0.000, +0.163] |
| `roc_permutation.py` (`.txt`) | Same sentence (check on the cluster bootstrap) | item-level paired permutation p = 0.0375 for that run, which fails Holm over the four runs (gpt-4o-mini attributed: p = 0.0020) |
| `roc_think_same_day.py` (`.txt`) | Reasoning on: "+0.23 [+0.15, +0.31] on the 116 items whose three arms all ran that day" | attributed − foreign on the 116 same-day items: +0.226 [+0.148, +0.313] |
| `roc_think_transitions.py` (`.txt`) | Reasoning on: "cut the twin flag rate from 91.6% to 80.4% (19 twins cleared, 3 newly flagged)" | twins flagged 131/143 → 115/143; 19 flag → no flag, 3 no flag → flag |

The short-reply numbers in the "Hidden reasoning" paragraph are in
`results/twins-kind-matched/posthoc-reply-length.txt`.
