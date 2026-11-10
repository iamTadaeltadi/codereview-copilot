# Run F: deepseek-auth (paper/PREREG-F.md, Amendment 1)

- model: `deepseek/deepseek-v3.2`; arms: 1-diff,2b-snippets,5-attributed; cap $1.45; extra flags: --authoritative
- shared flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip
- outcome: finished
- recorded cost of this run (smoke included): $0.2904; run F total so far: $1.8886
- log: 11-10 15:45:35 deepseek-auth smoke: OK

Files: launch.sh (the command), structure-{defects,twins}-shard{0,1,2}.jsonl (one record per item and arm),
manipulation-*.jsonl, run-*.log, smoke/ (the 3 smoke calls), cost.log, analysis-roc.txt
(`python3 experiments/analyse_roc.py results/v3-roc-deepseek-auth`).
