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
