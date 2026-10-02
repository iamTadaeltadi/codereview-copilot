# Results

All numbers come from the analysis files under `results/`, produced by `experiments/analyse_structure.py` from the frozen per-call records. Intervals are 95% percentile bootstraps that resample repositories; the task-resampled interval, shown in the analysis files, is never narrower in a way that changes a conclusion. "Excludes zero" and "spans zero" are the only verdicts used. Each run has 225 to 229 defects paired across all eight arms; three defects generated after the base runs had been relaunched appear only in the noise run.

## 4.1 The three diagnostics

**Diff-only ceiling.** On the rebuilt benchmark, a model given nothing but the diff finds the defect line in 97.8% of tasks (gpt-4o-mini). The mutated line is conspicuous among cosmetic edits, and hit rate cannot distinguish any arm from any other. Hit is reported in the analysis files and only once more in this section, for the corrupted arm. The withdrawn first benchmark had the same ceiling (93%) and, in addition, distractors that broke the file; its numbers are not reported (Section 6).

**Anchor versus evidence, on real comments.** Of 291 test-verified c-CRAB defects, 291 anchor in a file the pull request changed and 213 on a changed line. Under the strict reading, 97 (33%) refer to something the diff does not contain; under the loose reading, 146 (50%). Where a comment sits is not where its justification lives.

**Discrimination with safe twins.** Twins are the same surface mutation as a defect task, placed where the shown caller is verifiably robust to it. The generator produced 150, of two kinds, from 20 repositories; 143 have a decoy and are run, and the deepseek run completed 134 of them before credit ran out. Correct on a twin means not flagging the mutated line (Figure 1).

| Arm | gpt-4o-mini (n=143) | deepseek-v3.2 (n=134) |
|---|---|---|
| 1 diff only | 4.2% | 17.2% |
| 2 evidence | 1.4% | 20.9% |
| 3 topology | 0.7% | 12.7% |
| 4 typed | 0.0% | 14.9% |
| 5 attributed | 0.7% | 17.9% |
| 6 corrupted | 10.5% | 19.4% |
| 7 random | 1.4% | 13.4% |
| 8 header | 5.6% | 17.2% |

No arm on either model clears more than about a fifth of the twins (at most 21%), and on gpt-4o-mini none but the corrupted arm clears more than one in sixteen, and that one clears one in ten. Shown the robust caller, the model flags the change anyway; on deepseek the caller lifts the clear rate from 17.2% to 20.9%, which is within its interval. Balanced accuracy over defects and twins is therefore near chance for every arm, and no form of context moves it far. A variant that instructs the model that the shown code is every use of the changed function is reported in 4.5.

## 4.2 Does the caller help? A relevance control, and partly a sanity check

The scrambled control (arm 2) and the foreign-repository arm (arm 7) receive the same number of snippets at the same budget; only arm 2's snippets are the real definition, caller and decoy. The header-only arm (arm 8) receives the dependency section with no snippets. The metric is the validated judge: does the message on the defect line name a concrete fact about the caller (Figure 2).

Two judges are reported: J1 is deepseek-v3.2, which is also a reviewed model, and J2 is gemini-2.5-flash, a fourth family. Both agree with the 40 hand labels at kappa 0.43; J1 under-calls, J2 is calibrated to the human rate. Where they disagree on a verdict the table shows both.

| Comparison, judge J1 / J2 (rows 2–4: J1) | gpt tag | gpt flat | deepseek tag | llama tag |
|---|---|---|---|---|
| real snippets − foreign | +11.9 [+7.1, +17.2] / +8.0 [+2.3, +13.5] | +13.7 [+7.4, +20.5] / +8.0 [+0.4, +15.9] | +36.0 [+27.2, +44.7] / +11.6 [+4.0, +19.3] | +7.6 [+3.8, +11.6] / +9.8 [+4.0, +15.9] |
| real snippets − header only | +13.7 [+9.0, +19.1] | +16.4 [+10.6, +22.7] | +37.8 [+30.5, +45.1] | +8.0 [+5.2, +10.9] |
| header only − diff only | 0.0 [−2.7, +2.7] | −1.3 [−4.3, +1.8] | −3.1 [−8.4, +2.6] | −0.9 [−3.4, +1.6] |
| foreign − diff only | +1.8 [−1.0, +4.9] | +1.3 [−2.4, +5.2] | −1.3 [−5.8, +3.5] | −0.4 [−3.1, +2.2] |

Every real-versus-foreign interval excludes zero on every model and encoding under both judges, and every real-versus-header interval under J1. Part of this is a sanity check rather than a finding: a model that never saw the caller can only state a caller-side fact by inferring it from the mutation, which J2 credits in about a third of diff-only messages and J1 in a twentieth. The gap above that floor is what the caller adds. Arms that never see the caller sit at 1–8% on this metric for gpt-4o-mini and llama and at 14–18% for deepseek, which is the floor set by the judge's strictness. Under J2 the real-versus-header difference is +10.2 [+5.7, +14.8], +8.4 [+2.4, +14.6], +12.9 [+4.4, +21.4] and, on llama, +4.4 [−2.3, +11.7]; the rows below the first are J1.

The same snippets lower precision on two of three models. Precise means the defect line was found and no harmless line was flagged. Showing the real snippets costs 18.6 to 23.5 points of precision against the diff alone on gpt-4o-mini under both encodings and 19.1 on deepseek, while foreign snippets cost nothing on gpt-4o-mini (−0.4 and +0.9) and 8.9 [−14.2, −3.6] on deepseek. On llama the real snippets cost nothing: +2.7 [−3.5, +8.6] against the diff. Where it occurs, relevant code makes the model flag more of the diff than irrelevant code does.

## 4.3 Does stating the structure help, given the caller?

Arms 2 through 6 receive identical snippets. The pre-registered primary comparison is bare topology (arm 3) against the scrambled control (arm 2).

**On the pre-registered keyword rubric, the primary spans zero** on both runs where it was computed: −0.9 [−5.3, +3.2] on gpt-4o-mini and −2.7 [−6.7, +0.9] on llama. The rubric was found, before the full data existed, to pass boilerplate: a diff-only reviewer writing "may lead to unexpected behavior if the caller expects a None return value" satisfies it, and 50% of diff-only messages do. It is reported as pre-registered and not interpreted further.

**On the validated judges**, with a miss counted as a failure so that arms are compared on the same tasks (Figures 2 and 3):

| 3 topology − 2 control | gpt tag | gpt flat | deepseek tag | llama tag |
|---|---|---|---|---|
| judge J1 (deepseek) | **+7.5 [+3.0, +12.2]** | −0.9 [−5.0, +3.1] | **+11.6 [+4.3, +18.8]** | **+7.6 [+3.3, +12.2]** |
| judge J2 (gemini) | **+10.2 [+5.6, +15.2]** | +2.7 [−2.3, +7.7] | **+9.8 [+3.2, +16.2]** | +4.0 [−0.5, +8.3] |
| McNemar b / c, exact p (J1) | 25 / 8, 0.005 | 14 / 16, 0.86 | 42 / 16, 0.0009 | 24 / 7, 0.0033 |
| precise (no judge) | **+9.7 [+4.5, +15.5]** | **+10.2 [+4.8, +15.9]** | **+9.8 [+4.1, +15.0]** | **+14.2 [+9.2, +18.9]** |

Stating a bare true link between the snippets raises the rate at which the model explains the defect through the caller by 7 to 12 points on gpt-4o-mini and deepseek under the tag encoding, with both judges' intervals excluding zero; on llama the two judges disagree (+7.6 excluding zero, +4.0 spanning it); under the flat encoding the effect is absent on both judges. On precision, which needs no judge, the gain is 10 to 14 points on all four runs: on the two models where showing the snippets cost precision, the link recovers roughly half of it. Encoding dependence on the judge metric is real and is reported, not averaged away [arXiv:2511.10234].

The typed and attributed arms add the relation kind and its argument on top of the link. Attributed exceeds the control on every run under J2 and on three of four under J1 (gpt flat J1: +5.3 [−0.4, +11.1]), by 11.1 [+6.6, +15.8] (J1) and 21.2 [+16.2, +26.5] (J2) on gpt-4o-mini tag and by 25.8 [+18.1, +32.7] and 17.3 [+9.4, +24.7] on deepseek; the argument names the thing the judge looks for, so this comparison measures information supplied as much as structure, and is read as an upper bound.

**Corrupted structure.** Arm 6 keeps the relation kind and argument and moves the target to the decoy. Against the control it is 0.0 [−4.8, +4.9] on gpt tag, +2.7 [−2.1, +7.2] on gpt flat, +3.1 [−1.3, +8.0] on llama and +13.3 [+7.5, +18.9] on deepseek under J1; under J2, +4.0, +4.0, +1.8 and +10.7 [+4.8, +16.5]. A wrong pointer is inert on three runs and helps on deepseek, which extracts the kind and argument regardless of where the arrow points. This arm measures a wrong endpoint, not absent structure; the clean comparison for topology is arm 3 against arm 2. Corruption lowers hit rate on gpt-4o-mini under the tag encoding, 88.9% against 95.1% for the control [−10.6, −2.3], and not under flat or on the other models: there the model follows the wrong pointer.

**Comprehension probe.** Asked to read each block back alone, with no snippets, the model names the correct target file for topology in 28 or 29 of 29 probes on every run, for typed in 26 to 29, and for attributed in 25 to 28, and never for the scrambled control (0 of 29). The probe checks the file stem, and the decoy sits in the definition file, so it cannot tell a corrupted pointer from a correct one. The serialisation conveys the structure under both encodings; a null under flat encoding is a null of use, not of parsing.

## 4.4 Moderators

**Hidden evidence** (40 tasks of the two kinds that admit it). With the demonstrating line removed from the caller window, topology against control is 0.0 [−12.5, +15.8] under J1 and +12.5 [−5.1, +27.3] under J2; attributed is +20.0 [+4.7, +36.1] and +22.5 [+8.3, +37.5]. On forty tasks a bare link shows no detectable effect when the fact it points to is not visible; the attributed relation, which supplies the fact, does.

**Noise** (four foreign snippets added, 229 tasks). Topology against control is +2.6 [−1.7, +6.9] under J1 and +4.8 [−0.8, +10.5] under J2; the attributed arm +5.2 [0.0, +10.7] and +19.7 [+14.2, +25.6]. The structural gain shrinks under clutter rather than growing; the hypothesis that a map organises noisy evidence is not supported here.

**Two-hop chains.** The generator found three pass-through chains in 41 repositories at 300 to 500 files each. That is too few to run, and the hop moderator is reported as not evaluated.

## 4.5 The authoritative-callers variant

The twins were re-run on gpt-4o-mini with one added sentence, identical across arms: the related code shown is every use of the changed function, and a change compatible with every use shown is not a defect. Correct still means not flagging the mutated line. All 143 twins with a decoy:

| Arm | correct on twins |
|---|---|
| 1 diff only | 4.9% |
| 2 evidence | 9.1% |
| 3 topology | 1.4% |
| 4 typed | 0.0% |
| 5 attributed | 0.0% |
| 6 corrupted | 20.3% |
| 7 random | 14.0% |
| 8 header | 5.6% |

Told that the shown caller is the whole truth, and shown a caller that tolerates the change, the model flags the change in 91% of cases with the evidence and in 100% with the typed or attributed relation. The attributed arm is 9.1 points below the control [−14.3, −4.9]; the more the metadata says about the relation, the more certain the model is that the relation is the problem. On these twins the metadata moves the model toward flagging, never away from it; the evidence that should exonerate a change does not. The two arms above 10% are the ones whose context points away from the caller: corrupted and foreign. Context, in every form tested, moves the model's explanation of a defect and not its willingness to call a change safe.

On the defect side the instruction raises precision across the board, and the foreign-code arm shows why. On all 226 defects, precision is 71.2% for the diff alone, 73.0% with the real snippets, 85.8% with foreign snippets under the same instruction (+14.6 [+7.9, +21.2] over the diff), 91.6% with the bare link and 96.5% with the attributed relation. The instruction tells the model that the code shown is the whole truth, and the model flags fewer lines whatever that code is; the link adds +18.6 [+14.3, +22.8] over the scrambled control, and the foreign arm shows that most of a 15-point rise is available from the instruction alone, which that arm receives though for it the instruction is false. Told that the shown code is the whole truth, the model stops flagging the harmless lines around a defect, and still flags the twin.

## 4.6 Real defects: c-CRAB

The model throughout is gpt-4o-mini. The c-CRAB runs from August stand for the conditions that do not retrieve: on the 219 test-verified defects shared with the re-run below, no context, whole changed files and the fault-location oracle all localise 33 to 36%. The graph condition in those runs queried the file node rather than the function, walked two hops, and filled its budget with same-file neighbours, so it reached the depended-on caller in 4% of tasks where that caller was available; it is not reported. Three repairs were made and committed on 30 August, before the controlled re-run was designed: query the enclosing function, walk three hops, and rank other-file neighbours ahead of same-file ones before the budget applies. The fault-location oracle scores no better than the diff because it returns the entities spanning the defect line, which the diff already shows; it is an oracle for location, not for evidence.

All retrieval conditions were re-run on the same day (Figure 4) with the same pipeline, model, budget (1,500 tokens) and tolerance (5 lines), on 219 defects paired across the first four and 218 across all five.

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

One model (gemini-2.5-flash, which is also judge J2 and is not a reviewed model in the structure runs), the same two tools, the same repository and the same diff; one sentence of framing varies. Across 40 paired tasks a bare tool-equipped model searched in 0 of 40 under the review prompt and in 40 of 40 when told the defect depended on another file, reaching the caller in 20%. The result is scoped to a bare model: harnessed products explore unprompted [arXiv:2607.16740].


## 4.8 Explanation against precision, and cost per true finding

A reviewer may object that a better explanation is overcorrection in disguise [arXiv:2603.00539]: a model that says more may also flag more. The table below shows the two side by side for the arms that share the same snippets; on every run the arms with the highest judge rate are among those with the fewest confirmed false flags. With five arms per run this is a description, not a test.

Cost per true finding, in thousandths of a dollar per defect found and confirmed false flags per defect found:

| Run | diff only | evidence | topology | attributed | foreign |
|---|---|---|---|---|---|
| gpt-4o-mini tag | 0.11 / 0.51 | 0.25 / 0.94 | 0.21 / 0.71 | 0.20 / 0.64 | 0.19 / 0.54 |
| deepseek-v3.2 tag | 0.18 / 0.28 | 0.47 / 0.56 | 0.35 / 0.41 | 0.25 / 0.31 | 0.31 / 0.41 |
| llama-3.3-70b tag | 0.12 / 0.70 | 0.24 / 0.60 | 0.21 / 0.27 | 0.22 / 0.43 | 0.19 / 0.70 |

The bare link lowers false flags per true finding by a fifth to a half relative to the scrambled control on every run, at the same token cost. The diff alone is the cheapest condition per true finding on every run; on this benchmark it also finds the line 97.8% of the time, which is the ceiling problem of Section 4.1 restated as a cost.
