# Artifact

Everything needed to regenerate the benchmark, re-run every arm, and recompute every number is in the repository, with the frozen outputs beside the code.

**Benchmark generator.** `experiments/crossfile.py` holds the five mutation kinds, the import resolution, the per-kind verifiers that inspect the caller's syntax tree, and the parse-checked distractors. `experiments/rebuild_crossfile.py --clone` regenerates `data/crossfile-v2.jsonl` from depth-one clones of the source repositories and writes each task's definition and caller file into a local cache, so that every later run is offline. The funnel is printed, not hidden.

**Evidence and arms.** `experiments/evidence.py` builds the evidence set, the scrambled control, the typed and attributed relations, the corruption, the foreign-repository random arm and the hidden-evidence window. `data/foreign-snippets.jsonl` holds the 256 functions from `requests`, `click` and `rich` that the random arm draws from, with their provenance in `data/FOREIGN-SNIPPETS.md`.

**Runner.** `experiments/run_structure.py` runs the eight arms under any of the three serialisations, records the exact prompt length, the parsed findings, the message on the defect line, the mechanism verdict and the cost of every call, and runs the comprehension probe alongside. Runs resume.

**Analysis.** `experiments/analyse_structure.py` deduplicates by task and arm, restricts to tasks present in every arm, and reports the per-arm table, the repository-clustered and task-clustered bootstrap intervals side by side, McNemar's exact test and a Holm-adjusted family for every requested pair. It never prints the word "significant".

**Secondary measurements.** `experiments/evidence_scope.py` classifies c-CRAB comments by whether they refer to anything outside the diff, mechanically, with the reason recorded for every decision; `experiments/run_search_trigger.py` is the search-trigger test; `experiments/mine_regressions.py` mines the real cross-file regression candidates.

**Frozen results.** `results/` holds one directory per run with the raw per-call records and the analysis output. Directories measured on the withdrawn first benchmark carry a `WITHDRAWN.md` stating why, and are kept so the withdrawal can be checked.

**Tests.** 551 unit tests, including one for each fault found in the first benchmark: a distractor that breaks the file is rejected, an unresolved name is not evidence, a handler that also catches the new type is not evidence, a scrambled control contains no true token, a corrupted relation is never a self-loop.

**Not included.** Model outputs were obtained through OpenRouter at the prices recorded in each run's records; model versions change, and exact replication of a number is not guaranteed. The 96 regression candidates are unverified and are released as candidates.
