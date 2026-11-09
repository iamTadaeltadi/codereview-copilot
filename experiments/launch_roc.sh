#!/bin/zsh
# Run F (paper/PREREG-F.md), in the pre-registered order: gpt-4o-mini, deepseek-v3.2, then the
# optional gpt-4o-mini --authoritative and gpt-4.1 via :batch (kimi-k2-0905 if :batch gives no
# reply). Each run starts only if the OpenRouter balance covers its cap; an optional run only if
# the recorded total plus its cap stays within $4.00. Each finished run is frozen into
# results/<folder>/ and analysed. Nothing starts after Thursday 12 November 2026 (Ethiopia time).
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"; T="$PY experiments/roc_tools.py"
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
ge() { $PY -c "import sys, math; a=float(sys.argv[1]); print(1 if not math.isnan(a) and a >= float(sys.argv[2]) else 0)" $1 $2; }
can_start() { local cap=$1 optional=$2
  [ "$(date +%Y%m%d)" -le 20261112 ] || { echo "deadline passed"; return 1; }
  [ "$(ge $($T balance) $cap)" = "1" ] || { echo "balance $($T balance) below cap $cap"; return 1; }
  if [ $optional = 1 ]; then
    [ "$(ge $($PY -c "print(4.0 - $($T cost 'roc-*'))") $cap)" = "1" ] || { echo "total $($T cost 'roc-*') + cap $cap > 4.00"; return 1; }
  fi; return 0; }
freeze() { local tag=$1 folder=$2; shift 2; local d=results/$folder; mkdir -p $d/smoke
  printf '#!/bin/zsh\n# Run F model run, as launched by experiments/launch_roc.sh (paper/PREREG-F.md)\nzsh experiments/roc_run.sh %s\n' "$*" > $d/launch.sh
  cp runs/roc-smoke-$tag/structure.jsonl $d/smoke/ 2>/dev/null; cp runs/roc-smoke-$tag/run.log $d/smoke/ 2>/dev/null
  for kind in defects twins; do for s in 0 1 2; do local r=runs/roc-$tag-$kind-shard$s
    [ -f $r/structure.jsonl ] && cp $r/structure.jsonl $d/structure-$kind-shard$s.jsonl
    [ -f $r/manipulation.jsonl ] && cp $r/manipulation.jsonl $d/manipulation-$kind-shard$s.jsonl
    [ -f $r/run.log ] && cp $r/run.log $d/run-$kind-shard$s.log
    [ -f $r/run-pass1.log ] && cp $r/run-pass1.log $d/run-$kind-shard$s-pass1.log; done; done
  cp runs/roc-$tag-cost.log $d/cost.log 2>/dev/null
  ls $d/structure-*.jsonl >/dev/null 2>&1 && $PY experiments/analyse_roc.py $d > $d/analysis-roc.txt 2>&1; }
model() { local tag=$1 m=$2 cap=$3 folder=$4 optional=$5; shift 5
  echo "== $tag $(date '+%m-%d %H:%M')"; can_start $cap $optional || { echo "$tag NOT STARTED"; return 2; }
  zsh experiments/roc_run.sh $tag $m $cap "$@"; local rc=$?
  echo "$tag exit $rc"; freeze $tag $folder $tag $m $cap "$@"; return $rc; }
model gpt4omini openai/gpt-4o-mini 1.50 v3-roc-gpt4omini 0
model deepseek deepseek/deepseek-v3.2 1.50 v3-roc-deepseek 0
model gpt4omini-auth openai/gpt-4o-mini 0.50 v3-roc-gpt4omini-auth 1 --authoritative
model gpt41 openai/gpt-4.1:batch 2.00 v3-roc-gpt41 1
if grep -q "gpt41 smoke: NOREPLY" runs/roc-gpt41-cost.log 2>/dev/null; then
  echo "gpt-4.1:batch gave no reply; pre-registered fallback"
  model kimi moonshotai/kimi-k2-0905 2.00 v3-roc-kimi 1
fi
echo "ROC-DONE total=$($T cost 'roc-*') balance=$($T balance)"
