# Run F: deepseek-auth-ctrl (paper/PREREG-F.md, Amendment 3)

- model: `deepseek/deepseek-v3.2`; arms: 1-diff,2b-snippets,5-attributed; cap $0.50; extra flags: --authoritative
- shared flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip
- outcome: finished
- recorded cost of this run (smoke included): $0.2924; run F total so far: $2.5842
- log: 11-10 16:57:21 deepseek-auth-ctrl smoke: OK
- log: 11-10 17:23:18 deepseek-auth-ctrl smoke: OK
- settings on every call: OPENROUTER_REASONING=`{"enabled": false}` OPENROUTER_PROVIDER=`{"order": ["atlas-cloud/fp8"], "allow_fallbacks": false, "require_parameters": true}`
- calls seen: calls 888; providers {'AtlasCloud': 888}; reasoning_tokens max 0 (absent on 0); output tokens max 453

Smoke usage objects (raw, before the run was launched):

```
roc-smoke-deepseek-auth-ctrl/structure.jsonl s/attestation/dispatch.py::verify_evidence::default_flip::32 5-attributed: provider='AtlasCloud' reasoning_tokens=0 output_tokens=108 usage={"completion_tokens": 108, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 0}, "cost": 0.00045054, "cost_details": {"upstream_inference_completions_cost": 4.104e-05, "upstream_inference_cost": 0.00045054, "upstream_inference_prompt_cost": 0.0004095}, "is_byok": false, "prompt_tokens": 1575, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 1683}
roc-smoke-deepseek-auth-ctrl/structure.jsonl ui/pydantic_html_repr.py::create_html_repr::default_flip::94 5-attributed: provider='AtlasCloud' reasoning_tokens=0 output_tokens=108 usage={"completion_tokens": 108, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 0}, "cost": 0.00037358, "cost_details": {"upstream_inference_completions_cost": 4.104e-05, "upstream_inference_cost": 0.00037358, "upstream_inference_prompt_cost": 0.00033254}, "is_byok": false, "prompt_tokens": 1439, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 320, "video_tokens": 0}, "total_tokens": 1547}
roc-smoke-deepseek-auth-ctrl/structure.jsonl ook_ui/table_utils.py::prepare_table_data::default_flip::157 5-attributed: provider='AtlasCloud' reasoning_tokens=0 output_tokens=224 usage={"completion_tokens": 224, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 0}, "cost": 0.00045822, "cost_details": {"upstream_inference_completions_cost": 8.512e-05, "upstream_inference_cost": 0.00045822, "upstream_inference_prompt_cost": 0.0003731}, "is_byok": false, "prompt_tokens": 1435, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 0, "video_tokens": 0}, "total_tokens": 1659}
roc-smoke-deepseek-auth-ctrl/manipulation.jsonl s/attestation/dispatch.py::verify_evidence::default_flip::32 5-attributed: provider='AtlasCloud' reasoning_tokens=0 output_tokens=6 usage={"completion_tokens": 6, "completion_tokens_details": {"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 0}, "cost": 1.424e-05, "cost_details": {"upstream_inference_completions_cost": 2.28e-06, "upstream_inference_cost": 1.424e-05, "upstream_inference_prompt_cost": 1.196e-05}, "is_byok": false, "prompt_tokens": 78, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": 0, "cached_tokens": 64, "video_tokens": 0}, "total_tokens": 84}
```

Files: launch.sh (the command), structure-{defects,twins}-shard{0,1,2}.jsonl (one record per item and arm),
manipulation-*.jsonl, run-*.log, smoke/ (the 3 smoke calls), cost.log, analysis-roc.txt
(`python3 experiments/analyse_roc.py results/v3-roc-deepseek-auth-ctrl`).
