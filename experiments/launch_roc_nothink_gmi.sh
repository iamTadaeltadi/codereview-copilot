#!/bin/zsh
# Run 2g of run F (paper/PREREG-F.md, Amendment 6): deepseek-v3.2, reasoning off, GMICloud fp8 pinned
# (no fallback), arms 1-diff, 7-random, 5-attributed, cap $0.60 (smoke included) under run F's $4.90.
# 1. Start checks: no later than Thursday 12 November 2026, 15:00 (Ethiopia time, the Mac's zone);
#    the balance covers the cap; run F's recorded total plus the cap stays within $4.90.
# 2. Smoke test (roc_run_nothink.sh smoke). Its usage objects go into the README, which is committed
#    and pushed before the launch. A failed smoke test stops here: nothing else runs.
# 3. The run (roc_run_nothink.sh run), then the records, README, analysis-roc.txt, compare-2t.txt
#    (2t vs 2g, three arms) and compare-2c.txt (2g vs 2c, descriptive) are committed and pushed.
# Amendment 6 addendum: called by probe_nothink_gmi.sh with G_SETTING, the reasoning-off setting that
# passed the probes (JSON; null for no reasoning field). The first smoke test ({"enabled": false},
# failed) stays in smoke/, launch.sh and README-smoke1-and-probes.md (the README as pushed before
# this launch); the new smoke test goes to smoke-2/ and its commands to launch-2.sh.
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"; T() { "$PY" experiments/roc_tools.py "$@"; }
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
TAG=deepseek-nothink-gmi CAP=0.60 LIMIT=4.90 RES=results/v3-roc-deepseek-nothink-gmi RUNNER=experiments/roc_run_nothink.sh
LASTSTART=202611121500 SMOKE=roc-smoke-deepseek-nothink-gmi-2 SMOKEOUT=smoke-2
T2T=results/v3-roc-deepseek-think-complete T2C=results/v3-roc-deepseek-ctrl
LOG=runs/roc-$TAG-cost.log
G_SETTING=${G_SETTING:?set by experiments/probe_nothink_gmi.sh}
export G_REASONING=$G_SETTING
if [ "$G_SETTING" = null ]; then export OPENROUTER_REASONING=""; else export OPENROUTER_REASONING=$G_SETTING; fi
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

BAL0=$(T balance); TOTAL0=$(T cost 'roc-*'); G0=$(T cost "roc-smoke-$TAG*" "roc-probe-$TAG-s*")
echo "$(date '+%m-%d %H:%M:%S') $TAG launcher start (Amendment 6 addendum, G_REASONING=$G_REASONING): balance $BAL0, run F recorded $TOTAL0, run 2g so far $G0" >> $LOG
why=""
[ "$(date +%Y%m%d%H%M)" -gt $LASTSTART ] && why="start deadline (12 Nov 15:00) passed"
[ -z "$why" ] && [ "$(ge $BAL0 $CAP)" != "1" ] && why="balance $BAL0 below the cap"
[ -z "$why" ] && [ "$($PY -c "import sys; print(1 if float(sys.argv[1]) - float(sys.argv[2]) + float(sys.argv[3]) <= float(sys.argv[4]) + 1e-9 else 0)" $TOTAL0 $G0 $CAP $LIMIT)" != "1" ] && why="recorded total before run 2g + cap above \$$LIMIT"
verdict="not run"; smoke_rc=9
if [ -z "$why" ]; then
  zsh $RUNNER smoke $TAG $SMOKE; smoke_rc=$?
  verdict=$(grep "smoke $SMOKE: " $LOG | tail -1 | sed "s/.*smoke $SMOKE: //")
  [ $smoke_rc != 0 ] && why="smoke test failed: $verdict"
  [ -z "$why" ] && [ "$(date +%Y%m%d%H%M)" -gt $LASTSTART ] && why="start deadline (12 Nov 15:00) passed"
fi
[ -n "$why" ] && echo "$(date '+%m-%d %H:%M:%S') $TAG did not start: $why" | tee -a $LOG

errors() { grep -H "ERROR" runs/$SMOKE/run.log runs/roc-$TAG-mixed-shard*/run-pass*.log(N) 2>/dev/null; }
readme() { local outcome=$1
  { echo "# Run F: run 2g, deepseek-v3.2 with reasoning off on GMICloud (paper/PREREG-F.md, Amendment 6)"; echo
    echo "- model: \`deepseek/deepseek-v3.2\`; arms: 1-diff, 7-random, 5-attributed; items: run 2c's 139 default-flip defects and 143 twins, in run 2t's six seeded mixed shards"
    echo "- flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip --max-tokens 2048 --check-max-tokens 2048 --arm-order-seed 0 --no-repeat-checks; temperature 0.1"
    echo "- reasoning setting (Amendment 6 addendum): \`$G_REASONING\` (null: no reasoning field), the one that passed the probes; the first smoke test used \`{\"enabled\": false}\` and failed (README-smoke1-and-probes.md)"
    echo "- settings on every call: OPENROUTER_REASONING=\`$OPENROUTER_REASONING\` OPENROUTER_PROVIDER=\`$OPENROUTER_PROVIDER\` (served name expected: $CTRL_NAME; no fallback provider)"
    echo "- timing: the six shards run in parallel; each item's three arms back to back, in an order shuffled with seed 0, so all arms run at the same time"
    echo "- cap \$$CAP (both smoke tests, the probes and the run); run F limit \$$LIMIT"
    echo "- smoke test ($SMOKE): $verdict"
    echo "- outcome: $outcome"
    echo "- recorded cost of run 2g (both smoke tests, the probes and the run): \$$(T cost "roc-smoke-$TAG*" "roc-probe-$TAG-s*" "roc-$TAG-mixed-shard*") (\$$G0 before this launch); run F total: \$$(T cost 'roc-*') (\$$TOTAL0 before this launch)"
    echo "- OpenRouter balance: \$$BAL0 at this launch, \$$(T balance) now"
    grep -h "STOPPED\|ABORTED\|did not start\|$TAG done" $LOG 2>/dev/null | sed 's/^/- log: /'
    if [ -n "$(echo runs/roc-$TAG-mixed-shard*/structure.jsonl(N))" ]; then
      echo "- run calls: $(T thinkstats "roc-$TAG-mixed-shard*")"
      echo "- abort rules at the end: $(T guard_g $CTRL_NAME "roc-$TAG-mixed-shard*")"
      echo "- review calls per arm and day: $(T daysplit "roc-$TAG-mixed-shard*" | tr '\n' ';' | sed 's/;$//; s/;/; /g')"
    fi
    echo; echo "HTTP and other call errors in the logs (no record; asked once more in the next pass):"; echo; echo '```'
    errors || echo "none"; echo '```'
    echo; echo "Calls cut off at max_tokens (billed, not scored):"; echo; echo '```'
    T usage_think "roc-$TAG-mixed-shard*" | grep " CUT-OFF " || echo "none"; echo '```'
    echo; echo "Smoke usage objects and finish reasons ($SMOKE; raw; written before the run was launched):"; echo; echo '```'
    T usage_think $SMOKE; echo '```'
    echo; echo "Files: launch-2.sh (the commands of this launch), structure-mixed-shard{0..5}.jsonl (one record per item and arm),"
    echo "manipulation-mixed-shard*.jsonl, failed-mixed-shard*.jsonl (if any), run-mixed-shard*-pass{1,2}.log,"
    echo "smoke-2/ (this smoke test), smoke/, launch.sh and README-smoke1-and-probes.md (the first smoke test and the probes),"
    echo "probe-s*/ (the probes), items/ (the six shards, the smoke items and the probe items), cost.log,"
    echo "analysis-roc.txt (\`python3 experiments/analyse_roc.py $RES 5-attributed:7-random\`),"
    echo "compare-2t.txt (\`python3 experiments/compare_roc_runs.py $T2T $RES --arms 1-diff,7-random,5-attributed --amendment 6\`;"
    echo "A = 2t, reasoning on; B = 2g, reasoning off; same provider),"
    echo "compare-2c.txt (\`python3 experiments/compare_roc_runs.py $RES $T2C --amendment 6\`; A = 2g on GMICloud,"
    echo "B = 2c on AtlasCloud, both reasoning off; descriptive)."; } > $RES/README.md; }
copy_smoke() { mkdir -p $RES/$SMOKEOUT $RES/items
  for f in structure.jsonl manipulation.jsonl failed.jsonl run.log; do [ -f runs/$SMOKE/$f ] && cp runs/$SMOKE/$f $RES/$SMOKEOUT/; done
  cp runs/roc-items/think-mixed-shard*.jsonl runs/roc-items/smoke6.jsonl runs/roc-items/probe2.jsonl $RES/items/; cp $LOG $RES/cost.log; }
launchsh() { { echo '#!/bin/zsh'; echo "# Run 2g (paper/PREREG-F.md, Amendment 6 addendum), as launched by experiments/probe_nothink_gmi.sh and experiments/launch_roc_nothink_gmi.sh"
  [ $smoke_rc != 9 ] && echo "OPENROUTER_REASONING='$OPENROUTER_REASONING' G_REASONING='$G_REASONING' OPENROUTER_PROVIDER='$OPENROUTER_PROVIDER' CTRL_NAME=$CTRL_NAME zsh $RUNNER smoke $TAG $SMOKE"
  [ -z "$why" ] && echo "OPENROUTER_REASONING='$OPENROUTER_REASONING' G_REASONING='$G_REASONING' OPENROUTER_PROVIDER='$OPENROUTER_PROVIDER' CTRL_NAME=$CTRL_NAME zsh $RUNNER run $TAG $CAP $LIMIT"
  } > $RES/launch-2.sh; }
mkdir -p $RES
[ -f $RES/README.md ] && [ ! -f $RES/README-smoke1-and-probes.md ] && cp $RES/README.md $RES/README-smoke1-and-probes.md

if [ -n "$why" ]; then
  copy_smoke; launchsh; readme "did not start: $why"
  MSG="run F 2g (Amendment 6): did not start ($why)"; push $RES
  echo "G-DONE did not start: $why"; exit 5
fi
copy_smoke; launchsh
readme "smoke test passed; launched $(date '+%d %b %H:%M') EAT (this line is replaced when the run ends)"
MSG="run F 2g (Amendment 6): smoke usage objects and verdict, before the launch"; push $RES

zsh $RUNNER run $TAG $CAP $LIMIT; rc=$?
case $rc in 0) what="finished";; 4) what="stopped by its cap or the \$$LIMIT limit";; 6) what="stopped by an Amendment 6 abort rule (not restarted)";;
  8) what="stopped at the 18:00 deadline";; *) what="exit $rc";; esac
for s in 0 1 2 3 4 5; do r=runs/roc-$TAG-mixed-shard$s
  for f in structure manipulation failed; do [ -f $r/$f.jsonl ] && cp $r/$f.jsonl $RES/$f-mixed-shard$s.jsonl; done
  for p in 1 2; do [ -f $r/run-pass$p.log ] && cp $r/run-pass$p.log $RES/run-mixed-shard$s-pass$p.log; done; done
copy_smoke; readme "$what"
if ls $RES/structure-*.jsonl >/dev/null 2>&1; then
  $PY experiments/analyse_roc.py $RES 5-attributed:7-random > $RES/analysis-roc.txt 2>&1
  $PY experiments/compare_roc_runs.py $T2T $RES --arms 1-diff,7-random,5-attributed --amendment 6 > $RES/compare-2t.txt 2>&1
  $PY experiments/compare_roc_runs.py $RES $T2C --amendment 6 > $RES/compare-2c.txt 2>&1
fi
MSG="run F 2g (Amendment 6): records, analysis, comparisons with 2t and 2c, README as recorded ($what)"; push $RES
echo "G-DONE $what total=$(T cost 'roc-*') balance=$(T balance)"
