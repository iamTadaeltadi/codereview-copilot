# Limitations and threats to validity

## The graph is sparse, not repository-wide

Graphs were built from the files each diff touches plus one import hop, not
from whole repositories. This was forced by bandwidth: measured on the machine
used for this study, five 60-second downloads returned between 232KB and 1.3MB
and every one timed out, and a 153MB repository stalled at 5.1MB.

**This is the most serious threat to the central claim.** Condition B retrieves
from a neighbourhood rather than from everything, so our result speaks to
retrieval over changed files and their immediate imports. One import hop is
retained deliberately, because cross-file structure is the only thing a graph
offers over a text search and a graph of the diff alone would have no cross-file
edges left to compare. The implementation supports whole-repository graphs
(`--full-repo`), and replicating on a faster connection is the obvious next
step.

## Ground truth is partly model-generated

The comment classifications and the executable tests come from GPT-5.2 inside
the c-CRAB pipeline. This is not purely human ground truth.

It is materially stronger than a purely model-labelled benchmark: every retained
label is backed by a test that was **executed** and observed to fail before the
fix and pass after. That is a machine-checked fact rather than a model's
opinion, and it is a higher bar than AACR-Bench, where 1,114 of 1,505 ground
truth comments are model-generated and the authors concede that "constructing a
fully comprehensive Ground Truth remains a formidable challenge".

Residual risk: the classifier may systematically mislabel some defect classes,
and the generated tests may verify something adjacent to what the reviewer meant.

## Localisation, not resolution

We measure whether a review points at the file and line of a demonstrated
defect. We do not measure whether acting on the review fixes it. c-CRAB's own
endpoint is resolution, which requires per-instance containers; only 30 of the
339 images are published, covering 45 defects, at which size the minimum
detectable effect is roughly 25 points. Localisation is the weaker endpoint and
we report it as such.

## Single language in practice

The parser reads four languages, but c-CRAB's instances are Python-only, so the
cross-language claim is not tested here. Extending to AACR-Bench's ten languages
would cover four of them without new extraction rules.

## Statistical power

The minimum detectable lift at 80% power is approximately 7 percentage points.
A real benefit smaller than that would be reported as not distinguishable. This
cuts both ways and is why no null result here is stated as "no difference".

## Matching tolerance

A finding matches a defect within 5 lines in the same file. Too tight
under-counts reviews that identify the right problem at a neighbouring line; too
loose credits a review for finding something else nearby. The tolerance is a
parameter and results at other values should be reported.

## Author of the system under test

The graph retrieval implementation is our own. A negative result must therefore
be attributable to graph retrieval as a technique rather than to a private
deviation. The retriever's ego-graph semantics are verified against networkx's
own shortest-path computation: the depth-*k* neighbourhood is exactly the set of
nodes within *k* undirected hops, and each reported depth is the true
shortest-path length.

## Single gateway

Both model families are reached through OpenRouter, which routes to backends we
cannot observe. Model strings and generation settings are recorded with each
run.
