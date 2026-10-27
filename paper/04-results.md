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

Repairing the second version's leaks changed the ceiling by two points. Balanced position, function-name labels, mixed syntax-tree-neutral distractors and a strict resolver remove the ways a model could find the line without reading the change; they do not remove the fact that a flipped default or a swapped return among quote rewrites looks like the only thing worth saying. Detection rate on a mutation benchmark of this shape measures whether the mutated line looks odd, and it does. The same check on the real defects gives 32.9%: given only the diff, gpt-4o-mini localises 72 of the 219 paired c-CRAB defects. That set leaves room for context where the generated sets do not; 4.5 reports what retrieval did with the room, once a hint the graph condition had been given is removed.

## 4.2 Anchor versus evidence, on real comments

Of 291 test-verified c-CRAB defects, 291 anchor in a file the pull request changed and 213 on a changed line. Under the strict reading, 97 (33%) refer to something the diff does not contain; under the loose reading, 146 (50%). Where a comment sits is not where its justification lives. A benchmark that scores a review by where its comment lands will accept a comment that found the line for the wrong reason, and a benchmark that gives the model only the diff withholds the justification for a third to a half of its own ground truth.

## 4.3 Safe twins

Twins are the same surface mutation as a defect task, placed where no caller in the sampled repository depends on what changed (3.3). The generator produced 165 from 33 repositories; 158 have an evidence set and were run on both models, and 157 (gpt-4o-mini) and 155 (deepseek-v3.2) are paired across all nine arms. Correct on a twin means not flagging the mutated line. Both runs used the system prompt of 3.6, which tells the model that human reviewers found real problems in the diff and to assume there is something to find; every clear rate below is therefore a floor, and a neutral-prompt run that drops that sentence and states that an empty list is a correct answer is reported at the end of this section (Figure 3).

| Arm | gpt-4o-mini (n=157) | deepseek-v3.2 (n=155) |
|---|---|---|
| 1 diff only | 2.5% | 11.0% |
| 8 header only | 1.3% | 7.1% |
| 7 foreign code, same length | 1.9% | 9.0% |
| 2 tolerant caller shown | 1.9% | 1.9% |
| 3 caller + bare link | 2.5% | 3.9% |
| 4 caller + typed link | 2.5% | 2.6% |
| 5 caller + attributed link | 1.9% | 1.9% |
| 6 caller + wrong link | 1.9% | 3.2% |

| Comparison on twin clear rate | gpt-4o-mini | deepseek-v3.2 |
|---|---|---|
| tolerant caller − diff only | −0.6 [−3.0, +1.4] | **−9.0 [−14.1, −4.8]** |
| caller + attributed − diff only | −0.6 [−3.0, +1.4] | **−9.0 [−14.3, −4.2]** |
| foreign code − diff only | −0.6 [−3.0, +1.5] | −1.9 [−7.6, +3.2] |
| header only − diff only | −1.3 [−3.8, +1.2] | −3.9 [−9.8, +1.8] |
| bare link − caller alone | +0.6 [0.0, +2.1] | +1.9 [−0.7, +4.9] |

No arm on either model leaves more than 11% of the safe changes unflagged. On gpt-4o-mini every arm sits between 1% and 4%, a floor under which no comparison can be read. On deepseek-v3.2 the diff alone clears 11%; showing the caller that tolerates the change lowers that to 2%, by nine points with an interval that excludes zero, while foreign code of the same length and the header alone leave it within noise of the diff. Stating the link, in any form, moves nothing. The code that should exonerate the change makes the model more certain it is a defect, which is the same direction as the precision signal in 4.7: a relevant caller raises flagging, and a relation statement does not lower it. The twins on this version are safe repository-wide, so the second version's objection, that a caller elsewhere might not be robust, no longer applies within the sampled files.

**Under a neutral prompt.** The same 158 twins were re-run on both models with the one sentence removed and the output contract stating that an empty list is a correct answer (3.6); every arm is otherwise identical, and there were no parse failures in 1,422 replies on either model (`results/v3twins-neutral-gpt4omini/`, `results/v3twins-neutral-deepseek/`; the deepseek run was made as three interleaved shards of the same file in parallel, with identical per-call settings, because that model reasons three to four times longer under this prompt).

| Arm, neutral prompt | gpt-4o-mini left unflagged (n=158) | findings per twin | deepseek-v3.2 left unflagged (n=158) | findings per twin |
|---|---|---|---|---|
| 1 diff only | 81.6% | 0.19 | 89.2% | 0.11 |
| 8 header only | 87.3% | 0.14 | 88.0% | 0.14 |
| 7 foreign code, same length | 81.6% | 0.20 | 90.5% | 0.09 |
| 2 tolerant caller shown | 54.4% | 0.50 | 86.7% | 0.14 |
| 3 caller + bare link | 39.9% | 0.64 | 81.0% | 0.20 |
| 4 caller + typed link | 36.7% | 0.69 | 77.2% | 0.24 |
| 6 caller + wrong link | 13.9% | 0.96 | 82.3% | 0.20 |
| 5 caller + attributed link | 10.8% | 0.97 | 79.1% | 0.23 |

| Comparison, neutral prompt (repositories resampled) | gpt-4o-mini | deepseek-v3.2 |
|---|---|---|
| tolerant caller − diff only | **−27.2 [−37.7, −16.7]** | −2.5 [−8.5, +3.7] |
| foreign code − diff only | 0.0 [−4.4, +4.8] | +1.3 [−4.4, +7.2] |
| header only − diff only | +5.7 [0.0, +11.6] | −1.3 [−5.9, +4.1] |
| bare link − caller alone | **−14.6 [−20.8, −8.4]** | **−5.7 [−11.3, −0.7]** |
| wrong link − caller alone | **−40.5 [−49.1, −31.2]** | −4.4 [−10.3, +1.6] |
| attributed link − diff only | **−70.9 [−77.5, −63.6]** | **−10.1 [−18.1, −2.1]** |

Told that an empty answer is acceptable, gpt-4o-mini leaves four in five safe changes alone from the diff, and foreign code of the same length changes nothing. Showing the caller that tolerates the change costs 27 points; stating a bare link between the snippets costs 15 more; naming the relation and its argument takes the clear rate to one in nine, and a link that points to the wrong snippet does nearly the same as the right one. Every unit of dependency metadata moves the model toward flagging a change the metadata itself shows to be safe, in proportion to how much the metadata says. deepseek-v3.2 moves in the same order but by a tenth of the distance: 89% cleared from the diff, 87% with the caller, 81% with the bare link, 79% with the relation named, and only the attributed link against the diff and the bare link against the caller exclude zero. The direction of the effect is shared by the two models; its size is a property of the model. The presuming prompt had hidden all of this at a floor of 2.5%; under it the arms were indistinguishable, and the two-point fall on deepseek was the visible edge of an effect that is twenty-seven points on one model and two on the other.

**The defects under the same prompt, and balanced accuracy.** The 277 third-version defects were run on gpt-4o-mini under the neutral prompt with the same nine arms (`results/v3-neutral-gpt4omini/`; 6 defects had no evidence set, 271 are paired, 0 parse failures in 2,439 replies). The diff alone finds 30% of the mutated lines, not 95%: the ceiling of 4.1 was measured under a prompt that told the model a defect was there, and without that sentence the generated benchmark has headroom. Every unit of metadata fills it, in the same order as it empties the twins.

| Arm, neutral prompt, gpt-4o-mini | defects hit (n=271) | exact line | findings per defect | twins cleared (n=158) | balanced accuracy |
|---|---|---|---|---|---|
| 1 diff only | 29.9% | 29.5% | 0.36 | 81.6% | 55.8% |
| 8 header only | 32.8% | 31.4% | 0.39 | 87.3% | 60.1% |
| 7 foreign code, same length | 34.7% | 32.8% | 0.45 | 81.6% | 58.2% |
| 2 tolerant caller shown | 52.4% | 50.9% | 0.65 | 54.4% | 53.4% |
| 3 caller + bare link | 63.1% | 61.6% | 0.80 | 39.9% | 51.5% |
| 4 caller + typed link | 64.9% | 61.3% | 0.85 | 36.7% | 50.8% |
| 6 caller + wrong link | 78.2% | 75.6% | 0.96 | 13.9% | 46.1% |
| 5 caller + attributed link | 81.5% | 77.9% | 1.05 | 10.8% | 46.2% |

| Comparison, neutral prompt, gpt-4o-mini | defects hit | balanced accuracy |
|---|---|---|
| tolerant caller − diff only | **+22.5 [+14.9, +30.5]** | −2.4 [−9.7, +5.1] |
| foreign code − diff only | +4.8 [+0.4, +9.0] | +2.4 [−1.0, +5.8] |
| header only − diff only | +3.0 [−1.1, +7.0] | +4.3 [+0.9, +7.8] |
| bare link − caller alone | **+10.7 [+5.1, +16.3]** | −1.9 [−6.3, +2.1] |
| wrong link − caller alone | **+25.8 [+19.7, +32.0]** | **−7.3 [−12.5, −2.3]** |
| attributed link − diff only | **+51.7 [+43.9, +59.3]** | **−9.6 [−14.9, −3.8]** |

Balanced accuracy is the mean of the hit rate on defects and the clear rate on twins; defects and twins are different tasks, so the bootstrap pairs them by repository, drawing repositories with replacement and scoring both arms and both halves on the same draw (`analysis-balanced-with-twins.txt`). Each arm's gain on the defects is matched by its loss on the safe changes, almost point for point: the caller gains 22 and loses 27, the attributed link gains 52 and loses 71, and a link to the wrong snippet raises detection by 26 points over the caller alone, nearly as much as the right one. Balanced accuracy is 55.8% for the diff alone, within noise of that for the caller, for foreign code and for the bare link, four points above it for the header alone, and ten points below it for the attributed link. No arm that carries evidence beats the diff. Under a prompt that lets the model say nothing, the generated benchmark measures how much the context makes the model flag; it does not show the context helping the model tell a defect from a safe change. The defects were not run on deepseek-v3.2 under the neutral prompt.

## 4.4 Test verification of the generated defects

Of the second version's defects, 86 were run against their repositories' own test suites (`results/test-verified/`): 17 are test-verified, meaning a test that passed before the mutation fails after it; 28 are not caught by the tests selected for the mutated module; 24 repositories could not be installed in the sandbox (native builds, a Python 3.13 requirement); 11 had no passing test before the mutation and 6 had no test to select. Among the 45 that could be run to a verdict, 38% are caught by an existing test. The test-verified defects are 9 default flips, 6 tuple reorderings and 2 `None` sentinels, from eight repositories. The same check on all 277 third-version defects (`results/test-verified/summary-v3.txt`) reaches a verdict for 59: 32 are test-verified and 27 are not caught, so 54% of those with a verdict, and 12% of all 277, are caught by an existing test. The rest could not be run: 159 repositories failed to install in the sandbox, the third version's pools include heavier projects than the second's, 46 modules had no passing test before the mutation, 7 had no test to select, and 6 timed out or errored. The test-verified defects are 16 default flips, 15 tuple reorderings and one `None` sentinel, from nine repositories; their task identifiers are listed in the summary file, so a reader who wants the executable subset has it.

The syntax-tree verifier accepts many mutations whose breakage no existing test observes. That does not make them harmless: a flipped default on a public function that no test pins is the kind of change a reviewer exists to catch. It does mean that a reader who counts only test-verified defects should treat the generated benchmark as resting on an unverified majority, and that a benchmark of this kind should report the fraction.

## 4.5 Real defects: the retrieval result and the control that withdrew it

The model throughout is gpt-4o-mini, and the defect set is the 291 defects of 3.6 that pass the filters, of which 219 were paired across the four conditions run in August and re-run on one day in October (diff only, graph, random, lexical), 218 across five with the random-other-files control, and 223 across the four that matter here once the stripped control is added. Every condition shares the pipeline, the budget (1,500 tokens) and the tolerance (5 lines). The c-CRAB runs from August stand for the conditions that do not retrieve: on the test-verified defects they share with the re-run, no context, whole changed files and the fault-location oracle all localise 33 to 36%.

Three features of the pipeline are common to every retrieval condition and are disclosed here because a reader cannot infer them from the table. First, every retrieval condition (graph, random, random-other-files, lexical and the August oracle) starts its query from the function whose line range covers the ground-truth defect line, so retrieval begins at the fault location, which a reviewer would not know; the diff-only and whole-file conditions do not retrieve and have no seed. Second, the prompt for the retrieval conditions carries one sentence saying a retrieval tool is available, and the diff-only prompt does not; no tool is actually callable in any condition, the context is pre-computed and inserted. Third, a hit is any finding within five lines of the defect, so a condition under which the model reports more findings has more chances.

One feature was specific to the graph condition, and it is the reason this section reports a withdrawal. The graph tool returned the seed function with its `line_range` and `metadata` (its calls and parameters), while the random and lexical tools returned the seed with its name, type and path only. The seed covers the defect line, so the graph condition alone was told the span of the function containing the defect. An external reviewer found this on 27 October 2026. The control is the graph condition with the seed reduced to the entry the other conditions carry, on the same defects with the same model, budget and tolerance (`experiments/run.py --conditions B --strip-seed`, `results/ccrab-Bs-gpt4omini/`), re-run with the same repaired retrieval (Figure 2):

| Condition | Localised, 223 paired | at zero tolerance |
|---|---|---|
| A diff only | 33.2% | 2.5% |
| C′ random nodes, other files only, same budget | 33.2% | |
| **B′ graph retrieval, seed span removed** | **34.1%** | 2.9% |
| B graph retrieval, as first reported (withdrawn) | 48.4% | 9.4% |

| Comparison | Difference | 95% interval, repositories resampled |
|---|---|---|
| graph as reported − graph, span removed | +14.3 | [+8.8, +19.8] |
| graph, span removed − diff only | +0.9 | [−3.1, +5.1] |
| graph, span removed − random, other files | +0.9 | [−2.9, +4.9] |

The fourteen-point gain was the span. With it removed, graph retrieval that reaches the depended-on caller localises the same share of real defects as the diff alone and as random code from other files, and the ordering at zero tolerance says the same. The graph condition's neighbours are the right ones, the control in C′ is the right one, and the number is a null. Every figure from the graph condition in `results/ccrab-today/B-outcomes.jsonl` is withdrawn (`results/WITHDRAWN-ccrab-graph.md`); the file is kept so the withdrawal can be checked. The rates that stand are those of the conditions that never carried the span, run on one day with one pipeline (`experiments/analyse_ccrab.py`, `results/ccrab-today/analysis.txt`): diff only 32.9%, random nodes 34.7%, random from other files 33.5%, lexical 35.6% on the 219 paired defects, whole changed files 36.1% and the fault-location oracle 34.2% from August, and the stripped graph condition 34.1%. None differs from the diff alone by an interval that excludes zero.

On real defects, then, this project has no positive retrieval result. The diff alone, whole files, random nodes from anywhere or from other files only, lexical retrieval, graph retrieval through the dependency graph, and a fault-location oracle all localise a third of the test-verified c-CRAB defects at a 1,500-token budget on gpt-4o-mini. The anchor-versus-evidence measurement says a third to a half of these defects are justified by code outside the diff, so the room is there; a 25-line caller window at this budget, selected by any of the methods tried, does not fill it for this model. Whether a frontier model or a larger budget would is not measured here.

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
