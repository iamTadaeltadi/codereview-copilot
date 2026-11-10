# Run F: deepseek-ctrl (paper/PREREG-F.md, Amendment 3)

- model: `deepseek/deepseek-v3.2`; arms: 1-diff,7-random,2b-snippets,5-attributed; cap $0.70; extra flags: none
- shared flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip
- outcome: finished
- recorded cost of this run (smoke included): $0.4032; run F total so far: $2.2931
- log: 11-10 16:56:51 deepseek-ctrl smoke: OK
- log: 11-10 16:57:22 deepseek-ctrl smoke: OK
- settings on every call: OPENROUTER_REASONING=`{"enabled": false}` OPENROUTER_PROVIDER=`{"order": ["atlas-cloud/fp8"], "allow_fallbacks": false, "require_parameters": true}`
- calls seen: calls 1170; providers {'AtlasCloud': 1170}; reasoning_tokens max 0 (absent on 0); output tokens max 447

Smoke usage objects (raw, before the run was launched):

```
roc-smoke-deepseek-ctrl/structure.jsonl s/attestation/dispatch.py::verify_evidence::default_flip::32 5-attributed: provider='AtlasCloud' reasoning_tokens=0 output_tokens=108 usage={"completion_tokens": 108, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 0}, "cost": 0.00043182, "cost_details": {"upstream_inference_completions_cost": 4.104e-05, "upstream_inference_cost": 0.00043182, "upstream_inference_prompt_cost": 0.00039078}, "is_byok": false, "prompt_tokens": 1535, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 64, "video_tokens": 0}, "total_tokens": 1643}
roc-smoke-deepseek-ctrl/structure.jsonl ui/pydantic_html_repr.py::create_html_repr::default_flip::94 5-attributed: provider='AtlasCloud' reasoning_tokens=0 output_tokens=195 usage={"completion_tokens": 195, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 0}, "cost": 0.0004212, "cost_details": {"upstream_inference_completions_cost": 7.41e-05, "upstream_inference_cost": 0.0004212, "upstream_inference_prompt_cost": 0.0003471}, "is_byok": false, "prompt_tokens": 1399, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 128, "video_tokens": 0}, "total_tokens": 1594}
roc-smoke-deepseek-ctrl/structure.jsonl ook_ui/table_utils.py::prepare_table_data::default_flip::157 5-attributed: provider='AtlasCloud' reasoning_tokens=0 output_tokens=202 usage={"completion_tokens": 202, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 0}, "cost": 0.00043946, "cost_details": {"upstream_inference_completions_cost": 7.676e-05, "upstream_inference_cost": 0.00043946, "upstream_inference_prompt_cost": 0.0003627}, "is_byok": false, "prompt_tokens": 1395, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 1597}
roc-smoke-deepseek-ctrl/manipulation.jsonl s/attestation/dispatch.py::verify_evidence::default_flip::32 5-attributed: provider='AtlasCloud' reasoning_tokens=0 output_tokens=6 usage={"completion_tokens": 6, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 0}, "cost": 2.256e-05, "cost_details": {"upstream_inference_completions_cost": 2.28e-06, "upstream_inference_cost": 2.256e-05, "upstream_inference_prompt_cost": 2.028e-05}, "is_byok": false, "prompt_tokens": 78, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 84}
```

Files: launch.sh (the command), structure-{defects,twins}-shard{0,1,2}.jsonl (one record per item and arm),
manipulation-*.jsonl, run-*.log, smoke/ (the 3 smoke calls), cost.log, analysis-roc.txt
(`python3 experiments/analyse_roc.py results/v3-roc-deepseek-ctrl`).
