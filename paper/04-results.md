# Results

## Model 1: `openai/gpt-4o-mini`

175 pull requests scored under every condition; 218 confirmed defects.
Budget parity across the four competing arms: **6.4% spread**.

| | Condition | Context | Recall | 95% CI | \$/finding |
|---|---|---|---|---|---|
| A | none | 0 | 34.9% | [28.4, 41.6] | 0.0015 |
| B | graph | 4,756 | 35.3% | [28.7, 42.1] | 0.0018 |
| C | random | 5,019 | 34.4% | [28.0, 41.2] | 0.0016 |
| D | lexical | 4,698 | 34.4% | [27.9, 40.9] | 0.0016 |
| G | dense | 4,757 | 35.8% | [29.5, 42.4] | 0.0016 |
| E | whole file *(ref)* | 102,459 | 35.8% | [29.2, 42.6] | 0.0094 |
| F | **oracle** *(ref)* | 965 | 35.3% | [28.9, 42.1] | 0.0011 |

**Every condition falls within 1.4 percentage points of every other.**

| Comparison | Difference | 95% CI |
|---|---|---|
| B vs A (graph vs none) | +0.5% | [−3.9, +4.9] |
| D vs A (lexical vs none) | −0.5% | [−4.5, +3.5] |
| G vs A (dense vs none) | +0.9% | [−3.7, +5.5] |
| E vs A (whole file vs none) | +0.9% | [−5.0, +6.9] |
| **F vs A (oracle vs none)** | **+0.5%** | **[−3.2, +4.2]** |
| **B vs D (graph vs lexical)** | **+0.9%** | **[−3.1, +5.2]** |

Not one interval excludes zero. At this sample size the minimum detectable
lift is roughly 7 points, so we report these as **not distinguishable**, not as
demonstrated equality.

## The oracle result

The finding that constrains every other one is **F**. Condition F is handed the
graph entities that span the ground-truth defect location — the class, function
and variables on the exact line the human reviewer commented on. It cheats by
construction and exists to establish the ceiling.

**It scores 35.3% against no-context's 34.9%.**

We verified F is functioning: on `scikit-learn-9802`, whose confirmed defect is
at `sklearn/linear_model/stochastic_gradient.py:53`, F returns the `BaseSGD`
class, its `__init__`, and the variables declared at that line. Only 1% of F's
reviews received a context under 300 characters.

Perfect retrieval, therefore, does not help. **The bottleneck is not context.**
Either the model recognises the defect from the diff or it does not, and
supplying the surrounding code — whether structurally selected, lexically
selected, embedding-selected, randomly selected, exhaustively supplied, or
selected using the answer key — does not change the outcome.

This subsumes the budget question we set out to ask. There is no confound to
remove between strategies that are all equivalent to supplying nothing.

## Context reduces reported findings

| Condition | Findings reported |
|---|---|
| A none | 1,018 |
| E whole file | 1,027 |
| B graph | 960 |
| G dense | 944 |
| D lexical | 929 |
| F oracle | 880 |
| C random | 872 |

Every budgeted retrieval arm reports **fewer** findings than the no-context
baseline while hitting the same number of true defects. Retrieval makes this
reviewer quieter without making it more accurate.

## Cost

| Condition | \$ per true finding | Relative |
|---|---|---|
| F oracle | 0.0011 | 0.7× |
| A none | 0.0015 | 1.0× |
| D, G, C | 0.0016 | 1.1× |
| B graph | 0.0018 | 1.2× |
| **E whole file** | **0.0094** | **6.3×** |

Supplying whole files costs **six times more per true finding** than supplying
nothing, for a difference of 0.9 points with an interval spanning zero. Three
of E's reviews failed outright with HTTP 400 because the file exceeded the
model's context window — a limitation of the approach, not of the measurement.

Total experiment cost: **$1.43** for 1,718 scored reviews.

## Reliability

0 parse failures across all 1,718 reviews. 13 replies (1.4%) arrived truncated
and were excluded rather than scored as empty; without that guard they would
have entered the results as false zeros.


## Model 2: `meta-llama/llama-3.3-70b-instruct`

The same 175 pull requests, 215 confirmed defects, six conditions. Budget
parity: **6.0% spread**.

| | Condition | Recall | 95% CI |
|---|---|---|---|
| A | none | **47.0%** | [40.1, 54.2] |
| B | graph | 46.0% | [39.0, 53.3] |
| C | random | 41.9% | [34.7, 49.1] |
| D | lexical | 44.7% | [37.3, 51.7] |
| G | dense | 43.3% | [36.1, 50.5] |
| F | oracle *(ref)* | 47.9% | [40.7, 54.8] |

Llama localises defects considerably better in absolute terms — 47.0% against
gpt-4o-mini's 34.9% — and the pattern is unchanged. **No retrieval arm
separates from the baseline**, every interval spans zero, and the oracle sits
0.9 points from supplying nothing.

| Comparison | gpt-4o-mini | llama-3.3-70b |
|---|---|---|
| B vs A | +0.5% [−3.9, +4.9] | −0.9% [−6.5, +4.3] |
| D vs A | −0.5% [−4.5, +3.5] | −2.3% [−7.9, +3.2] |
| G vs A | +0.9% [−3.7, +5.5] | −3.7% [−8.3, +0.9] |
| **F vs A** | **+0.5% [−3.2, +4.2]** | **+0.9% [−3.6, +5.4]** |
| **B vs D** | **+0.9% [−3.1, +5.2]** | **+1.4% [−4.0, +6.8]** |

**The null replicates across two model families.**

The quieting effect is larger on llama: 927 findings reported with no context
against 658 with graph context and 642 with dense — a 30% reduction in what the
reviewer says, for no change in what it finds.

## Depth ablation

Condition B at hop depths 1, 2 and 3, over 241 defects scored at every depth.

| Condition | Recall | 95% CI |
|---|---|---|
| A none | 33.2% | [26.9, 40.1] |
| B @ depth 1 | 37.3% | [30.9, 43.7] |
| B @ depth 2 | 34.0% | [27.9, 40.6] |
| B @ depth 3 | 37.3% | [30.9, 43.8] |

**No trend with depth.** One hop and three hops score identically; two hops
lands below both. B@3 vs B@1 is +0.0% [−3.4, +3.4].

This closes the obvious objection to the main result — that the graph arm was
configured at the wrong radius. It was not: no radius helps.

## Summary

Across two model families, seven context conditions, three graph depths, 390
scored pull requests and 3,000+ reviews at a total cost of **$2.24**:

**No form of retrieved context measurably improves defect localisation — not
graph retrieval, not lexical retrieval, not dense retrieval, not whole files,
and not the answer key itself.**
