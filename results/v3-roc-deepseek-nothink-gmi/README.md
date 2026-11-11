# Run F: run 2g, deepseek-v3.2 with reasoning off on GMICloud (paper/PREREG-F.md, Amendment 6)

- model: `deepseek/deepseek-v3.2`; arms: 1-diff, 7-random, 5-attributed; items: run 2c's 139 default-flip defects and 143 twins, in run 2t's six seeded mixed shards
- flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip --max-tokens 2048 --check-max-tokens 2048 --arm-order-seed 0 --no-repeat-checks; temperature 0.1
- settings on every call: OPENROUTER_REASONING=`{"enabled": false}` OPENROUTER_PROVIDER=`{"order": ["gmicloud/fp8"], "allow_fallbacks": false, "require_parameters": true}` (served name expected: GMICloud; no fallback provider)
- timing: the six shards run in parallel; each item's three arms back to back, in an order shuffled with seed 0, so all arms run at the same time
- cap $0.60 (smoke included); run F limit $4.90
- smoke test: FAIL struc ch.py::verify_evidence::default_flip::32 reasoning_tokens 5444; struc ch.py::verify_evidence::default_flip::32 output tokens 5674; struc ::jobs_list_str::default_flip::745::safe reasoning_tokens 3076; struc ::jobs_list_str::default_flip::745::safe output tokens 3316; struc r.py::create_html_repr::default_flip::94 reasoning_tokens 1651; struc r.py::create_html_repr::default_flip::94 output tokens 1881; struc _list_repr_html::default_flip::857::safe reasoning_tokens 5654; struc _list_repr_html::default_flip::857::safe output tokens 5887; struc y::prepare_table_data::default_flip::157 reasoning_tokens 1887; struc y::prepare_table_data::default_flip::157 output tokens 2112; struc testation_token::default_flip::135::safe reasoning_tokens 7983; struc testation_token::default_flip::135::safe output tokens 8107; manip ch.py::verify_evidence::default_flip::32 reasoning_tokens 120
- outcome: did not start: smoke test failed: FAIL struc ch.py::verify_evidence::default_flip::32 reasoning_tokens 5444; struc ch.py::verify_evidence::default_flip::32 output tokens 5674; struc ::jobs_list_str::default_flip::745::safe reasoning_tokens 3076; struc ::jobs_list_str::default_flip::745::safe output tokens 3316; struc r.py::create_html_repr::default_flip::94 reasoning_tokens 1651; struc r.py::create_html_repr::default_flip::94 output tokens 1881; struc _list_repr_html::default_flip::857::safe reasoning_tokens 5654; struc _list_repr_html::default_flip::857::safe output tokens 5887; struc y::prepare_table_data::default_flip::157 reasoning_tokens 1887; struc y::prepare_table_data::default_flip::157 output tokens 2112; struc testation_token::default_flip::135::safe reasoning_tokens 7983; struc testation_token::default_flip::135::safe output tokens 8107; manip ch.py::verify_evidence::default_flip::32 reasoning_tokens 120
- recorded cost of this run (smoke included): $0.0103; run F total: $3.8946 ($3.8843 before this run)
- OpenRouter balance: $1.0363 before the first call, $1.0288 now
- log: 11-11 13:11:02 deepseek-nothink-gmi did not start: smoke test failed: FAIL struc ch.py::verify_evidence::default_flip::32 reasoning_tokens 5444; struc ch.py::verify_evidence::default_flip::32 output tokens 5674; struc ::jobs_list_str::default_flip::745::safe reasoning_tokens 3076; struc ::jobs_list_str::default_flip::745::safe output tokens 3316; struc r.py::create_html_repr::default_flip::94 reasoning_tokens 1651; struc r.py::create_html_repr::default_flip::94 output tokens 1881; struc _list_repr_html::default_flip::857::safe reasoning_tokens 5654; struc _list_repr_html::default_flip::857::safe output tokens 5887; struc y::prepare_table_data::default_flip::157 reasoning_tokens 1887; struc y::prepare_table_data::default_flip::157 output tokens 2112; struc testation_token::default_flip::135::safe reasoning_tokens 7983; struc testation_token::default_flip::135::safe output tokens 8107; manip ch.py::verify_evidence::default_flip::32 reasoning_tokens 120

HTTP and other call errors in the logs (no record; asked once more in the next pass):

```
none
```

Calls cut off at max_tokens (billed, not scored):

```
none
```

Smoke usage objects and finish reasons (raw; written before the run was launched):

```
roc-smoke-deepseek-nothink-gmi review s/attestation/dispatch.py::verify_evidence::default_flip::32 5-attributed: finish_reason='stop' provider='GMICloud' reasoning_tokens=5444 output_tokens=5674 usage={"completion_tokens": 5674, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 5444}, "cost": 0.0020917944, "cost_details": {"upstream_inference_completions_cost": 0.0017566704, "upstream_inference_cost": 0.0020917944, "upstream_inference_prompt_cost": 0.000335124}, "is_byok": false, "prompt_tokens": 1605, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 7279}
roc-smoke-deepseek-nothink-gmi review syft_job/job_repr.py::jobs_list_str::default_flip::745::safe 5-attributed: finish_reason='stop' provider='GMICloud' reasoning_tokens=3076 output_tokens=3316 usage={"completion_tokens": 3316, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 3076}, "cost": 0.0013314816, "cost_details": {"upstream_inference_completions_cost": 0.0010266336, "upstream_inference_cost": 0.0013314816, "upstream_inference_prompt_cost": 0.000304848}, "is_byok": false, "prompt_tokens": 1460, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 4776}
roc-smoke-deepseek-nothink-gmi review ui/pydantic_html_repr.py::create_html_repr::default_flip::94 5-attributed: finish_reason='stop' provider='GMICloud' reasoning_tokens=1651 output_tokens=1881 usage={"completion_tokens": 1881, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 1651}, "cost": 0.0008905464, "cost_details": {"upstream_inference_completions_cost": 0.0005823576, "upstream_inference_cost": 0.0008905464, "upstream_inference_prompt_cost": 0.0003081888}, "is_byok": false, "prompt_tokens": 1476, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 3357}
roc-smoke-deepseek-nothink-gmi review ob/job_repr.py::jobs_list_repr_html::default_flip::857::safe 5-attributed: finish_reason='stop' provider='GMICloud' reasoning_tokens=5654 output_tokens=5887 usage={"completion_tokens": 5887, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 5654}, "cost": 0.0021111768, "cost_details": {"upstream_inference_completions_cost": 0.0018226152, "upstream_inference_cost": 0.0021111768, "upstream_inference_prompt_cost": 0.0002885616}, "is_byok": false, "prompt_tokens": 1382, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 7269}
roc-smoke-deepseek-nothink-gmi review ook_ui/table_utils.py::prepare_table_data::default_flip::157 5-attributed: finish_reason='stop' provider='GMICloud' reasoning_tokens=1887 output_tokens=2112 usage={"completion_tokens": 2112, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 1887}, "cost": 0.0009595584, "cost_details": {"upstream_inference_completions_cost": 0.0006538752, "upstream_inference_cost": 0.0009595584, "upstream_inference_prompt_cost": 0.0003056832}, "is_byok": false, "prompt_tokens": 1464, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 3576}
roc-smoke-deepseek-nothink-gmi review _space.py::verify_attestation_token::default_flip::135::safe 5-attributed: finish_reason='stop' provider='GMICloud' reasoning_tokens=7983 output_tokens=8107 usage={"completion_tokens": 8107, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 7983}, "cost": 0.002843172, "cost_details": {"upstream_inference_completions_cost": 0.0025099272, "upstream_inference_cost": 0.002843172, "upstream_inference_prompt_cost": 0.0003332448}, "is_byok": false, "prompt_tokens": 1596, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 9703}
roc-smoke-deepseek-nothink-gmi check s/attestation/dispatch.py::verify_evidence::default_flip::32 5-attributed: finish_reason='stop' provider='GMICloud' reasoning_tokens=120 output_tokens=127 usage={"completion_tokens": 127, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 120}, "cost": 6.4584e-05, "cost_details": {"upstream_inference_completions_cost": 3.93192e-05, "upstream_inference_cost": 6.4584e-05, "upstream_inference_prompt_cost": 2.52648e-05}, "is_byok": false, "prompt_tokens": 121, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 248}
```

Files: launch.sh (the commands), structure-mixed-shard{0..5}.jsonl (one record per item and arm),
manipulation-mixed-shard*.jsonl, failed-mixed-shard*.jsonl (if any), run-mixed-shard*-pass{1,2}.log,
smoke/ (the smoke test), items/ (the six shards and the smoke items), cost.log,
analysis-roc.txt (`python3 experiments/analyse_roc.py results/v3-roc-deepseek-nothink-gmi 5-attributed:7-random`),
compare-2t.txt (`python3 experiments/compare_roc_runs.py results/v3-roc-deepseek-think-complete results/v3-roc-deepseek-nothink-gmi --arms 1-diff,7-random,5-attributed --amendment 6`;
A = 2t, reasoning on; B = 2g, reasoning off; same provider),
compare-2c.txt (`python3 experiments/compare_roc_runs.py results/v3-roc-deepseek-nothink-gmi results/v3-roc-deepseek-ctrl --amendment 6`; A = 2g on GMICloud,
B = 2c on AtlasCloud, both reasoning off; descriptive).

## Probes of other reasoning-off settings (Amendment 6 addendum; written 11 Nov 2026 15:13 EAT)

- on GMICloud fp8, same pin, no fallback; 5-attributed, the run's flags, no manipulation check; items: the defect `create_html_repr::94`, then the twin `jobs_list_str::745::safe` (runs/roc-items/probe2.jsonl)
- a setting passes only if both calls report reasoning_tokens 0, served by GMICloud with the settings sent; the second call is made only if the first reports 0; probe cap $0.01
- setting 0 `{"enabled": false}` (the smoke test above): reasoning_tokens 120, 5444, 3076, 1651, 5654, 1887, 7983 on its 7 calls
- setting 1 `{"effort": "none"}`: FAIL struc r.py::create_html_repr::default_flip::94 reasoning_tokens 1350
- setting 2 no reasoning field: FAIL struc r.py::create_html_repr::default_flip::94 reasoning_tokens 2292
- setting 3 `{"max_tokens": 0}`: FAIL struc r.py::create_html_repr::default_flip::94 reasoning_tokens 2159
- outcome: no setting passed: GMICloud ignored every reasoning-off setting tried; run 2g is not run
- recorded cost of the probes: $0.0025; run 2g so far (smoke test and probes): $0.0128; run F total: $3.8971; OpenRouter balance $1.0260 before the probes, $1.0252 now

Probe calls (raw usage objects):

```
s1:
    struc r.py::create_html_repr::default_flip::94: provider='GMICloud' reasoning_tokens=1350 output_tokens=1578 finish_reason='stop' usage={"completion_tokens": 1578, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 1350}, "cost": 0.0007967376, "cost_details": {"upstream_inference_completions_cost": 0.0004885488, "upstream_inference_cost": 0.0007967376, "upstream_inference_prompt_cost": 0.0003081888}, "is_byok": false, "prompt_tokens": 1476, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 3054}
s2:
    struc r.py::create_html_repr::default_flip::94: provider='GMICloud' reasoning_tokens=2292 output_tokens=2530 finish_reason='stop' usage={"completion_tokens": 2530, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 2292}, "cost": 0.000899784, "cost_details": {"upstream_inference_completions_cost": 0.000783288, "upstream_inference_cost": 0.000899784, "upstream_inference_prompt_cost": 0.000116496}, "is_byok": false, "prompt_tokens": 1476, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 1024, "video_tokens": 0}, "total_tokens": 4006}
s3:
    struc r.py::create_html_repr::default_flip::94: provider='GMICloud' reasoning_tokens=2159 output_tokens=2331 finish_reason='stop' usage={"completion_tokens": 2331, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 2159}, "cost": 0.0008381736, "cost_details": {"upstream_inference_completions_cost": 0.0007216776, "upstream_inference_cost": 0.0008381736, "upstream_inference_prompt_cost": 0.000116496}, "is_byok": false, "prompt_tokens": 1476, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 1024, "video_tokens": 0}, "total_tokens": 3807}
```

HTTP and other call errors in the probe logs:

```
none
```

Files: probe-s{1,2,3}/ (records and logs of each probe made), items/probe2.jsonl, cost.log; commands: experiments/probe_nothink_gmi.sh.
