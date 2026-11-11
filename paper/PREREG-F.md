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

## Amendment 2 (10 November 2026, 14:33 EAT; during run 2, before its cap was reached)

**Reason.** Under the Amendment 1 contract, deepseek-v3.2 writes much longer replies than the
projection assumed: 2,700–3,700 output tokens per call, against 900–2,100 in the earlier deepseek
runs on the same items. A call costs about $0.0014 instead of about $0.0006. At the caps of
Amendment 1, run 2 would stop at about 63% of its calls and run 4 at about 52%. This was seen only
in the cost log and the token counts of the 413 calls recorded so far. No deepseek result has been
analysed or looked at.

**Changes.**
- Run 2 (deepseek-v3.2, 4 arms): cap $1.85. Projected from the recorded calls: $1.58.
- Run 4 (deepseek-v3.2 `--authoritative`, 3 arms): cap $1.45. Projected: $1.16.
- Run 5 (gpt-4.1:batch, or kimi-k2-0905) is dropped.
- The $4.00 total is unchanged. With every cap reached, the total would be $3.93 ($0.23 recorded
  for run 1, plus $1.85, $0.40 and $1.45).

**Mechanics.** Run 2 is stopped and restarted from its own records with the new cap. The runner
skips every (item, arm) already recorded, so nothing is asked twice. The smoke test is not repeated:
its 3 records exist and pass. Calls in flight at the restart (at most 6) are lost and asked again;
they are billed but not recorded. The interrupted logs are kept as `run-*-interrupted.log`.

Everything else in Amendment 1 stands.

## Amendment 3 (10 November 2026, 16:56 EAT; before any call of the controlled reruns)

**What was found, and when.** After the results of runs 2 and 4 had been seen, the deepseek records
were examined for reply length.
- **Run 2:** 505 of 1,128 calls billed more than 1,500 output tokens (median 3,592, max 131,244),
  while their visible replies stayed short (median 624 characters). The other 623 calls billed at
  most 1,500 (median 183). The long calls are the first 60–75% of each shard, and the switch came at
  about the same time in all six shards.
- **Run 4:** at most 457 output tokens per call.
- **What it indicates:** billed output above the 2,048 max_tokens with a short visible reply
  indicates hidden reasoning tokens.
- **Why it was not controlled:** OpenRouter serves deepseek/deepseek-v3.2 through seven providers
  that differ in reasoning default and quantization (DeepInfra fp4; AtlasCloud, GMICloud,
  SiliconFlow and Baidu fp8; DigitalOcean and Phala unknown). Run F's requests set neither reasoning
  nor provider, so the reasoning mode and the weights were not controlled, and the records do not
  name the provider.
- **Table 2:** the deepseek records behind it (default flips, parsed) are 19.7% long by the same
  threshold (485 of 2,460): 33.0% of defect records and 7.6% of twin records. Defects and twins
  were run at different times, so this difference cannot be told apart from routing over time.

**Status.** The two reruns below are post hoc: they were decided after seeing the results of runs 2
and 4. They use exactly the analysis of Amendment 1:
- the same 139 default-flip defects and 143 twins, arms and output contract;
- temperature 0.1 and max_tokens 2,048;
- the hunk-rating AUC, with ΔAUC 5-attributed − 1-diff as the primary comparison;
- the ±0.10 margin (±0.05 secondary);
- the repository bootstrap (6,000 draws, seed 0);
- the surface-match gate.

Runs 2 and 4 stay in the repository and are reported as recorded. The paper reports the reruns as
"deepseek-v3.2, reasoning off, one fp8 provider", next to runs 2 and 4. No run is dropped or chosen
by its result. Turning reasoning off makes the reruns a different condition from runs 2 and 4 and
from Table 2; they are reported as a controlled condition, not as a replacement.

**Fixed settings for every call of the reruns** (reviews, manipulation checks, smoke tests). The
request adds:

    "reasoning": {"enabled": false}
    "provider": {"order": ["atlas-cloud/fp8"], "allow_fallbacks": false, "require_parameters": true}

- **How they are set:** through `OPENROUTER_REASONING` and `OPENROUTER_PROVIDER` (code commit
  8625a60). With both unset, requests are byte-identical to before.
- **Fallback:** `gmicloud/fp8` with the same settings, used only if an AtlasCloud smoke test
  fails. Both reruns use one provider, and providers are never mixed within a run.
- **Recorded per call:** the response's provider field, `usage.completion_tokens_details.reasoning_tokens`,
  output tokens and the raw usage object.

**Runs.**

| run | model | arms | flags | folder | cap |
|---|---|---|---|---|---|
| 2c | deepseek-v3.2 | 1-diff, 7-random, 2b-snippets, 5-attributed | neutral | `results/v3-roc-deepseek-ctrl/` | $0.70 |
| 4c | deepseek-v3.2 | 1-diff, 2b-snippets, 5-attributed | `--authoritative` | `results/v3-roc-deepseek-auth-ctrl/` | $0.50 |

- **Budget:** run F's $1.89 recorded plus $1.20 in caps = $3.09, within $4.00.
- **Start rules:** as before (the balance covers the cap, the total stays within $4.00, and no run
  starts after 12 November 2026, 18:00 EAT).

**Smoke tests.** Both reruns get a smoke test before either is launched: 3 defect items ×
5-attributed, with the run's exact flags and settings. A smoke test passes only if:
- every reply parses with a rating for every hunk and no non-header lines;
- every call has reasoning_tokens 0 or absent, and fewer than 600 output tokens;
- the served provider is the pinned one (matched to OpenRouter's provider name for that endpoint,
  ignoring case, spaces and hyphens), or is not reported, which is then stated in the README
  (allow_fallbacks false still pins it).

The raw usage objects and provider fields of the smoke calls are written to the run's log and
README before the run is launched. If either AtlasCloud smoke test fails, both reruns switch to
gmicloud/fp8 and both smoke tests are repeated (the failed smoke records are kept). If a GMICloud
smoke test fails, nothing runs and this is reported.

**Abort rule.** A watcher checks every recorded call of a running rerun every 30 seconds and at the
end of each pass. It stops the run if any call has reasoning_tokens > 0, more than 1,500 output
tokens, or a reported provider other than the pinned one. The stop is logged in the README, the run
is not restarted, and if 2c is stopped, 4c does not start.

**Unchanged.** No rerun, extension or early stop for a nicer result. A run stopped by its cap or by
the abort rule is analysed as recorded.

**Also post hoc (descriptive, no cost).** The Table 2 deepseek records split by reply length (more
than 1,500 output tokens = long), with the share of long records per arm for defects and twins and
n, H, F, d′, c per arm and split: `results/twins-kind-matched/posthoc-reply-length.txt`
(`experiments/posthoc_table2_reply_length.py`).

## Amendment 4 (10 November 2026, 20:36 EAT; before any call of run 2t)

**Status.** Post hoc: decided after seeing the results of runs 1–4, 2c and 4c.
- **Why:** run 2c (reasoning off, AtlasCloud fp8) gave ΔAUC +0.081 [+0.017, +0.148]. In run 2,
  where reasoning was not controlled, the calls with hidden reasoning seemed to drive a larger gain
  (`results/v3-roc-deepseek/posthoc-reply-length.txt`).
- **What it tests:** one run that changes only the reasoning mode, compared with 2c. It tests whether
  reasoning lets the model use the caller to tell defects from twins, or only makes it flag more.

**Run 2t.**
- **Model and arms:** `deepseek/deepseek-v3.2`, neutral prompt, not authoritative, two arms only:
  1-diff and 5-attributed.
- **Items and contract:** the same 139 default-flip defects and 143 twins as 2c, the same output
  contract (hunk ratings, per-finding confidence), temperature 0.1.
- **Folder:** `results/v3-roc-deepseek-think/`.
- **The only change from 2c** is `"reasoning": {"enabled": true}`.
- **Provider:** pinned exactly as in 2c:
  `{"order": ["atlas-cloud/fp8"], "allow_fallbacks": false, "require_parameters": true}`. GMICloud
  fp8, with the same settings, is used only if the AtlasCloud smoke test fails.
- **max_tokens:** 2,048 as before. If any smoke reply is cut off (finish_reason "length"), empty, or
  without JSON at max_tokens because the reasoning used up the budget, the run uses 16,000 for
  every call instead. This is decided from the smoke test only. Once 16,000 is chosen, it also
  holds for any later smoke test, including GMICloud's. The value used is recorded in the README and
  in every record.

**Timing.** In Table 2 the defects and twins ran at different times, and routing changed between
them. In 2t they run at the same time:
- **Shards:** 2c's 282 items are shuffled together (`random.Random(0).shuffle` of the sorted task
  ids) and dealt round-robin into six shards of 47. Each shard holds 21–26 defects and 21–26 twins.
  The six shards run in parallel.
- **Arm order:** each item's two arms are called back to back, in an order shuffled with
  `random.Random("0:<task id>")`.
- **Code and records:** `experiments/roc_tools.py prep_think`; `run_structure.py --arm-order-seed 0`.
  Every record stores its arm position and call time.

**Recorded per call:**
- the served provider, `usage.completion_tokens_details.reasoning_tokens`, output tokens and
  finish_reason;
- the raw usage object;
- the request's reasoning and provider settings.

A reply cut off at max_tokens is billed but not scored. It is now written, with its cost, to
`failed.jsonl`, and it counts toward the cost watcher and the abort rules.

**Forced deviation: the manipulation check.** Runs 1–4, 2c and 4c gave the manipulation check
max_tokens 48. With reasoning on, 48 tokens cannot hold the reasoning, so in 2t the check uses the
review max_tokens (2,048 or 16,000). Its question and scoring are unchanged.

**Budget.** Run F's limit is raised from $4.00 to $4.90. Reasoning replies are much longer than
2c's: run 2's long replies had a median of 3,592 output tokens, against 2c's maximum of 447. This was
decided before any 2t call.
- **Cap:** $2.30, smoke tests included.
- **Fit:** run F's recorded $2.5842 plus $2.30 is $4.8842, within $4.90.

**Smoke test.** 3 defects (`runs/roc-items/smoke3.jsonl`) and 3 twins (the first three default-flip
twins with at least 3 evidence snippets, the rule used for the defects), alternating, ×
5-attributed. With the first item's manipulation check, that is 7 calls, with the run's exact flags
and settings.
- **Pass criteria:**
  - every reply parses, with a rating for every hunk and no non-header lines;
  - every call has reasoning_tokens > 0;
  - the served provider is reported as AtlasCloud;
  - no reply is cut off;
  - the manipulation check is recorded.
- **Resume:** missing replies with no cut-off record (a network failure) are asked once more.
- **Projection:** the mean smoke review-call cost × 564 × 1.5, plus the cost of every smoke test so
  far.
- **Before the launch:** the smoke usage objects, finish reasons and projection are written to the
  README and pushed.
- **Launch:** if the smoke test passes, the projection is within $2.30 and the start rules hold, the
  run starts without further approval. Otherwise the projection is reported and nothing runs. No
  partial runs by design.

**Start rules:**
- the balance covers the cap;
- run F's total before 2t plus the cap stays within $4.90;
- no launch after Wednesday 11 November 2026, 15:00 EAT; the run is stopped at 18:00 that day.

**Abort rules.** A watcher runs every 30 seconds and at the end of each pass, over the run's calls
(reviews, manipulation checks and cut-off calls). It stops the run on:
- a reported provider other than the pinned one;
- more calls with reasoning_tokens 0 than 2% of the larger of the recorded calls and 564;
- any call billing more than 40,000 output tokens;
- a call without the run's settings.

On an abort, the run stops, the stop is logged in the README, and the run is not restarted. The cap
and the $4.90 limit also stop the run. As in runs 1–4c, a second pass asks the calls that have no
record (network errors and cut-off replies) once more.

**Primary analysis.** Identical to Amendment 1 (`results/v3-roc-deepseek-think/analysis-roc.txt`,
`experiments/analyse_roc.py`):
- the hunk-rating AUC, with ΔAUC 5-attributed − 1-diff;
- the repository bootstrap, 6,000 draws, seed 0;
- gain if the 95% interval lies above 0;
- equivalence if the 90% interval lies inside ±0.10 (±0.05 secondary);
- the surface-match gate.

**Secondary, stated now.**
- **H, F, d′, c and Δc for 2t:** section 6 of analysis-roc.txt.
- **Between runs:** the difference on the same items, (5-attributed − 1-diff in 2t) −
  (5-attributed − 1-diff in 2c), in hunk-rating AUC, with each cell over its scored items. The
  repository bootstrap covers the repositories with a scored item in all four cells, with 6,000
  draws, seed 0, and the same draw for both runs. It gives a 95% interval. Saved as
  `results/v3-roc-deepseek-think/compare-2c.txt` (`experiments/compare_roc_runs.py`).
- **Also in that file:**
  - per arm, the change from 2c to 2t in H, F, d′ and c;
  - per run, the change from 1-diff to 5-attributed in H, F, d′ and c, and its difference between
    runs;
  - all with 95% intervals from the same draws;
  - descriptive: the difference of differences on the items scored in all four cells.

**Reporting.** Runs 2c and 2t are both reported, 2t as "deepseek-v3.2, reasoning on, one fp8
provider". Nothing is dropped or chosen by its result. A run stopped by its cap, the limit, the
deadline or an abort rule is analysed as recorded.

**Code.** All new or changed code is under `experiments/`:
- `roc_run_think.sh` and `launch_roc_think.sh`;
- `roc_tools.py`: prep_think, smoke_think, project_think, guard_think, usage_think, thinkstats; its
  cost readers now also count `failed.jsonl`;
- `run_structure.py`: `--max-tokens`, `--check-max-tokens`, `--arm-order-seed`, `failed.jsonl`;
- `llm.py`: keeps a cut-off reply's usage;
- `compare_roc_runs.py`.

With the new flags unset, requests and records are as before.

## Amendment 5 (10 November 2026, 22:48 EAT; before any call under it)

**Status.** Post hoc: decided after seeing the partial results of run 2t. Amendment 4's run was
stopped at 22:20 on 10 November by its 40,000-token abort rule, after 330 of 564 review calls. Its
partial results:
- ΔAUC 5-attributed − 1-diff: +0.156 [+0.062, +0.254];
- difference from run 2c: +0.074 [−0.055, +0.201];
- 1-diff AUC: 0.593 [0.519, 0.668], so the surface-match gate excludes 0.5.

These partial results stay in `results/v3-roc-deepseek-think/` as committed, and are reported beside
the complete run.

**What runs.** Two parts, both in run 2t's six seeded shards (`runs/roc-items/think-mixed-shard*.jsonl`,
unchanged).
1. **Completion of run 2t:** the 234 calls of arms 1-diff and 5-attributed that have no record. They
   use the same settings as Amendment 4's run:
   - reasoning on;
   - GMICloud fp8 pinned: `{"order": ["gmicloud/fp8"], "allow_fallbacks": false, "require_parameters": true}`;
   - max_tokens 16,000 for reviews and manipulation checks;
   - temperature 0.1 and the same flags.
2. **A third arm, 7-random** (foreign code), on the same 282 items, with the same settings, mixed
   into the same shards.

**How the calls are ordered:**
- Each shard is walked in its fixed order.
- An item's missing arms are called back to back, in an order shuffled with
  `random.Random("0:<task id>")` over (1-diff, 7-random, 5-attributed).

**What is not asked again:**
- Calls already recorded are kept as recorded. This includes the 1-diff twin call that billed 53,234
  output tokens (`dask/bag/avro.py::to_avro::default_flip::182::safe`), which was scored and stays
  scored.
- Manipulation checks already recorded are not repeated. 7-random has no manipulation check (no
  dependency block), as in runs 1–4c.
- There is no new smoke test.

**Timing.** All 7-random calls run on Wednesday. For the 164 items finished on Tuesday, 1-diff and
5-attributed ran on Tuesday, so for those items the arm coincides with the day. The README reports
the review calls per arm and day.

**Runaway rule** (replaces Amendment 4's 40,000-token abort):
- A call billing more than 40,000 output tokens is written to `failed.jsonl` with its cost, and it is
  not scored.
- Like a reply cut off at max_tokens, it is asked once more in the resume pass.

**Abort rules (only these).** The run stops on:
- more than 3 calls over the runaway limit, among the calls made under this amendment;
- a served provider other than GMICloud, or a call without the pinned settings;
- the cap.

Amendment 4's zero-reasoning rule no longer stops the run; calls with zero reasoning tokens are
counted and reported. On a stop, the run is logged, not restarted, and analysed as recorded.

**Budget.**
- **Cap:** $1.40 for the spend under this amendment.
- **Fit:** run F's recorded $3.1146 plus $1.40 is $4.5146, within the $4.90 limit.
- **Expected:** about $0.80 (516 review calls at run 2t's mean of $0.00154).

**Timing of the run.** It starts at 08:00 EAT on Wednesday 11 November 2026, with no start after
12:00. It is stopped at 15:00.

**Analysis.**
- **Complete run:** `results/v3-roc-deepseek-think-complete/analysis-roc.txt`, with all three arms
  and Amendment 1's method.
  - The primary comparison is unchanged: ΔAUC 5-attributed − 1-diff.
  - Secondary: ΔAUC 7-random − 1-diff (section 4, as for every arm), and ΔAUC 5-attributed −
    7-random (new section 4b, with the same bootstrap and readings).
- **`compare-2c.txt`** for the complete run: Amendment 4's between-run secondary, arms 1-diff and
  5-attributed.
- **The 330-call partial analysis** is reported beside the complete one.

Nothing is dropped or chosen by its result.

**Code.** All new or changed code is under `experiments/`:
- `run_structure.py`: `--runaway-tokens`, `--no-repeat-checks`;
- `analyse_roc.py`: optional `A:B` pairs for section 4b; without them the output is unchanged
  (checked on runs 1, 2, 2c, 4c and 2t);
- `roc_tools.py`: guard_a5, daysplit;
- `roc_run_think_a5.sh` and `launch_roc_think_a5.sh`.

**Addendum (11 November 2026, 12:06 EAT; before the retry calls).** Decided by the author after
seeing the complete results. The run finished at 09:53 (commit f4d6e7b). Pass 1 got `HTTP 400 Bad
Request` on 42 calls, and pass 2 got 38 of them back. Four calls still have no record: 1-diff and
5-attributed of two defect items in shard 3 (`dask/delayed.py::delayed::default_flip::414` and
`numba/core/cgutils.py::get_item_pointer2::default_flip::739`).
- The error text was not logged. The errors were not billed: the balance fell $0.7596, against
  $0.7612 recorded.
- These 4 calls are asked once more, with the same settings and flags, on shard 3 only. No
  manipulation check falls on these items.
- This starts after the 12:00 rule, with the author's approval, and ends by 15:00. The expected cost
  is about $0.005, within the $1.40 cap.
- `experiments/llm.py` now writes the first 300 characters of an HTTP error's body into the error
  message. Nothing else changes.
- Replies are recorded as they come. A call that fails again stays missing, and this is reported.
- `analysis-roc.txt` and `compare-2c.txt` are rerun on the complete folder. The 09:53 versions stay
  in git history.
