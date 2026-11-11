#!/bin/zsh
# Run 2g (paper/PREREG-F.md, Amendment 6), as launched by experiments/launch_roc_nothink_gmi.sh
OPENROUTER_REASONING='{"enabled": false}' OPENROUTER_PROVIDER='{"order": ["gmicloud/fp8"], "allow_fallbacks": false, "require_parameters": true}' CTRL_NAME=GMICloud zsh experiments/roc_run_nothink.sh smoke deepseek-nothink-gmi roc-smoke-deepseek-nothink-gmi
