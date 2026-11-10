#!/bin/zsh
# Run 2t completed, with 7-random added (paper/PREREG-F.md, Amendment 5). Waits until Wednesday
# 11 November 2026, 08:00 (Ethiopia time, the Mac's zone); starts only if it is no later than 12:00,
# the balance covers the $1.40 cap, and run F's recorded total plus the cap stays within $4.90. The
# complete run (Amendment 4's records and the new ones) is frozen into
# results/v3-roc-deepseek-think-complete/, analysed (all three arms, plus 5-attributed - 7-random),
# compared with run 2c, committed and pushed. Run 2t's partial folder (results/v3-roc-deepseek-think/)
# is not touched.
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"; T() { "$PY" experiments/roc_tools.py "$@"; }
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
TAG=deepseek-think CAP=1.40 LIMIT=4.90 RES=results/v3-roc-deepseek-think-complete RUNNER=experiments/roc_run_think_a5.sh
START=202611110800 LASTSTART=202611111200
LOG=runs/roc-$TAG-cost.log
export OPENROUTER_REASONING='{"enabled": true}'
export OPENROUTER_PROVIDER='{"order": ["gmicloud/fp8"], "allow_fallbacks": false, "require_parameters": true}'
export CTRL_NAME=GMICloud
ge() { $PY -c "import sys, math; a=float(sys.argv[1]); print(1 if not math.isnan(a) and a >= float(sys.argv[2]) else 0)" $1 $2; }
push() { git add "$@" && git -c commit.gpgsign=false -c user.name="Tadael Shewarega" \
    -c user.email="iamTadaeltadi@users.noreply.github.com" commit -q -m "$MSG" || return 0
  git pull -q --rebase --autostash
  for i in 1 2 3 4 5; do
    git -c http.postBuffer=524288000 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=600 push -q && return 0
    sleep 30
  done
  echo "PUSH FAILED: $MSG"; }

echo "$(date '+%m-%d %H:%M:%S') $TAG Amendment 5 launcher waiting for $START" >> $LOG
while [ "$(date +%Y%m%d%H%M)" -lt $START ]; do sleep 60; done
BAL0=$(T balance); TOTAL0=$(T cost 'roc-*'); BEFORE=$(T cost "roc-smoke-$TAG-*" "roc-$TAG-mixed-shard*")
echo "$(date '+%m-%d %H:%M:%S') $TAG Amendment 5 launcher: balance $BAL0, run F recorded $TOTAL0, run 2t recorded $BEFORE" >> $LOG
why=""
[ "$(date +%Y%m%d%H%M)" -gt $LASTSTART ] && why="start deadline (11 Nov 12:00) passed"
[ -z "$why" ] && [ "$(ge $BAL0 $CAP)" != "1" ] && why="balance $BAL0 below the cap"
[ -z "$why" ] && [ "$($PY -c "import sys; print(1 if float(sys.argv[1]) + float(sys.argv[2]) <= float(sys.argv[3]) + 1e-9 else 0)" $TOTAL0 $CAP $LIMIT)" != "1" ] && why="recorded total + cap above \$$LIMIT"
rc=5
if [ -z "$why" ]; then zsh $RUNNER $TAG $CAP $LIMIT; rc=$?
else echo "$(date '+%m-%d %H:%M:%S') $TAG Amendment 5 did not start: $why" | tee -a $LOG; fi
case $rc in 0) what="finished";; 4) what="stopped by its cap or the \$$LIMIT limit";; 6) what="stopped by an Amendment 5 abort rule (not restarted)";;
  8) what="stopped at the 15:00 deadline";; 5) what="did not start: $why";; *) what="exit $rc";; esac

mkdir -p $RES/items
for s in 0 1 2 3 4 5; do r=runs/roc-$TAG-mixed-shard$s
  for f in structure manipulation failed; do [ -f $r/$f.jsonl ] && cp $r/$f.jsonl $RES/$f-mixed-shard$s.jsonl; done
  [ -f $r/run.log ] && cp $r/run.log $RES/run-mixed-shard$s-amendment4.log
  for p in 1 2; do [ -f $r/run-a5-pass$p.log ] && cp $r/run-a5-pass$p.log $RES/run-mixed-shard$s-amendment5-pass$p.log; done; done
cp runs/roc-items/think-mixed-shard*.jsonl runs/roc-items/smoke6.jsonl $RES/items/; cp $LOG $RES/cost.log
{ echo '#!/bin/zsh'; echo "# Run 2t completed with 7-random added (paper/PREREG-F.md, Amendment 5), as launched by experiments/launch_roc_think_a5.sh"
  echo "# Amendment 4's part of the run: results/v3-roc-deepseek-think/launch.sh"
  echo "OPENROUTER_REASONING='$OPENROUTER_REASONING' OPENROUTER_PROVIDER='$OPENROUTER_PROVIDER' CTRL_NAME=$CTRL_NAME zsh $RUNNER $TAG $CAP $LIMIT"; } > $RES/launch.sh
{ echo "# Run F: run 2t completed, with 7-random added (paper/PREREG-F.md, Amendment 5)"; echo
  echo "- model: \`deepseek/deepseek-v3.2\`; arms: 1-diff, 7-random, 5-attributed; items: run 2c's 139 default-flip defects and 143 twins"
  echo "- flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip --max-tokens 16000 --check-max-tokens 16000 --arm-order-seed 0 (Amendment 5 adds --runaway-tokens 40000 --no-repeat-checks); temperature 0.1"
  echo "- settings on every call: OPENROUTER_REASONING=\`$OPENROUTER_REASONING\` OPENROUTER_PROVIDER=\`$OPENROUTER_PROVIDER\` (served name expected: GMICloud)"
  echo "- the records are Amendment 4's run (results/v3-roc-deepseek-think/, stopped at 22:20 on 10 Nov after 330 review calls) followed by the calls under Amendment 5; recorded calls were not asked again"
  echo "- timing, review calls per arm and day: $(T daysplit "roc-$TAG-mixed-shard*" | tr '\n' ';' | sed 's/;$//; s/;/; /g')"
  echo "- cap \$$CAP for the spend under Amendment 5; run F limit \$$LIMIT"
  echo "- outcome of the Amendment 5 part: $what"
  echo "- recorded cost: run 2t before Amendment 5 \$$BEFORE; run 2t now \$$(T cost "roc-smoke-$TAG-*" "roc-$TAG-mixed-shard*") (smoke tests included); run F total \$$(T cost 'roc-*')"
  echo "- OpenRouter balance: \$$BAL0 before the first Amendment 5 call, \$$(T balance) now"
  grep -h "Amendment 5 did not start\|STOPPED\|ABORTED (Amendment 5\|Amendment 5 done" $LOG 2>/dev/null | sed 's/^/- log: /'
  echo "- all calls of the run: $(T thinkstats "roc-$TAG-mixed-shard*")"
  echo "- abort rules at the end: $(T guard_a5 $CTRL_NAME 3 "roc-$TAG-mixed-shard*")"
  echo; echo "Calls logged as failed (cut off, or over the runaway limit: billed, not scored):"; echo; echo '```'
  T usage_think "roc-$TAG-mixed-shard*" | grep " \(RUNAWAY\|CUT-OFF\) " || echo "none"; echo '```'
  echo; echo "Files: launch.sh, structure-mixed-shard{0..5}.jsonl (one record per item and arm, both amendments),"
  echo "manipulation-mixed-shard*.jsonl, failed-mixed-shard*.jsonl, run-mixed-shard*-amendment4.log and"
  echo "run-mixed-shard*-amendment5-pass{1,2}.log, items/ (the six shards as run), cost.log (both amendments),"
  echo "analysis-roc.txt (\`python3 experiments/analyse_roc.py $RES 5-attributed:7-random\`),"
  echo "compare-2c.txt (\`python3 experiments/compare_roc_runs.py $RES results/v3-roc-deepseek-ctrl\`)."
  echo "The smoke tests of run 2t are in results/v3-roc-deepseek-think/smoke-*/."; } > $RES/README.md
if ls $RES/structure-*.jsonl >/dev/null 2>&1; then
  $PY experiments/analyse_roc.py $RES 5-attributed:7-random > $RES/analysis-roc.txt 2>&1
  $PY experiments/compare_roc_runs.py $RES results/v3-roc-deepseek-ctrl > $RES/compare-2c.txt 2>&1
fi
MSG="run F 2t completed with 7-random (Amendment 5): records, analysis, between-run comparison and README as recorded ($what)"; push $RES
echo "A5-DONE $what total=$(T cost 'roc-*') balance=$(T balance)"
