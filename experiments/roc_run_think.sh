#!/bin/zsh
# Run 2t of run F (paper/PREREG-F.md, Amendment 4): deepseek-v3.2 with reasoning on, arms 1-diff and
# 5-attributed, the 282 items of run 2c in six shuffled mixed shards (defects and twins together,
# each item's arm order shuffled with seed 0). The caller exports OPENROUTER_REASONING,
# OPENROUTER_PROVIDER and CTRL_NAME (the served provider name the pin should give).
#   roc_run_think.sh smoke TAG MAXTOK SMOKEDIR   6 smoke replies (3 defects + 3 twins x 5-attributed)
#                                                 and 1 manipulation check; exit 0 OK, 7 BUDGET, 3 FAIL
#   roc_run_think.sh run TAG MAXTOK CAP LIMIT     two passes over the shards (the second resumes calls
#       with no record: network errors and cut-off replies). A watcher every 30 s and the end of each
#       pass: exit 6 on an abort rule (roc_tools.py guard_think), exit 4 at the run's cap or when run F's
#       recorded total passes LIMIT, exit 8 at the 18:00 deadline (11 Nov 2026, EAT); 0 when finished.
set -u
PHASE=$1 TAG=$2 MAXTOK=$3
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"; T() { "$PY" experiments/roc_tools.py "$@"; }
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
MODEL=deepseek/deepseek-v3.2 ARMS=1-diff,5-attributed PLANNED=564
SET=(--limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip --model $MODEL
     --max-tokens $MAXTOK --check-max-tokens $MAXTOK --arm-order-seed 0)
LOG=runs/roc-$TAG-cost.log
stamp() { date '+%m-%d %H:%M:%S'; }
gt() { $PY -c "import sys; print(1 if float(sys.argv[1]) > float(sys.argv[2]) else 0)" $1 $2; }

if [ $PHASE = smoke ]; then
  SMOKE=$4; mkdir -p runs/$SMOKE
  echo "$(stamp) $TAG smoke $SMOKE max_tokens=$MAXTOK OPENROUTER_REASONING=$OPENROUTER_REASONING OPENROUTER_PROVIDER=$OPENROUTER_PROVIDER CTRL_NAME=$CTRL_NAME" >> $LOG
  # One resume, only for replies missing without a cut-off record (a network failure).
  for attempt in 1 2; do
    [ "$(cat runs/$SMOKE/structure.jsonl 2>/dev/null | grep -c .)" -ge 6 ] && break
    [ $attempt = 2 ] && [ -s runs/$SMOKE/failed.jsonl ] && break
    $PY -u experiments/run_structure.py --name $SMOKE "${SET[@]}" --arms 5-attributed \
        --benchmark runs/roc-items/smoke6.jsonl >> runs/$SMOKE/run.log 2>&1 &
    sp=$!; waited=0
    while kill -0 $sp 2>/dev/null && [ $waited -lt 3600 ]; do sleep 10; waited=$((waited + 10)); done
    kill $sp 2>/dev/null
  done
  verdict=$(T smoke_think $SMOKE $CTRL_NAME)
  { echo "$(stamp) $TAG smoke $SMOKE usage objects:"; T usage_think $SMOKE | sed 's/^/    /'; } >> $LOG
  echo "$(stamp) $TAG smoke $SMOKE: $verdict" | tee -a $LOG
  case $verdict in OK) exit 0;; BUDGET*) exit 7;; *) exit 3;; esac
fi

CAP=$4 LIMIT=$5
RUNCOST=("roc-smoke-$TAG-*" "roc-$TAG-mixed-shard*")
echo "$(stamp) $TAG run start model=$MODEL arms=$ARMS cap=$CAP limit=$LIMIT flags=${SET[*]} OPENROUTER_REASONING=$OPENROUTER_REASONING OPENROUTER_PROVIDER=$OPENROUTER_PROVIDER CTRL_NAME=$CTRL_NAME" >> $LOG
for pass in 1 2; do
  pids=()
  for s in 0 1 2 3 4 5; do
    name=roc-$TAG-mixed-shard$s; mkdir -p runs/$name
    [ -f runs/$name/run.log ] && cp runs/$name/run.log runs/$name/run-pass1.log
    $PY -u experiments/run_structure.py --name $name "${SET[@]}" --arms $ARMS \
        --benchmark runs/roc-items/think-mixed-shard$s.jsonl > runs/$name/run.log 2>&1 &
    pids+=($!)
  done
  alive() { for p in $pids; do kill -0 $p 2>/dev/null && return 0; done; return 1; }
  while alive; do
    sleep 30; c=$(T cost "${RUNCOST[@]}"); total=$(T cost "roc-*"); g=$(T guard_think $CTRL_NAME $PLANNED "roc-$TAG-mixed-shard*")
    echo "$(stamp) pass $pass cost=$c total=$total guard: $g" >> $LOG
    case $g in ABORT*) kill $pids 2>/dev/null; wait
      echo "$(stamp) ABORTED (Amendment 4 rule): $TAG $g; cost $c" | tee -a $LOG; exit 6;; esac
    if [ "$(gt $c $CAP)" = "1" ] || [ "$(gt $total $LIMIT)" = "1" ]; then
      kill $pids 2>/dev/null; wait
      echo "$(stamp) STOPPED: $TAG cost $c (cap $CAP), run F total $total (limit $LIMIT)" | tee -a $LOG; exit 4
    fi
    if [ "$(date +%Y%m%d%H%M)" -ge 202611111800 ]; then
      kill $pids 2>/dev/null; wait
      echo "$(stamp) STOPPED at the 18:00 deadline: $TAG cost $c" | tee -a $LOG; exit 8
    fi
  done
  wait
  g=$(T guard_think $CTRL_NAME $PLANNED "roc-$TAG-mixed-shard*")
  echo "$(stamp) end of pass $pass guard: $g" >> $LOG
  case $g in ABORT*) echo "$(stamp) ABORTED (Amendment 4 rule): $TAG $g; cost $(T cost "${RUNCOST[@]}")" | tee -a $LOG; exit 6;; esac
done
echo "$(stamp) $TAG done cost=$(T cost "${RUNCOST[@]}") total=$(T cost "roc-*")" | tee -a $LOG
