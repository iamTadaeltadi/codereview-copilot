#!/bin/zsh
# Run 2t (paper/PREREG-F.md, Amendment 4), as launched by experiments/launch_roc_think.sh
OPENROUTER_REASONING='{"enabled": true}' OPENROUTER_PROVIDER='{"order": ["atlas-cloud/fp8"], "allow_fallbacks": false, "require_parameters": true}' CTRL_NAME=AtlasCloud zsh experiments/roc_run_think.sh smoke deepseek-think 2048 roc-smoke-deepseek-think-atlas-cloud-2048
OPENROUTER_REASONING='{"enabled": true}' OPENROUTER_PROVIDER='{"order": ["atlas-cloud/fp8"], "allow_fallbacks": false, "require_parameters": true}' CTRL_NAME=AtlasCloud zsh experiments/roc_run_think.sh smoke deepseek-think 16000 roc-smoke-deepseek-think-atlas-cloud-16000
OPENROUTER_REASONING='{"enabled": true}' OPENROUTER_PROVIDER='{"order": ["gmicloud/fp8"], "allow_fallbacks": false, "require_parameters": true}' CTRL_NAME=GMICloud zsh experiments/roc_run_think.sh smoke deepseek-think 16000 roc-smoke-deepseek-think-gmicloud-16000
OPENROUTER_REASONING='{"enabled": true}' OPENROUTER_PROVIDER='{"order": ["gmicloud/fp8"], "allow_fallbacks": false, "require_parameters": true}' CTRL_NAME=GMICloud zsh experiments/roc_run_think.sh run deepseek-think 16000 2.30 4.90
