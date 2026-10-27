# Method

The question we set out to answer is whether telling a model how retrieved code is connected helps it review a change, once the code itself is already in front of it. Prior comparisons cannot answer this because retrieval and representation change together. The design that can, holding the snippets constant and intervening only on the metadata that describes their relationships, needs a benchmark on which the diff alone does not already give the answer. This section describes the benchmark, the twins, the four diagnostics that test whether the benchmark can carry the experiment, and the real-defect set on which a retrieval result is reported. The held-constant design itself is described briefly in 3.5, because its two runs are withdrawn and the diagnostics are the reason.

## 3.1 Task

A reviewer receives a pull-request diff and must report defects as a list of `(file, line, message)`. Each task contains exactly one defect, introduced by a mutation in one file, that is wrong only because of an assumption a different file makes. The diff also contains three harmless edits, so the reviewer must say *which* change is wrong rather than *that* something is.

## 3.2 Benchmark construction

Tasks are generated from 39 production repositories at a fixed commit, each sampled to at most 300 production files. For every public function with a caller in another file, the generator attempts one of five mutations and keeps the task only when the caller's syntax tree demonstrates the dependency the mutation breaks:

| Kind | Mutation | What the caller must contain |
|---|---|---|
| `exception_type` | `raise A` → `raise B` | a handler that catches `A` and not `B`, enclosing the call |
| `none_sentinel` | `return None` → `return -1` | a comparison of the call's result with `None` |
| `default_flip` | `p=True` → `p=False` in the signature | a call that omits `p`, positionally and by keyword |
| `tuple_order` | `return a, b` → `return b, a` | an unpacking assignment of the call's result |
| `empty_to_none` | `return []` → `return None` | iteration over, `list()` of, or `len` of the call's result |

Calls are resolved through imports: a bare name imported from the defining module, or re-exported from it through package `__init__` files followed to three levels, or `module.name` after a module import. A same-name import from any other module is not a call to the mutated function. Attribute calls on arbitrary objects are not matched, which excludes most methods and removes name collisions between unrelated functions called `run` or `write`. Each task records the verified caller line and the *argument* of the dependency: the exception type, the parameter name, the unpacked names.

Distractors are rewrites that leave the file's syntax tree identical: a change of string quote style in either direction, redundant parentheses around a return value or a right-hand side, a spacing change. Each is applied to a copy of the whole file and rejected unless the tree is unchanged. Three are chosen per task from a window around the defect whose centre is jittered and whose split above and below the defect is seeded, so the defect's position among the four hunks is close to uniform: in the third version it is last in 28% of diffs. The diff lists the four hunks in line order with nothing marking which is which. Where the generator names a snippet, in the metadata blocks of 3.5, it uses the file stem and the enclosing function, never a line number, because the diff shows line numbers too.

The third version holds 277 defects from 37 repositories: 144 default flips, 91 tuple reorderings, 27 `None` sentinels, 8 exception types and 7 empty-to-`None`. An audit script re-checks every released task with the generator's own resolver and tree comparison, following re-exports through the cached repository: 0 of 277 have a caller import that does not resolve to the mutated module, 0 have a distractor that changes the tree.

Two earlier versions are withdrawn. The first located evidence by a regular expression within eight lines of any same-named call, which demonstrated the dependency in roughly a third of tasks, and its distractor rewriter broke docstrings in 145 of 204 tasks, so a model that flagged a syntax error was scored as a false positive. The second was audited after an external review on 26 October 2026 and had five defects: its metadata labels carried the mutated line's number, which the diff also shows; its resolver accepted a same-name import from any module, in 36 of 229 tasks; 25 of its 150 twins had a dependent call in one of the two files shown; 91 of its 650 distractors changed the syntax tree, 639 of the 650 were quote rewrites, and the defect sat last in the diff in 62% of tasks; and an unparseable reply was scored as correctly silent. Each has a pinned test in the artifact. The present generator was written against both lists.

## 3.3 Safe twins

A twin is the same surface mutation as a defect task placed where no caller depends on what changed: a flipped default that every call site passes explicitly, a changed exception type that no enclosing handler catches. Safety is checked repository-wide, not on the two files shown: every non-test file in the pool is scanned for a bound call to the function, or an attribute call of the same name, that the kind's verifier would accept, and the mutation is rejected as a twin if any is found. The third version holds 165 twins from 33 repositories, 149 default flips and 16 exception types; the audit finds 0 with a dependent call. A twin task is rendered like a defect task, with the same distractors and, in the evidence arms, a caller window that shows a call the change does not break. Correct on a twin means not flagging the mutated line.

## 3.4 Four diagnostics

*Partial-input ceiling.* The model is given the diff alone and must report defects; a hit is a finding whose line equals the mutated line, with no tolerance. The rate is reported for every version of the benchmark and for the real-defect set of 3.6. A rule for the third version was fixed before its run: if the diff-only hit rate was 95% or higher, the remaining arms would not be run and only the ceiling would be reported; the target was under about 80%.

*Anchor versus evidence.* For each real reference comment, `experiments/evidence_scope.py` records where the comment is anchored (a changed file, a changed line) and whether its text refers to anything the diff does not contain, under a strict reading (a named identifier, file or behaviour absent from the diff) and a loose one (any reference beyond the changed lines). Every decision carries its reason.

*Safe twins.* As in 3.3; the clear rate per arm is the diagnostic, compared between the diff-only arm and the arm that shows the tolerant caller.

*Test verification.* `experiments/verify_by_tests.py` clones each repository at the benchmark commit, installs it, selects the tests nearest the mutated module, runs them before the mutation, applies the mutation and runs them again. A defect is test-verified when a test that passed before fails after. The funnel, including repositories that could not be installed and modules with no passing test, is reported in full.

## 3.5 The experiment the diagnostics gate

The held-constant-evidence design fixes an evidence set per task, a 25-line window around the mutated line, a 25-line window around the verified caller line and a decoy function from the definition file, and renders it identically in every arm that receives it. Arms differ only in a metadata block: absent; scrambled so that it has the same shape and says nothing true; a bare link; a typed relation; a typed relation with its argument; or a relation with its target moved to the decoy. Two further arms replace the snippets with length-matched functions from repositories outside the benchmark, or remove them while keeping the metadata section. The primary comparison, bare link against scrambled control on a metric that asks whether the message explains the defect through the caller, was recorded in the repository (commit 71fb660, 1 October 2026) before the second version's runs. Both versions' runs are withdrawn with the benchmarks they were run on. A third run was conditional on the diagnostic in 3.4, and Section 4.1 reports why it was stopped after one arm set. The runner, arms, serialisations, judges and analysis remain in the artifact for a benchmark that passes the gate.

## 3.6 The real-defect set, and the reviewer prompt

c-CRAB's paper reports 184 pull requests and 234 comments; its public release holds 410 instances and 595 comments, and its stage-three test-verified file holds 339 Python pull requests with 485 reference comments. We use that file and the test-generation archive, downloaded on 27 August 2026, and filter in four steps: 477 comments carry a line; 340 of those carry a generated test that fails before the fix and passes after it; 291 of those sit in a source file of a supported language, and these are the set for the anchor-versus-evidence measurement; 246 remain after diffs longer than 40,000 characters are dropped (195 pull requests). The diff-only and graph conditions returned an answer for 244 of them, the random and lexical conditions for 228 and 224, so 219 defects are paired across the four conditions and 218 across five once the random-other-files control is added. Every number in Section 4.5 is on one of those two paired sets.

The system prompt is one text for every arm and both benchmarks. It tells the model that humans have reviewed the diff and found real problems, to assume there is something to find, and the output contract asks for best candidates even when uncertain while allowing an empty list. The sentence was written for the real-defect runs, where every diff carries a confirmed defect, and was kept for the generated benchmark and the twins so that arms differ only in the metadata. It pushes the model toward flagging, so the twin clear rates in 4.3 are a floor on what a neutral prompt would give. A neutral variant that drops the sentence and states that an empty list is a correct answer is implemented (`--neutral-prompt`); it is the prompt of the neutral runs in 4.3.

## 3.7 Models and statistics

The ceiling and the test-verification check use gpt-4o-mini; the twins use gpt-4o-mini and deepseek-v3.2; the search-trigger test uses gemini-2.5-flash; all at temperature 0.1 through one API. Tasks are paired across arms. The reported interval is a 95% percentile bootstrap that resamples repositories rather than tasks, because several tasks share a repository and a definition file, with the task-resampled interval shown beside it in the analysis files. McNemar's exact test on discordant pairs is reported for each comparison. "Excludes zero" and "spans zero" are the only verdicts used, and a result is reported only from a run that completed on its full paired set.
