# Research plan v2 — Structure or Content?

Written 28 August 2026. Supersedes `ARCHIVE-plan-v1-superseded.md`, which was
organised around a claim that does not survive scrutiny.

Repository: `~/Desktop/education stff/canada-2027/capstone/codereview-copilot`
Branch `main`, 30 commits ahead of origin, 450 tests passing.

---

## 1. Why this plan replaces the last one

An external review, checked against the sources, found two errors in the v1
position. Both are real and both were mine.

### 1.1 Anchor location is not evidence location

v1 argued:

> GitHub forbids a review comment on an unmodified file → mined benchmarks
> cannot contain defects requiring unmodified files → those benchmarks cannot
> test repository context.

The first step is true. **The second does not follow.** A reviewer can attach a
comment to the *changed* line and say "this breaks callers that catch
`TypeError`". The comment sits in the changed file; the evidence proving it
lives elsewhere.

**Our own generated benchmark demonstrates the error.** Every mutation is
applied to a changed line, and every one requires another file to recognise.
So a defect on a changed line can absolutely require cross-file context, and
the v1 inference from "213/218 sit on changed lines" to "already visible to the
reviewer" is invalid.

Three concepts were being treated as one:

| | |
|---|---|
| **Anchor location** | where a human attached the review comment |
| **Fault location** | which changed line introduced the defect |
| **Evidence location** | which code proves the change is wrong |

v1 measured anchor/fault location and drew conclusions about evidence location.

### 1.2 Condition F is a fault-location oracle, not an evidence oracle

`build_oracle_context_tool` returns the graph entities whose line range spans
the ground-truth defect line — the class, the function, the variables **at the
fault site**. It supplies more of what the model could already see.

So "F performs like A" means only: *enlarging the already-visible fault site
does not help.* It does **not** mean *no useful repository context exists*,
which is what v1's headline claimed. The strongest result in v1 rests on a
mislabelled condition.

**Immediate action:** rename to `fault_location_oracle` in code and results.

### 1.3 The novelty claim was also wrong

v1 said benchmark construction "has never been examined". Verified against the
paper: **AACR-Bench already annotates every issue by required context level.**

| Level | Definition (their words) | Count |
|---|---|---|
| Diff | "can be provided by looking solely at the current diff hunk" | 754 |
| File | "require the context of the entire file containing the diff hunk" | 518 |
| Repo | "require repository-wide context, including PR metadata and the contents of other files" | 233 |

They also compare No-context / BM25 / Embedding / Agent **stratified by level**.
The space is crowded: CodeFuse-CR-Bench (601 instances, 70 projects),
SWR-Bench (1,000 verified PRs), c-CRAB, Magistrate.

---

## 1.5 Two results that arrived after this plan was written

Both blocking items ran. Both changed what the study says.

### The random control removes the relevance reading

Condition C had run on the cross-file benchmark and had never been scored. 176
tasks under all seven conditions, strict measure:

| | Condition | Context | Exactly right | vs no context |
|---|---|---|---|---|
| A | none | 0 | 36% | — |
| B | graph | 3,603 | 43% | +6.8% [+2.3, +11.4] |
| **C** | **random** | 3,806 | **46%** | **+9.7% [+4.5, +14.8]** |
| D | lexical | 4,631 | 44% | +7.4% [+2.8, +12.5] |
| F | fault-loc oracle | 591 | 43% | +6.8% [+2.8, +11.4] |
| G | dense | 4,767 | 43% | +6.2% [+1.7, +11.4] |
| E | whole file | 55,850 | 36% | +0.0% |

**Random context scores highest.** Against random at the same budget: graph
−2.8% [−5.7, +0.0], lexical −2.3% [−5.1, +0.0], dense −3.4% [−6.8, −0.6] with
the interval excluding zero.

So the +7 points is real and **is not caused by relevance**. Every strategy
beats no context; none beats random selection from the same repository; the
strategy targeting the actual dependency does not beat the one ignoring it.

The effect is not monotonic in volume either, which rules out the simplest
alternative: 0 chars → 36%, 591 → 43%, 3,806 → 46%, 55,850 → 36%. A moderate
amount of repository code of any kind helps. None does not. Fifteen times as
much stops helping.

**This makes §4 the only remaining version of the question.** If relevance is
undetectable, whether *representing relationships among* relevant evidence
helps is what is left to ask.

### The agent's zero tool calls were behaviour, not breakage

Same model, same tools, same repository, same diff; one sentence of framing
varies. 40 paired tasks:

| Arm | Searched at all | Reached the caller | Mean tool calls |
|---|---|---|---|
| NEUTRAL — the review prompt | **0 / 40** | 0% | 0.00 |
| PRIMED — "the defect is in another file" | **40 / 40** | 20% | 2.83 |

`+100% [+100%, +100%]` on searching. Perfect separation.

The tools fire when the model decides they are needed, and on a diff that looks
locally correct it never decides that. **Two failure stages, and only the second
is in the literature:** a *retrieval gap* — even primed, it reached the caller
on 20% of tasks — preceded by a **trigger gap** that prior work cannot observe,
because SWE-bench and Terminal-Bench agents are handed an issue or a failing
test. Code review has no such signal.

This is one small model on 40 generated tasks. It is reported as such, and it
is no longer a candidate for deletion — it is a separate, narrow, supported
result.

---

## 1.6 The core experiment has run, on three serialisations

§4's pre-registered comparison executed under all three encodings the plan
required. Same snippets, same canonical order, same formatting; only the
metadata block differs, and prompt lengths across arms 2–6 sit within nine
characters of each other.

| Arm | flat (n=84) | tag (n=179) | prose (n=166) |
|---|---|---|---|
| 1 — diff only | 42% | 37% | 36% |
| 2 — scrambled control | 42% | 39% | 39% |
| **3 — topology** | 38% | 40% | 36% |
| 4 — typed | 44% | 37% | 36% |
| 5 — attributed | 44% | 38% | 37% |
| **6 — corrupted** | 43% | **29%** | 33% |
| 7 — random evidence | **45%** | **40%** | **41%** |

### Primary — correct structure against the control

| | Effect | 95% CI | |
|---|---|---|---|
| flat | −3.6% | [−9.5, +2.4] | spans zero |
| tag | +1.1% | [−2.8, +5.0] | spans zero |
| prose | −3.0% | [−7.8, +1.8] | spans zero |

**Stating the true relationships does not help, under any encoding.**

### Secondary — corrupted structure against the control

| | Effect | 95% CI | |
|---|---|---|---|
| flat | +1.2% | [−4.8, +7.1] | spans zero |
| **tag** | **−9.5%** | **[−15.1, −3.9]** | **excludes zero** |
| prose | −5.4% | [−10.8, +0.0] | boundary |

**Stating false ones costs 9.5 points under the tag encoding.**

### The asymmetry is the result

A model that ignored the metadata could not be harmed by corrupting it. So it
is being read — and the manipulation check confirms it directly:

| Arm | Read the relation back correctly |
|---|---|
| topology / typed / attributed | **50 / 50** |
| corrupted | faithfully reports the *wrong* endpoint |
| scrambled control | 1 / 13 ✓ correctly carries nothing |

**The dependency information is parsed, provides no benefit when true, and
misleads when false.** That is a sharper claim than either "structure helps" or
"structure is inert", and it is available only because both directions were
measured.

### Why three encodings mattered

Reported under flat alone the conclusion would have been *structure is inert*.
Under tag alone, *structure matters and corruption is dangerous*. Both would
have been claims about the format rather than about structure. GraphSOS and
GraphDO warned that serialisation carries its own effect; this is that warning
arriving in our own data.

### And the relevance result replicates

Random evidence scores highest under all three encodings — 45%, 40%, 41% —
matching §1.5, where random repository code beat targeted retrieval.

### The second model family — and a correction to §1.5

160 paired tasks on llama-3.3-70b, tag encoding, identical tasks and arms.

| Comparison | gpt-4o-mini | llama-3.3-70b |
|---|---|---|
| **correct structure vs control** | +1.1% [−2.8, +5.0] | +0.6% [−3.7, +5.0] |
| corrupted vs control | **−9.5%** [−15.1, −3.9] | −3.1% [−8.1, +1.9] |
| evidence vs diff only | +1.1% [−4.5, +6.7] | **+24.4%** [+16.9, +31.9] |
| real evidence vs random | −1.1% [−7.3, +5.0] | **+16.9%** [+10.6, +23.7] |

**The primary comparison replicates.** Correct structural metadata does not
improve defect detection, on either model family, under any of three
serialisations. That is the result the study was built to produce, and it
holds.

**§1.5's relevance claim does not replicate, and is withdrawn in that form.**
The cross-file run reported that which code is retrieved does not matter,
because random repository code scored highest. On llama the evidence set is
worth **24.4 points** over the diff alone, and real evidence beats random by
**16.9**, both intervals excluding zero.

So *"retrieval relevance is undetectable"* was a claim about gpt-4o-mini, not
about code review. What the two models share is narrower and is what the paper
carries:

> **Relevant context can matter a great deal. Stating the relationships among
> that context adds nothing on top of it.**

The corruption effect inverts between them — significant for the model that
ignores the evidence, absent for the one that uses it. Worth reporting, not yet
worth explaining.

**Third correction in this project.** The discipline is unchanged: when a
measurement contradicts a claim, the measurement wins.

---

## 1.7 Phase B — the measurement §1.1 should have made

The withdrawn claim reasoned from *where comments sit* to *what they need*.
Those are different, and now both are measured on the same 291 confirmed
defects.

| | Count | |
|---|---|---|
| anchored in a file the pull request changed | 291 | **100%** |
| anchored on a line the pull request changed | 213 | 98% |
| **refer to something outside the diff — strict** | **97** | **33%** |
| refer to something outside the diff — loose | 146 | 50% |

**Anchoring is near-total. Evidence scope is not.** A reviewer attaches the
note to the changed line because GitHub allows nothing else, then justifies it
with something the diff does not contain:

> *"`augment()` is called by `augment_squad()` and it passes the device as a
> str so this won't work as intended."*

That comment sits on a changed line. Its justification does not.

### Why the classification is mechanical

A model-assigned label would inherit exactly the weakness this project has
criticised in benchmarks whose ground truth is model-generated, and could not
be checked. Every rule is a regular expression over the comment and a
membership test against the diff, and each decision records the reason that
produced it, so a reader can disagree with a specific case and see why.

**Two bounds, not one number.** Strict counts only comments naming a file the
diff does not contain, linking outside it, or using a phrase such as *"called
by"*. Loose also counts identifiers absent from the diff, which over-triggers
on assertion messages — the test suite pins that case as loose-only rather than
hiding it.

A test caught a bug in the first version: paths were matched against the diff's
content lines but not its headers, so a comment naming a file the pull request
*had* changed counted as pointing outside it. The figure moved by one point,
which is the useful thing to know about it.

### The comparison worth one sentence

AACR-Bench labels **233 of 1,505** issues repository-level — **15%**. Our
strict figure on c-CRAB is **33%**. Two estimates of the same quantity by
different means; the gap belongs in the paper as an observation, not a claim.

---

## 1.8 The sixth withdrawal — the benchmark itself (1 October 2026)

An independent audit of the code, prompted by the request to criticise the
paper before finishing it, found three faults in the generated cross-file
benchmark. Each was confirmed against the data.

| Fault | Measured |
|---|---|
| Distractors broke the file (`"""` → `''"`) | 304 hunks, 145 of 204 tasks |
| Evidence line actually calls the mutated function | 65/65 `default_flip`; 18/139 all other kinds |
| Diff-only already finds the defect line | 93% |

**Everything in §1.5–§1.6 measured on that benchmark is withdrawn**: the
+9-point context effect, the structure null, the corruption asymmetry, the
retrieval re-run. The "confirmed false positives" were correct flags of syntax
errors. §1.7 (anchor vs evidence), the trigger gap, and the c-CRAB runs do not
use this benchmark and stand.

The structure arms had faults of their own: the control kept line numbers and
the relation kind, typed and attributed were identical on 171/179 tasks, the
random arm drew from the two relevant files, the analysis script was not in
the repository, and 133 duplicate rows were counted.

### The rebuild

- calls resolved through imports; each kind verified on the caller's syntax
  tree; four unverifiable kinds dropped; every distractor parse-checked;
  ids carry the line; each record carries its verified `argument`
- control scrambles stem, line, kind and argument; random arm draws from
  requests/click/rich; every kind has an argument; an eighth arm carries the
  dependency header with no snippets; a hidden-evidence mode windows the caller
  above the demonstrating line
- messages stored; a per-kind keyword rubric scores whether the finding names
  what the caller depends on (`mechanism`)
- `experiments/analyse_structure.py`: dedup with counts, repo-clustered and
  task-clustered paired bootstrap side by side, exact McNemar, Holm across cells

### Pre-registration for the re-run — written before any result exists

| | Comparison | Metric |
|---|---|---|
| **Primary** | 3-topology vs 2-evidence | `mechanism` |
| Secondary | 3-topology vs 2-evidence | `precise` |
| Secondary | 6-corrupted vs 2-evidence | `mechanism`, `precise` |
| Exploratory, Holm family | 5 vs 2; 2 vs 8; 8 vs 1; 7 vs 1; 2 vs 7 | both |
| Conditional | hidden-evidence variant, 5 vs 2 | `mechanism` |

Two models, tag and flat encodings. Interval excludes zero or spans zero;
the word "significant" is not used. Clustering by repository is the reported
interval; task-clustered shown beside it.


### Pre-analysis note, written on the first 34 tasks before the run completed

The run-time `mechanism` rubric looks for the dependency token (the exception
type, the parameter name) and a reference to the caller. The typed, attributed
and corrupted blocks *contain* those tokens, so a model that echoes the
metadata passes the rubric without using the snippets. The primary comparison
is clean — neither the topology block nor the scrambled control carries a
rubric token. Every other `mechanism` comparison is read on `mechanism_strict`
(`experiments/mechanism_strict.py`), which additionally requires the message to
name the caller by its enclosing function or file stem, which only the caller
snippet shows. `precise` and `hit` are unaffected. This is recorded here so it
cannot be adopted after seeing which way the contaminated numbers point.


### Second pre-analysis note, at 51 of ~170 tasks

The keyword rubric also passes boilerplate. A diff-only reviewer writes "may
lead to unexpected behavior if the caller expects a None return value", which
satisfies it without any evidence; and it fails genuine explanations that say
"the calling code". A keyword rubric cannot measure mechanism. The
pre-registered primary stays on the keyword rubric as written, and is reported
as such. Alongside it, `experiments/judge_mechanism.py` asks a third model
family (deepseek-v3.2), blind to arm and to the snippets, whether the message
states the same specific reason the generator recorded. The judge is validated
against a hand-labelled sample before any arm comparison is read on it, and
the sample is released. `hit` is at ceiling on the rebuilt benchmark too
(≈97% diff-only), as the audit predicted: the semantic hunk is conspicuous
among cosmetic ones. `precise` therefore measures distractor silence, now on
distractors that are genuinely harmless.


### Gap search, 1 October 2026 (second sweep, ~45 further papers)

Nothing found does any of: a diff-only ceiling as a benchmark-level verdict;
anchor-vs-evidence as a measured property; matched safe twins with an
identical surface mutation; hop-stratified defect detection with pass-through
intermediaries; a noise × structure factorial on a review task; graph-as-
metadata vs graph-as-tool for review.

Direct support for the diagnostic framing: on paired vulnerability datasets
the function alone already scores ≈0.98 and adding callers/callees *lowers*
accuracy (arXiv 2604.08417); ContextCRBench (2511.07017) finds code context
lowers line-level localisation; Mono (2506.03651) and VulAgentRL (2607.26656)
audit evidence scope per sample by judge, not by a diff-only model. Nearest
cousin to twins: equivalent-mutant detection (2607.00511), intra-function
only. CodeGlance (2602.13962) is the one-hop hidden-evidence precedent
(37.5% → 6.0% with callee hidden). 2607.25851 finds only 16% of CodeReviewer
comments context-dependent, which must be reconciled with our 33–50% on
c-CRAB (different dataset, different measure). CodeNib (2607.25431) gives the
only upfront-vs-on-demand number, for issue resolution.

### The reframed paper

**Can this benchmark measure context?** Three diagnostics — diff-only
ceiling, anchor-vs-evidence scope, twin discrimination — applied to c-CRAB,
the withdrawn v1, and v2 with twins. The structure experiment runs only on
the benchmark that passes, with moderators: hidden evidence, noise (k foreign
snippets), two-hop chains, one 2026 model. Built today: twins, noise,
chains, balanced accuracy, typed-signature default flips, tokenizer-based
spacing distractors.


### Third pre-analysis note — the judge, validated, and another generator bug

Forty judged messages were hand-labelled under a strict criterion: YES only
if the message names a concrete caller-side fact (the value, order, exception
type or parameter the caller relies on). The first judge prompt agreed 62%
(kappa 0.25) and over-called generic hedges. The prompt now excludes "may
lead to unexpected behaviour" explicitly; agreement 74%, kappa 0.43, and the
judge under-calls relative to the human (6 vs 15 YES of 35), which is the
conservative direction. On the first 46 tasks per arm it separates arms that
see the caller from arms that do not: diff-only 2%, header-only 2%, random
6%, evidence arms 26–36%. `mechanism_judge` (strict) is therefore reported
beside `precise` and `correct`; the keyword rubric is reported only as the
pre-registered primary. Labels and sample are in `results/judge-validation-*`.

The hand-labelling also exposed a generator bug: five of forty messages were
the model correctly reporting unmatched parentheses, because the tuple-swap
mutation split `return (host, port)` at its first comma. The swap now uses
syntax-tree column spans, every generator parse-checks the mutated line, and
an audit dropped 7 of 79 tasks whose mutated file did not parse, from the
benchmark and from every run file.

### What the literature sweep (June–October 2026) changes

- No scoop of the held-constant design. Cite arXiv 2511.16767 and 2509.18487
  as general-graph precedents; confront 2606.25356.
- **SWE-PRBench (2603.26130)** reports monotonic degradation as file context is
  added to a diff across eight frontier models. Any context effect must be
  reconciled with it.
- The trigger gap is scoped to a bare tool-equipped LLM: CodeCompass
  (2602.20048) supports it; harnessed products explore unprompted
  (2607.16740).
- CR-Bench (2603.11078) and the ICSE 2026 Fudan regression paper are the prior
  art for mined regressions.

---

## 2. What survives

Kept, and all of it useful:

- the runner, resumable, with per-call token and cost accounting
- **token-budget parity enforced on the delivered string** (0–4% spread, tested)
- the finding-level matcher, clustered analysis, honest interval reporting
- four retrieval implementations sharing one signature and payload shape
- the mutation generator with caller-evidence verification
- the cross-file graph fix (0 → 126 cross-file edges on a real repository)
- ~3,000 review traces, two model families, frozen in `results/` — **as a
  pilot that motivated the controlled experiment, not as headline evidence.**
  The count is not the contribution; a reviewer cares whether the tasks were
  valid, and for the review-comment benchmark we now believe they answered a
  question that was framed wrongly.
- 450 tests, CI, Apache-2.0, RepoGraph attribution

Discarded:

- the GitHub → no-context-defects argument (§1.1)
- the oracle claim as stated (§1.2)
- "benchmark construction has never been examined" (§1.3)
- the agent section — 145 records, zero tool calls, almost certainly an
  instrument fault; it makes the paper look unfocused and belongs in its own
  study later

Reframed, not discarded:

- **213/218 on changed lines** is a valid measurement of *anchor* location. Paired
  with an evidence-requirement annotation it becomes the interesting result:
  *"N% of comments anchor in changed files, but M% require unchanged files."*

---

## 3. The new question

> **When the relevant repository evidence and the token budget are held
> constant, does explicitly representing the dependency structure among that
> evidence improve LLM detection of cross-file defects?**

This isolates what every graph-retrieval paper conflates: whether the gain
comes from **better code being retrieved** or from **the relationships between
that code being expressed**.

Secondary questions:

1. Does the effect vary by dependency type (calls / returns / catches / implements)?
2. Does *incorrect* structure actively hurt?
3. Does structure reduce false positives as well as raise recall?
4. Do stronger models benefit more or less?

### Why this is defensible against the crowded field

| Existing work | Covers | Does not do |
|---|---|---|
| RepoGraph, LARGER | repository graph retrieval | separate retrieval quality from representation |
| **GRACE** (arXiv 2509.05980) | **ablates graph fusion against plain concatenation** | per-defect fixed evidence; corrupted structure; code review |
| AACR-Bench | context-level annotation, retriever comparison | hold evidence constant |
| CodeFuse-CR-Bench, SWR-Bench | repository-level evaluation | same |
| c-CRAB | executable ground truth | context at all |

**GRACE is the nearest work and the claim must be written around it.** It
argues that ordinary retrieval loses structure when snippets are concatenated,
and ablates its fusion component. So no absolute novelty statement is
available. What remains is narrower and still defensible:

> Prior work evaluates structure-aware retrieval end-to-end, so improvements
> cannot be attributed to better evidence selection rather than to the
> structural representation of that evidence. We hold the evidence set fixed at
> the level of the individual defect, intervene directly on the correctness and
> the richness of the dependency metadata, and do so for code review rather
> than completion.

That sentence survives a reviewer who knows GRACE. "Nobody has isolated
structure" does not. **One overclaim has already been withdrawn in this
project; a second would be worse than the first.**

---

## 4. The core experiment

Revised after a second review. The v2 design had three confounds of its own,
two of them large enough to swamp the effect being measured.

### 4.1 What was wrong with the v2 arms

**The relation label leaked the answer.** The worked example was
`ec2.py:632 --catches--> _text.py:253 (TypeError)`. The defect *is* that the
raised type changed from `TypeError`. Writing `catches(TypeError)` into the
metadata hands the model the explanation. Any gain would measure the leak.

**Shuffling one arm and not the other varied two things.** And ordering is not
a small effect: GraphDO reports BFS order at **89.43%** against random order at
**78.36%** on identical graphs — an 11-point swing from serialization alone,
larger than any structure effect we would be measuring. GraphSOS finds
performance "fluctuates between high performance and random guessing" when node
or edge order is shuffled.

**The arms were not token-matched.** Arm 3 carries relation tokens that Arm 2
does not, so length is confounded with structure.

### 4.2 The revised arms

Every arm receives the same diff. Arms 2–6 receive **the same snippets, in the
same canonical order, with identical formatting**. Only the metadata block
differs.

| Arm | Metadata block | Isolates |
|---|---|---|
| **1 — diff only** | — | floor |
| **2 — evidence** | label-shuffled graph string | value of the code alone |
| **3 — topology** | `B → A` | does connectivity alone help? |
| **4 — typed** | `B --calls--> A` | does the relation *kind* add anything? |
| **5 — attributed** | `B --catches(TypeError)--> A` | does the *argument* add anything? |
| **6 — corrupted** | plausible wrong endpoints, degree-preserving | is structure being used at all? |
| **7 — random evidence** | unrelated snippets @ same budget | relevance control |

This decomposition is better science than the binary it replaces: it separates
**connectivity** from **relation type** from **relation argument**, and only
arm 5 can leak an answer. If the gain appears at arm 3, it is structure. If it
appears only at arm 5, it is leakage, and that is now visible rather than
hidden.

**Canonical order:** snippets sorted by file path then line number, identical
across arms 2–6. The order is randomised *across tasks* so no single
serialisation is privileged, and the same permutation is used for every arm of
a given task.

**The unstructured control must match semantic density, not just length.** A
block of low-signal filler dilutes attention across the context window, while
`B --calls--> A` is dense. If arm 3 beat a filler arm, the cause could be
signal-to-noise rather than topology.

So arm 2 receives the **same graph string with node labels shuffled**: identical
token count, identical vocabulary, identical edge syntax, identical density —
and no recoverable topology. Arm 3 versus arm 2 then differs in whether the
edges point anywhere true, and nothing else.

Arm 6 provides the same guarantee from the other side: same edge count, degree
distribution, relation types and length, with only the endpoints permuted. Two
independent density-matched controls, one destroying topology and one falsifying
it.

**Corruption must be hard.** Preserve edge count, in/out degree, relation
types, node types, serialised length and ordering; permute only endpoints, and
only to other nodes present in the evidence set. `A.foo --calls--> C.baz` where
`C.baz` is real and plausible — never `A.foo --inherits--> local_var_x`, which
the model can dismiss as nonsense and thereby teach us nothing.

### 4.3 Manipulation check — non-negotiable

If arm 3 ≈ arm 2, there are two explanations and they are not the same:

1. structure carries no additional value, or
2. **the serialisation failed to communicate structure at all.**

Before interpreting any null, probe comprehension directly on the same
serialisation: *"which function catches TypeError?"*, *"what calls X?"*. A
model that cannot answer those has not been given structure in any meaningful
sense, and the null says nothing about structure.

**Three encodings** are tested, because the GraphRAG literature shows format
itself matters and because a naive format invites the charge of testing a
strawman against GRACE's multi-semantic fusion:

| | Form |
|---|---|
| flat edge table | `B --calls--> A` |
| structured tag | `<dependency type="call" target="A.py:42"/>` |
| natural language | *"Function B calls function A."* |

A result that holds under only one encoding is a result about that encoding,
and must be reported as such.

### 4.4 Reading the outcome

| Pattern | Conclusion |
|---|---|
| 3 > 2, and 6 < 2 | the model consumes structure; wrong structure actively misleads |
| 3 ≈ 2 but 5 > 2 | the gain is the relation *argument* — likely leakage, not structure |
| 3 ≈ 2, comprehension probe passes | **structure adds nothing once the code is present** — a clean negative |
| 3 ≈ 2, comprehension probe fails | the serialisation is broken; the arm is uninterpretable |
| 2 ≈ 1 | the evidence set is wrong; fix the dataset before interpreting anything |

Two quantities are reported, not one:

- benefit of correct structure — `P(correct | E,S) − P(correct | E)`
- **harm of incorrect structure** — `P(correct | E,S̃) − P(correct | E)`

The second is the more interesting number and nobody reports it.

### 4.5 Two stages, framed explicitly

Holding the evidence constant removes retrieval as a variable. That is the
design, not an oversight — structure cannot be isolated while retrieval varies
— but it does bound what the result can say, and the paper must say so in the
abstract rather than leave it for a reviewer to notice.

| Stage | Question | Arms |
|---|---|---|
| **1 — retrieval** | can the method *find* `E` in the repository at all? | graph vs BM25 vs dense vs random, reported alone |
| **2 — reasoning** | **given** `E`, does representing its structure help? | arms 1–7, the core experiment |

The paper's claim is therefore explicitly conditional: *assuming the relevant
evidence has been retrieved, does explicit dependency structure improve
reasoning over it?* A finding of "no" in stage 2 says nothing about whether
graphs are useful retrievers, and the two are never combined into one number.

## 5. The dataset

Two sets. The real one carries the claim; the synthetic one is a controlled
supplement, never the primary evidence.

### 5.1 Primary — real cross-file regressions

Target **100–300** instances mined from repository history:

1. Find candidate pairs: a commit that introduced a regression, and the later
   fix or revert. Sources: revert commits, commits referencing "regression",
   issue-linked fixes, SZZ-style blame on bug-fix commits.
2. Require the fix to touch a **different file** than the one that introduced
   the fault, or the fix to restore a contract the introducing change broke.
3. Where possible require executable proof:
   `base PASS → introducing commit FAIL → fix PASS`.
4. Annotate each instance with the schema below.

**The yield will be poor and the timeline in §6 is optimistic.** Separating a
genuine regression-introducing commit from one that merely exposed an existing
bug, from a refactor bundled with a fix, from a dependency-version problem, is
manual work. Historical environments rot: dependency drift, unavailable
packages, interpreter incompatibility, flaky tests. **80 clean executable
regressions is worth more than 300 questionable ones**, and the paper reports
the funnel honestly.

**Selection bias must be stated, and the excluded classes named.** Keeping only
regressions with a clean static cross-file dependency, a small evidence set and
a working historical environment selects for graph-shaped bugs. A static call
graph does not represent dynamic dispatch, event listeners and callbacks,
dependency injection, framework lifecycle hooks, reflection, database schema
mismatches, or configuration-driven behaviour — and real cross-file defects
frequently arrive through exactly those channels.

The defensible claim is therefore conditional: *among reproducible regressions
whose dependency is statically expressible*. Not a population claim about
cross-file regressions, and the paper says which mechanisms it cannot speak to.

**Who decides the evidence set is the next oracle problem.** If we choose `E`
because it demonstrates the dependency we intended, the structured arm
describes it perfectly by construction and we have rebuilt the circularity one
level up. The procedure must therefore be independent of the hypothesis:

- **two annotators**, independently, per instance
- disagreement adjudicated, **agreement reported**
- **minimality by ablation**: remove each snippet and check whether a competent
  reviewer can still establish the defect — the set is minimal when no snippet
  can be dropped
- the result is an **annotated evidence set**, not an "oracle". Repository code
  is not a complete proof: documentation, runtime behaviour, API contracts,
  schemas and conventions can all carry the invariant. Calling it an oracle
  would repeat the mistake §1.2 documents.

**Annotation schema.** Useful, and domain-specific in one respect only —
software engineering has separated fault from failure manifestation for
decades, so the schema is not a new theory of defects. The part worth claiming
is narrower: **anchor location versus evidence location in review-benchmark
construction.**

| Field | Meaning |
|---|---|
| `fault_location` | file + line of the change that introduced the defect |
| `manifestation_location` | where incorrect behaviour appears |
| `evidence_location` | the code needed to infer the change is invalid |
| `anchor_location` | where a human review comment was attached, if any |
| `relation` | calls / returns / catches / implements / reads / writes / schema / type |
| `evidence_verified` | whether removing the evidence makes the defect unrecognisable |

The measurement this enables, and which nobody has published:

> **How often do fault location, evidence location and anchor location differ?**

### 5.2 Secondary — the mutation set

The existing 199, kept as a controlled supplement with its circularity stated
plainly: the dataset is conditioned on a retrievable dependency existing, so it
cannot carry a real-world claim. It is useful for the structure-vs-content
comparison precisely because `E` is known exactly by construction.

---

## 6. Phases

### Phase A — correct the record (2 days, ~$1)

| | |
|---|---|
| Rename F to `fault_location_oracle` everywhere | code, results, artifact |
| Rewrite the briefing artifact around the corrected position | |
| Build a **real evidence oracle**: supply `E`, not the fault site | |
| Re-run F' on both benchmarks | this is the number v1 should have had |
| ~~Run condition C~~ | ✅ **done** — it removed the relevance reading, §1.5 |
| ~~Drop the agent section~~ | **kept** — the trigger gap is supported, see §1.5 |

### Phase B — the evidence annotation (4 days)

| | |
|---|---|
| Annotate c-CRAB's 218 confirmed defects with `evidence_location` | the reframed 213/218 result |
| Cross-check a sample against AACR's Diff/File/Repo labels | do they agree? |
| Report anchor vs evidence divergence | the interesting number |

### Phase C — real regressions (1–2 weeks)

| | |
|---|---|
| Mine revert and regression-fix commits | target 100–300 |
| Verify executably where possible | Docker for a subset |
| Annotate with the schema | |
| Release the miner | |

### Phase D — the core experiment (3 days, ~$20)

| | |
|---|---|
| Implement arms 1–5 with evidence-set control | |
| Corrupted-structure padding to exact token parity | |
| One frontier model + one open model | |
| Per-relation-type breakdown | |
| Task-level paired bootstrap, clustered by repository | |
| Pre-register the primary comparison (3 vs 2) before running | |

### Phase E — write and release (1 week)

Method → Results → Limitations → Related Work → Intro → Abstract.
Related Work opens with AACR-Bench, CodeFuse-CR-Bench, SWR-Bench, RepoGraph,
LARGER — and states the delta in one sentence: **they vary the retriever, we
vary the representation with the retrieved content held fixed.**

Release: benchmark, miner, generator, prompts, raw traces, analysis scripts.

### Phase F — review, then publish

1. Hostile self-review.
2. Two or three real readers.
3. Then Sheleme, with the draft in hand, for co-authorship.
4. arXiv cs.SE only after 2 and 3.

---

## 6b. Two review points examined and rejected

Not everything raised in review survived checking. Recording both, so neither is
quietly re-adopted.

### Underpowering

A reviewer argued that 100–300 defects across seven arms yields a standard error
near 4%, that intervals would heavily overlap, and that the null could not be
rejected.

**This treats the arms as independent samples.** They are paired — every arm
reviews the same defect — so the test is McNemar's on discordant pairs and the
standard error depends on the discordance rate, not the marginal proportions.
Measured on the cross-file run already completed:

| | |
|---|---|
| paired n | 167 |
| discordant pairs | 18 (15 one way, 3 the other) |
| observed effect | +7.2% |
| 95% CI | [+2.4%, +12.0%] — excludes zero |
| implied SE | **2.44%**, not 4% |

The null was rejected at n=167. The same review's own remedy specifies
McNemar's, which contradicts its power calculation.

**Still adopted from it:** more data is better regardless, and the target
remains 100–300 with the funnel reported honestly.

### "The study misses GRACE"

GRACE is cited by arXiv number, named as the nearest work, and the novelty
sentence in §3 is written around it. The observation was made against an earlier
draft.

**Still adopted from it:** the point that a naive `B --calls--> A` format invites
the charge of testing a strawman against GRACE's multi-semantic fusion. Hence
three encodings in §4.3 rather than two.

---

## 7. Statistical discipline

- Unit of independence is the **defect**, not the individual generated review.
- **Paired** comparisons across arms — every arm reviews the same defect.
- Cluster the bootstrap by **repository** as well as task; several benchmarks
  draw many instances from one project.
- **Pre-register** the primary comparison — arm 3 vs arm 2 — and the secondary
  — arm 6 vs arm 2. Everything else is exploratory and labelled as such.
- Report effect sizes with intervals. Never a bare significance verdict.
- State the minimum detectable effect for the achieved sample size.

### Scoring rubric, fixed before any run

"Exactly right" is not a definition. Each review is scored on four binaries and
one count, and the primary endpoint is declared in advance:

| | |
|---|---|
| `defect_detected` | did it report the defect at all |
| `fault_localised` | did it name the correct file and line |
| `mechanism_correct` | did it state *why* the change is wrong |
| `evidence_cited` | did it reference the depended-upon code |
| `false_positives` | count of other findings |

**False positives require verification, not assumption.** A finding outside the
labelled set may be a real defect the annotation missed. Three categories:
`confirmed_false_positive` (checked and wrong), `unverified_finding`,
`additional_valid_issue`. Only the first counts against precision.

## 8. Honest risks

| Risk | Severity | Mitigation |
|---|---|---|
| Real regressions are hard to mine at scale | **high** | accept 100; report the yield honestly; mutation set as supplement |
| Structure turns out not to matter | medium | it is a publishable negative result, and the design is what is being judged |
| Evidence sets are wrong | **high** | two independent annotators, agreement reported, minimality by per-snippet ablation |
| Structure arm wins by leakage | **high** | attribute is isolated in its own arm; a gain at arm 5 only is leakage, visible not hidden |
| Serialisation fails to convey structure | **high** | comprehension probe before interpreting any null; two encodings |
| Ordering swamps the effect | **high** | canonical order identical across arms, randomised across tasks |
| A second overclaim | **high** | GRACE cited in the claim sentence itself; no absolute novelty statement |
| Field moves again before submission | medium | the isolation question is durable; retriever rankings are not |

---

## 10. Rules

1. Nothing is "fixed" without a test.
2. Nothing merges without CI green.
3. Every number in the paper traces to a file in `results/`.
4. **Every claim states what it does not establish.**
5. When a measurement contradicts the hypothesis, the measurement wins.
6. Nothing is published until a qualified human has read it and said yes.
