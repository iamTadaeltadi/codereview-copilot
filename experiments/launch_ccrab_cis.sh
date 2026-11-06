#!/bin/zsh
# Condition E, CIS context on c-CRAB (paper/PREREG-E.md). Run 4's flags, condition CIS, the
# precomputed context; gpt-4o-mini then deepseek-v3.2. A run is stopped when its own recorded cost
# passes $3.00. A rerun resumes: calls already scored are skipped, unscored ones are retried.
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
COMMON=(--limit 400 --budget 3000 --hops 3 --depth 3 --tolerance 5
        --plain-context --exclude-tests --callers-first --drop-class-seeds --prefer-cross-file
        --conditions CIS --external-context results/ccrab-cis/context-E-delivered.json)
cost() { $PY - "$1" <<'PYEOF'
import json, sys
t = 0.0
try:
    for l in open(f"runs/{sys.argv[1]}/raw.jsonl"):
        if l.strip(): t += json.loads(l).get("usage", {}).get("cost_usd") or 0
except FileNotFoundError:
    pass
print(f"{t:.4f}")
PYEOF
}
watch() { local pid=$1 name=$2; while kill -0 $pid 2>/dev/null; do sleep 60; c=$(cost $name)
  echo "$(date +%H:%M:%S) $name cost=$c" >> runs/ccrab-cis-cost.log
  if [ "$($PY -c "print(1 if $c > 3.0 else 0)")" = "1" ]; then kill $pid
    echo "STOPPED: $name cost $c passed the 3.00 rule" >> runs/ccrab-cis-cost.log; return 1; fi; done; return 0; }
run() { local name=$1 model=$2; mkdir -p runs/$name
  [ -f runs/$name/run.log ] && cp runs/$name/run.log runs/$name/run-$(date +%H%M%S).log
  $PY -u experiments/run.py --name $name --model $model "${COMMON[@]}" > runs/$name/run.log 2>&1 &
  local pid=$!; watch $pid $name || return 1; wait $pid; echo "$name exit $? cost=$(cost $name)"; }
run ccrab-cis-gpt-4o-mini openai/gpt-4o-mini
run ccrab-cis-deepseek-v3.2 deepseek/deepseek-v3.2
echo "CCRAB-CIS-DONE"
