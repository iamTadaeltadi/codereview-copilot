# Run F: deepseek (paper/PREREG-F.md, Amendment 1)

- model: `deepseek/deepseek-v3.2`; arms: 1-diff,7-random,2b-snippets,5-attributed; cap $1.85; extra flags: none
- shared flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip
- outcome: finished
- recorded cost of this run (smoke included): $1.1956; run F total so far: $1.4261
- log: 11-10 13:25:35 deepseek smoke: OK
- log: 11-10 14:34:53 deepseek smoke: OK

Files: launch.sh (the command), structure-{defects,twins}-shard{0,1,2}.jsonl (one record per item and arm),
manipulation-*.jsonl, run-*.log, smoke/ (the 3 smoke calls), cost.log, analysis-roc.txt
(`python3 experiments/analyse_roc.py results/v3-roc-deepseek`).

## Notes

- **Amendment 2 (paper/PREREG-F.md).** The run started at 13:23 EAT with a $1.00 cap. At 14:33,
  with 417 calls recorded and $0.58 spent, Amendment 2 raised the cap to $1.85 and dropped run 5,
  because replies were about twice as long as projected (cost log and token counts only; no
  result was looked at). The run was stopped at 14:34 and restarted from its own records: every
  recorded (item, arm) was skipped, so nothing was asked twice. Up to 6 calls in flight at the stop
  were billed but not recorded. The logs of the interrupted pass are `run-*-interrupted.log`.
- **Smoke log.** The 3 smoke records in `smoke/structure.jsonl` are the originals (13:23-13:25,
  all OK, $0.0038). `smoke/run.log` is from the restart, which skipped the 3 recorded calls and
  made none; the original smoke log was overwritten.
- **Reply length changed during the run.** Mean output tokens per call were about 3,000-5,000 for
  the first 60-75% of each shard and about 150-180 afterwards, switching at about the same time in
  all six shards (173 items long, 109 short). Run 4 (`v3-roc-deepseek-auth`) was short throughout.
  The records do not name the OpenRouter provider, so the cause is not known. Each item's four arms
  were asked one after another, so arm comparisons stay paired within items. A post hoc,
  descriptive split by reply length is in `posthoc-reply-length.txt`
  (`python3 experiments/posthoc_reply_length.py results/v3-roc-deepseek results/v3-roc-deepseek-auth`).
