# Audit of the retrieval comparison

Prompted by a review arguing that "additional context helps by 9 points" and
"which code does not matter" cannot both be concluded from the same run. Three
analyses. Two of the review's objections are refuted by the data; the third is
correct and withdraws a claim.

## Refuted — the gain is not a response-policy effect

The concern: adding context makes the model report more findings, so it hits
the ground truth more often by guessing more.

| Condition | Exactly right | Findings/review | Confirmed FP/review |
|---|---|---|---|
| diff only | 37% | **2.42** | **1.29** |
| graph | 46% | 2.09 | 1.06 |
| random | 46% | 2.07 | 1.05 |
| lexical | 46% | 2.07 | 1.06 |
| dense | 49% | 2.03 | 1.00 |

Context conditions report **fewer** findings and **fewer** false positives while
scoring higher. The opposite of guessing more.

## Refuted — equal marginals are not hiding different behaviour

The concern: two conditions can score 46% while succeeding on disjoint sets.

|  | random right | random wrong |
|---|---|---|
| **graph right** | 76 | 4 |
| **graph wrong** | 5 | 90 |

**9 discordant pairs out of 175.** They agree on 95% of tasks. Not disjoint —
nearly identical.

## Correct, and it withdraws a claim — the retrievers did not separate

The concern: before concluding that retrieval quality does not matter, show
that the retrievers differ in retrieval quality.

Evidence recall — did the retriever return the file the defect depends on,
measured on 36 tasks where that file is in the pool:

| Retriever | Evidence recall |
|---|---|
| graph | **61%** |
| random | **83%** |
| lexical | 89% |
| dense | 78% |

**Random retrieves the needed file more often than the graph.** So equal
downstream accuracy cannot support "which code does not matter" — the
conditions were never separated on the variable that claim is about.

### Why random performs so well here

The pool it samples from is small: a median of **12 files** per task, and the
budget returns up to **80 nodes**. Sampling 80 nodes from a graph spanning a
dozen files is not a sample of unrelated code — it is most of the pool.

`random` was never a relevance control in this setup. It is closer to "return
much of what is available", which is why its evidence recall is high and its
accuracy matches targeted retrieval.

## What is withdrawn

> "Which code is retrieved does not matter."

Not supported. The retrievers did not differ in retrieval quality in the
direction the claim assumes, and the one labelled random was not irrelevant.

## What still stands

- **Additional context raises detection from 37% to 46%**, with fewer findings
  and fewer false positives — not a response-policy artifact.
- **Explicit dependency structure adds nothing**, replicated across two model
  families and three serialisations, with a comprehension probe passed 50/50.
  That experiment supplies the evidence set directly and never retrieves, so
  none of the above touches it.

## What a valid relevance control requires

Random drawn from **outside** the pool — another repository entirely — so that
it cannot accidentally contain the evidence. And evidence recall reported
alongside accuracy for every retrieval arm, so that a null in accuracy can be
attributed rather than assumed.
