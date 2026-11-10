#!/bin/zsh
# Run F (paper/PREREG-F.md, Amendment 1), in the pre-registered order: gpt-4o-mini and deepseek-v3.2
# with 4 arms, then both --authoritative with 3 arms, then gpt-4.1 via :batch with 4 arms
# (kimi-k2-0905 instead if gpt-4.1's smoke test fails or projects the run above the money left).
# A run starts only if the OpenRouter balance covers its cap, the recorded total plus its cap stays
# within $4.00, and it is before Thursday 12 November 2026, 18:00 (Ethiopia time, the Mac's zone).
# Each run is frozen into results/<folder>/, analysed, committed and pushed.
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"; T() { "$PY" experiments/roc_tools.py "$@"; }
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
ARMS4=1-diff,7-random,2b-snippets,5-attributed; ARMS3=1-diff,2b-snippets,5-attributed
ge() { $PY -c "import sys, math; a=float(sys.argv[1]); print(1 if not math.isnan(a) and a >= float(sys.argv[2]) else 0)" $1 $2; }
can_start() { local cap=$1
  [ "$(date +%Y%m%d%H%M)" -le 202611121800 ] || { echo "start deadline (12 Nov 18:00) passed"; return 1; }
  [ "$(ge $(T balance) $cap)" = "1" ] || { echo "balance $(T balance) below cap $cap"; return 1; }
  [ "$(ge $(T remaining) $cap)" = "1" ] || { echo "recorded total $(T cost 'roc-*') + cap $cap > 4.00"; return 1; }
  return 0; }
push() { git add "$1" && git -c commit.gpgsign=false -c user.name="Tadael Shewarega" \
    -c user.email="iamTadaeltadi@users.noreply.github.com" commit -q -m "$2" || return 0
  git pull -q --rebase --autostash
  for i in 1 2 3 4 5; do
    git -c http.postBuffer=524288000 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=600 push -q && return 0
    sleep 30
  done
  echo "PUSH FAILED for $1"; }
freeze() { local tag=$1 folder=$2 rc=$3 model=$4 cap=$5 arms=$6; shift 6; local d=results/$folder; mkdir -p $d/smoke
  printf '#!/bin/zsh\n# Run F model run (paper/PREREG-F.md, Amendment 1), as launched by experiments/launch_roc.sh\n%szsh experiments/roc_run.sh %s %s %s %s %s\n' \
    "$([ $tag = gpt41 ] && echo 'PROJECT=1 ')" $tag $model $cap $arms "$*" > $d/launch.sh
  for f in structure.jsonl manipulation.jsonl run.log; do cp runs/roc-smoke-$tag/$f $d/smoke/ 2>/dev/null; done
  for kind in defects twins; do for s in 0 1 2; do local r=runs/roc-$tag-$kind-shard$s
    [ -f $r/structure.jsonl ] && cp $r/structure.jsonl $d/structure-$kind-shard$s.jsonl
    [ -f $r/manipulation.jsonl ] && cp $r/manipulation.jsonl $d/manipulation-$kind-shard$s.jsonl
    [ -f $r/run.log ] && cp $r/run.log $d/run-$kind-shard$s.log
    [ -f $r/run-pass1.log ] && cp $r/run-pass1.log $d/run-$kind-shard$s-pass1.log; done; done
  cp runs/roc-$tag-cost.log $d/cost.log 2>/dev/null
  local what; case $rc in 0) what="finished";; 3) what="did not start: smoke test failed or gave no reply";;
    4) what="stopped by its cap or the \$4.00 total";; 5) what="did not start: smoke cost projected the run above its cap";;
    *) what="exit $rc";; esac
  { echo "# Run F: $tag (paper/PREREG-F.md, Amendment 1)"; echo
    echo "- model: \`$model\`; arms: $arms; cap \$$cap; extra flags: ${*:-none}"
    echo "- shared flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip"
    echo "- outcome: $what"
    echo "- recorded cost of this run (smoke included): \$$(T cost roc-smoke-$tag "roc-$tag-defects-shard*" "roc-$tag-twins-shard*"); run F total so far: \$$(T cost 'roc-*')"
    grep -h "STOPPED\|smoke:\|projection:" runs/roc-$tag-cost.log 2>/dev/null | sed 's/^/- log: /'
    echo; echo "Files: launch.sh (the command), structure-{defects,twins}-shard{0,1,2}.jsonl (one record per item and arm),"
    echo "manipulation-*.jsonl, run-*.log, smoke/ (the 3 smoke calls), cost.log, analysis-roc.txt"
    echo "(\`python3 experiments/analyse_roc.py results/$folder\`)."; } > $d/README.md
  ls $d/structure-*.jsonl >/dev/null 2>&1 && $PY experiments/analyse_roc.py $d > $d/analysis-roc.txt 2>&1
  push $d "run F ($tag): records, analysis and README as recorded ($what)"; }
model() { local tag=$1 m=$2 cap=$3 folder=$4 arms=$5; shift 5
  echo "== $tag $(date '+%m-%d %H:%M') cap $cap"; can_start $cap || { echo "$tag NOT STARTED"; return 2; }
  zsh experiments/roc_run.sh $tag $m $cap $arms "$@"; local rc=$?
  echo "$tag exit $rc"; freeze $tag $folder $rc $m $cap $arms "$@"; return $rc; }
# Run 5's cap: the money left under $4.00, less a 5-cent margin for calls in flight when the watcher stops.
left() { $PY -c "import sys; print(f'{float(sys.argv[1]) - 0.05:.2f}')" $(T remaining); }

model gpt4omini openai/gpt-4o-mini 1.00 v3-roc-gpt4omini $ARMS4
model deepseek deepseek/deepseek-v3.2 1.00 v3-roc-deepseek $ARMS4
model gpt4omini-auth openai/gpt-4o-mini 0.40 v3-roc-gpt4omini-auth $ARMS3 --authoritative
model deepseek-auth deepseek/deepseek-v3.2 0.60 v3-roc-deepseek-auth $ARMS3 --authoritative
PROJECT=1 model gpt41 openai/gpt-4.1:batch $(left) v3-roc-gpt41 $ARMS4; rc=$?
if [ $rc = 3 ] || [ $rc = 5 ]; then
  echo "gpt-4.1:batch smoke failed or projected over the money left (exit $rc); pre-registered fallback"
  model kimi moonshotai/kimi-k2-0905 $(left) v3-roc-kimi $ARMS4
fi
echo "ROC-DONE total=$(T cost 'roc-*') balance=$(T balance)"
