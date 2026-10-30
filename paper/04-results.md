# Results

All numbers come from the files under `results/`, recomputed from the frozen per-call records by `scripts/reproduce.py`. Intervals are 95% percentile bootstraps that resample repositories; the task-resampled interval, shown in the analysis files, never changes a verdict. Nothing is reported from a run that did not complete on its paired set; the one stopped run is described in 4.7 and kept whole.

## 4.1 The partial-input ceiling

Under the presuming prompt of 3.6, a model given nothing but the diff finds the mutated line almost always, on every version of the generated benchmark (gpt-4o-mini, a hit is the exact line):

| Benchmark version | tasks | diff-only hit | what was wrong with the instrument |
|---|---|---|---|
| first (withdrawn) | 204 | 93% | regex evidence; distractors broke the file in 145 tasks |
| second (withdrawn) | 229 | 97.8% | line numbers in labels; loose resolver; tree-changing distractors; defect last in 62% |
| third | 201 of 277 | 95.5% | none found: audit 0 / 0 / 0, position balanced, labels name functions |
| third, neutral prompt (4.3) | 271 | 29.9% | the prompt no longer says a defect is present |
| c-CRAB real defects (3.6), raw diff, 5-line tolerance | 219 | 32.9% | the rate of random line placement (4.5) |
| c-CRAB real defects, numbered diff, 5-line tolerance | 244 | 50.8% | 15 points above random placement |

The third version was run under the stop rule of 3.4 and stopped at 201 defects when the rate was clearly above 95%; there were no parse failures in 1,802 replies. By kind the rate is 104 of 107 default flips, 58 of 61 tuple reorderings, 19 of 21 `None` sentinels, 6 of 6 exception types and 5 of 6 empty-to-`None`. The reason is not that the model reads the defect: it reports 2.66 findings per task on average against four hunks, and 1.58 of those findings are on the three harmless rewrites. A semantic change among three cosmetic ones is always among the lines it flags. Precision, the rate at which the mutated line is the only line flagged, is 24.4%.

Repairing the second version's leaks changed the ceiling by two points. Balanced position, function-name labels, mixed syntax-tree-neutral distractors and a strict resolver remove the ways a model could find the line without reading the change; they do not remove the fact that a flipped default or a swapped return among quote rewrites looks like the only thing worth saying. Detection rate on a mutation benchmark of this shape measures whether the mutated line looks odd, and it does. Every generated-benchmark rate in the table is under a prompt that tells the model a defect is present. Under the neutral prompt the third version's diff-only rate is 29.9% (4.3): the ceiling is a property of the benchmark and the prompt together, and once the prompt no longer presumes a defect the arms separate, by flagging rather than by discriminating, as 4.3 shows. The same check on the real defects gives 32.9% on the raw diff at a five-line tolerance, which 4.5 shows to be the rate of random line placement, and 50.8% once the diff lines carry their numbers. That set leaves room for context; 4.5 reports four runs on it.

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

**Sensitivity and criterion.** The same two rates read as one detection task give a sensitivity and a decision threshold: with H the hit rate on defects and F the flag rate on twins, d′ = z(H) − z(F) and c = −(z(H) + z(F))/2, repository bootstrap as above (`experiments/signal_detection.py`, `analysis-signal-detection.txt`).

| Arm, neutral prompt, gpt-4o-mini | H | F | d′ [95%] | c [95%] |
|---|---|---|---|---|
| 1 diff only | 0.30 | 0.18 | 0.37 [+0.05, +0.70] | +0.71 [+0.60, +0.85] |
| 8 header only | 0.33 | 0.13 | 0.70 [+0.42, +1.00] | +0.79 [+0.64, +0.98] |
| 7 foreign code, same length | 0.35 | 0.18 | 0.51 [+0.25, +0.79] | +0.65 [+0.51, +0.80] |
| 2 tolerant caller shown | 0.52 | 0.46 | 0.17 [−0.12, +0.46] | +0.03 [−0.12, +0.16] |
| 3 caller + bare link | 0.63 | 0.60 | 0.08 [−0.20, +0.34] | −0.30 [−0.46, −0.14] |
| 4 caller + typed link | 0.65 | 0.63 | 0.04 [−0.28, +0.36] | −0.36 [−0.50, −0.23] |
| 6 caller + wrong link | 0.78 | 0.86 | −0.30 [−0.59, −0.04] | −0.93 [−1.11, −0.77] |
| 5 caller + attributed link | 0.82 | 0.89 | −0.34 [−0.67, −0.05] | −1.07 [−1.26, −0.91] |

Every arm that carries the caller's code or a statement about the dependency has d′ at or below the diff's 0.37, and for the attributed and wrong links d′ is below zero: the model flags the safe twin more often than the defect. The criterion moves from +0.71, a model that needs persuading, to −1.07, one that flags by default; the difference in c from the diff excludes zero for every evidence arm (−0.69 [−0.85, −0.54] for the caller alone, −1.78 [−2.00, −1.60] for the attributed link), while the difference in d′ excludes zero only for the attributed and wrong links, downward (−0.72 [−1.13, −0.29] and −0.68 [−1.09, −0.28]). The only arm that raises d′ by an interval excluding zero carries no evidence at all, the header alone (+0.32 [+0.06, +0.59]). Dependency context in this experiment moves the threshold, not the sensitivity.

## 4.4 Test verification of the generated defects

Of the second version's defects, 86 were run against their repositories' own test suites (`results/test-verified/`): 17 are test-verified, meaning a test that passed before the mutation fails after it; 28 are not caught by the tests selected for the mutated module; 24 repositories could not be installed in the sandbox (native builds, a Python 3.13 requirement); 11 had no passing test before the mutation and 6 had no test to select. Among the 45 that could be run to a verdict, 38% are caught by an existing test. The test-verified defects are 9 default flips, 6 tuple reorderings and 2 `None` sentinels, from eight repositories. The same check on all 277 third-version defects (`results/test-verified/summary-v3.txt`) reaches a verdict for 59: 32 are test-verified and 27 are not caught, so 54% of those with a verdict, and 12% of all 277, are caught by an existing test. The rest could not be run: 159 repositories failed to install in the sandbox, the third version's pools include heavier projects than the second's, 46 modules had no passing test before the mutation, 7 had no test to select, and 6 timed out or errored. The test-verified defects are 16 default flips, 15 tuple reorderings and one `None` sentinel, from nine repositories; their task identifiers are listed in the summary file, so a reader who wants the executable subset has it.

The syntax-tree verifier accepts many mutations whose breakage no existing test observes. That does not make them harmless: a flipped default on a public function that no test pins is the kind of change a reviewer exists to catch. It does mean that a reader who counts only test-verified defects should treat the generated benchmark as resting on an unverified majority, and that a benchmark of this kind should report the fraction.

## 4.5 Real defects: four runs, one withdrawal, and what stands

The model throughout is gpt-4o-mini, the tolerance is five lines, and the defect set is the 246 defects of 3.6 whose diff fits the pipeline, in 195 pull requests from 63 repositories; each run is analysed on the defects answered in all of its conditions. Four runs were made: the first on 26 October 2026, withdrawn; the other three pre-registered in `paper/PLAN.md` (§10, its amendment, and §11), each run once and reported whatever it gave, and the last declared the final one before it started. Every run compares a diff-only condition A against four retrieval conditions at one budget: B, a walk over the dependency graph; C, random entities of the same type mix as B's walk, from any file; Cx, random entities from files other than the changed ones; D, lexical retrieval on the seed names. Two features are common to all four and are disclosed because the tables do not show them: the prompt for the retrieval conditions carries one sentence saying a retrieval tool is available and the diff-only prompt does not, though no tool is callable in any condition and the context is pre-computed; and a hit is any finding within five lines of the defect, so a condition under which the model reports more findings has more chances, which is why every rate from the second run on is read against a random-placement baseline.

**Run 1, withdrawn.** The first run seeded every retrieval condition from the function whose line range covers the ground-truth defect line, so retrieval began at the fault location, which a reviewer would not know; and its graph tool alone returned that seed with its `line_range` and `metadata`, while the random and lexical tools returned the seed by name, type and path only. The graph condition alone was therefore told the span of the function containing the defect. An external reviewer found this on 27 October 2026. The control is the graph condition with the seed reduced to the entry the other conditions carry, on the same defects with the same model, budget (1,500 tokens) and tolerance (`experiments/run.py --conditions B --strip-seed`, `results/ccrab-Bs-gpt4omini/`):

| Run 1 | Localised, 223 paired | at zero tolerance |
|---|---|---|
| A diff only | 33.2% | 2.5% |
| Cx random nodes, other files only, same budget | 33.2% | |
| **B′ graph retrieval, seed span removed** | **34.1%** | 2.9% |
| B graph retrieval, as first reported (withdrawn) | 48.4% | 9.4% |

| Comparison | Difference | 95% interval, repositories resampled |
|---|---|---|
| graph as reported − graph, span removed | +14.3 | [+8.8, +19.8] |
| graph, span removed − diff only | +0.9 | [−3.1, +5.1] |
| graph, span removed − random, other files | +0.9 | [−2.9, +4.9] |

The fourteen-point gain was the span. Every figure from the graph condition in `results/ccrab-today/B-outcomes.jsonl` is withdrawn (`results/WITHDRAWN-ccrab-graph.md`); the file is kept so the withdrawal can be checked. The other conditions of that run, diff only 32.9%, random nodes 34.7%, random from other files 33.5% and lexical 35.6% on 219 paired defects, stand as what they are; the next run shows that they are not a model result either.

**Run 2: the repair, and a result at chance.** The repair of 27 October changed three things for every retrieval condition. The graph builder's caller edges were rebuilt and validated against `jedi` on six repositories outside the task set: pooled recall 0.40 before and 0.92 after, precision 0.89 and 0.85 (`results/graph-validation/`). The seeds became every function or class overlapping a changed hunk, read from the new-file side of the diff and never from the ground truth. And the payload became the entity's source, cut at 40 lines, with no line range, metadata, depth or score, at 3,000 tokens for every retrieval condition. The pre-registered run of 28 October (`results/ccrab-v2/`, 239 paired defects, $0.82) gave A 36.0%, B 32.2%, C 34.7%, Cx 34.7%, D 35.6%; B − Cx −2.5 [−6.0, +1.0]; nothing excludes zero. Two checks on its records, both made before any further model call, say why the numbers sit where they do. A chance baseline places the same number of findings as the model on uniformly random lines of the diff's hunks and scores them with the same matcher (`experiments/chance_ccrab.py`, 500 draws per task): it gives 36.0% for A against the model's 36.0% and 34.9% for B against 32.2%, and at the exact line every condition is below chance, two of them with intervals excluding zero. And of the diff-only findings whose message quotes a token present in the diff, 459 of 1,014, 8.9% report the line that holds the token and 39.4% are more than five lines off (`experiments/line_accuracy.py`). The model was given a raw unified diff with no per-line numbers, had to count from each hunk header, and mostly did not; the ground truth is not at fault, since 237 of the 246 defect lines lie inside a hunk of their file. The generated benchmark is unaffected, because every one of its 1,103 hunks is one line on the new-file side. Run 2 measures the harness, and so, in retrospect, does every rate of run 1.

**Run 3: numbered lines.** The amendment of 29 October prefixed every context and added line of the diff with its new-file line number, identically for every condition, said so in one sentence of the output contract, and changed nothing else (`results/ccrab-numbered/`, 243 paired, $0.87). Quoted-token line accuracy went from 8.9% to 71.2% exact and from 39.4% to 3.3% more than five lines off. Every condition rose to about half: A 49.8%, B 51.4%, C 52.3%, Cx 50.6%, D 51.9%, each 15 to 17 points above its random-placement baseline with an interval excluding zero, and at the exact line 23 to 24% against 5% chance. B − Cx +0.8 [−1.3, +3.3]; B − A +1.6 [−1.1, +4.5]; at the exact line B − Cx +2.1 [−0.9, +5.1]; no paired difference excludes zero.

**Run 4: the final run, with a primary comparison fixed in advance.** An audit of run 3 found four weaknesses in how the context reached the model, none specific to one condition: entities arrived as a JSON envelope; the delivered ids were not logged; the graph walk returned test files and ranked neighbours breadth-first; and a class was seeded beside its own changed methods. §11 of the plan, committed before the run, rendered every entity as a plain code block under a path-and-name header, logged the delivered ids, excluded test files from what B, C and Cx draw so that B and Cx differ only in graph structure and ranking, ranked direct callers of the changed functions first, then callees, then depth two, and dropped class seeds whose methods were already seeds. It also fixed the primary comparison before the run: B − Cx on source-file defects whose reference comment is strict outside-diff under the classification of 4.2, 77 ids committed in advance, 64 of them paired, in 34 repositories. The plan discloses that this subset had been seen in exploratory analysis before it was chosen: on run 3's records it read B 54.7% against Cx 51.6%, and on run 2's, B 40.6% against Cx 42.2%. Run 4 (`results/ccrab-final/`, 244 paired, $0.76) gives:

| Run 4, all 244 paired defects | localised, tol 5 | random placement | exact line | chance |
|---|---|---|---|---|
| A diff only | 50.8% | 35.3% | 23.4% | 4.8% |
| B graph, callers first | 54.1% | 35.4% | 24.6% | 4.9% |
| C random, any file | 52.0% | 34.9% | 24.2% | 4.8% |
| Cx random, other files | 52.9% | 35.1% | 24.6% | 4.6% |
| D lexical | 52.9% | 35.3% | 25.0% | 4.8% |

| Comparison, repositories resampled | all 244 defects | pre-registered subset, 64 outside-diff defects |
|---|---|---|
| B − Cx (the primary, on the subset) | +1.2 [−2.2, +5.0] | **+12.5 [+5.0, +20.8]** |
| B − A | +3.3 [−0.9, +7.2] | **+12.5 [+3.6, +22.4]** |
| Cx − A | +2.0 [−1.7, +5.2] | 0.0 [−4.5, +4.8] |
| D − A | +2.0 [−1.8, +5.4] | +3.1 [0.0, +8.1] |
| B − Cx at the exact line | +0.4 [−2.1, +3.4] | +3.1 [−3.2, +9.0] |

On all defects nothing excludes zero. On the subset B localises 41 of 64 against 33 for Cx and 33 for A; the eight defects that separate B from Cx are all ones B finds and Cx does not, seven repositories favour B and none the other way, and the task-resampled interval, [+4.7, +20.3], agrees. At the exact line the gap is +3.1 and spans zero, so the extra hits land within the tolerance rather than on the line. Evidence recall, the share of defects whose comment names a file or identifier that the delivered context contains, is B 61.9%, D 60.4%, C 50.6% and Cx 50.0% on all defects, and on the 85 whose comment names something outside the diff, D 22.6%, B 18.8%, Cx 14.1%, C 11.8% (`evidence-recall.txt`). The subset comparison passed the test the plan set for it, and we still report it as a lead rather than a result: it is eight defects on one model, in a subset chosen after two readings of it, one +3.1 and one −1.6, and neither the exact-line rate nor evidence recall singles B out.

**What stands.** Across four runs and three harness repairs (Figure 2):

| Run, paired defects | A | B | C | Cx | D | B − Cx |
|---|---|---|---|---|---|---|
| 1, 26 Oct: fault-location seeds, 1,500 tokens, raw diff (219; B is the span-removed control, 223) | 32.9 | 34.1 | 34.7 | 33.5 | 35.6 | +0.9 [−2.9, +4.9] |
| 2, 28 Oct: repaired graph, diff seeds, code payloads, 3,000 tokens (239) | 36.0 | 32.2 | 34.7 | 34.7 | 35.6 | −2.5 [−6.0, +1.0] |
| 3, 29 Oct: numbered diff lines (243) | 49.8 | 51.4 | 52.3 | 50.6 | 51.9 | +0.8 [−1.3, +3.3] |
| 4, 30 Oct: plain rendering, callers first, no test files (244) | 50.8 | 54.1 | 52.0 | 52.9 | 52.9 | +1.2 [−2.2, +5.0] |

Random line placement, computed for runs 2 to 4, is 35 to 36% in every condition. No comparison on the full defect set excludes zero in any run. Runs 1 and 2 sit at chance for every condition and measure nothing about context; runs 3 and 4 sit fifteen points above it and still show no condition above the diff alone on all defects. The one interval that excludes zero is the pre-registered subset of run 4, where the reference comments say the evidence lies outside the diff, and it is a lead for a study with a second model and a subset fixed before any look at the data. No c-CRAB iteration follows run 4.

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
