#!/bin/zsh
# Run 2t of run F (paper/PREREG-F.md, Amendment 4): deepseek-v3.2, reasoning on, provider pinned as in
# run 2c, arms 1-diff and 5-attributed, cap $2.30 under run F's raised limit of $4.90.
# 1. Smoke tests: AtlasCloud at max_tokens 2,048; if reasoning used up the budget (BUDGET), again at
#    16,000, which then holds for everything after; if AtlasCloud fails otherwise, GMICloud at the
#    max_tokens decided so far. Every smoke folder is kept.
# 2. Projection: mean smoke review cost x 564 x 1.5 + every smoke cost so far, against the cap.
# 3. The README with the smoke usage objects, finish reasons and projection is committed and pushed
#    before the launch. The run starts only if the projection is within the cap, the balance covers
#    the cap, run F's recorded total plus the cap stays within $4.90, and it is no later than
#    Wednesday 11 November 2026, 15:00 (Ethiopia time, the Mac's zone).
# 4. The run's records, README, analysis-roc.txt and compare-2c.txt are committed and pushed.
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"; T() { "$PY" experiments/roc_tools.py "$@"; }
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
TAG=deepseek-think CAP=2.30 LIMIT=4.90 RES=results/v3-roc-deepseek-think RUNNER=experiments/roc_run_think.sh
LOG=runs/roc-$TAG-cost.log
export OPENROUTER_REASONING='{"enabled": true}'
ge() { $PY -c "import sys, math; a=float(sys.argv[1]); print(1 if not math.isnan(a) and a >= float(sys.argv[2]) else 0)" $1 $2; }
push() { git add "$@" && git -c commit.gpgsign=false -c user.name="Tadael Shewarega" \
    -c user.email="iamTadaeltadi@users.noreply.github.com" commit -q -m "$MSG" || return 0
  git pull -q --rebase --autostash
  for i in 1 2 3 4 5; do
    git -c http.postBuffer=524288000 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=600 push -q && return 0
    sleep 30
  done
  echo "PUSH FAILED: $MSG"; }
BAL0=$(T balance); TOTAL0=$(T cost 'roc-*')
echo "$(date '+%m-%d %H:%M:%S') $TAG launcher start: balance $BAL0, run F recorded $TOTAL0" >> $LOG

# 1. Smoke tests
MAXTOK=2048 chosen="" smokes=()
for pair in "atlas-cloud/fp8 AtlasCloud" "gmicloud/fp8 GMICloud"; do
  slug=${pair% *}; export CTRL_NAME=${pair#* }
  export OPENROUTER_PROVIDER="{\"order\": [\"$slug\"], \"allow_fallbacks\": false, \"require_parameters\": true}"
  while true; do
    SMOKE=roc-smoke-$TAG-${slug%%/*}-$MAXTOK; smokes+=($SMOKE)
    zsh $RUNNER smoke $TAG $MAXTOK $SMOKE; rc=$?
    [ $rc = 0 ] && { chosen=$slug; break 2; }
    if [ $rc = 7 ] && [ $MAXTOK = 2048 ]; then MAXTOK=16000; continue; fi
    break
  done
done

readme() { local outcome=$1
  { echo "# Run F: run 2t, deepseek-v3.2 with reasoning on (paper/PREREG-F.md, Amendment 4)"; echo
    echo "- model: \`deepseek/deepseek-v3.2\`; arms: 1-diff, 5-attributed; items: run 2c's 139 default-flip defects and 143 twins"
    echo "- flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip --max-tokens $MAXTOK --check-max-tokens $MAXTOK --arm-order-seed 0; temperature 0.1"
    if [ -n "$chosen" ]; then echo "- settings on every call of the run: OPENROUTER_REASONING=\`$OPENROUTER_REASONING\` OPENROUTER_PROVIDER=\`$OPENROUTER_PROVIDER\` (served name expected: $CTRL_NAME)"
    else echo "- settings: OPENROUTER_REASONING=\`$OPENROUTER_REASONING\`; no provider passed the smoke test"; fi
    echo "- max_tokens used: $MAXTOK (2,048 unless a smoke reply showed reasoning using up the budget; see the smoke verdicts)"
    echo "- timing: six shards of 47 items, shuffled together (seed 0) from run 2c's items, so every shard holds defects and twins; each item's two arms in an order shuffled with seed 0 (\`roc_tools.py prep_think\`); the shards run in parallel"
    echo "- cap \$$CAP; run F limit \$$LIMIT (raised from \$4.00 by Amendment 4)"
    echo "- outcome: $outcome"
    echo "- recorded cost of this run (smoke tests included): \$$(T cost "roc-smoke-$TAG-*" "roc-$TAG-mixed-shard*"); run F total: \$$(T cost 'roc-*')"
    echo "- OpenRouter balance: \$$BAL0 before the first smoke call, \$$(T balance) now; run F recorded \$$TOTAL0 before"
    grep -h "smoke roc-smoke.*: \(OK\|BUDGET\|FAIL\)\|projection\|STOPPED\|ABORTED\|did not start\|done cost" $LOG 2>/dev/null | sed 's/^/- log: /'
    if [ -n "$(echo runs/roc-$TAG-mixed-shard*/structure.jsonl(N))" ]; then
      echo "- run calls: $(T thinkstats "roc-$TAG-mixed-shard*")"
      echo "- abort rules at the end: $(T guard_think ${CTRL_NAME} 564 "roc-$TAG-mixed-shard*")"
    fi
    echo; echo "Smoke usage objects and finish reasons (raw; written before the run was launched):"; echo; echo '```'
    T usage_think "${smokes[@]}"; echo '```'
    echo; echo "Files: launch.sh (the commands), structure-mixed-shard{0..5}.jsonl (one record per item and arm),"
    echo "manipulation-mixed-shard*.jsonl, failed-mixed-shard*.jsonl (calls cut off at max_tokens: billed, not scored),"
    echo "run-mixed-shard*.log, smoke-*/ (each smoke test), items/ (the six shards and the smoke items, as run), cost.log, analysis-roc.txt"
    echo "(\`python3 experiments/analyse_roc.py $RES\`), compare-2c.txt"
    echo "(\`python3 experiments/compare_roc_runs.py $RES results/v3-roc-deepseek-ctrl\`)."; } > $RES/README.md; }
copy_smokes() { for s in $smokes; do mkdir -p $RES/smoke-${s#roc-smoke-$TAG-}
  for f in structure.jsonl manipulation.jsonl failed.jsonl run.log; do [ -f runs/$s/$f ] && cp runs/$s/$f $RES/smoke-${s#roc-smoke-$TAG-}/; done; done
  mkdir -p $RES/items; cp runs/roc-items/think-mixed-shard*.jsonl runs/roc-items/smoke6.jsonl $RES/items/
  cp $LOG $RES/cost.log; }
launchsh() { { echo '#!/bin/zsh'; echo "# Run 2t (paper/PREREG-F.md, Amendment 4), as launched by experiments/launch_roc_think.sh"
  for s in $smokes; do local sl=${s#roc-smoke-$TAG-}; local mt=${sl##*-}; local pv=${sl%-*}
    echo "OPENROUTER_REASONING='$OPENROUTER_REASONING' OPENROUTER_PROVIDER='{\"order\": [\"$pv/fp8\"], \"allow_fallbacks\": false, \"require_parameters\": true}' CTRL_NAME=$([ $pv = atlas-cloud ] && echo AtlasCloud || echo GMICloud) zsh $RUNNER smoke $TAG $mt $s"; done
  [ -n "$chosen" ] && [ -z "${why:-}" ] && echo "OPENROUTER_REASONING='$OPENROUTER_REASONING' OPENROUTER_PROVIDER='$OPENROUTER_PROVIDER' CTRL_NAME=$CTRL_NAME zsh $RUNNER run $TAG $MAXTOK $CAP $LIMIT"
  } > $RES/launch.sh; }
mkdir -p $RES

if [ -z "$chosen" ]; then
  copy_smokes; launchsh; readme "did not start: no provider passed the smoke test"
  MSG="run F 2t (Amendment 4): no provider passed the smoke test; nothing ran"; push $RES
  echo "THINK-DONE no provider passed"; exit 3
fi

# 2. Projection, and the README before the launch
proj=$(T project_think ${smokes[-1]} $CAP 564 "roc-smoke-$TAG-*")
echo "$(date '+%m-%d %H:%M:%S') $TAG projection: $proj" | tee -a $LOG
why=""
case $proj in OVER*) why="projection over the cap";; esac
[ -z "$why" ] && [ "$(date +%Y%m%d%H%M)" -gt 202611111500 ] && why="launch deadline (11 Nov 15:00) passed"
[ -z "$why" ] && [ "$(ge $(T balance) $CAP)" != "1" ] && why="balance $(T balance) below the cap"
# The cap covers this run's smoke tests, so the limit check uses run F's total from before them.
[ -z "$why" ] && [ "$($PY -c "import sys; print(1 if float(sys.argv[1]) + float(sys.argv[2]) <= float(sys.argv[3]) + 1e-9 else 0)" $TOTAL0 $CAP $LIMIT)" != "1" ] && why="recorded total before this run + cap above \$$LIMIT"
copy_smokes; launchsh
if [ -n "$why" ]; then
  echo "$(date '+%m-%d %H:%M:%S') $TAG did not start: $why" | tee -a $LOG; cp $LOG $RES/cost.log
  readme "did not start: $why"; MSG="run F 2t (Amendment 4): smoke tests and projection; did not start ($why)"; push $RES
  echo "THINK-DONE did not start: $why"; exit 5
fi
readme "smoke test passed on $chosen at max_tokens $MAXTOK; projection within the cap; launched $(date '+%d %b %H:%M') EAT (this line is replaced when the run ends)"
MSG="run F 2t (Amendment 4): smoke usage objects, finish reasons and projection, before the launch"; push $RES

# 3. The run
zsh $RUNNER run $TAG $MAXTOK $CAP $LIMIT; rc=$?
case $rc in 0) what="finished";; 4) what="stopped by its cap or the \$$LIMIT limit";; 6) what="stopped by an Amendment 4 abort rule (not restarted)";;
  8) what="stopped at the 18:00 deadline";; *) what="exit $rc";; esac
for s in 0 1 2 3 4 5; do r=runs/roc-$TAG-mixed-shard$s
  for f in structure manipulation failed; do [ -f $r/$f.jsonl ] && cp $r/$f.jsonl $RES/$f-mixed-shard$s.jsonl; done
  [ -f $r/run.log ] && cp $r/run.log $RES/run-mixed-shard$s.log
  [ -f $r/run-pass1.log ] && cp $r/run-pass1.log $RES/run-mixed-shard$s-pass1.log; done
copy_smokes; readme "$what"
$PY experiments/analyse_roc.py $RES > $RES/analysis-roc.txt 2>&1
$PY experiments/compare_roc_runs.py $RES results/v3-roc-deepseek-ctrl > $RES/compare-2c.txt 2>&1
MSG="run F 2t (Amendment 4): records, analysis, between-run comparison and README as recorded ($what)"; push $RES
echo "THINK-DONE $what total=$(T cost 'roc-*') balance=$(T balance)"
