# Smart context or just more context?

## Abstract

Recent work reports that supplying repository context improves LLM-based code
review. These comparisons do not hold the amount of context constant: published
setups fix the number of retrieved snippets while varying granularity from diff
to whole repository, so gains attributed to better context are inseparable from
gains caused by more text.

We compare retrieval strategies for code review at a fixed token budget, on
ground truth restricted to defects that are both classified as functional and
demonstrated by an executed test that failed before the fix and passed after
(291 defects, 221 pull requests, 67 repositories). Budget parity is enforced on
the payload the model receives and verified at 6.0–6.4% spread across arms.

Across two model families, seven context conditions, three graph depths and
over 3,000 reviews, **no form of retrieved context measurably improved defect
localisation.** Graph retrieval did not beat lexical retrieval (+0.9% [−3.1,
+5.2] and +1.4% [−4.0, +6.8]); neither beat supplying no context. Supplying
entire changed files — a hundred times the budget — did not help and cost 6.3×
more per true finding.

Most constraining, an oracle condition supplied with the code entities spanning
the ground-truth defect location scored within one point of supplying nothing on
both models. Perfect retrieval does not help: the bottleneck is not context.

We also observe that retrieval makes reviewers **quieter without making them
more accurate** — up to 30% fewer findings reported for no change in true
defects found.

We release the harness, the frozen results, and the analysis.
