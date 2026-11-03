#!/bin/zsh
# Neutral-prompt defects (277, nine arms) on deepseek-v3.2, PLAN.md section 13: three interleaved shards in parallel,
# same per-call settings as results/v3-neutral-gpt4omini (model changed) and results/v3twins-neutral-deepseek (benchmark changed).
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
mkdir -p runs/v3-shards
$PY - <<'PYEOF'
lines = [l for l in open("data/crossfile-v3.jsonl").read().splitlines() if l.strip()]
for s in range(3):
    open(f"runs/v3-shards/crossfile-v3-shard{s}.jsonl", "w").write("\n".join(l for i, l in enumerate(lines) if i % 3 == s) + "\n")
PYEOF
cost() { $PY - <<'PYEOF'
import json, glob
t = 0.0
for f in glob.glob("runs/v3-neutral-deepseek-shard*/structure.jsonl"):
    for l in open(f):
        if l.strip(): t += json.loads(l).get("usage", {}).get("cost_usd") or 0
print(f"{t:.4f}")
PYEOF
}
pids=()
for s in 0 1 2; do
  mkdir -p runs/v3-neutral-deepseek-shard$s
  $PY -u experiments/run_structure.py --name v3-neutral-deepseek-shard$s --limit 400 --encoding tag --model deepseek/deepseek-v3.2 \
      --neutral-prompt --benchmark runs/v3-shards/crossfile-v3-shard$s.jsonl > runs/v3-neutral-deepseek-shard$s/run.log 2>&1 &
  pids+=($!)
done
alive() { for p in $pids; do kill -0 $p 2>/dev/null && return 0; done; return 1; }
while alive; do
  sleep 60; c=$(cost); echo "$(date +%H:%M:%S) cost=$c" >> runs/v3-neutral-deepseek-cost.log
  if [ "$($PY -c "print(1 if $c > 1.5 else 0)")" = "1" ]; then kill $pids 2>/dev/null; echo "STOPPED: cost $c passed the 1.50 rule" >> runs/v3-neutral-deepseek-cost.log; break; fi
done
wait
echo "V3-NEUTRAL-DEEPSEEK-DONE cost=$(cost)"
