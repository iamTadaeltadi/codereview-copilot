# Run F: gpt4omini (paper/PREREG-F.md, Amendment 1)

- model: `openai/gpt-4o-mini`; arms: 1-diff,7-random,2b-snippets,5-attributed; cap $1.00; extra flags: none
- shared flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip
- outcome: finished
- recorded cost of this run (smoke included): $0.2305; run F total so far: $0.2305
- log: 11-10 13:15:57 gpt4omini smoke: OK

Files: launch.sh (the command), structure-{defects,twins}-shard{0,1,2}.jsonl (one record per item and arm),
manipulation-*.jsonl, run-*.log, smoke/ (the 3 smoke calls), cost.log, analysis-roc.txt
(`python3 experiments/analyse_roc.py results/v3-roc-gpt4omini`).
