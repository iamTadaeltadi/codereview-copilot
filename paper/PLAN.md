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
| **2 — evidence** | placebo of matched length | value of the code alone |
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

**Placebo metadata:** arm 2 receives a block of matched token length carrying
no relational information, so length is held constant rather than confounded.

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

**Two encodings** are tested, because the GraphRAG literature shows format
itself matters: an edge table (`B --calls--> A`) and natural language
(*"Function B calls function A."*). A result that holds only under one encoding
is a result about that encoding.

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

### 4.5 Retrieval comparison, kept separate

Graph vs BM25 vs dense vs random answers *which method finds E*. It is a
different question, reported in its own section, never folded into the
structure comparison.

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

**Selection bias must be stated, not hidden.** Keeping only regressions with a
clean static cross-file dependency, a small evidence set, and a working
historical environment selects for graph-shaped bugs. The defensible claim is
therefore conditional — *among reproducible regressions with explicit static
dependencies* — not a population claim about real-world regressions.

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
| **Run condition C on the cross-file set** | still blocking, still 30¢ |
| Drop the agent section from the paper | park the harness |

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
