# c-CRAB replication of the final run on deepseek-v3.2 (1–3 November 2026)

The replication pre-registered in `paper/PLAN.md` §12 (commit 15d84ab, amendments b071936 and
ee00499), executed once. Run 4's exact configuration (`results/ccrab-final/`) with one change,
the model: `deepseek/deepseek-v3.2` through OpenRouter, temperature 0.1, seed 0. Same 195 tasks,
246 defects, 63 repositories, numbered diff, plain code-block context, callers-first graph walk
without test files, class seeds dropped, 3,000 code tokens for B/C/Cx/D, tolerance 5. The
launcher is `launch.sh`; the gpt-4o-mini records in `ccrab-final/` were not changed.

**How it ran.** Three sequential passes (A,B,D; Cx; C), 975 calls, $2.15 recorded (`cost.log`).
The machine slept for long stretches on 1–2 November, and 15 calls returned no scorable reply
(7 read timeouts after four attempts, 5 unparseable JSON, 3 cut off at the output limit); the
runner writes no row for such a call. By the §12 amendment of 3 November each pass was relaunched
once in resume mode, which calls only the missing pairs; all 15 came back (`*-run-pass1.log` are
the first-pass logs, `*-run.log` the retry logs). numpy-20310 is skipped in B, C, Cx and D as in
run 4 (no source file fetchable), so 245 defects are paired in all five conditions.

**Primary comparison, fixed before the run** (`analysis-primary-subset.txt`): B − Cx on the
localised rate at tolerance 5, on the 77 committed strict outside-diff source-file defect ids
(`primary-subset.txt`, byte-identical to run 4's); 65 paired here.

| subset: strict outside-diff, source files (n = 65) | B graph | Cx random other files | A diff only | C random any | D lexical |
|---|---|---|---|---|---|
| localised, tolerance 5 | 67.7% | 75.4% | 72.3% | 70.8% | 70.8% |
| exact line | 36.9% | 50.8% | 44.6% | 41.5% | 36.9% |

B − Cx = **−7.7 points**, repository bootstrap [−17.8, +3.6], task bootstrap [−18.5, +1.5];
spans zero, sign reversed from run 4's +12.5 [+5.0, +20.8] on gpt-4o-mini. B − A −4.6
[−11.9, +3.4]; Cx − A +3.1 [−6.7, +11.3]. At exact line B − Cx is −13.8 [−24.7, −1.4], excludes
zero in Cx's favour. **The run-4 lead does not replicate on a second model.**

**Secondary (a), loose outside-diff source-file defects** (`analysis-secondary-loose.txt`,
`secondary-subset-loose.txt`, 118 ids, 103 paired): B 64.1%, Cx 72.8%, A 69.9%, C 69.9%,
D 65.0%. B − Cx −8.7 [−17.2, 0.0]; B − A −5.8 [−11.7, 0.0]; exact line B − Cx −12.6
[−21.5, −3.1], excludes zero.

**Secondary (b)–(d), all 245 paired defects** (`analysis.txt`, `analysis-exact.txt`,
`chance-baseline.txt`):

| condition | localised, tol 5 | random-line chance | exact line | chance | mean findings |
|---|---|---|---|---|---|
| A diff only | 64.5% | 43.4% | 35.1% | 6.4% | 5.5 |
| B graph | 61.6% | 42.0% | 34.3% | 6.3% | 5.1 |
| C random, any file | 66.9% | 43.9% | 35.1% | 6.5% | 5.5 |
| Cx random, other files | 66.9% | 39.3% | 38.8% | 5.8% | 4.7 |
| D lexical | 60.8% | 42.7% | 32.2% | 6.4% | 5.2 |

B − Cx −5.3 [−12.0, +0.8] (task bootstrap [−11.0, +0.4]); B − A −2.9 [−6.6, +0.9]; B − C −5.3
[−9.8, −1.4], excludes zero; Cx − A +2.4 [−2.6, +8.3]; C − A +2.4 [−1.4, +6.8]; D − A −3.7
[−8.1, +1.0]. Every condition is 18 to 28 points above its random-line baseline at tolerance 5
and 26 to 33 at exact line, intervals excluding zero. deepseek-v3.2 localises 10 to 14 points
more defects than gpt-4o-mini did in run 4 in every condition, and its random-line baseline is
higher (39 to 44% against 35%) because it reports about as many findings over fewer lines.
(Exact line in `analysis-exact.txt` is recomputed from the tolerance-5 match; `chance-baseline.txt`
re-matches at tolerance 0; they differ by one or two defects.)

**Line accuracy** (`line-accuracy.txt`): 74.7% exact, 95.8% within 5 lines, 4.2% more than 5
off, pooled over 3,441 located findings; by condition 72.0% to 77.4% exact.

**Evidence recall** (`evidence-recall.txt`): identical to run 4 by construction, since the
delivered context does not depend on the model: B 61.9%, D 60.6%, C 50.6%, Cx 50.0%, A 0.0%.
So B delivered the named evidence to the same defects as in run 4, and deepseek-v3.2 localised
fewer of them with it than with random other files.

**Reading.** On gpt-4o-mini the graph context raised the localised rate on the subset; on
deepseek-v3.2, which localises more from the diff alone, the same delivered context lowers it
and random other-file context is the best condition. The primary interval spans zero and the
exact-line interval favours the control. The paper reports this as the replication outcome.

**Files.** `{A,B,C,Cx,D}-outcomes.jsonl` (the `condition` field of `Cx-outcomes.jsonl` reads `C`),
`{main,Cx,C}-raw.jsonl` with `context_text` and delivered ids, `{main,Cx,C}-run.log` (retry pass),
`{main,Cx,C}-run-pass1.log` (first pass), `{main,Cx,C}-config.json`, `primary-subset.txt`,
`secondary-subset-loose.txt`, `analysis-primary-subset{,-exact}.txt`,
`analysis-secondary-loose{,-exact}.txt`, `launch.sh`, `launcher.log`, `launcher-pass1.log`,
`cost.log`, and `hand-label-sample.csv` (50 findings, seed 0).
