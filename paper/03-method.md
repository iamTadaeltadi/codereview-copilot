# Method

## Research question

Published results showing that repository context improves LLM code review do
not hold the amount of context constant. AACR-Bench fixes the *number* of
retrieved snippets — "for similarity-based retrieval methods, the number of
retrieved code contexts was uniformly set to 3" — while its granularity arms
(diff, file, repository) differ by an order of magnitude in size. The reported
benefit of richer context is therefore inseparable from the benefit of *more
text*.

We ask: **at a fixed token budget, does structural retrieval outperform cheap
lexical retrieval, or no retrieval at all, for automated code review?**

## Conditions

Seven conditions. Five are budget-matched and directly comparable; two are
reference points reported separately.

| | Condition | Context supplied | Budgeted |
|---|---|---|---|
| A | none | the diff only | — |
| B | graph retrieval | ego-graph neighbourhood at depth *d* | ✓ |
| C | random | nodes sampled to match B's node-type mix, seeded | ✓ |
| D | lexical | identifier-overlap ranking | ✓ |
| G | dense | embedding cosine similarity | ✓ |
| E | whole file | complete text of every file the diff touches | ✗ |
| F | oracle | the entities covering the ground-truth locations | ✗ |

All budgeted conditions expose a tool with the **same name** (`retrieve_graph`),
the **same signature**, and the **same payload shape**, so the model cannot
identify which condition it is in. The prompt differs across conditions in
exactly one respect: whether it mentions a retrieval tool. Conditions A and E
receive a separately written prompt rather than the tool prompt with a sentence
removed, because a prompt containing a dangling reference to a tool that does
not exist is a different prompt, not a control.

F consumes the benchmark's answer key and therefore cheats by construction. It
establishes the ceiling: no retrieval strategy can exceed it, and the distance
between the best honest arm and F is the headroom. It is fenced in code —
`REFERENCE_CONDITIONS` marks it, and a test asserts that no honest condition can
observe `oracle_targets` regardless of what is passed to the tool factory.

## Budget parity

Parity is enforced on the **serialised payload the model receives**, not on the
list of entries inside it. An earlier implementation budgeted the entry list;
because each condition wraps its entries differently and the graph arm's
entries carry additional fields, an identical entry budget still delivered the
graph arm roughly twice the text of the dense arm — reproducing precisely the
confound this study exists to remove.

Entries are dropped from the end until the whole serialised string fits.
Measured across budgets of 300, 800 and 1500 tokens the spread between
conditions is 0–4% of budget. Conditions consequently differ in **how many
entries fit**, not in how much text is sent: at 1500 tokens the graph arm fits
41 entries where the lexical arm fits 50.

Every condition also shares one candidate cap. An earlier version allowed the
graph arm 60 candidates and the others 12, so the budget could never bind for
the others; they exhausted their candidates first.

## Ground truth

We use c-CRAB (arXiv:2603.23448, CC BY 4.0), whose instances are pull requests
with human review comments. Raw comments are **not** a defect list: 61% are
multi-speaker threads including the author's replies, 17% point at test files,
and the content ranges from "This is wrong, please remove" to "API question: do
we want the default to be `weight`?".

The c-CRAB release records, for every comment, a type assigned by its pipeline
(functional, style, documentation, structural) and the result of executing a
generated test before and after the fix. We retain only comments that are
**functional and whose test failed before the fix and passed after** — a
machine-checked demonstration that the defect is real.

We further restrict to defects located in files the parser reads (`.py`, `.js`,
`.java`, `.c`). A defect in a `.rst` page or a `.yaml` configuration cannot be
reached by any retrieval condition, so scoring it charges every arm with a miss
it had no means of avoiding.

**Study population: 291 confirmed defects across 221 pull requests and 67
repositories.**

## Unit of analysis

The unit is the **defect**, not the task. Each pull request contains several
defects, and recording one verdict per task discards that structure: a review
that finds two of three defects becomes a single yes or no. Scoring per task
raises the minimum detectable effect from roughly 5 points to 10, which would
report a real 6-point benefit as no difference.

Every ground-truth defect produces exactly one outcome row per condition, hit or
miss, and every reported finding matching no defect is counted as a false
positive. A finding is matched to the nearest unconsumed defect in the same file
within a line tolerance of 5; one finding cannot satisfy two defects.

## Statistics

Defects within a task are correlated — a review that understands a pull request
tends to find all of its defects, and one that does not tends to find none —
so all intervals come from a **cluster bootstrap resampling whole tasks**.
Paired comparisons use McNemar's test on discordant pairs, since every condition
reviews the same pull request.

At this sample size the minimum detectable lift at 80% power is approximately 7
percentage points. **Results are reported as effect sizes with confidence
intervals, never as bare significance verdicts.** Where an interval spans zero
we report that the difference is not distinguishable at this sample size, which
is a different and weaker claim than reporting no difference.

Only tasks scored under every condition enter a comparison; a task whose sources
fail to fetch in one arm is excluded from all.

## Implementation

Reviews were generated through OpenRouter. Model selection was empirical: five
candidates were run against identical tasks and prompts, and
`anthropic/claude-3.5-haiku`, `google/gemini-2.0-flash-001` and
`qwen/qwen-2.5-coder-32b-instruct` returned `finish_reason: error` on every
call. We report `openai/gpt-4o-mini` and `meta-llama/llama-3.3-70b-instruct`,
two distinct model families.

Truncated replies are never scored. A cut-off response still returns HTTP 200,
and scoring one naively records a network failure as "the reviewer found
nothing".

Graphs are constructed with tree-sitter and networkx, adapting RepoGraph
(arXiv:2410.14684, Apache-2.0; see NOTICE).
