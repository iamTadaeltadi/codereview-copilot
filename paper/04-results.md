# Results

All numbers come from the files under `results/`, recomputed from the frozen per-call records by `scripts/reproduce.py`. Intervals are 95% percentile bootstraps that resample repositories; the task-resampled interval, shown in the analysis files, never changes a verdict. Nothing is reported from a run that did not complete on its paired set; the one stopped run is described in 4.7 and kept whole.

## 4.1 The partial-input ceiling

A model given nothing but the diff finds the mutated line almost always, on every version of the generated benchmark (gpt-4o-mini, a hit is the exact line):

| Benchmark version | tasks | diff-only hit | what was wrong with the instrument |
|---|---|---|---|
| first (withdrawn) | 204 | 93% | regex evidence; distractors broke the file in 145 tasks |
| second (withdrawn) | 229 | 97.8% | line numbers in labels; loose resolver; tree-changing distractors; defect last in 62% |
| third | 201 of 277 | 95.5% | none found: audit 0 / 0 / 0, position balanced, labels name functions |
| c-CRAB real defects (3.6) | 219 | 32.9% | |

The third version was run under the stop rule of 3.4 and stopped at 201 defects when the rate was clearly above 95%; there were no parse failures in 1,802 replies. By kind the rate is 104 of 107 default flips, 58 of 61 tuple reorderings, 19 of 21 `None` sentinels, 6 of 6 exception types and 5 of 6 empty-to-`None`. The reason is not that the model reads the defect: it reports 2.66 findings per task on average against four hunks, and 1.58 of those findings are on the three harmless rewrites. A semantic change among three cosmetic ones is always among the lines it flags. Precision, the rate at which the mutated line is the only line flagged, is 24.4%.

Repairing the second version's leaks changed the ceiling by two points. Balanced position, function-name labels, mixed syntax-tree-neutral distractors and a strict resolver remove the ways a model could find the line without reading the change; they do not remove the fact that a flipped default or a swapped return among quote rewrites looks like the only thing worth saying. Detection rate on a mutation benchmark of this shape measures whether the mutated line looks odd, and it does. The same check on the real defects gives 32.9%: given only the diff, gpt-4o-mini localises 72 of the 219 paired c-CRAB defects. That set leaves room for context where the generated sets do not, and it is the set on which 4.5 reports a retrieval result.

## 4.2 Anchor versus evidence, on real comments

Of 291 test-verified c-CRAB defects, 291 anchor in a file the pull request changed and 213 on a changed line. Under the strict reading, 97 (33%) refer to something the diff does not contain; under the loose reading, 146 (50%). Where a comment sits is not where its justification lives. A benchmark that scores a review by where its comment lands will accept a comment that found the line for the wrong reason, and a benchmark that gives the model only the diff withholds the justification for a third to a half of its own ground truth.

## 4.3 Safe twins

[[TWINS-RESULTS]]

## 4.4 Test verification of the generated defects

Of the second version's defects, 86 were run against their repositories' own test suites (`results/test-verified/`): 17 are test-verified, meaning a test that passed before the mutation fails after it; 28 are not caught by the tests selected for the mutated module; 24 repositories could not be installed in the sandbox (native builds, a Python 3.13 requirement); 11 had no passing test before the mutation and 6 had no test to select. Among the 45 that could be run to a verdict, 38% are caught by an existing test. The test-verified defects are 9 default flips, 6 tuple reorderings and 2 `None` sentinels, from eight repositories. The same check on the third version is running at the time of writing and will be reported in the artifact. [[TESTVERIFY-V3]]

The syntax-tree verifier accepts many mutations whose breakage no existing test observes. That does not make them harmless: a flipped default on a public function that no test pins is the kind of change a reviewer exists to catch. It does mean that a reader who counts only test-verified defects should treat the generated benchmark as resting on an unverified majority, and that a benchmark of this kind should report the fraction.

## 4.5 Real defects: retrieval that reaches the caller

The model throughout is gpt-4o-mini, and the defect set is the 219 paired defects of the 291 that pass the filters in 3.6. The c-CRAB runs from August stand for the conditions that do not retrieve: on the 219 test-verified defects shared with the re-run below, no context, whole changed files and the fault-location oracle all localise 33 to 36%. The graph condition in those runs queried the file node rather than the function, walked two hops, and filled its budget with same-file neighbours, so it reached the depended-on caller in 4% of tasks where that caller was available; it is not reported. Three repairs were made and committed on 30 August, before the controlled re-run was designed: query the enclosing function, walk three hops, and rank other-file neighbours ahead of same-file ones before the budget applies. The fault-location oracle scores no better than the diff because it returns the entities spanning the defect line, which the diff already shows; it is an oracle for location, not for evidence.

All retrieval conditions were re-run on the same day (Figure 2) with the same pipeline, model, budget (1,500 tokens) and tolerance (5 lines), on 219 defects paired across the first four and 218 across all five. The intervals below resample defects and were drawn with an unseeded bootstrap; `experiments/analyse_ccrab.py` redraws them with a fixed seed and prints the repository-resampled interval beside each (`results/ccrab-today/analysis-seeded.txt`): no bound moves by more than half a point and no verdict changes.

| Condition | Localised |
|---|---|
| A diff only | 32.9% |
| C random nodes, any file, same budget | 34.7% |
| C′ random nodes, other files only, same budget | 33.5% |
| D lexical retrieval, same budget | 35.6% |
| **B graph retrieval, repaired** | **48.4%** |
| E whole changed files (August, n=205) | 36.1% |
| F fault-location oracle (August) | 34.2% |

| Comparison | Difference | 95% interval |
|---|---|---|
| graph − diff only | +15.5 | [+10.0, +21.0] |
| graph − random, any file | +13.7 | [+8.7, +19.2] |
| graph − random, other files only | +15.1 | [+9.6, +21.1] |
| graph − lexical | +12.8 | [+7.8, +17.8] |
| lexical − diff only | +2.7 | [−0.9, +6.4] |
| random − diff only | +1.8 | [−1.4, +5.0] |

On real, test-verified defects, retrieval that reaches the caller through the dependency graph localises thirteen to fifteen points more than random or lexical retrieval at the same budget, which do no better than the diff alone. The August diff-only run on these defects gave 33.8%, so the baseline has not moved. This is the result the withdrawn comparison in August claimed to refute; it refuted nothing, because its graph arm never left the file.

The graph condition is the only one that ranks neighbours in other files ahead of the defect's own file, so a control that draws random nodes from other files only (C′, 218 paired defects) separates "found through the graph" from "from another file". It localises 33.5%, within noise of the diff alone, and the graph condition is +15.1 [+9.6, +21.1] over it. What helps is reaching the code that depends on the change, not code from elsewhere. One caution remains: this is one model and one run per condition, on a benchmark where 73% of defects anchor on a changed line and all on a changed file, so what the caller contributes is understanding of how the changed function is used, not a dependency the diff cannot show.

## 4.6 The search-trigger test

One model (gemini-2.5-flash), the same two tools, the same repository and the same diff; one sentence of framing varies. Across 40 paired tasks a bare tool-equipped model searched in 0 of 40 under the review prompt and in 40 of 40 when told the defect depended on another file, reaching the caller in 20%. The result is scoped to a bare model: harnessed products explore unprompted [arXiv:2607.16740].

## 4.7 The withdrawn and stopped runs

The held-constant experiment of 3.5 was run in full on the second benchmark: four base runs across three model families and two serialisations, two twin runs, a hidden-evidence and a noise variant, and an authoritative-callers variant, each judged by two models. Every number from those runs is withdrawn with the benchmark, for the five instrument defects listed in 3.2; the raw records, the analyses and the judge labels are kept under `results/` with a notice (`results/WITHDRAWN-v2-structure.md`) so that the withdrawal can be checked, and so that a reader can see what the effects looked like on a leaking instrument. On the third benchmark one base run was started and stopped under the pre-set rule at 201 defects; its nine arms are kept whole in `results/v3-ceiling/` and its arm-level numbers are not reported as results, because a comparison between arms on a benchmark where the diff alone scores 95.5% is a comparison of what the model does with the other 4.5%.

One number from that run is reported, as a signal and not as a result of the experiment, because it is judge-free, because it answers a question the twins also answer, and because it does not depend on detection: precision, whether the mutated line is the only line flagged. On the 200 defects paired across all nine arms (`results/v3-ceiling/analysis-precise-partial.txt`; one model, one serialisation, stopped run):

| Comparison on precision | Difference | 95% interval, repositories resampled |
|---|---|---|
| real caller shown (evidence) − diff only | −14.0 | [−20.7, −7.9] |
| real caller + attributed relation − diff only | −11.5 | [−17.6, −5.6] |
| foreign code, same length − diff only | +6.0 | [+1.7, +10.1] |
| header only − diff only | −3.0 | [−7.5, +1.1] |
| bare link − scrambled control | 0.0 | [−3.2, +3.0] |
| attributed relation − scrambled control | +2.5 | [−0.9, +6.2] |

Showing the model the caller that depends on the change makes it flag more of the harmless lines, by fourteen points against the diff alone, while foreign code of the same length makes it flag slightly fewer. Stating the link between the snippets recovers none of the loss: the bare link against the scrambled control is 0.0 with an interval of three points either side. The withdrawn second-version runs had reported a ten-to-fourteen-point precision gain for the bare link on all four runs; on the repaired benchmark, where labels no longer carry line numbers, that gain is absent on the one run made. The second version's structure effect on precision is therefore best read as the line-number leak, and the twins in 4.3 are the direct measurement of what the caller does to false alarms.
