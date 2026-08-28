# Introduction

Large language models are increasingly deployed as automated code reviewers, and
a consistent finding in recent work is that supplying repository context
improves them. AACR-Bench reports that "context granularity, retrieval methods,
LLM type, programming language, and architecture paradigm significantly
influence performance". Systems built on repository-level code graphs report
gains over context-free baselines.

These comparisons share a property that makes them difficult to interpret:
**the amount of context is not held constant.** AACR-Bench fixes the *number* of
retrieved snippets — "for similarity-based retrieval methods, the number of
retrieved code contexts was uniformly set to 3" — while its granularity arms
span diff, file, and repository, differing by an order of magnitude in length.
A gain attributed to better context is therefore inseparable from a gain caused
by more text. Evidence from code completion suggests this matters: one
controlled study finds that doubling the context budget yields up to 4.2 points
while swapping the retriever moves performance by at most 1.11.

We set out to separate the two for code review, by comparing retrieval
strategies at a fixed token budget on ground truth that is machine-verified
rather than annotated.

**We did not find what we expected to find.** Across two model families, seven
context conditions, three graph depths, 390 scored pull requests and over 3,000
reviews, no form of retrieved context measurably improved defect localisation.
Graph retrieval did not beat lexical retrieval. Neither beat supplying no
context at all. Supplying the entire contents of every changed file — a hundred
times the budget — did not help, and cost 6.3 times more per true finding.

The result that constrains all the others is the oracle. We included a condition
that reads the benchmark's own answer key and returns the code entities spanning
the ground-truth defect location: perfect retrieval, by construction, as a
ceiling. **It performed within one point of supplying nothing, on both models.**

Perfect context does not help. The bottleneck is not retrieval. Either the model
recognises the defect from the diff or it does not, and what surrounds that diff
appears not to change the outcome.

This subsumes the question we set out to ask. There is no confound to remove
between strategies that are all equivalent to supplying nothing — and it
suggests that gains attributed to context in prior work deserve re-examination
against a no-context baseline at matched budget.

## Contributions

1. **A budget-controlled comparison of retrieval strategies for code review.**
   Parity is enforced on the serialised payload the model receives, verified at
   6.0–6.4% spread across arms, with an accompanying test that fails if it
   drifts.
2. **An oracle ceiling**, which we believe has not been reported for this task,
   and which we argue should be standard: it distinguishes "retrieval is
   imperfect" from "retrieval is irrelevant".
3. **A replicated null across two model families**, with effect sizes and
   confidence intervals rather than significance verdicts, and an explicit
   statement of the minimum detectable effect.
4. **Cost per true finding** alongside accuracy, showing whole-file context to
   be 6.3× more expensive for no measurable benefit.
5. **A reusable harness and frozen results**, with every reported number
   traceable to a committed file.
