#!/bin/zsh
# One model run of run F (paper/PREREG-F.md, Amendment 1): smoke test (3 defect items x 5-attributed,
# the run's exact flags), then defects and twins in three interleaved shards each, in parallel, then
# one resume pass for calls that failed on the network. Stops at the run's cap or at the $4.00 total
# over runs/roc-*. With PROJECT=1, the run does not start if the smoke cost per call x the run's calls
# exceeds the cap (exit 5).
# Usage: roc_run.sh TAG MODEL CAP ARMS [extra run_structure flags]
set -u
TAG=$1 MODEL=$2 CAP=$3 ARMS=$4; shift 4; EXTRA=("$@")
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"; T() { "$PY" experiments/roc_tools.py "$@"; }
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
SET=(--limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip --model $MODEL "${EXTRA[@]}")
LOG=runs/roc-$TAG-cost.log
RUNCOST=(roc-smoke-$TAG "roc-$TAG-defects-shard*" "roc-$TAG-twins-shard*")
gt() { $PY -c "import sys; print(1 if float(sys.argv[1]) > float(sys.argv[2]) else 0)" $1 $2; }
echo "$(date '+%m-%d %H:%M:%S') $TAG start model=$MODEL cap=$CAP arms=$ARMS flags=${SET[*]}" >> $LOG

mkdir -p runs/roc-smoke-$TAG
$PY -u experiments/run_structure.py --name roc-smoke-$TAG "${SET[@]}" --arms 5-attributed \
    --benchmark runs/roc-items/smoke3.jsonl > runs/roc-smoke-$TAG/run.log 2>&1 &
sp=$!; waited=0
while kill -0 $sp 2>/dev/null && [ $waited -lt 900 ]; do sleep 10; waited=$((waited + 10)); done
kill $sp 2>/dev/null
verdict=$(T smoke roc-smoke-$TAG 2>>$LOG); echo "$(date '+%m-%d %H:%M:%S') $TAG smoke: $verdict" | tee -a $LOG
[ "$verdict" = "OK" ] || { echo "SMOKE-$verdict"; exit 3; }
CALLS=$(( $(echo $ARMS | tr ',' '\n' | wc -l) * 282 ))
if [ "${PROJECT:-0}" = "1" ]; then
  proj=$(T project roc-smoke-$TAG $CALLS $CAP); echo "$(date '+%m-%d %H:%M:%S') $TAG projection: $proj" | tee -a $LOG
  case $proj in OVER*) echo "PROJECTED-OVER"; exit 5;; esac
fi

for pass in 1 2; do
  pids=()
  for kind in defects twins; do
    file=crossfile-v3; [ $kind = twins ] && file=crossfile-v3-twins
    for s in 0 1 2; do
      name=roc-$TAG-$kind-shard$s; mkdir -p runs/$name
      [ -f runs/$name/run.log ] && cp runs/$name/run.log runs/$name/run-pass1.log
      $PY -u experiments/run_structure.py --name $name "${SET[@]}" --arms $ARMS \
          --benchmark runs/roc-items/$file-shard$s.jsonl > runs/$name/run.log 2>&1 &
      pids+=($!)
    done
  done
  alive() { for p in $pids; do kill -0 $p 2>/dev/null && return 0; done; return 1; }
  while alive; do
    sleep 30; c=$(T cost "${RUNCOST[@]}"); total=$(T cost "roc-*")
    echo "$(date '+%m-%d %H:%M:%S') pass $pass cost=$c total=$total" >> $LOG
    if [ "$(gt $c $CAP)" = "1" ] || [ "$(gt $total 4.0)" = "1" ]; then
      kill $pids 2>/dev/null; wait
      echo "STOPPED: $TAG cost $c (cap $CAP), total $total (cap 4.00)" | tee -a $LOG; exit 4
    fi
  done
  wait
done
echo "$(date '+%m-%d %H:%M:%S') $TAG done cost=$(T cost "${RUNCOST[@]}") total=$(T cost "roc-*")" | tee -a $LOG
