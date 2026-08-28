# ULTIMATE PLAN — repo → evaluation → paper → publish

Written 27 Aug 2026. Supersedes the "12-week plan" in the old handoff.
Repo under work: `~/Desktop/education stff/canada-2027/capstone/codereview-copilot`
Branch: `main` @ `75552fa`

---

## The one-sentence version

Make the repo actually installable and testable → fix the nine defects that make
the experiment impossible → build the harness that runs the experiment →
run it → write the paper → have real people read it → then publish.

Nothing gets published until a human who is qualified has read it and said it is
publishable. That is the last step, not the first.

---

## Ground truth as of today

What was already done before today:

| Done | Commit |
|---|---|
| Webhook handler made idempotent, signature verified before any write | `54da554` |
| `Finding` table, `Review.condition`, `LLMUsage.step`, `parent_review` → PROTECT, rating 1–5 constraint | `dbd463d` |
| Webhook test expects 400 not 500 on malformed payload | `75552fa` |

**Phase 0 was executed on 27 Aug 2026 — commit `c4bab1f`.** What it found is
worse than expected, and worth stating plainly because it changes the risk
picture for the paper.

### Finding 1 — the test suite had never passed

`TESTING.md` claims "~86% coverage" and tells you to run `bash scripts/test.sh`.
Running it for the first time produced **33 errors**. Every one had the same
cause: the five standalone test modules load source files from `agent_runtime/`,
a directory that was renamed to `services/agents/` and never updated in the
tests. So the suite could not import, let alone pass.

### Finding 2 — the graph service could not parse a single file

This is the serious one, because the repository graph **is** the contribution.

`services/graph/codecontext/utils.py` and `construct_graph.py` each contain a
copy of the same block. They build the tree-sitter languages with the **post-0.22
API**:

```python
PY_LANGUAGE = Language(tspython.language())
```

and then select a language with the **pre-0.22 API**, which was removed:

```python
parser.set_language(LANGUAGE_MAP[file_extension])
```

These two cannot both work on any single version of tree-sitter. On modern
tree-sitter you get `AttributeError: 'tree_sitter.Parser' object has no
attribute 'set_language'` on the first file. On the pinned 0.21.3 the
`Language(...)` single-argument constructor fails instead. The graph builder had
not been run in a long time.

The fix is one line in each file — assign to `parser.language`. After it, the
builder works: over this repository's own Django app it produces **2,984 nodes
and 20,493 edges across 34 files**, and the retriever resolves
`models.py::class::Review` and returns its neighbourhood.

**What this means for the paper:** every experimental result depends on this
code path. If the intention had been to start running experiments in October,
they would have failed on day one for a reason that had nothing to do with the
research question.

### Finding 3 — the retrieved "context" is mostly noise

Querying `models.py::class::Review` on the real graph returns these neighbours:

```
file      models.py
function  __str__
class     TimestampMixin
class     unknown
class     Meta
class     UserManager        <- unrelated
function  create_user        <- unrelated
function  create_superuser   <- unrelated
```

This is defect **C1** made visible. `_bounded_neighbors` caps by node *count*,
not hop distance, and everything in a file connects through that file's node —
so a two-hop walk reaches every class in the file and the cap fills up with
whatever BFS happened to touch first. Right now "graph-grounded context" is
partly "other things that live in the same file". That is exactly the claim a
reviewer will attack, and fixing C1 is what makes the claim true.

### State after Phase 0

| Suite | Result |
|---|---|
| Django backend | 52 passed |
| Python integration | 185 passed, 0 skipped |
| Web client (Vitest) | 54 passed |
| **Total** | **291 passing, 0 failing, 0 skipped** |

Also added in `c4bab1f`: Apache-2.0 `LICENSE`; `NOTICE` crediting RepoGraph
(confirmed Apache-2.0, `ozyyshr/RepoGraph`) with the list of changes;
provenance in `README.md` and `services/graph/README.md`; a single
`requirements-dev.txt` covering all three services; `.github/workflows/ci.yml`;
and `tests/test_graph_parser_end_to_end.py`, five tests that would have caught
Finding 2.

Still not done: `.env` required-vs-optional split (B5), and the push to GitHub.

## Defect register

Every item has an ID. Nothing is "fixed" until it has a test and the test is
green in CI.

### Group B — blocks the repo from running at all

| ID | Defect | Why it matters |
|---|---|---|
| B1 | No CI workflow | No proof the suite passes; a reviewer's first check |
| B2 | No LICENSE | Repo is legally unusable as a research artifact |
| B3 | No RepoGraph NOTICE/attribution | Apache-2.0 violation + undisclosed prior art |
| B4 | Three incompatible dependency systems (pip for `api`, poetry for `agents` and `graph`) with no single install path | Nobody can reproduce your results |
| B5 | `.env.example` lists ~25 keys with no indication which are required to boot | Nobody can start the system |

### Group C — correctness defects

| ID | File:line | Defect |
|---|---|---|
| ~~C0~~ | `codecontext/utils.py:35`, `construct_graph.py:45` | **FIXED `c4bab1f`.** `parser.set_language()` removed in tree-sitter ≥0.22 while languages were built with the ≥0.22 API. The graph builder could not parse any file on any version |
| C1 | `services/graph/codecontext/retriever.py:33` | `_bounded_neighbors` caps by **node count** (`max_nodes=12`), not hop distance. There is no `max_depth` anywhere in the retrieval path. **The depth ablation in the paper is currently impossible — there is no knob to turn.** |
| C2 | `models.py:146` | `Review.condition` never written by any code path |
| C3 | migration 0007 | `LLMUsage.step` never written by any code path |
| C4 | migration 0007 | `Finding` never populated; findings still live as unschematised blobs in `Review.review_data`, so metrics cannot be computed in SQL |
| C5 | `tasks/review_tasks.py:60` | `Review.objects.get_or_create(..., status__in=['pending','in_progress'], ...)` — Django strips lookups (`__in`) from the create kwargs, so a concurrent webhook can create duplicate pending reviews |
| C6 | `models.py` | `User.github_access_token` stored as plaintext `TextField` |
| C7 | `Utils/ToolOrganizer.py:14` | The `retrieve_graph` tool signature exposes only `node`. No depth parameter reaches the LLM |
| C8 | `Utils/ToolOrganizer.py:28` | `build_tools()` **always** returns the graph tool. There is no way to run the pipeline without graph retrieval, so **Condition A (no graph) cannot be run** |
| ~~C1, C7, C8, C9~~ | | **FIXED `7abda43`** — hop-bounded BFS with `max_depth`, condition switch, budget-matched random tool, lexical tool, `ContextBudget` |
| **C10** | `retriever.py:33` | **NEW.** Which neighbours survive the `max_nodes` cap is decided by graph insertion order, not relevance. A file node is a hub, so at depth 2 the cap fills with whatever was parsed first. At `max_nodes=12`, depth 2 and depth 3 return an identical set — **a depth ablation at that cap measures nothing.** Either raise the cap for the ablation or rank neighbours before capping; state which in the paper |
| C9 | — | There is no random-node retrieval tool. Without it, any A-vs-B difference is confounded with "having any tool at all" versus "having no tool" |

### Group E — experiment infrastructure that does not exist

| ID | Missing |
|---|---|
| E1 | Benchmark loader + the benchmark itself |
| E2 | Experiment runner (`experiments/run.py`) |
| E3 | Metrics module (precision / recall / F1 / false-positive rate / tokens / cost) |
| E4 | Ground-truth labelling scheme and labelled data |
| E5 | Determinism control (seed, pinned model, pinned prompt version) |
| E6 | Results storage + export to the tables the paper prints |

---

---

## Research position — revised 27 Aug 2026 after a literature sweep

The original novelty claim is dead. A search of 2026 work found the gap I told
you was open has been filled, in public, by better-resourced groups.

### What is already claimed

| Claim we were going to make | Who published it |
|---|---|
| Graph context for code review, cross-language | AACR-Bench, arXiv 2601.19494 |
| Hop-depth ablation on repository graphs | LARGER, arXiv 2605.16352 |
| Grep-like vs graph retrieval for code | GrepRAG, arXiv 2601.23254 |
| Budget-controlled context study | arXiv 2605.04763 — but for code *completion* |
| Per-agent marginal contribution | CodeX-Verify, arXiv 2511.16708 (all 15 combinations) |
| Executable-test ground truth for review | c-CRAB, arXiv 2603.23448 |
| Model-level cost efficiency in review | arXiv 2606.15689 |

AACR-Bench opens by naming our exact gap as theirs: *"the lack of multi-language
support in repository-level contexts"*. Their findings sentence — *"context
granularity, retrieval methods, LLM type, programming language, and architecture
paradigm significantly influence performance"* — is the study we were planning.

One of these also has a direct warning for this system's architecture.
arXiv 2606.15689 found that combining models **lowered** F1 (0.365 alone → 0.333
in ensemble): *"the models largely detect the same bugs; adding a second model
introduces its false positives without meaningfully increasing true positives."*
This pipeline runs syntax, standard, and error-analysis agents in parallel. That
may be manufacturing false positives. It is now something to measure, not assume.

### What is still unclaimed — the three arms of the paper

**Arm 1 — equal token budget, for review.** The budget-controlled comparison
exists for code completion. It does not exist for code review. Every published
"graph context helps review" result gives the graph arm more text than the
baseline, so **smart context and more context have never been separated** for
this task. This is the strongest remaining gap and the headline claim.

**Arm 2 — cost per true finding, across retrieval strategies.** arXiv 2606.15689
does cost efficiency across *models*. Nobody does it across *retrieval
strategies* in review. `LLMUsage` already stores `input_tokens`,
`output_tokens`, `cost`, and `llm_model` per review — this data exists here by
default and does not exist in the other systems.

**Arm 3 — does structural context still pay on the second review?** `Review`
has a `parent_review` self-FK, plus `Thread`, `Comment`, and a memory-aware
re-review pipeline. c-CRAB does one review-then-revise loop. Nobody studies
round two. When the model has already seen the file, is retrieval still worth
its tokens? Unasked, and the schema for asking it already exists here.

### Working title

> **Smart context or just more context?** A budget-controlled study of retrieval
> strategies for automated code review, including the second round.

### The condition set

Every arm is capped at the same token budget T. That cap is the contribution.

**The honest arms** — all capped at the same budget T, all exposed to the agent
under the same tool name and the same payload shape, so the model cannot tell
which condition it is in:

| | Condition | Context | Kills the objection |
|---|---|---|---|
| **A** | none | diff only | is context worth anything? |
| **B** | graph retrieval @ T | ego-graph neighbours at depth *d* | the system under test |
| **C** | random @ T, type-matched to B | same tool shape | "any tool helps" |
| **D** | lexical @ T | name/grep-like matching | "grep would do the same" |
| **G** | **dense retrieval @ T** | embedding similarity | **"you only beat a strawman"** |

**The reference arms** — not competitors, reported separately:

| | Condition | Context | What it is for |
|---|---|---|---|
| **E** | whole file, unbounded | the entire touched file | what practitioners actually do |
| **F** | **oracle, unbounded** | the exact lines the ground truth points at | **the ceiling** |

**Why G was added.** Condition D alone is a weak opponent. AACR-Bench used
Qwen3-Embedding-8B, so a study that beats grep and never tests embeddings
invites one obvious rejection: *the baseline was a strawman*. G removes it.

**Why F was added, and it is the most valuable of the two.** F cheats on
purpose — it reads the benchmark's own answer key. It is standard practice as an
upper bound, and without it the numbers have no ceiling: a reader cannot tell
whether 30% recall is good or terrible. If the oracle scores 45%, **no
retrieval strategy can exceed 45%**, and the distance between the best honest
arm and 45% is the headroom the paper actually reports. F must never be
compared to the honest arms as if it were one; `REFERENCE_CONDITIONS` in
`experiments/config.py` marks it, and a test asserts no honest condition can
see `oracle_targets`.

**Rejected for now — H, issue/PR description text.** Every c-CRAB instance
already carries `problem_statement`, `body`, and `hints_text`, so testing
whether natural-language context beats code context costs only the LLM calls.
It is a genuinely open question and a good second paper. It is not this one.

Secondary: B at depth 1 / 2 / 3 (weaker now that LARGER published it first).
Secondary: per-agent attribution via `LLMUsage.step`, to test whether the
parallel agents add findings or add false positives.

**The matrix.** 9 cells per model (A, C, D, E, F, G, plus B at three depths)
× 2 model families = **18 cells × 339 tasks = 6,102 runs, ≈ $25.63**. One
model family alone is 3,051 runs at $19.77. Adding F and G cost $5.70 over the
five-condition design and removed the two objections most likely to sink the
paper.

**The dense embedder is a pinned choice, not a detail.** `hashing_embedder` in
`ToolOrganizer.py` is a deterministic character-ngram baseline so the condition
is runnable and testable offline; a real run injects a trained embedder through
`embed_fn`, and `RunMatrix.embedder` records which one produced the results.

### Language coverage — decided 27 Aug

Three different numbers were being conflated, so they are pinned here.

| | Languages | Note |
|---|---|---|
| The parser (`construct_graph.py`) | **4** — `.py` `.js` `.java` `.c` | what `LANGUAGE_MAP` actually holds |
| c-CRAB | **1** — Python | all 410 instances, verified |
| AACR-Bench | **10** — JS, Python, TS, Java, C#, C++, C, PHP, Go, Rust | |

**Decision: option 2 — test four languages.** c-CRAB carries the headline
result (Python, executable-test ground truth); AACR-Bench supplies the
multi-language check, restricted to the **four languages the parser can read**:
Python, JavaScript, Java, C. Their other six — TypeScript, C#, C++, PHP, Go,
Rust — are excluded, and the paper says so and says why.

**Rejected: option 3, extending to all ten.** Every one of the six missing
languages has a published tree-sitter package (`tree-sitter-go` 0.25.0,
`tree-sitter-rust` 0.24.2, `tree-sitter-typescript` 0.23.2, `tree-sitter-cpp`
0.23.4, `tree-sitter-php` 0.24.1, `tree-sitter-c-sharp` 0.23.5), so adding them
to `LANGUAGE_MAP` is trivial. Extraction is not: `construct_graph.py` carries
hand-written per-language queries for classes, functions, calls and variables,
and each new language needs its own written and tested. Roughly half a day
each — five days of plumbing that does not touch the research question.

**Rejected: option 1, Python only.** The README already advertises four
languages. Publishing a paper whose experiments cover one, while the tool
claims four, is a gap a reviewer would find.

### Ground truth — settled 27 Aug, and it moved twice

**What was planned:** score reviews against c-CRAB's reference review comments.

**Why that failed.** Reading the 477 comments showed they are not a defect list.
61% are multi-speaker threads including the author's replies, 17% point at test
files, and the content runs from *"This is wrong, please remove"* to *"API
question: do we want the default to be `weight`?"* and *"can you also replicate
the `.loc` case?"*. Scoring a reviewer against those measures agreement with
opinion. No reviewer could be expected to guess a design question.

**Why Docker was not the answer either.** c-CRAB published only **30** of the
339 instance images, which covers 29 tasks and 45 defects. At 45 the minimum
detectable effect is roughly 25 percentage points — nothing in this literature
is that large, so the strong endpoint would have measured nothing.

**What actually solved it.** `raw_results_compressed/testgen_combined.zip` in
the release had not been opened. For every comment it records the
`comment_type` the pipeline assigned — functional, style, documentation,
structural — and the result of running the generated test before and after the
fix: `before_passed`, `after_passed`, `success`. **519 comments are both
functional and verified fail-to-pass.** The verification was already run; the
verdicts are in the archive; no containers are needed.

**The answer key is therefore: functional AND test-verified.**

| | Defects | Tasks | Repos |
|---|---|---|---|
| All reference comments | 477 | 335 | 75 |
| Confirmed (functional + verified) | **340** | **259** | **72** |

The other 179 confirmed comments in the archive refer to comments the release's
own filter removed, so there is nothing to score them against.

**Join on comment text, never on index.** The released instances have had
`reference_review_comments` reduced to a retained subset, so the archive's
`comment_index` points into the original SWE-CARE list. Joining on index
silently dropped 198 confirmed defects and misattributed others.

**Minimum detectable effect moves from 6 points to 7.** That is the right
trade: a slightly blunter instrument aimed at demonstrated defects beats a
sharper one aimed at preferences.

**Stated honestly in Limitations:** the classifications and tests were produced
by GPT-5.2 inside the c-CRAB pipeline, so this is not purely human ground
truth. It is materially stronger than a purely model-labelled benchmark,
because every retained label is backed by an executed test that actually
flipped from failing to passing — a machine-checked fact rather than a model's
opinion.

### The connection constraint — measured 27 Aug

Five 60-second downloads on this machine returned between 232KB and 1.3MB, and
**every one timed out**. `Avaiga/taipy` is 153MB and stalled at 5.1MB. An
actual API reply arrived severed mid-JSON with `finish_reason: length` and one
output token, while still returning HTTP 200.

Two consequences, both now handled in code.

**Graphs are built sparsely.** `experiments/sparse.py` fetches only the files
the diff touches plus one import hop, over raw.githubusercontent: a 150MB
transfer becomes tens of kilobytes. scikit-learn resolved to 2 files and 77KB
in 32 seconds and produced a 609-node, 5,939-edge graph. **This belongs in the
paper's threats to validity**: condition B retrieves from the changed files and
their immediate imports, not from the whole repository. One import hop is kept
deliberately — cross-file structure is the only thing a graph offers over a
text search, and a graph of the diff alone would have no cross-file edges left
to test. `--full-repo` restores whole-repository graphs for anyone with the
bandwidth, and the paper should report which mode produced the numbers.

**Truncated replies are never scored.** A cut-off response scored naively
becomes "the reviewer found nothing", which puts a network failure into the
results. The client raises on a truncating `finish_reason`, and the review step
flags output that begins as JSON and fails to parse.

### The risk that had to be closed first — CLOSED 27 Aug

AACR-Bench was read. **It does not hold token budget constant.** Its setup says:

> *"for similarity-based retrieval methods, the number of retrieved code
> contexts was uniformly set to 3"*

They fix the **number of snippets**, not the token count — and their three
granularity arms (diff / file / repo) differ by an order of magnitude in size.
So the confound stands and Arm 1 survives. Their own sentence is the citation
for why the study is needed.

A second finding sharpens the position further. Their ground truth is 1,505
comments, of which **1,114 are model-generated** and 391 human-augmented, and
they concede:

> *"constructing a fully comprehensive Ground Truth remains a formidable
> challenge"*

**73% of AACR-Bench's ground truth is written by an LLM.** c-CRAB's executable
tests are strictly stronger evidence. The unoccupied intersection is therefore:
**a budget-controlled context study run on executable-test ground truth.**

| | AACR-Bench | c-CRAB | this paper |
|---|---|---|---|
| Budget held constant | no | n/a | **yes** |
| Ground truth | 73% LLM-generated | executable tests | executable tests |
| Studies context/retrieval | yes | no | **yes** |
| Cost per finding | no | no | **yes** |
| Second review round | no | no | **yes** |

### What the numbers allow — settled 27 Aug

**Statistical power, and the unit of analysis.** The conditions form a paired
design (every condition reviews the same PR), so the test is McNemar's.
Simulated at c-CRAB's 184 tasks with a 30% baseline, **the minimum detectable
lift at 80% power is 10 percentage points** — an 8-point effect reaches only
64% power and a 3-point effect 13%. That floor is too high: a real 6-point
benefit would come back as "no difference found", which is a false conclusion
rather than a null result.

**The fix is the unit of analysis, not more data.** A task is one pull request,
but each pull request contains several defects — c-CRAB has 234 tests across
184 instances, AACR-Bench 1,505 comments across 200 PRs. Scoring one row per
task throws that structure away:

| | per task (as first planned) | per finding (as revised) |
|---|---|---|
| what one row records | did the review find the bugs? | did the review find **this** bug? |
| rows | 184 | ~1,500 |
| minimum detectable lift | 10 points | **3 points** |
| LLM runs | 2,576 | 2,576 — unchanged |
| cost | $10.82 | $10.82 — unchanged |

Same experiment, same money, same runtime. Only what is written down changes.
Measured: n=184 → 10pp, n=250 → 8pp, n=384 → 7pp, n=700 → 5pp, n=1000 → 4pp,
n=1500 → 3pp (`experiments/power.py --n N`).

**Findings within a task are correlated**, so the analysis clusters standard
errors by task rather than pretending 1,500 rows are independent. The effective
sample sits between the two extremes: 3 points is the optimistic bound, 10 the
pessimistic one, and the paper reports the clustered estimate with its interval.

**At any n, results are reported as effect sizes with confidence intervals**,
never as a bare significance claim. "We could not detect an effect smaller than
X" is honest at every sample size; "graph retrieval does not help" would not be.

**Cost.** 18 matrix cells × 339 tasks = 6,102 runs, ~36.6M input and ~7.3M
output tokens, **≈ $25.63** across two providers; one provider alone is $19.77.
The second model family — the single largest generalisability objection —
costs **$5.86**. `experiments/config.py`.

**Retriever fidelity.** A negative result must be attributable to graph
retrieval as a technique, not to a private deviation in this code.
`tests/test_retriever_fidelity.py` checks the depth-k neighbourhood against
networkx's own shortest-path computation, so the retriever is provably a
correct ego-graph retrieval at radius k.

---

## Phases

### Phase 0 — Make it run — **DONE 27 Aug**, `c4bab1f`, `8208640`

Test suite repaired (33 errors → 0), tree-sitter API fixed so the graph builds
at all, Apache-2.0 LICENSE, NOTICE crediting RepoGraph, unified
`requirements-dev.txt`, CI workflow, `.env` tiering plus `scripts/check_env.py`.

### Phase 1 — The knobs — **DONE 27 Aug**, `7abda43`, `6f08cae`, `6aa6000`

Hop-bounded BFS with `max_depth`; seven conditions behind one tool name and one
payload shape; `ContextBudget`; the oracle ceiling fenced by
`REFERENCE_CONDITIONS` and a test asserting no honest arm can see
`oracle_targets`; a dense arm so the study is not only beating grep; the power
analysis; the pinned run matrix; and ego-graph fidelity checked against
networkx's own shortest-path computation.

### Phase 2 — Experiment harness — **DONE 27 Aug**, `5fa0a74` … `6936132`

`benchmark.py` (answer key), `matcher.py` (one row per defect, clustered by
task), `llm.py` (OpenRouter with per-call cost), `review.py` (prompt, parser,
truncation guards), `sparse.py` (graphs on a slow link), `repo.py`, `run.py`
(resumable), `metrics.py` (cluster bootstrap), `analyse.py` (+ LaTeX).
**455 tests pass.**

**Six defects the pilots found, each one in the thing the paper claims:**

1. **Budget parity was fake.** `ContextBudget` capped the entry list, not the
   delivered string, so B sent 6,897 characters against G's 3,209 — the exact
   confound this study attacks. The cap now applies to the serialised payload;
   spread is 0–4% of budget, and conditions differ in *entries kept* (41 for B,
   50 for D at 1500 tokens) rather than in text sent.
2. **The candidate cap was unequal by construction.** B was allowed 60
   candidates and D and G only 12, so the budget could never bind for them. One
   `candidate_cap` for every condition now.
3. **The prompt suppressed findings.** "Report only defects you can point at a
   line" and "do not report style preferences" read as an instruction to stay
   silent, and every condition returned `{"findings": []}`. Rewritten to state
   that humans found real problems here and to ask for best candidates rather
   than certainty: zero findings became twelve across three tasks.
4. **Three of five candidate models were broken**, not conservative.
   claude-3.5-haiku, gemini-2.0-flash and qwen-2.5-coder-32b returned
   `finish_reason: error` on every call. The matrix now runs
   `openai/gpt-4o-mini` and `meta-llama/llama-3.3-70b-instruct`, chosen by
   measurement. `ModelSpec.family` exists because both are reached through
   OpenRouter and what must differ is who trained the model, not who serves it.
5. **The wrong revision was fetched.** Sources came from `base_commit`, the
   branch point, so every file the pull request added was missing — the cause
   of the "no source files fetched" skips. `head_commit` is the reviewed
   revision and the instance id is named after it.
6. **The wrong diff was shown.** `merged_patch` is everything that eventually
   landed, so the model was asked to find defects in code the human reviewers
   never saw, while being scored against their comments.
   `commit_to_review.patch_to_review` is what they reviewed.

**Cost, measured rather than assumed: about $4 for the full two-model matrix**,
not the $25.63 previously budgeted.

### Phase 3 — Run it — **FIRST MODEL COMPLETE 28 Aug**

`runs/full-gpt4omini/` — 175 pull requests scored under all seven conditions,
218 confirmed defects, 1,718 reviews, **$1.43**, 0 parse failures. Budget
parity across the four competing arms: **6.4% spread**.

| | Condition | Context | Recall | 95% CI |
|---|---|---|---|---|
| A | none | 0 | 34.9% | [28.4, 41.6] |
| B | graph | 4,756 | 35.3% | [28.7, 42.1] |
| C | random | 5,019 | 34.4% | [28.0, 41.2] |
| D | lexical | 4,698 | 34.4% | [27.9, 40.9] |
| G | dense | 4,757 | 35.8% | [29.5, 42.4] |
| E | whole file (ref) | 102,459 | 35.8% | [29.2, 42.6] |
| F | **oracle** (ref) | 965 | 35.3% | [28.9, 42.1] |

**Every condition sits within 1.4 points of every other, and not one interval
excludes zero.** B vs D — the question the paper was built to ask — is +0.9%
[−3.1, +5.2].

**The result that reframes the paper is F.** The oracle is handed the graph
entities spanning the ground-truth defect location and still scores 35.3%
against no-context's 34.9%. It was verified working: on scikit-learn-9802 it
returns `BaseSGD`, its `__init__`, and the variables on the exact commented
line, and only 1% of its reviews got under 300 characters of context.

**Perfect retrieval does not help. The bottleneck is not context.** That
subsumes the budget question — there is no confound to remove between
strategies that are all equivalent to supplying nothing.

Two secondary findings:

- **Retrieval makes the reviewer quieter, not better.** Every budgeted arm
  reports fewer findings than the baseline (872–960 against 1,018) while
  hitting the same number of true defects.
- **Whole-file context costs 6.3x more per true finding** ($0.0094 against
  $0.0015) for +0.9 points, and three reviews failed outright because the file
  exceeded the model's context window.

Running now: `meta-llama/llama-3.3-70b-instruct` over the same tasks, to
establish whether the null generalises across model families. Then the depth
ablation.

**The paper's claim changes.** It was "at equal budget, does structural
retrieval beat lexical retrieval". The honest headline is now: **retrieval
context — of any kind, at any budget, up to and including the answer key —
does not measurably improve defect localisation for this model on this
benchmark.** That is a stronger and more useful contribution than the one we
set out to make, and it is exactly the kind of result the field's confounded
comparisons were hiding.

### Phase 4 — Write — **DRAFTED 28 Aug**

All eight sections drafted in `paper/draft/` and mirrored into the repository
at `paper/`: abstract, introduction, related work, method, results,
discussion, artifact, limitations. Every number traces to `results/`.

**Not done, and all of it needs you:**

- **Author block and affiliation.** Still blank. Needs the university name and
  department for the byline.
- **References in a bibliography format.** Currently inline arXiv numbers.
- **Figures.** None yet. A recall-by-condition plot with intervals, and a
  cost-per-finding plot, would carry the result better than the tables.
- **A read-through by a second person.** Nothing has been read by anyone but us.

### Phase 5 — Review, then publish

Unchanged and unstarted. The order still matters:

1. Read it once as a hostile reviewer.
2. Two or three real readers **before** anyone official.
3. Then Sheleme, with the draft in hand, for co-authorship — the order you
   chose, and it respects the line that matters: his name never goes public
   without his yes.
4. arXiv cs.SE only after 2 and 3.
5. Do not rush MSR. arXiv is what the applications need.

**One thing the result changes about Phase 5.** A replicated null with an
oracle ceiling is a more defensible paper than a positive result would have
been, and it is harder to attack: the obvious objections — bad retriever,
wrong radius, too small a budget — are each closed by an arm in the design.
But a null result is also easier for a reader to dismiss without engaging. The
abstract has to lead with the oracle, because that is the sentence that stops
someone scrolling past.

## Rules for this project

1. Nothing is "fixed" without a test.
2. Nothing merges without CI green.
3. Every number in the paper traces to a file in `results/`.
4. Nothing is published until a qualified human has read it and said yes.
5. The repository history is what it is. The paper stands on the code and the
   experiments, both of which are real and both of which are yours.
