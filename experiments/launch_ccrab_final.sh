#!/bin/zsh
# Final pre-registered c-CRAB run (paper/PLAN.md section 11): plain code-block context, callers-first
# graph walk without test files, class seeds dropped when their methods are seeds, numbered diff.
# Three sequential passes as before; stop if the summed recorded cost passes $2.00.
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY=/private/tmp/claude-501/-Users-tadaelshewarega/9c0408ce-8c21-4e7c-a0f6-92330e46007d/scratchpad/venv/bin/python
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
COMMON=(--limit 400 --budget 3000 --hops 3 --depth 3 --tolerance 5 --model openai/gpt-4o-mini
        --plain-context --exclude-tests --callers-first --drop-class-seeds)
cost() { $PY - <<'PYEOF'
import json,glob
t=0.0
for f in glob.glob("runs/ccrab-final-*/raw.jsonl"):
    for l in open(f):
        if l.strip(): t+=json.loads(l).get("usage",{}).get("cost_usd") or 0
print(f"{t:.4f}")
PYEOF
}
watch() { local pid=$1; while kill -0 $pid 2>/dev/null; do sleep 60; c=$(cost); echo "$(date +%H:%M:%S) cost=$c" >> runs/ccrab-final-cost.log
  if [ "$($PY -c "print(1 if $c > 2.0 else 0)")" = "1" ]; then kill $pid; echo "STOPPED: cost $c passed the 2.00 rule" >> runs/ccrab-final-cost.log; return 1; fi; done; return 0; }
run() { local name=$1; shift; mkdir -p runs/$name; $PY -u experiments/run.py --name $name "${COMMON[@]}" "$@" > runs/$name/run.log 2>&1 & local pid=$!; watch $pid || return 1; wait $pid; echo "$name exit $?"; }
run ccrab-final-main --conditions A,B,D --prefer-cross-file && run ccrab-final-Cx --conditions C --prefer-cross-file && run ccrab-final-C --conditions C
echo "CCRAB-FINAL-DONE cost=$(cost)"
