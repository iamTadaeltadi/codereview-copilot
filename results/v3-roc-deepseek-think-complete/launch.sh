#!/bin/zsh
# Run 2t completed with 7-random added (paper/PREREG-F.md, Amendment 5), as launched by experiments/launch_roc_think_a5.sh
# Amendment 4's part of the run: results/v3-roc-deepseek-think/launch.sh
OPENROUTER_REASONING='{"enabled": true}' OPENROUTER_PROVIDER='{"order": ["gmicloud/fp8"], "allow_fallbacks": false, "require_parameters": true}' CTRL_NAME=GMICloud zsh experiments/roc_run_think_a5.sh deepseek-think 1.40 4.90
