# Neutral prompt on the third-version defects, deepseek-v3.2 — PARTIAL (stopped by the cost rule)

The run pre-registered in `paper/PLAN.md` §13 (commit 4eb7627), executed once on 3–4 November 2026:
`experiments/run_structure.py --limit 400 --encoding tag --model deepseek/deepseek-v3.2 --neutral-prompt`
on `data/crossfile-v3.jsonl`, all nine arms, the same per-call settings as `v3-neutral-gpt4omini/`
(model changed) and `v3twins-neutral-deepseek/` (benchmark changed). As for those twins, the 277
defects were split into three interleaved shards (`crossfile-v3-shard{0,1,2}.jsonl`, rows 0,3,6,…;
1,4,7,…; 2,5,8,…) run in parallel by `launch.sh`; `structure-shard{0,1,2}.jsonl` are the records,
read together by every analysis.

**Stopped.** The pre-registered rule stopped the run when the recorded cost passed $1.50
(`cost.log`: $1.5053; `launcher.log`). The estimate in §13, near $1.00 for 2,439 replies, was wrong
by the cost per reply, $0.00067 against $0.00039 on the twins. 2,243 replies were recorded: 251
defects have at least one arm, 244 are paired on all nine arms, 26 were never reached (shard 0
stopped at its task 74 of 93, shard 1 at 87 of 92, shard 2 complete) and 5 calls failed on the
network (`run-shard*.log`, DNS or read timeout after four attempts; not re-issued, since the stop
rule had fired). The 244 paired defects are the analysis set, reported as partial. Completing the
run would take about 230 calls, near $0.15, under the runner's resume rule; it was not done
because that would change a stop rule after seeing the data.

**Primary (§13), both parts hold** (`analysis-signal-detection.txt`, H from this run, F from
`v3twins-neutral-deepseek/`, 251 defects and 158 twins in 37 repositories, repository bootstrap):

| arm | H | F | d′ [95%] | c [95%] | d′ − d′(diff) | c − c(diff) |
|---|---|---|---|---|---|---|
| 1 diff only | 0.44 | 0.11 | 1.08 [+0.67, +1.61] | +0.70 [+0.48, +0.98] | | |
| 8 header only | 0.48 | 0.12 | 1.12 [+0.72, +1.65] | +0.61 [+0.36, +0.94] | +0.03 [−0.28, +0.40] | −0.08 [−0.21, +0.09] |
| 7 foreign code | 0.53 | 0.10 | 1.38 [+0.91, +2.07] | +0.62 [+0.38, +0.99] | +0.29 [−0.11, +0.83] | −0.07 [−0.24, +0.15] |
| 2 tolerant caller | 0.59 | 0.13 | 1.34 [+0.99, +1.76] | +0.45 [+0.20, +0.74] | +0.25 [−0.18, +0.64] | −0.25 [−0.43, −0.06] |
| 3 caller + bare link | 0.62 | 0.19 | 1.19 [+0.88, +1.56] | +0.28 [+0.06, +0.52] | +0.11 [−0.30, +0.45] | −0.42 [−0.60, −0.25] |
| 4 caller + typed link | 0.64 | 0.23 | 1.09 [+0.74, +1.51] | +0.20 [−0.02, +0.44] | +0.01 [−0.51, +0.45] | −0.50 [−0.70, −0.32] |
| 6 caller + wrong link | 0.64 | 0.18 | 1.28 [+0.93, +1.71] | +0.29 [+0.06, +0.53] | +0.20 [−0.26, +0.58] | −0.41 [−0.59, −0.25] |
| 5 caller + attributed link | 0.61 | 0.21 | 1.09 [+0.70, +1.55] | +0.27 [+0.04, +0.54] | **+0.00 [−0.40, +0.39]** | **−0.43 [−0.62, −0.25]** |

(i) c(attributed) − c(diff) = −0.43 [−0.62, −0.25], excludes zero: the criterion moves. (ii) d′(attributed)
− d′(diff) = +0.00 [−0.40, +0.39]: the sensitivity is not raised. Every arm with caller code or
dependency metadata lowers c by an interval excluding zero and changes d′ by an interval that
spans zero. The movement is a quarter of gpt-4o-mini's (c −0.43 against −1.78) on a model whose
d′ from the diff alone is three times higher (1.08 against 0.37).

**Secondary** (`analysis-hit.txt`, `analysis-precise.txt`, `analysis-balanced-with-twins.txt`, 244 paired):

| arm | defects hit | exact line | findings per defect | twins cleared | balanced |
|---|---|---|---|---|---|
| 1 diff only | 43.0% | 43.0% | 0.43 | 89.2% | 66.1% |
| 8 header only | 47.1% | 46.3% | 0.48 | 88.0% | 67.6% |
| 7 foreign code | 51.6% | 51.2% | 0.52 | 90.5% | 71.1% |
| 2 tolerant caller | 58.2% | 57.8% | 0.59 | 86.7% | 72.5% |
| 3 caller + bare link | 61.5% | 60.2% | 0.64 | 81.0% | 71.2% |
| 4 caller + typed link | 63.1% | 61.1% | 0.68 | 77.2% | 70.2% |
| 6 caller + wrong link | 63.1% | 61.5% | 0.66 | 82.3% | 72.7% |
| 5 caller + attributed link | 60.2% | 59.4% | 0.61 | 79.1% | 69.7% |

| comparison | defects hit | balanced accuracy |
|---|---|---|
| tolerant caller − diff | +15.2 [+6.9, +22.1] | +6.3 [+0.8, +11.3] |
| foreign code − diff | +8.6 [+1.2, +15.6] | +4.9 [−0.2, +10.0] |
| header − diff | +4.1 [−1.9, +9.8] | +1.4 [−2.7, +5.4] |
| bare link − caller | +3.3 [+0.4, +6.4] | −1.2 [−4.3, +1.6] |
| wrong link − caller | +4.9 [+0.4, +9.3] | +0.2 [−3.1, +3.5] |
| attributed link − diff | +17.2 [+9.1, +23.9] | +3.5 [−2.0, +9.0] |

Where the two models differ: on deepseek-v3.2 the tolerant caller raises the hit rate by 15 points
and costs 2.5 points on the twins, so balanced accuracy rises by 6.3 [+0.8, +11.3]; on gpt-4o-mini
the same caller cost 27 points on the twins and balanced accuracy fell. Foreign code of the same
length raises the hit rate by 8.6 points on this model. Statements about the dependency on top of
the caller add nothing to balanced accuracy on either model (bare link −1.2, wrong link +0.2 here).

**Files.** `structure-shard{0,1,2}.jsonl`, `manipulation-shard{0,1,2}.jsonl`, `run-shard{0,1,2}.log`,
`crossfile-v3-shard{0,1,2}.jsonl` (the shard inputs), `launch.sh`, `launcher.log`, `cost.log`, and the
four analyses. Cost $1.51 recorded.
