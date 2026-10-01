# Results

All numbers come from `results/v2-*/analysis-*.txt`, produced by `experiments/analyse_structure.py` from the frozen per-call records. Intervals are 95% percentile bootstraps that resample repositories; the task-resampled interval, shown in the analysis files, is never narrower in a way that changes a conclusion. "Excludes zero" and "spans zero" are the only verdicts used. Each run has 225–230 defects paired across all eight arms; a handful of the 229 generated defects lack a decoy and are dropped before any arm sees them.

## 4.1 The three diagnostics

**Diff-only ceiling.** On the rebuilt benchmark, a model given nothing but the diff finds the defect line in 97.8% of tasks (gpt-4o-mini). The mutated line is conspicuous among cosmetic edits, and hit rate cannot distinguish any arm from any other. Hit is reported in the analysis files and nowhere else in this section. The withdrawn first benchmark had the same ceiling (93%) and, in addition, distractors that broke the file; its numbers are not reported (Section 7).

**Anchor versus evidence, on real comments.** Of 291 test-verified c-CRAB defects, 291 anchor in a file the pull request changed and 213 on a changed line. Under the strict reading, 97 (33%) refer to something the diff does not contain; under the loose reading, 146 (50%). Where a comment sits is not where its justification lives.

**Discrimination with safe twins.** Twins are the same surface mutation as a defect task, placed where the shown caller is verifiably robust to it; the generator produced 150 (two kinds, 57 of the first 60 being default flips), and the table reports the 60 that had been generated when the run started. The remaining 90 are being run and will replace this table. Correct on a twin means not flagging the mutated line.

| Arm | gpt-4o-mini | deepseek-v3.2 |
|---|---|---|
| 1 diff only | 1.7% | 8.3% |
| 2 evidence | 1.7% | 3.3% |
| 3 topology | 0.0% | 0.0% |
| 5 attributed | 0.0% | 1.7% |
| 7 random | 0.0% | 1.7% |

No arm on either model declines to flag a change that the shown caller tolerates. Shown the robust caller, the model flags the change anyway. Balanced accuracy over defects and twins is therefore at chance for every arm, and no form of context moves it. A variant that instructs the model that the shown code is every use of the changed function is reported in 4.5.

## 4.2 Does the caller help? The relevance control done properly

The scrambled control (arm 2) and the foreign-repository arm (arm 7) receive the same number of snippets at the same budget; only arm 2's snippets are the real definition, caller and decoy. The header-only arm (arm 8) receives the dependency section with no snippets. The metric is the validated judge: does the message on the defect line name a concrete fact about the caller.

| Comparison (judge) | gpt tag | gpt flat | deepseek tag | llama tag |
|---|---|---|---|---|
| real snippets − foreign snippets | +11.9 [+7.1, +17.2] | +13.7 [+7.4, +20.5] | +36.0 [+27.2, +44.7] | +7.6 [+3.8, +11.6] |
| real snippets − header only | +13.7 [+9.0, +19.1] | +16.4 [+10.6, +22.7] | +37.8 [+30.5, +45.1] | +8.0 [+5.2, +10.9] |
| header only − diff only | 0.0 [−2.7, +2.7] | −1.3 [−4.3, +1.8] | −3.1 [−8.4, +2.6] | −0.9 [−3.4, +1.6] |
| foreign − diff only | +1.8 [−1.0, +4.9] | +1.3 [−2.4, +5.2] | −1.3 [−5.8, +3.5] | −0.4 [−3.1, +2.2] |

Every real-versus-foreign and real-versus-header interval excludes zero on every model and encoding. Foreign code and the header alone do nothing. The caller is what helps, and it helps the model say why the change is wrong. Arms that never see the caller sit at 2–7% on this metric for gpt-4o-mini and llama and at 14–17% for deepseek, which is the floor set by the judge's strictness.

The same snippets lower precision on two of three models. Precise means the defect line was found and no harmless line was flagged. Showing the real snippets costs 18.6 to 23.5 points of precision against the diff alone on gpt-4o-mini under both encodings and 19.1 on deepseek, while foreign snippets cost nothing on gpt-4o-mini (−0.4 and +0.9) and 8.7 [−13.9, −3.5] on deepseek. On llama the real snippets cost nothing (+2.2 [−4.6, +8.9]). Where it occurs, relevant code makes the model flag more of the diff than irrelevant code does.

## 4.3 Does stating the structure help, given the caller?

Arms 2 through 6 receive identical snippets. The pre-registered primary comparison is bare topology (arm 3) against the scrambled control (arm 2).

**On the pre-registered keyword rubric, the primary spans zero** on both runs where it was computed: −0.9 [−5.3, +3.2] on gpt-4o-mini and −2.7 [−6.7, +0.9] on llama. The rubric was found, before the full data existed, to pass boilerplate: a diff-only reviewer writing "may lead to unexpected behavior if the caller expects a None return value" satisfies it, and 50% of diff-only messages do. It is reported as pre-registered and not interpreted further.

**On the validated judge**, with a miss counted as a failure so that arms are compared on the same tasks:

| 3 topology − 2 control | gpt tag | gpt flat | deepseek tag | llama tag |
|---|---|---|---|---|
| judge | **+7.5 [+3.0, +12.2]** | −0.9 [−5.0, +3.1] | **+11.6 [+4.3, +18.8]** | **+7.6 [+3.3, +12.2]** |
| McNemar b / c, exact p | 25 / 8, 0.005 | — | — | — |
| precise | **+9.7 [+4.5, +15.5]** | **+10.2 [+4.8, +15.9]** | **+9.8 [+4.1, +15.0]** | **+14.2 [+9.2, +18.9]** |

Stating a bare true link between the snippets raises the rate at which the model explains the defect through the caller by 7 to 11 points on three model families under the tag encoding, and by nothing under the flat encoding on gpt-4o-mini. On precision the gain is 10 to 14 points on all four runs: the link recovers roughly half of what showing the snippets cost. Encoding dependence on the judge metric is real and is reported, not averaged away [arXiv:2511.10234].

The typed and attributed arms add the relation kind and its argument on top of the link. Attributed exceeds the control by 11.1 [+6.6, +15.8] on gpt-4o-mini and +25.8 [+18.1, +32.7] on deepseek on the judge; the argument names the thing the judge looks for, so this comparison measures information supplied as much as structure, and is read as an upper bound.

**Corrupted structure.** Arm 6 keeps the relation kind and argument and moves the target to the decoy. Against the control it is 0.0 [−4.8, +4.9] on gpt tag, +2.7 [−2.1, +7.2] on gpt flat, +3.1 [−1.3, +8.0] on llama and +13.3 [+7.5, +18.9] on deepseek. A wrong pointer is inert on three runs and helps on deepseek, which extracts the kind and argument regardless of where the arrow points. This arm measures a wrong endpoint, not absent structure; the clean comparison for topology is arm 3 against arm 2. Corruption lowers hit rate on gpt-4o-mini under the tag encoding, 88.9% against 95.1% for the control [−10.6, −2.3], and not under flat or on the other models: there the model follows the wrong pointer.

**Comprehension probe.** Asked to read each block back alone, with no snippets, the model names the correct target file for topology in 28 or 29 of 29 probes on every run, for typed in 26 to 29, and for attributed in 25 to 28, and never for the scrambled control (0 of 29). The probe checks the file stem, and the decoy sits in the definition file, so it cannot tell a corrupted pointer from a correct one. The serialisation conveys the structure under both encodings; a null under flat encoding is a null of use, not of parsing.

## 4.4 Moderators

**Hidden evidence** (40 tasks of the two kinds that admit it). With the demonstrating line removed from the caller window, topology against control is 0.0 [−12.5, +15.8] and attributed is +20.0 [+4.7, +36.1]. A bare link does nothing when the fact it points to is not visible; the attributed relation supplies the fact.

**Noise** (four foreign snippets added, 232 tasks). Topology against control is +2.6 [−1.7, +6.9] on the judge and the attributed arm +5.2 [0.0, +10.7]. The structural gain shrinks under clutter rather than growing; the hypothesis that a map organises noisy evidence is not supported here.

**Two-hop chains.** The generator found three pass-through chains in 41 repositories at 300 to 500 files each. That is too few to run, and the hop moderator is reported as not evaluated.

## 4.5 The authoritative-callers variant

The twins were re-run with one added sentence, identical across arms: the related code shown is every use of the changed function, and a change compatible with every use shown is not a defect. Correct still means not flagging the mutated line.

| Arm | correct on twins |
|---|---|
| 1 diff only | 5.0% |
| 2 evidence | 8.3% |
| 3 topology | 1.7% |
| 5 attributed | 0.0% |
| 6 corrupted | 18.3% |
| 7 random | 10.0% |
| 8 header | 6.7% |

Told that the shown caller is the whole truth, and shown a caller that tolerates the change, the model flags the change in 92% of cases with the evidence and in 100% with the attributed relation. The attributed arm is 8.3 points below the control [−17.0, −2.8]; the more the metadata says about the relation, the more certain the model is that the relation is the problem. Dependency metadata is read as an accusation, not as information, and the evidence that should exonerate a change does not. The only arm above 10% is the corrupted one, where the pointer leads away from the caller. Context, in every form tested, moves the model's explanation of a defect and not its willingness to call a change safe.

On the defect side the instruction raises precision across the board, and the foreign-code arm shows why. On 188 defects, precision is 71.3% for the diff alone, 73.9% with the real snippets, 89.4% with foreign snippets under the same instruction (+18.1 [+11.6, +24.7] over the diff), 91.5% with the bare link and 96.3% with the attributed relation. The instruction tells the model that the code shown is the whole truth, and the model flags fewer lines whatever that code is; the link adds +17.6 [+12.6, +22.6] over the scrambled control, but a quarter of that is the instruction itself, which the foreign arm receives too though for it the instruction is false. The judge comparisons keep their direction (real caller over foreign code +15.4 [+7.1, +23.9]; link over control +3.2 [−3.6, +10.2]). Told that the shown code is the whole truth, the model stops flagging the harmless lines around a defect, and still flags the twin.

## 4.6 Real defects: c-CRAB

The c-CRAB runs from August stand for the conditions that do not retrieve: on the 219 test-verified defects shared with the re-run below, no context, whole changed files and the fault-location oracle all localise 33 to 36%. The graph condition in those runs queried the file node and never reached a caller, and is not reported.

All four retrieval conditions were re-run on the same day with the same pipeline, model, budget (1,500 tokens) and tolerance (5 lines), on 219 defects paired across all four.

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

## 4.7 The search-trigger test

Same model, same two tools, same repository, same diff; one sentence of framing varies. Across 40 paired tasks a bare tool-equipped model searched in 0 of 40 under the review prompt and in 40 of 40 when told the defect depended on another file, reaching the caller in 20%. The result is scoped to a bare model: harnessed products explore unprompted [arXiv:2607.16740].


## 4.8 Explanation against precision, and cost per true finding

A reviewer may object that a better explanation is overcorrection in disguise [arXiv:2603.00539]: a model that says more may also flag more. Across the five arms that share the same snippets, the judge rate and the false-flag rate move in opposite directions on three of four runs. The correlation of judge-YES with confirmed false flags per review across arms 2 to 6 is −0.72 on gpt-4o-mini under the tag encoding, −0.94 on deepseek, −0.71 on llama, and +0.11 on gpt-4o-mini under flat. Where the metadata improves the explanation it also reduces the noise; the two are not traded against each other.

Cost per true finding, in thousandths of a dollar per defect found and confirmed false flags per defect found:

| Run | diff only | evidence | topology | attributed | foreign |
|---|---|---|---|---|---|
| gpt-4o-mini tag | 0.11 / 0.51 | 0.25 / 0.94 | 0.21 / 0.71 | 0.20 / 0.64 | 0.19 / 0.54 |
| deepseek-v3.2 tag | 0.18 / 0.28 | 0.47 / 0.56 | 0.35 / 0.41 | 0.25 / 0.31 | 0.31 / 0.41 |
| llama-3.3-70b tag | 0.12 / 0.70 | 0.24 / 0.60 | 0.21 / 0.27 | 0.22 / 0.43 | 0.19 / 0.70 |

The bare link lowers false flags per true finding by a fifth to a third relative to the scrambled control on every run, at the same token cost. The diff alone is the cheapest condition per true finding on every run; on this benchmark it also finds the line 97.8% of the time, which is the ceiling problem of Section 4.1 restated as a cost.
