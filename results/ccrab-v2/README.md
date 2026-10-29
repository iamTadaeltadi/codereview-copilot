# c-CRAB rerun after the retrieval repair (28 October 2026)

The pre-registered run of `paper/PLAN.md` §10, executed once, reported whatever came out.
It replaces nothing: `results/ccrab-today/` and `results/WITHDRAWN-ccrab-graph.md` stay as they are.

**Setup.** 195 c-CRAB stage-3 tasks (246 defects, 63 repositories), gpt-4o-mini via OpenRouter,
temperature 0.1, seed 0. Every condition receives the same diff; B, C, Cx and D receive the same
diff-derived seeds and a 3,000-token payload of code (id, name, type, path, source cut at 40 lines).
No payload carries a line range, metadata, depth or score; the model text carries neither the
condition letter nor the budget block (both stay in the raw records). Graph cache suffix `-v2`.
Three sequential passes of `experiments/run.py` (see `launch.sh`): A, B, D with `--prefer-cross-file`
(only B reads the flag); then C with the flag (= Cx); then C without it.

**Outcome.** Tolerance 5 lines (`analysis.txt`); exact line recomputed from `line_distance`
(`analysis-exact.txt`). 239 defects answered in all five conditions. Rows missing from a condition
are replies the runner could not score (eleven in all: 4 began as JSON but did not parse, 7 hit the
4,096 output-token cap; all logged in the `*-run.log` files).

| condition | localised, tol 5 | exact line | mean findings / task |
|---|---|---|---|
| A diff only | 36.0% | 2.9% | 5.28 |
| B graph, repaired | 32.2% | 2.1% | 5.01 |
| C random, any file | 34.7% | 2.9% | 4.91 |
| Cx random, other files | 34.7% | 3.8% | 5.03 |
| D lexical | 35.6% | 2.1% | 4.98 |

Primary comparison, B − Cx: −2.5 points, repository-clustered bootstrap [−6.0, +1.0], task-clustered
[−6.3, +0.8]; spans zero. B − A: −3.8 [−7.4, +0.0]. No paired difference excludes zero at either
tolerance (`analysis.txt`, `analysis-exact.txt`).

**Cost.** $0.82 recorded (`cost.log`, `launcher.log`); the $3.00 stop rule never triggered.

**Files.** `{A,B,C,Cx,D}-outcomes.jsonl` (the `condition` field of `Cx-outcomes.jsonl` reads `C`;
the file is the pass run with `--prefer-cross-file`), `{main,Cx,C}-raw.jsonl` (findings, usage,
context size, retrieval metadata, raw model text), `{main,Cx,C}-run.log`, `{main,Cx,C}-config.json`,
`findings-per-task.txt`, `analysis.txt`, `analysis-exact.txt`, `launch.sh`.

**Reproduce.** `python experiments/analyse_ccrab.py results/ccrab-v2 results/gpt-4o-mini "<header>"`
and the same with a fifth argument `exact`.

**Known limitation, stated before the run.** Methods are keyed without their class, so same-named
methods in one file share a node (69 of the new builder's 84 false-positive caller edges in
`results/graph-validation/` were on methods). Not fixed for this run.

**Checks on these records (29 October).** `chance-baseline.txt`: the same number of findings as the
model on uniformly random hunk lines, same matcher (`experiments/chance_ccrab.py`); no condition is
above chance at tolerance 5, exact line or top-1. `line-accuracy.txt`: of findings quoting a token
present in the diff, 8.5% name the line containing it and 41.8% are more than 5 lines off
(`experiments/line_accuracy.py`); the diff reached the model without line numbers. Both led to the
amendment in `paper/PLAN.md` §10 and the numbered-diff rerun.
