#!/bin/zsh
# Run F model run (paper/PREREG-F.md, Amendment 1), as launched by experiments/launch_roc.sh
zsh experiments/roc_run.sh gpt4omini-auth openai/gpt-4o-mini 0.40 1-diff,2b-snippets,5-attributed --authoritative
