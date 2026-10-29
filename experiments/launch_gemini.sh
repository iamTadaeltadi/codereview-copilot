#!/bin/zsh
# gemini-2.5-flash, thinking off, numbered diff: c-CRAB A,B (+flag) then Cx; v3 neutral defects; v3 neutral twins.
# Three streams in parallel; one watcher kills all if the summed recorded cost passes $3.00.
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY=/private/tmp/claude-501/-Users-tadaelshewarega/9c0408ce-8c21-4e7c-a0f6-92330e46007d/scratchpad/venv/bin/python
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents; export OPENROUTER_REASONING='{"enabled": false}'
MODEL=google/gemini-2.5-flash
cost() { $PY - <<'PYEOF'
import json,glob
t=0.0
for f in glob.glob("runs/ccrab-gem-*/raw.jsonl")+glob.glob("runs/v3*-gemini/structure.jsonl")+glob.glob("runs/v3*-gemini/manipulation.jsonl"):
    for l in open(f):
        if l.strip():
            r=json.loads(l); t+=(r.get("usage",{}).get("cost_usd") if "usage" in r else r.get("cost")) or 0
print(f"{t:.4f}")
PYEOF
}
mkdir -p runs/ccrab-gem-main runs/ccrab-gem-Cx runs/v3-neutral-gemini runs/v3twins-neutral-gemini
( $PY -u experiments/run.py --name ccrab-gem-main --conditions A,B --prefer-cross-file --limit 400 --budget 3000 --hops 3 --depth 3 --tolerance 5 --model $MODEL > runs/ccrab-gem-main/run.log 2>&1
  $PY -u experiments/run.py --name ccrab-gem-Cx --conditions C --prefer-cross-file --limit 400 --budget 3000 --hops 3 --depth 3 --tolerance 5 --model $MODEL > runs/ccrab-gem-Cx/run.log 2>&1 ) & P1=$!
$PY -u experiments/run_structure.py --name v3-neutral-gemini --limit 400 --encoding tag --model $MODEL --neutral-prompt --benchmark data/crossfile-v3.jsonl --arms 1-diff,2-evidence,5-attributed,7-random > runs/v3-neutral-gemini/run.log 2>&1 & P2=$!
$PY -u experiments/run_structure.py --name v3twins-neutral-gemini --limit 400 --encoding tag --model $MODEL --neutral-prompt --benchmark data/crossfile-v3-twins.jsonl --arms 1-diff,2-evidence,5-attributed,7-random > runs/v3twins-neutral-gemini/run.log 2>&1 & P3=$!
while kill -0 $P1 2>/dev/null || kill -0 $P2 2>/dev/null || kill -0 $P3 2>/dev/null; do
  sleep 60; c=$(cost); echo "$(date +%H:%M:%S) cost=$c" >> runs/gemini-cost.log
  if [ "$($PY -c "print(1 if $c > 3.0 else 0)")" = "1" ]; then
    pkill -f "experiments/run.py --name ccrab-gem" ; pkill -f "run_structure.py --name v3"; echo "STOPPED: cost $c passed the 3.00 rule" >> runs/gemini-cost.log; break
  fi
done
wait; echo "GEMINI-DONE cost=$(cost)"
