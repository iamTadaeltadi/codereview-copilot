# c-CRAB rerun with numbered diff lines (29 October 2026)

The run pre-registered in the amendment of `paper/PLAN.md` §10 (commit 7644b70), executed once.
Identical to `results/ccrab-v2/` in every setting (195 tasks, 246 defects, 63 repositories,
gpt-4o-mini, temperature 0.1, seed 0, code payloads of 3,000 tokens for B/C/Cx/D, diff-derived
seeds, `-v2` graph cache read from disk) except one: every context and added line of the diff
carries its new-file line number (`experiments/review.py::number_diff`), the same for all
conditions, and the output contract says so in one sentence. `results/ccrab-v2/` stays as it is.

**Line accuracy, before and after** (`line-accuracy.txt`; findings that quote a token present in
the diff): diff-only exact-line share 8.9% → 71.2%, more than 5 lines off 39.4% → 3.3%; the
other conditions move the same way (pooled 8.5% → 71.3%, 41.8% → 3.8%).

**Outcome** (`analysis.txt`, `analysis-exact.txt`, `chance-baseline.txt`): 243 defects answered in
all five conditions. Six replies were not scored (4 unparseable JSON, 2 cut at the output cap).

| condition | localised, tol 5 | random-line chance | exact line | chance | mean findings |
|---|---|---|---|---|---|
| A diff only | 49.8% | 35.0% | 24.3% | 4.9% | 5.17 |
| B graph | 51.4% | 35.0% | 24.3% | 4.9% | 4.95 |
| C random, any file | 52.3% | 35.6% | 23.0% | 5.0% | 5.07 |
| Cx random, other files | 50.6% | 35.9% | 22.6% | 4.9% | 5.02 |
| D lexical | 51.9% | 34.9% | 23.5% | 4.9% | 4.89 |

Every condition is now above its random-line baseline with intervals excluding zero (tolerance 5
by about 15 to 17 points, exact line by 18 to 20, top-1 by 12 to 13). Primary comparison B − Cx:
+0.8 points, repository bootstrap [−1.3, +3.3], task bootstrap [−2.1, +3.7]; spans zero. B − A
+1.6 [−1.1, +4.5]; C − A +2.5 [−0.8, +5.4]; D − A +2.1 [−1.7, +5.7]. No paired difference between
conditions excludes zero at either tolerance. (The exact-line rate in `analysis-exact.txt` is
recomputed from the run's tolerance-5 match, `chance-baseline.txt` re-matches at tolerance 0; the
two differ by one defect for A and B.)

**Cost.** $0.87 recorded (`cost.log`, `launcher.log`); the $2.00 stop never triggered.

**Files.** `{A,B,C,Cx,D}-outcomes.jsonl` (the `condition` field of `Cx-outcomes.jsonl` reads `C`;
it is the pass run with `--prefer-cross-file`), `{main,Cx,C}-raw.jsonl`, `{main,Cx,C}-run.log`,
`{main,Cx,C}-config.json`, `findings-per-task.txt`, `launch.sh`, and `hand-label-sample.csv`:
50 findings drawn with seed 0 from all 4,863 in this run (`experiments/sample_comments.py`), each
with its task, condition, path, line, comment, whether the line is in a hunk, the distance to the
nearest ground-truth defect in that file, the containing hunk, the full diff, and empty `label`
and `note` columns.

**Known limitation, as before.** Methods are keyed without their class (69 of 84 false-positive
caller edges in `results/graph-validation/` were on methods). Not fixed for this run.
