#!/bin/zsh
# Run 2g of run F (paper/PREREG-F.md, Amendment 6 addendum): the smoke test failed because GMICloud
# reasoned with "reasoning": {"enabled": false}. This probes up to three other ways to turn reasoning
# off, still on GMICloud fp8 (same pin, no fallback), in this order:
#   s1 {"effort": "none"}   s2 no reasoning field   s3 {"max_tokens": 0}
# Each probe: 2 review calls (5-attributed, the run's flags, no manipulation check) on
# runs/roc-items/probe2.jsonl, the defect first; the second call only if the first reports
# reasoning_tokens 0. Probe cap $0.01: no call starts once the probes' recorded cost plus $0.003 would
# pass it. A setting passes only if both calls report reasoning_tokens 0, served by GMICloud with the
# settings sent (roc_tools.py probe_g). The first setting that passes goes to
# launch_roc_nothink_gmi.sh (run 2g as planned); if none passes, the README records every setting
# tried and its reasoning tokens, and nothing else runs.
set -u
ROOT="/Users/tadaelshewarega/Desktop/education stff/canada-2027/capstone/codereview-copilot"
PY="$ROOT/.venv/bin/python"; T() { "$PY" experiments/roc_tools.py "$@"; }
cd "$ROOT"; export PYTHONPATH=.:services/graph:services/agents
TAG=deepseek-nothink-gmi RES=results/v3-roc-deepseek-nothink-gmi LAUNCHER=experiments/launch_roc_nothink_gmi.sh
PCAP=0.01 PMAX=0.003 LASTSTART=202611121500 ITEMS=runs/roc-items/probe2.jsonl FIRSTSMOKE=roc-smoke-deepseek-nothink-gmi
LOG=runs/roc-$TAG-cost.log
SET=(--encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip --model deepseek/deepseek-v3.2
     --max-tokens 2048 --check-max-tokens 2048 --arm-order-seed 0 --no-repeat-checks --check-every 1 --arms 5-attributed)
SETTINGS=('{"effort": "none"}' 'null' '{"max_tokens": 0}')
export OPENROUTER_PROVIDER='{"order": ["gmicloud/fp8"], "allow_fallbacks": false, "require_parameters": true}'
export CTRL_NAME=GMICloud
stamp() { date '+%m-%d %H:%M:%S'; }
over() { $PY -c "import sys; print(1 if float(sys.argv[1]) + float(sys.argv[2]) > float(sys.argv[3]) + 1e-9 else 0)" $1 $2 $3; }
push() { git add "$@" && git -c commit.gpgsign=false -c user.name="Tadael Shewarega" \
    -c user.email="iamTadaeltadi@users.noreply.github.com" commit -q -m "$MSG" || return 0
  git pull -q --rebase --autostash
  for i in 1 2 3 4 5; do
    git -c http.postBuffer=524288000 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=600 push -q && return 0
    sleep 30
  done
  echo "PUSH FAILED: $MSG"; }

if [ "$(date +%Y%m%d%H%M)" -gt $LASTSTART ]; then
  echo "$(stamp) $TAG probes did not start: start deadline (12 Nov 15:00) passed" | tee -a $LOG; exit 5
fi
BAL0=$(T balance); TOTAL0=$(T cost 'roc-*')
echo "$(stamp) $TAG probes start (Amendment 6 addendum): balance $BAL0, run F recorded $TOTAL0" >> $LOG
winner="" capped="" lines=()
for k in 1 2 3; do
  s=${SETTINGS[$k]} name=roc-probe-$TAG-s$k
  export G_REASONING=$s
  if [ "$s" = null ]; then export OPENROUTER_REASONING=""; else export OPENROUTER_REASONING=$s; fi
  verdict="not run"
  for n in 1 2; do
    spent=$(T cost "roc-probe-$TAG-s*")
    if [ "$(over $spent $PMAX $PCAP)" = 1 ]; then
      verdict="call $n not made: probe cap (\$$spent recorded + \$$PMAX > \$$PCAP)"; capped=1; break
    fi
    mkdir -p runs/$name
    echo "$(stamp) $TAG probe s$k call $n: OPENROUTER_REASONING='$OPENROUTER_REASONING' G_REASONING='$G_REASONING' OPENROUTER_PROVIDER=$OPENROUTER_PROVIDER" >> $LOG
    $PY -u experiments/run_structure.py --name $name "${SET[@]}" --limit $n --benchmark $ITEMS >> runs/$name/run.log 2>&1
    verdict=$(T probe_g $name $CTRL_NAME $n 2>/dev/null)
    [ "$verdict" = PASS ] || break
  done
  { echo "$(stamp) $TAG probe s$k reasoning=$s: $verdict"; T probe_g $name $CTRL_NAME 0 2>&1 >/dev/null; } >> $LOG
  lines+=("$k|$s|$verdict")
  [ "$verdict" = PASS ] && { winner=$s; break; }
  [ -n "$capped" ] && break
done

mkdir -p $RES/items; cp $ITEMS $RES/items/
for k in 1 2 3; do r=runs/roc-probe-$TAG-s$k; [ -d $r ] || continue; mkdir -p $RES/probe-s$k
  for f in structure.jsonl failed.jsonl run.log; do [ -f $r/$f ] && cp $r/$f $RES/probe-s$k/; done; done
if [ -n "$winner" ]; then outcome="setting \`$winner\` passed; run 2g is launched with it (launch_roc_nothink_gmi.sh)"
else outcome="no setting passed: GMICloud ignored every reasoning-off setting tried; run 2g is not run"; fi
echo "$(stamp) $TAG probes done: $outcome; probes cost $(T cost "roc-probe-$TAG-s*")" >> $LOG; cp $LOG $RES/cost.log
{ echo; echo "## Probes of other reasoning-off settings (Amendment 6 addendum; written $(date '+%d %b %Y %H:%M') EAT)"; echo
  echo "- on GMICloud fp8, same pin, no fallback; 5-attributed, the run's flags, no manipulation check; items: the defect \`create_html_repr::94\`, then the twin \`jobs_list_str::745::safe\` (runs/roc-items/probe2.jsonl)"
  echo "- a setting passes only if both calls report reasoning_tokens 0, served by GMICloud with the settings sent; the second call is made only if the first reports 0; probe cap \$$PCAP"
  echo "- setting 0 \`{\"enabled\": false}\` (the smoke test above): reasoning_tokens $($PY -c "
import json, glob
v = [json.loads(l).get('reasoning_tokens') for f in sorted(glob.glob('runs/$FIRSTSMOKE/*.jsonl')) for l in open(f) if l.strip()]
print(', '.join(str(x) for x in v))") on its 7 calls"
  for ln in $lines; do k=${ln%%|*}; rest=${ln#*|}; s=${rest%%|*}; v=${rest#*|}
    [ "$s" = null ] && shown="no reasoning field" || shown="\`$s\`"
    echo "- setting $k $shown: $v"; done
  echo "- outcome: $outcome"
  echo "- recorded cost of the probes: \$$(T cost "roc-probe-$TAG-s*"); run 2g so far (smoke test and probes): \$$(T cost "roc-smoke-$TAG*" "roc-probe-$TAG-s*"); run F total: \$$(T cost 'roc-*'); OpenRouter balance \$$BAL0 before the probes, \$$(T balance) now"
  echo; echo "Probe calls (raw usage objects):"; echo; echo '```'
  for k in 1 2 3; do [ -d runs/roc-probe-$TAG-s$k ] && { echo "s$k:"; T probe_g roc-probe-$TAG-s$k $CTRL_NAME 0 2>&1 >/dev/null; }; done
  echo '```'; echo; echo "HTTP and other call errors in the probe logs:"; echo; echo '```'
  grep -H "ERROR" runs/roc-probe-$TAG-s*/run.log(N) 2>/dev/null || echo "none"; echo '```'
  echo; echo "Files: probe-s{1,2,3}/ (records and logs of each probe made), items/probe2.jsonl, cost.log; commands: experiments/probe_nothink_gmi.sh."
} >> $RES/README.md
[ -n "$winner" ] && what="passed: $winner" || what="none passed"
MSG="run F 2g (Amendment 6 addendum): reasoning-off probes on GMICloud ($what)"; push $RES
if [ -z "$winner" ]; then echo "PROBE-DONE none passed: $(T cost "roc-probe-$TAG-s*") spent"; exit 7; fi
echo "PROBE-DONE passed: $winner; launching run 2g"
G_SETTING=$winner zsh $LAUNCHER
