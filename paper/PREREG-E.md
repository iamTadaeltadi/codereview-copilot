# Pre-registration: condition E, CIS context on c-CRAB (6 November 2026)

Written and committed before any model call for this condition. Nothing below has been run on a
model. The only thing done before writing it was to read the run 4 harness and to download and
build CIS.

## Why

Condition B, our graph retrieval, did not beat random code from other files (Cx) on c-CRAB, on
gpt-4o-mini (run 4, `results/ccrab-final/`) or on deepseek-v3.2 (`results/ccrab-deepseek/`). A
reviewer can answer that our graph was too simple. Condition E puts a second, independently built
code-graph tool in B's place under the same rules. If E also fails to beat Cx, the null does not
depend on our graph builder. If E beats Cx, that is a finding about graph quality.

## Hypothesis

E beats Cx (random code from other files, same budget) on real c-CRAB defects.

## The tool

CIS, the Codebase Intelligence System by co-author Abdissa:
`https://github.com/abdissa-png/Codebase-Intelligence-System`, pinned at commit
`4ea4bfe9e37b1a91311d88b6ae9797dd2b5f8ea9` (27 September 2026). Source taken as the GitHub tarball
of that commit, sha256 `c34112bf0d078fe109e79164e9d5edede1a2a7f860b14f1decd7fe1088e73166`. Built with

    cargo build --release -p cis-mcp --features python-ast,body-sqlite

and queried as `cisd --mcp` over stdio, with `CIS_REPO_ROOT` set to the directory of one task.

## What CIS indexes

For each task, CIS indexes **the same source files our graph was built from** for B, C, Cx and D
in run 4. These are stored in each cached run-4 graph as `graph.graph["sources"]`
(`.repo-cache/<repo>@<commit>-sparse-h3-v2.pkl`): the files the diff touches plus up to three
import hops, at most 60 files, at the reviewed head commit. They are written to a fresh directory,
CIS indexes that directory, and the directory and its `.cis/` state are deleted after extraction.

This departs from the request to check out each repository at the base commit, for three reasons.

1. Every run-4 condition reads the reviewed revision, `BenchmarkTask.review_commit`, which is the
   head commit. The diff's new-file line numbers refer to it. The base commit lacks every file the
   pull request added.
2. With the same files, E differs from B only in the graph built over them. A full checkout would
   also give E files that B, Cx and D never had, so a gain could come from file coverage rather
   than graph quality, and the comparison with Cx would no longer hold the material fixed.
3. On 6 November a 1.3 MB clone of CIS itself failed on a dropped connection. Full checkouts of the
   63 repositories were not feasible before the 10 November deadline.

A full-repository variant is not part of this pre-registration.

## Extraction, per task

1. **Seeds.** The symbols the diff changes: CIS symbols in the diff's changed files whose span
   overlaps a changed hunk's new-file line range. The ranges come from `changed_ranges` in
   `experiments/run.py`, as for B. Symbols are located with `find_symbol` and kept when their
   `file_path` and span match. Only functions, methods and classes are seeds. A class whose own
   method is already a seed is not seeded as well, the drop-class-seeds rule of run 4.
2. **Callers.** `get_callers` on each seed's identity id.
3. **Expansion.** `expand_context` on each seed's revision id with `depth` 1: the seed's own calls,
   imports, uses and extends.
4. **Text.** `get_symbol_body` on every hit.
5. **Raw record.** Saved before any budget as `results/ccrab-cis/context-E.json`, as
   `{task_id: [{path, start_line, end_line, relation, text}]}`, together with the seeds, CIS's
   index status and any error per task.

`build_context` is not used: it truncates text it is given and does not read the graph.

## From raw hits to the context the model sees

The same rules as B in run 4, applied to CIS's hits.

- **Order.** Callers first, then expansion hits. Within each group, hits in files other than the
  seeds' files come first, the cross-file preference B used in run 4. Ties keep CIS's returned
  order, which is nearest first.
- **Filter.** Seeds themselves are dropped. Test files are dropped with the same `is_test_path` as
  run 4. Only function, method and class symbols are kept, as B keeps only functions and classes.
  File hubs and module nodes are dropped. A symbol reached twice is kept once, at its first
  position.
- **Cap and budget.** At most 80 candidates, the candidate cap every condition had in run 4. Each
  body is cut at 40 lines with the same "more lines" marker as `entity_source`. The entries go
  through the same `_budgeted` function as B, C, Cx and D, which drops entries from the end until
  the serialised payload fits 3,000 tokens counted with tiktoken `cl100k_base`.

  This corrects one number in the request, which said "at most 12 entities". Twelve is the
  tool's default; run 4 passed a cap of 80 to every condition. In run 4 B kept a median of 7 and
  at most 18 entities under the 3,000-token budget.
- **Rendering.** The same `render_context` as every run-4 condition: one header line naming the
  entities that overlap the diff, then each entity as a code block under a path-and-name line.
  The header line is copied from B's run-4 context for the same task, so E's prompt differs from
  B's only in the related-code blocks.
- **Empty context.** A task where CIS fails to index, finds no seed or returns no hit still runs,
  with no repository context, exactly as B runs when its context is empty. It is not dropped.

## Coverage report, before any model call

Committed before any model call: tasks indexed, tasks that failed to index and why, tasks with
non-empty context, and the median delivered context size in tokens for E beside B, D and Cx from
run 4.

## The model runs

- **Models.** `openai/gpt-4o-mini` and `deepseek/deepseek-v3.2` through OpenRouter, temperature
  0.1, as in run 4 and its replication.
- **Tasks.** Run 4's 195 tasks: `load_ccrab` with confirmed defects and supported source only,
  diffs up to 40,000 characters, sorted by task id, `--limit 400`.
- **Prompt and matching.** The same `build_messages`, with numbered diff lines and the tool clause
  B, C and D receive, the same matcher, tolerance 5 lines and the exact line.
- **Recording.** The per-call records name the condition `CIS`, because the letter `E` already
  names the unbudgeted whole-file arm in `experiments/config.py`. Files and the paper call it E.
- **Comparators.** A, B and Cx are the frozen run-4 records for gpt-4o-mini and the frozen
  replication records for deepseek-v3.2. They are not rerun. E therefore runs on a later date than
  its comparators, so a change in a hosted model between dates would enter E − Cx. This is
  disclosed with every result.
- **Unscored calls.** A call that times out, returns unparseable output or is cut off writes no
  outcome. One resume relaunch retries such calls, as in the replication, and both logs are kept.

## Tests

Every comparison is a paired difference in detection rate on defects present in both conditions,
with the repository-clustered percentile bootstrap of `experiments/analyse_ccrab.py`: 6,000
trials, seed 0, repositories resampled, the task-clustered interval reported beside it.

**Primary: E − Cx**, in four cells:

| | tolerance 5 | exact line |
|---|---|---|
| all paired defects | reported | reported |
| pre-registered subset | **decision cell** | reported |

The pre-registered subset is the 77 defect ids in `results/ccrab-final/primary-subset.txt`,
committed before run 4: source-file defects whose reference comment lies strictly outside the
diff. In run 4 64 of them were paired, in 35 repositories; in the replication 65 were paired.

**Decision rule.** E is said to beat Cx only if the repository-clustered 95% interval of E − Cx
lies wholly above zero on **both** models in the decision cell. The other three cells are
reported under the same rule, each named, and none of them can carry the claim alone. An
interval that includes zero on either model is reported as no detectable gain. An interval wholly
below zero on both models is reported as E doing worse than random.

**Secondary, reported in the same four cells and not used for the claim:** E − B and E − A.

## Spend and stops

- **Stop rule.** If any single run, one model's E pass, costs more than $3.00 by the recorded
  per-call cost, it is stopped and the partial records are reported as partial.
- **Credit.** The OpenRouter balance on 6 November was −$0.03. No model call is made until credit
  is added.
- **Deadlines.** If `context-E.json` is not ready by 10 November 2026, or the runs are not done by
  12 November 2026, the work stops and becomes future work, not part of this paper.

## Optional, only after the tests

CIS's caller edges checked against the jedi validation used for our graph on its six
repositories, with caller-edge precision and recall reported beside ours.

## What is not changed

No existing result file is changed. Run 4, the replication and every earlier record stay as
frozen. Git history is not rewritten.

## Amendment before any model call, 6 November 2026

Written after the first extraction and its coverage count, and before any model call.

**A rule of B's that the text above left out.** When a changed file has no function or class
overlapping a changed hunk, B seeds that file's own node (`seed_queries` in `experiments/run.py`).
In run 4, 28 of B's 194 tasks had a file-node seed, and 2 had only file-node seeds. E now does the
same: a changed file with no function, method or class seed contributes its CIS file hub as a
seed, and `get_callers` and `expand_context` are asked about it like any other seed. The
extraction was rerun with this rule. The first extraction's records and coverage are kept in
`results/ccrab-cis/superseded/`. Its counts were: 194 of 195 tasks indexed, 187 with a seed, 167
with at least one delivered entity, median delivered context 1,098 tokens against 1,790 for B.

**How the kind of a symbol is decided.** CIS's hits carry no kind field, and its Python index also
holds module-level assignments. A symbol counts as a function when its source, after decorator
lines, starts with `def` or `async def`, and as a class when it starts with `class`. Anything else
is neither and is dropped, as B keeps only functions and classes. CIS names Python symbols
`path::Class.method`, so the drop-class-seeds rule drops a seed whose qualified name, followed by
a dot, begins another seed's name.

**Coverage limits found, not changed.**
- Four tasks change only JavaScript (three in ccxt, one in zulip). The pre-registered build has
  the Python parser only, so CIS indexes no symbol there. They run with no CIS entity. Building
  with the `ts-javascript` feature would change the pre-registered build and is not done.
- In one sympy task the changed file, `bin/coverage_doctest.py`, has no symbol in CIS's index.
