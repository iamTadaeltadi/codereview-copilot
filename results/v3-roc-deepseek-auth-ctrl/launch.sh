#!/bin/zsh
# Run F model run (paper/PREREG-F.md, Amendment 3), as launched by experiments/launch_roc.sh
OPENROUTER_REASONING='{"enabled": false}' OPENROUTER_PROVIDER='{"order": ["atlas-cloud/fp8"], "allow_fallbacks": false, "require_parameters": true}' CTRL_NAME=AtlasCloud zsh experiments/roc_run.sh deepseek-auth-ctrl deepseek/deepseek-v3.2 0.50 1-diff,2b-snippets,5-attributed --authoritative
