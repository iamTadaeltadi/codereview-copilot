# Pre-registration F: graded confidence and ROC on kind-matched default flips (9 November 2026)

Written, committed and pushed before any model call for this run. The only work done before it:
reading the runner, counting the items offline from the local source cache, checking model prices
on OpenRouter's public model list, and testing the new parsing and analysis code on records that
already exist. Condition E (CIS, `PREREG-E.md`) is dropped and is not run.

## Why

The twin result in the paper (Table 2, kind-matched default flips) is that showing the caller
lowers the criterion c on gpt-4o-mini and deepseek-v3.2, while no caller arm changes d′ by an
interval that excludes zero. Reviewers note that d′ from one yes/no point per arm rests on the
equal-variance assumption, and ask for a threshold-free test. This run asks for a graded
confidence on every finding, builds an ROC per arm, and compares areas under the curve.

## Items

All `default_flip` defects in `data/crossfile-v3.jsonl` and all `default_flip` twins in
`data/crossfile-v3-twins.jsonl` that have an evidence set (at least three snippets, the runner's
existing rule). Counted offline on 9 November from the local source cache, with no fetch error:

| file | default_flip rows | with an evidence set | repositories |
|---|---|---|---|
| defects, `crossfile-v3.jsonl` | 144 | 139 | 34 |
| twins, `crossfile-v3-twins.jsonl` | 149 | 143 | 30 |

These are the same 139 defects and 143 twins as Table 2's gpt-4o-mini rows.

## Arms

`1-diff` (diff only), `7-random` (foreign code), `2b-snippets` (the caller, no dependency block)
and `5-attributed`. With 282 items, that is 1,128 replies per model.

## Settings

Identical to `results/v3-neutral-gpt4omini/` and its twins:
`experiments/run_structure.py --limit 400 --encoding tag --neutral-prompt`, temperature 0.1,
`max_tokens` 2048, the same evidence, foreign-code draw and source cache, and the manipulation
check every eighth task as before. Two flags are added: `--kinds default_flip`, which filters the
items, and `--confidence`.

**The only change to what the model sees** is in the output contract, identical in every arm.
The JSON shape line becomes

    {"findings": [{"path": "relative/file.py", "line": 42, "message": "what is wrong", "confidence": 70}]}

and this sentence is added before "Never wrap the JSON in prose.":

    "confidence" is an integer from 0 to 100: how likely you think it is that the finding is a real defect (0 = almost certainly not, 100 = certain).

Without `--confidence`, every prompt is byte-identical to the current runner: checked on 184
prompts across the four arms, with and without `--authoritative`.

## Scoring

- **Confidence.** An integer, a number or a numeric string such as "80" or "80%", rounded to an
  integer and kept if it lies within 0–100. Anything else is missing.
- **Item score.** The highest confidence among the findings that the existing matcher
  (`score_review`, tolerance 0) counts as a hit on the mutated line. The score is 0 when no
  finding is a hit.
- **Left out and counted, never scored 0.** A reply that cannot be parsed (`parse_failed`). An item
  with a hit whose confidence is missing (`confidence_missing`). Both are counted per arm,
  separately for defects and twins.
- **Recorded per reply.** Each finding's line, hit and confidence, the item score, and the raw
  reply.

## Primary measure

- **AUC per arm** = P(defect score > twin score) + 0.5·P(tie), over all defect–twin pairs of the
  arm.
- **ΔAUC** = arm − `1-diff`, for each of the three other arms.
- **Bootstrap.** Percentile bootstrap over repositories (the second field of the task id): 6,000
  draws, seed 0, defects and twins of a repository resampled together, the same draws for every
  arm. These are the draws of `experiments/signal_detection.py`. 95% and 90% intervals.
- **Reading, stated now for each ΔAUC:**
  - *equivalence* (no discrimination gain) if the 90% interval lies inside ±0.05;
  - *a gain* if the 95% interval lies above 0;
  - *inconclusive* otherwise.

  If both of the first two hold, both are reported.

Code: `experiments/analyse_roc.py`, which writes `analysis-roc.txt` per model. It was checked on
the existing gpt-4o-mini records with each hit scored 100 and each miss 0. In that case AUC must
equal (1 + H − F)/2, and it does (diff only 0.488). The secondary H, F, d′ and c it prints
reproduce Table 2's gpt-4o-mini diff-only row (H 0.144, F 0.168, d′ −0.10, c 1.01).

## Secondary

H, F, d′ and c per arm from the same run's binary hit, as now (`signal_detection.py`: parse
failures dropped, rates of 0 or 1 moved by 1/(2n)), with Δd′ and Δc against `1-diff` on the same
draws, 95% intervals. The criterion shift is said to replicate on a model if Δc for `2b-snippets`
and for `5-attributed` each has a 95% interval wholly below zero. These numbers come from this
run, with the confidence contract, and are compared with Table 2, not pooled with it.

## Models, order and stops

| order | run | model | cap |
|---|---|---|---|
| 1 | primary | `openai/gpt-4o-mini` | $1.50 |
| 2 | primary | `deepseek/deepseek-v3.2` | $1.50 |
| 3 | optional (a) | `openai/gpt-4o-mini` with `--authoritative`, same items and arms | $0.50 |
| 4 | optional (b) | `openai/gpt-4.1` through OpenRouter's `:batch` variant, same items and arms | $2.00 |

- **Overall.** A hard cap of **$4.00 in total** over everything in this pre-registration, smoke
  tests included. Each run's cap is checked every minute against the recorded per-call cost of
  its replies and manipulation checks, and the run is stopped when it passes the cap.
- **When optional runs start.** An optional run starts only if the recorded total so far plus its
  own cap stays at or under $4.00, and the OpenRouter balance covers its cap.
- **Re-issuing calls.** After each model's pass, one resume pass re-issues calls that failed on
  the network, within the same cap. Parse failures are recorded rows and are not re-issued.

**Why gpt-4.1 through `:batch`.** Prices from OpenRouter's model list on 9 November, applied to
the token counts these 1,128 replies used on gpt-4o-mini (1,042,850 input, 33,725 output):

| model | input / output per million tokens | projected cost |
|---|---|---|
| `openai/gpt-4.1` | $2.00 / $8.00 | $2.36, above the $2.00 cap |
| `openai/gpt-4.1:batch` (same model) | $1.00 / $4.00 | $1.18 |

**Fallback, fixed now.** `:batch` showed no recent traffic on OpenRouter's endpoint list. If its
smoke test does not return a reply, run (b) uses `moonshotai/kimi-k2-0905` instead: non-reasoning,
$0.60 / $2.50 per million tokens, about $0.69 projected on the same counts. The trigger is
whether a reply comes back, not its content.

For reference, these same items and arms cost $0.161 on gpt-4o-mini, recorded. On deepseek-v3.2
they cost $0.510 for the 1,097 replies its partial runs recorded. The confidence field adds a few
output tokens.

## Smoke test before each model

Before each run starts, the same model is called on 3 defect items × 1 arm (`5-attributed`, the
longest prompt), with the same settings. The run starts only if every reply parses and every
finding carries a valid confidence. Otherwise it does not start, and the problem is reported. A
smoke test may lead to a parser fix that accepts another format. A change to the prompt would be
written here as an amendment before any full run. Smoke replies are kept in `smoke/`, are not
analysed, and count toward the $4.00.

## Files

`results/v3-roc-gpt4omini/` and `results/v3-roc-deepseek/`, plus `results/v3-roc-gpt4omini-auth/`
and `results/v3-roc-gpt41/` (or `v3-roc-kimi/`) if the optional runs happen. Each folder holds:
- `launch.sh`, `README.md` and `cost.log`;
- the records, `structure-{defects,twins}-shard{0,1,2}.jsonl` with their `manipulation-*` and
  `run-*` logs, in three interleaved shards per file as in `results/v3-neutral-deepseek/`;
- `smoke/` and `analysis-roc.txt`.

## Rules

- **Runs.** No run is repeated, extended or stopped early for a nicer result. A run stopped by
  its cap is reported as partial in its README, and what it recorded is analysed.
- **Records and history.** No existing result file is changed, and git history is not rewritten.
- **Reporting.** Every deviation from this text is reported with the results.
- **Deadline.** If the runs are not done by Thursday 12 November 2026, Ethiopia time, the work
  stops and what exists is reported.

## Amendment 1 (10 November 2026, 13:15 EAT; before any model call of run F)

No model call of run F has been made when this amendment is committed. It replaces the primary
measure, the margin, the smoke test and the run list above. Everything not named here stands.

**Reason.** An independent review found that the item score above (the highest confidence among
hits on the mutated line, else 0) is censored. On the frozen gpt-4o-mini diff-only records, about
86% of defects and 83% of twins would score 0. AUC is then mostly (1 + H − F)/2, and in arms with
few zeros the censoring alone could produce an apparent gain. With 139 defects and 143 twins, the
±0.05 margin is also out of reach: the simulated 90% interval is about 0.10 wide.

**Contract.** With `--hunk-ratings` (code: `experiments/run_structure.py`, commit cfd4483), the
output contract of every arm also asks for a rating of every hunk. The shape line becomes:

    {"findings": [{"path": "relative/file.py", "line": 42, "message": "what is wrong", "confidence": 70}], "hunk_ratings": [{"line": <hunk start line>, "defect_probability": <integer 0-100>}, ...]}

The hunk ratings carry placeholders, not example numbers, to avoid anchoring; the findings example
is unchanged. This sentence is added after the confidence sentence, before "Never wrap the JSON
in prose.":

    "hunk_ratings" is required, also when "findings" is empty: one entry for every hunk in the diff, in diff order. "line" is the new-file start line from that hunk's @@ header (the number after "+"); "defect_probability" is an integer from 0 to 100: how likely you think it is that the change in that hunk is a defect (0 = almost certainly not, 100 = certain).

The wording is the same in every arm. The per-finding confidence stays as a secondary field.
Without the flag, all 20,304 prompts (282 items × 9 arms × neutral or not × authoritative or not ×
confidence or not) are byte-identical to the code before this amendment. The contract's sentence
that diff lines carry line-number prefixes is inaccurate in `run_structure.py`, which sends the raw
diff. It is kept, for comparability with Table 2; it is harmless here because every hunk header is
the changed line.

**Items and hunks.** The items are unchanged: 139 default-flip defects and 143 default-flip twins
with an evidence set. Check over all 293 default-flip items (144 defects, 149 twins): every diff
touches one file and has 3 or 4 one-line hunks (`-x,1 +x,1`, one removed and one added line, no
context; 283 items have 4, 10 have 3). Old and new start lines are equal. The hunk header lines are
exactly the mutated line plus the distractor lines, all different. In the run, the mutated hunk is
the 1st, 2nd, 3rd or 4th hunk for 32, 32, 38 and 37 defects, and 34, 27, 31 and 51 twins; this is a
property of the items, reported and not corrected.

**Item score.** The defect_probability of the hunk whose header line equals the mutated line. A
rating counts when "line" equals a header line (an integer, an integral number or a numeric string)
and "defect_probability" is a number from 0 to 100 ("70", 70.0 and "70%" are accepted, and
non-integers are rounded, as for confidence). A header line rated twice with different values has
no rating. Replies without a JSON object (`json_failed`) and replies without a rating for the
mutated line's hunk (`rating_missing`) are left out and counted, for defects and twins separately;
they are never scored 0. Entries for lines that are not hunk headers are counted and ignored. The
hunk score does not depend on `findings`: a reply with ratings and no `findings` key counts for the
primary measure and as a parse failure for the binary secondary.

**Primary.** Per arm, the AUC of the hunk score: P(defect > twin) + ½ P(tie). The primary
comparison, per model, is 5-attributed − 1-diff. ΔAUC uses the repository bootstrap above (6,000
draws, seed 0, defects and twins of a repository resampled together, the same draws for every arm),
with 95% and 90% intervals. The smallest effect of interest is ±0.10 AUC:
- **equivalence:** the 90% interval lies inside ±0.10;
- **gain:** the 95% interval lies above 0;
- **gain and equivalence:** both hold;
- **inconclusive:** otherwise.

The same reading at ±0.05 is reported as secondary.

**Surface-match gate.** The diff-only AUC and its 95% interval are reported first. If the interval
excludes 0.5, the twins are distinguishable from the diff alone for that model, and ΔAUC is read
relative to that baseline.

**Secondary.** From the same replies: H, F, d′, c, Δd′ and Δc from the binary hit, as a replication
check of Table 2 under the new contract (Table 2's values are printed beside them where the prompt
differs only in the contract); the binary AUC (1 + H − F)/2; the censored confidence AUC defined
above; ΔAUC for 7-random and 2b-snippets. Descriptive only: tie fraction, number of distinct rating
values, a histogram of item scores per arm (defects and twins), and the zROC slope.

**Multiplicity.** One primary comparison per run. Every other comparison, measure and run (5 runs,
up to 3 comparisons each, several measures) is reported without correction and read as secondary.

**Runs, in order.** Total at most $4.00 recorded. A run starts only if the OpenRouter balance
covers its cap, the recorded total plus its cap stays within $4.00, and it is before Thursday 12
November 2026, 18:00 EAT. Arms: 4 = 1-diff, 7-random, 2b-snippets, 5-attributed; 3 = 1-diff,
2b-snippets, 5-attributed.

| # | model | arms | cap |
|---|---|---|---|
| 1 | openai/gpt-4o-mini | 4 | $1.00 |
| 2 | deepseek/deepseek-v3.2 | 4 | $1.00 |
| 3 | openai/gpt-4o-mini `--authoritative` | 3 | $0.40 |
| 4 | deepseek/deepseek-v3.2 `--authoritative` | 3 | $0.60 |
| 5 | openai/gpt-4.1:batch | 4 | $4.00 − recorded total − $0.05 |

Runs 3 and 4 are the authoritative runs, for both models. 7-random is dropped there because "every
use of the function" is false for foreign code. The authoritative sentence is not shown in 1-diff,
so that arm repeats the neutral 1-diff prompt. Run 5 is checked after its smoke test: if the smoke
cost per call × 1,128 calls exceeds its cap, or its smoke test fails or gets no reply within 15
minutes, moonshotai/kimi-k2-0905 runs instead with 4 arms and the same kind of cap (the money left,
less $0.05). The $0.05 margin covers calls in flight when the cost watcher, which checks every 30
seconds, stops a run.

**Smoke test.** Before each run: 3 calls on 3 defect items in 5-attributed, with that run's exact
flags. The run does not start if any reply fails to parse, lacks a valid rating for any hunk, or
rates a line that is not a hunk header. A finding without a valid confidence is logged and does not
stop the run (confidence is now secondary). Only the parser may change after a failed smoke test;
a change to the prompt needs a further amendment.

**Files.** One folder per run: `results/v3-roc-gpt4omini/`, `v3-roc-deepseek/`,
`v3-roc-gpt4omini-auth/`, `v3-roc-deepseek-auth/`, and `v3-roc-gpt41/` (or `v3-roc-kimi/`), laid out
as above. Each is committed and pushed when its run ends.

**Unchanged.** No run is repeated, extended or stopped early for a nicer result. A run stopped by
its cap is analysed as recorded.
