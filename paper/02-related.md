# Related work

## Repository-level context for code review

**AACR-Bench** (arXiv:2601.19494) is the closest work. It evaluates automated
code review with cross-file context across ten languages and reports that
"context granularity, retrieval methods, LLM type, programming language, and
architecture paradigm significantly influence performance". Two properties
motivate the present study.

First, it does not hold input size constant. Its setup fixes the *number* of
retrieved snippets — "for similarity-based retrieval methods, the number of
retrieved code contexts was uniformly set to 3" — while its granularity arms
(diff, file, repository) differ by an order of magnitude in length. A gain
attributed to richer context is therefore inseparable from a gain caused by
more text.

Second, 1,114 of its 1,505 ground-truth comments are model-generated, and the
authors state that "constructing a fully comprehensive Ground Truth remains a
formidable challenge".

**LAURA** (arXiv:2512.01356) augments review generation with retrieved
exemplars and reports gains over prior work, again without equalising context
length.

## Executable ground truth

**c-CRAB** (arXiv:2603.23448) converts human review comments into tests that
fail before the fix and pass after, and evaluates whether a review guides a
coding agent to a passing patch. It reports that current agents solve roughly
40% of its tasks. c-CRAB supplies evidence but does not study retrieval: it
evaluates finished products, not context strategies. We take its verified
labels and ask the question it does not.

## Graph retrieval over repositories

**RepoGraph** (arXiv:2410.14684, ICLR 2025) builds a repository-level code graph
and retrieves ego-graphs around matched entities; our graph service is derived
from it. **LARGER** (arXiv:2605.16352) extends graph exploration with lexical
anchoring and reports hop-depth ablations against RepoGraph and CodeXGraph.
**GraphCoder** (ASE 2024) uses a code context graph for completion.

These target issue resolution, localisation, and completion. None studies code
review, and none equalises the token budget across retrieval strategies.

## Cheap baselines

**GrepRAG** (arXiv:2601.23254) studies grep-like retrieval for code completion
and finds it competitive with graph approaches at lower latency. A controlled
chunking study (arXiv:2605.04763) varies the context budget for completion and
reports that doubling it yields up to 4.2 points while swapping the retriever
moves performance by at most 1.11 — evidence that *quantity* dominates
*strategy* when quantity is free to vary.

Both are completion, not review. The present study is the review analogue.

## Model choice and multi-agent review

A comparative evaluation (arXiv:2606.15689) finds that combining models lowers
F1 — 0.365 alone against 0.333 in ensemble — because "the models largely detect
the same bugs; adding a second model introduces its false positives without
meaningfully increasing true positives". **CodeX-Verify** (arXiv:2511.16708)
tests all 15 combinations of four specialised agents and reports negative
marginal contributions for three of them.

Both motivate reporting model family as a factor rather than assuming results
transfer.

## Position of this work

| | AACR-Bench | c-CRAB | LARGER | This work |
|---|---|---|---|---|
| Task | review | review | localisation | review |
| Studies retrieval strategy | ✓ | ✗ | ✓ | ✓ |
| Token budget held constant | ✗ | n/a | ✗ | **✓** |
| Ground truth | 73% model-generated | executed tests | — | executed tests |
| Cost per true finding | ✗ | ✗ | ✗ | **✓** |

We contribute the budget-controlled comparison, on executed-test ground truth,
with cost per true finding reported alongside accuracy.
