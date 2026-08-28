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
- ~3,000 review traces, two model families, frozen in `results/`
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

| Existing work | Covers | Does not isolate |
|---|---|---|
| RepoGraph, LARGER | repository graph retrieval | retrieval quality vs structural representation |
| AACR-Bench | context-level annotation, retriever comparison | same |
| CodeFuse-CR-Bench, SWR-Bench | repository-level evaluation | same |
| c-CRAB | executable ground truth | context at all |

No listed paper holds the evidence constant and varies only its representation.
That is the gap, and it is narrow enough to be answerable.

---

## 4. The core experiment

For each defect, define the **evidence set** `E` = the minimal set of code
snippets that prove the change is wrong. Every arm below receives the same
diff; arms 2–4 receive **the same snippets**, differing only in what is said
about their relationships.

| Arm | Receives | Isolates |
|---|---|---|
| **1 — diff only** | the change | floor |
| **2 — content** | diff + `E`, shuffled, no relations stated | value of the code itself |
| **3 — content + structure** | diff + `E` + correct relations | **the variable under test** |
| **4 — content + wrong structure** | diff + `E` + permuted relations | **negative control** |
| **5 — random @ same budget** | diff + unrelated snippets | relevance control |

Relations are stated explicitly, for example:

```
ec2.py:632  --catches-->  _text.py:253 (TypeError)
```

**Token parity is enforced on the serialised payload** across arms 2–4, using
the existing `ContextBudget`. Arm 4 is padded to match arm 3 exactly.

### Reading the outcome

| Pattern | Conclusion |
|---|---|
| 3 > 2 and 4 < 2 | the model uses structure, and wrong structure misleads it |
| 3 > 2 and 4 ≈ 2 | structure helps, corruption is ignored |
| 3 ≈ 2 | **structure adds nothing beyond the code** — a clean negative result |
| 2 ≈ 1 | the evidence set is wrong; fix the dataset before interpreting anything |

**A negative result here is publishable and worth writing.** It would say the
field's graph machinery earns its keep as a *retriever*, not as a
*representation* — which is a useful correction.

### Separately, and not mixed in

Retriever comparison — graph vs BM25 vs dense vs random — answers a different
question: *which method finds `E`?* It is reported in its own section, never
folded into the structure comparison.

---

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

**Annotation schema** — this is itself a contribution:

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

- Unit of independence is the **defect**, not the individual review.
- Cluster the bootstrap by **repository** as well as task — several benchmarks
  draw many instances from the same project.
- **Pre-register the primary comparison** (arm 3 vs arm 2) and report everything
  else as secondary.
- Report effect sizes with intervals. Never a bare significance verdict.
- State the minimum detectable effect for the achieved sample size.

---

## 8. Honest risks

| Risk | Severity | Mitigation |
|---|---|---|
| Real regressions are hard to mine at scale | **high** | accept 100; report the yield honestly; mutation set as supplement |
| Structure turns out not to matter | medium | it is a publishable negative result, and the design is what is being judged |
| Evidence sets are wrong | **high** | verify by ablation: removing `E` must make the defect unrecognisable |
| Field moves again before submission | medium | the isolation question is durable; retriever rankings are not |

---

## 10. Rules

1. Nothing is "fixed" without a test.
2. Nothing merges without CI green.
3. Every number in the paper traces to a file in `results/`.
4. **Every claim states what it does not establish.**
5. When a measurement contradicts the hypothesis, the measurement wins.
6. Nothing is published until a qualified human has read it and said yes.
