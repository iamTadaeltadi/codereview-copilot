# Run F: run 2t completed, with 7-random added (paper/PREREG-F.md, Amendment 5)

- model: `deepseek/deepseek-v3.2`; arms: 1-diff, 7-random, 5-attributed; items: run 2c's 139 default-flip defects and 143 twins
- flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip --max-tokens 16000 --check-max-tokens 16000 --arm-order-seed 0 (Amendment 5 adds --runaway-tokens 40000 --no-repeat-checks); temperature 0.1
- settings on every call: OPENROUTER_REASONING=`{"enabled": true}` OPENROUTER_PROVIDER=`{"order": ["gmicloud/fp8"], "allow_fallbacks": false, "require_parameters": true}` (served name expected: GMICloud)
- the records are Amendment 4's run (results/v3-roc-deepseek-think/, stopped at 22:20 on 10 Nov after 330 review calls) followed by the calls under Amendment 5; recorded calls were not asked again
- timing, review calls per arm and day: 1-diff: Tue 10 Nov 165, Wed 11 Nov 115; 7-random: Wed 11 Nov 282; 5-attributed: Tue 10 Nov 165, Wed 11 Nov 115
- cap $1.40 for the spend under Amendment 5; run F limit $4.90
- outcome of the Amendment 5 part: finished
- recorded cost: run 2t before Amendment 5 $0.5304; run 2t now $1.2916 (smoke tests included); run F total $3.8758
- OpenRouter balance: $1.8059 before the first Amendment 5 call, $1.0463 now
- log: 11-11 09:53:18 deepseek-think Amendment 5 done spend=0.7612 run 2t=1.2916 total=3.8758
- all calls of the run: calls 878 (reviews 842, manipulation checks 36, cut off 0, over the runaway limit 0); providers {'GMICloud': 878}; reasoning tokens max 53070, median 2460.5, zero on 0; output tokens max 53234, median 2661.5; finish reasons {'structure:stop': 842, 'manipulation:stop': 36}
- abort rules at the end: OK 878 calls, provider reported on 878, over the runaway limit 0, reasoning_tokens 0 on 0

Calls logged as failed (cut off, or over the runaway limit: billed, not scored):

```
none
```

Files: launch.sh, structure-mixed-shard{0..5}.jsonl (one record per item and arm, both amendments),
manipulation-mixed-shard*.jsonl, failed-mixed-shard*.jsonl, run-mixed-shard*-amendment4.log and
run-mixed-shard*-amendment5-pass{1,2}.log, items/ (the six shards as run), cost.log (both amendments),
analysis-roc.txt (`python3 experiments/analyse_roc.py results/v3-roc-deepseek-think-complete 5-attributed:7-random`),
compare-2c.txt (`python3 experiments/compare_roc_runs.py results/v3-roc-deepseek-think-complete results/v3-roc-deepseek-ctrl`).
The smoke tests of run 2t are in results/v3-roc-deepseek-think/smoke-*/.

## Notes (added 11 November 2026, after the retry)

The lines above were written when the run ended at 09:53 (commit f4d6e7b). The records, `cost.log`,
`analysis-roc.txt` and `compare-2c.txt` now include the retry below.

**HTTP 400 errors.**
- Pass 1 got `HTTP 400 Bad Request` on 42 calls, in shards 1 to 5, mostly at their last items.
- Pass 2 asked them again. 38 came back, and 4 got HTTP 400 again: arms 1-diff and 5-attributed of
  two defect items in shard 3 (`xf::dask__dask::dask/delayed.py::delayed::default_flip::414` and
  `xf::numba__numba::numba/core/cgutils.py::get_item_pointer2::default_flip::739`).
- At 09:53 the run therefore had 842 of 846 review records.
- The error text was not logged, so the cause is unknown. The errors were not billed.
- These calls are not in `failed.jsonl`, which holds only billed calls (cut off or over the runaway
  limit).

**Retry** (`paper/PREREG-F.md`, Amendment 5 addendum, committed 12:06 before the first retry call).
- The 4 calls were asked once more, from 12:06 to 12:13, with the same settings and flags, on shard 3
  only (log: `run-mixed-shard3-amendment5-retry.log`). This started after Amendment 5's 12:00 rule,
  with the author's approval.
- All 4 came back: finish reason stop, served by GMICloud, 2,579 to 12,023 output tokens, $0.0085 in
  total. No manipulation check falls on these items.
- `experiments/llm.py` now logs the body of an HTTP error, but no call failed during the retry.

**After the retry.**
- Calls: 882 (846 reviews, 36 manipulation checks). 0 cut off, 0 over the runaway limit, all served
  by GMICloud, 0 with zero reasoning tokens.
- Review calls per arm and day:
  - 1-diff: 165 on Tuesday 10 November, 117 on Wednesday 11 November;
  - 7-random: 282 on Wednesday;
  - 5-attributed: 165 on Tuesday, 117 on Wednesday.
- Spend under Amendment 5: $0.7697 ($0.7612 + $0.0085), against the $1.40 cap.
- Run 2t: $1.3001 recorded. Run F total: $3.8843, against the $4.90 limit.
- OpenRouter balance: $1.0374.
- The first `analysis-roc.txt` and `compare-2c.txt` (842 records) are in git history at commit
  f4d6e7b.
