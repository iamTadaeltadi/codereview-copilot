#!/bin/zsh
# Run F model run (paper/PREREG-F.md, Amendment 1), as launched by experiments/launch_roc.sh
zsh experiments/roc_run.sh deepseek deepseek/deepseek-v3.2 1.85 1-diff,7-random,2b-snippets,5-attributed 
