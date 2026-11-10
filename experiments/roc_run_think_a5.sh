#!/bin/zsh
# Run 2t completed, with 7-random added (paper/PREREG-F.md, Amendment 5): deepseek-v3.2, reasoning on,
# GMICloud fp8 pinned, max_tokens 16,000. The same six seeded shards are walked in their fixed order;
# only item x arm calls with no record are asked (1-diff and 5-attributed left over from Amendment 4's
# run, and 7-random on every item), each item's missing arms back to back in an order shuffled with
# seed 0. A call over 40,000 output tokens is logged as failed (cost counted, not scored). The caller
# exports OPENROUTER_REASONING, OPENROUTER_PROVIDER and CTRL_NAME.
#   roc_run_think_a5.sh TAG CAP LIMIT
# Two passes (the second asks once more every call with no record: network errors, cut-off replies and
# calls over the runaway limit). A watcher every 30 s and the end of each pass: exit 6 on an abort
# rule (roc_tools.py guard_a5), exit 4 when the spend under Amendment 5 passes CAP or run F's recorded
# total passes LIMIT, exit 8 at 15:00 on 11 Nov 2026 (EAT); 0 when finished.
set -u
TAG=$1 CAP=$2 LIMIT=$3
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"; T() { "$PY" experiments/roc_tools.py "$@"; }
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
MODEL=deepseek/deepseek-v3.2 ARMS=1-diff,7-random,5-attributed MAXRUN=3
SET=(--limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip --model $MODEL
     --max-tokens 16000 --check-max-tokens 16000 --arm-order-seed 0 --runaway-tokens 40000 --no-repeat-checks)
LOG=runs/roc-$TAG-cost.log
RUNCOST=("roc-smoke-$TAG-*" "roc-$TAG-mixed-shard*")
stamp() { date '+%m-%d %H:%M:%S'; }
gt() { $PY -c "import sys; print(1 if float(sys.argv[1]) > float(sys.argv[2]) else 0)" $1 $2; }
new() { $PY -c "import sys; print(f'{float(sys.argv[1]) - float(sys.argv[2]):.4f}')" $(T cost "${RUNCOST[@]}") $BASE; }
BASE=$(T cost "${RUNCOST[@]}")
echo "$(stamp) $TAG Amendment 5 start: arms=$ARMS cap=$CAP (spend under Amendment 5) limit=$LIMIT recorded before=$BASE flags=${SET[*]} OPENROUTER_REASONING=$OPENROUTER_REASONING OPENROUTER_PROVIDER=$OPENROUTER_PROVIDER CTRL_NAME=$CTRL_NAME" >> $LOG
for pass in 1 2; do
  pids=()
  for s in 0 1 2 3 4 5; do
    name=roc-$TAG-mixed-shard$s
    $PY -u experiments/run_structure.py --name $name "${SET[@]}" --arms $ARMS \
        --benchmark runs/roc-items/think-mixed-shard$s.jsonl > runs/$name/run-a5-pass$pass.log 2>&1 &
    pids+=($!)
  done
  alive() { for p in $pids; do kill -0 $p 2>/dev/null && return 0; done; return 1; }
  while alive; do
    sleep 30; c=$(new); total=$(T cost "roc-*"); g=$(T guard_a5 $CTRL_NAME $MAXRUN "roc-$TAG-mixed-shard*")
    echo "$(stamp) A5 pass $pass spend=$c total=$total guard: $g" >> $LOG
    case $g in ABORT*) kill $pids 2>/dev/null; wait
      echo "$(stamp) ABORTED (Amendment 5 rule): $TAG $g; spend $c" | tee -a $LOG; exit 6;; esac
    if [ "$(gt $c $CAP)" = "1" ] || [ "$(gt $total $LIMIT)" = "1" ]; then
      kill $pids 2>/dev/null; wait
      echo "$(stamp) STOPPED: $TAG spend $c (cap $CAP), run F total $total (limit $LIMIT)" | tee -a $LOG; exit 4
    fi
    if [ "$(date +%Y%m%d%H%M)" -ge 202611111500 ]; then
      kill $pids 2>/dev/null; wait
      echo "$(stamp) STOPPED at the 15:00 deadline: $TAG spend $c" | tee -a $LOG; exit 8
    fi
  done
  wait
  g=$(T guard_a5 $CTRL_NAME $MAXRUN "roc-$TAG-mixed-shard*")
  echo "$(stamp) A5 end of pass $pass guard: $g" >> $LOG
  case $g in ABORT*) echo "$(stamp) ABORTED (Amendment 5 rule): $TAG $g; spend $(new)" | tee -a $LOG; exit 6;; esac
done
echo "$(stamp) $TAG Amendment 5 done spend=$(new) run 2t=$(T cost "${RUNCOST[@]}") total=$(T cost "roc-*")" | tee -a $LOG
