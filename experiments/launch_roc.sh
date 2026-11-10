#!/bin/zsh
# Run F (paper/PREREG-F.md, Amendments 1 and 2), in the pre-registered order: gpt-4o-mini and
# deepseek-v3.2 with 4 arms, then both --authoritative with 3 arms. Amendment 2 raised the deepseek
# caps and dropped run 5. A run whose results folder already records it as finished is skipped.
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
  local envp="" amend="Amendment 1"
  [ $tag = gpt41 ] && envp="PROJECT=1 "
  if [ -n "${CTRL_NAME:-}" ]; then amend="Amendment 3"
    envp="OPENROUTER_REASONING='$OPENROUTER_REASONING' OPENROUTER_PROVIDER='$OPENROUTER_PROVIDER' CTRL_NAME=$CTRL_NAME "; fi
  printf '#!/bin/zsh\n# Run F model run (paper/PREREG-F.md, %s), as launched by experiments/launch_roc.sh\n%szsh experiments/roc_run.sh %s %s %s %s %s\n' \
    "$amend" "$envp" $tag $model $cap $arms "$*" > $d/launch.sh
  for f in structure.jsonl manipulation.jsonl run.log; do cp runs/roc-smoke-$tag/$f $d/smoke/ 2>/dev/null; done
  for f in runs/roc-smoke-$tag-*-failed(N); do cp -R $f $d/smoke-${f#runs/roc-smoke-$tag-}; done
  for kind in defects twins; do for s in 0 1 2; do local r=runs/roc-$tag-$kind-shard$s
    [ -f $r/structure.jsonl ] && cp $r/structure.jsonl $d/structure-$kind-shard$s.jsonl
    [ -f $r/manipulation.jsonl ] && cp $r/manipulation.jsonl $d/manipulation-$kind-shard$s.jsonl
    [ -f $r/run.log ] && cp $r/run.log $d/run-$kind-shard$s.log
    [ -f $r/run-pass1.log ] && cp $r/run-pass1.log $d/run-$kind-shard$s-pass1.log
    [ -f $r/run-interrupted.log ] && cp $r/run-interrupted.log $d/run-$kind-shard$s-interrupted.log; done; done
  cp runs/roc-$tag-cost.log $d/cost.log 2>/dev/null
  local what; case $rc in 0) what="finished";; 3) what="did not start: smoke test failed or gave no reply";;
    4) what="stopped by its cap or the \$4.00 total";; 5) what="did not start: smoke cost projected the run above its cap";;
    6) what="stopped by the Amendment 3 abort rule (not restarted)";;
    *) what="exit $rc";; esac
  { echo "# Run F: $tag (paper/PREREG-F.md, $amend)"; echo
    echo "- model: \`$model\`; arms: $arms; cap \$$cap; extra flags: ${*:-none}"
    echo "- shared flags: --limit 400 --encoding tag --neutral-prompt --confidence --hunk-ratings --kinds default_flip"
    echo "- outcome: $what"
    echo "- recorded cost of this run (smoke included): \$$(T cost roc-smoke-$tag "roc-$tag-defects-shard*" "roc-$tag-twins-shard*"); run F total so far: \$$(T cost 'roc-*')"
    grep -h "STOPPED\|ABORTED\|smoke:\|projection:" runs/roc-$tag-cost.log 2>/dev/null | sed 's/^/- log: /'
    if [ -n "${CTRL_NAME:-}" ]; then
      echo "- settings on every call: OPENROUTER_REASONING=\`$OPENROUTER_REASONING\` OPENROUTER_PROVIDER=\`$OPENROUTER_PROVIDER\`"
      echo "- calls seen: $(T ctrlstats roc-smoke-$tag "roc-$tag-defects-shard*" "roc-$tag-twins-shard*")"
      [ "$(T usage roc-smoke-$tag "roc-$tag-defects-shard*" "roc-$tag-twins-shard*" | grep -c "provider=None")" -gt 0 ] && \
        echo "- some calls did not report the provider; allow_fallbacks false still pins it to $CTRL_NAME"
      echo; echo "Smoke usage objects (raw, before the run was launched):"; echo; echo '```'
      T usage roc-smoke-$tag; echo '```'
    fi
    echo; echo "Files: launch.sh (the command), structure-{defects,twins}-shard{0,1,2}.jsonl (one record per item and arm),"
    echo "manipulation-*.jsonl, run-*.log, smoke/ (the 3 smoke calls), cost.log, analysis-roc.txt"
    echo "(\`python3 experiments/analyse_roc.py results/$folder\`)."; } > $d/README.md
  ls $d/structure-*.jsonl >/dev/null 2>&1 && $PY experiments/analyse_roc.py $d > $d/analysis-roc.txt 2>&1
  push $d "run F ($tag): records, analysis and README as recorded ($what)"; }
model() { local tag=$1 m=$2 cap=$3 folder=$4 arms=$5; shift 5
  grep -q "outcome: finished" results/$folder/README.md 2>/dev/null && { echo "== $tag already finished, skipped"; return 0; }
  echo "== $tag $(date '+%m-%d %H:%M') cap $cap"; can_start $cap || { echo "$tag NOT STARTED"; return 2; }
  zsh experiments/roc_run.sh $tag $m $cap $arms "$@"; local rc=$?
  echo "$tag exit $rc"; freeze $tag $folder $rc $m $cap $arms "$@"; return $rc; }
# Run 5's cap: the money left under $4.00, less a 5-cent margin for calls in flight when the watcher stops.
left() { $PY -c "import sys; print(f'{float(sys.argv[1]) - 0.05:.2f}')" $(T remaining); }

model gpt4omini openai/gpt-4o-mini 1.00 v3-roc-gpt4omini $ARMS4
model deepseek deepseek/deepseek-v3.2 1.85 v3-roc-deepseek $ARMS4
model gpt4omini-auth openai/gpt-4o-mini 0.40 v3-roc-gpt4omini-auth $ARMS3 --authoritative
model deepseek-auth deepseek/deepseek-v3.2 1.45 v3-roc-deepseek-auth $ARMS3 --authoritative

# Amendment 3 (post hoc): controlled deepseek reruns, reasoning off, one fp8 provider. Both smoke tests
# run first; if either fails on AtlasCloud, both reruns move to GMICloud (failed smoke folders kept).
ctrl_smokes() { local rc=0
  SMOKE_ONLY=1 zsh experiments/roc_run.sh deepseek-ctrl deepseek/deepseek-v3.2 0.70 $ARMS4 || rc=1
  SMOKE_ONLY=1 zsh experiments/roc_run.sh deepseek-auth-ctrl deepseek/deepseek-v3.2 0.50 $ARMS3 --authoritative || rc=1
  return $rc; }
if [ "$(date +%Y%m%d%H%M)" -le 202611121800 ]; then
  export OPENROUTER_REASONING='{"enabled": false}'
  chosen=""
  for pair in "atlas-cloud/fp8 AtlasCloud" "gmicloud/fp8 GMICloud"; do
    slug=${pair% *}; export CTRL_NAME=${pair#* }
    export OPENROUTER_PROVIDER="{\"order\": [\"$slug\"], \"allow_fallbacks\": false, \"require_parameters\": true}"
    echo "== ctrl smoke tests on $slug $(date '+%m-%d %H:%M')"
    if ctrl_smokes; then chosen=$slug; break; fi
    echo "ctrl smoke FAILED on $slug"
    for t in deepseek-ctrl deepseek-auth-ctrl; do [ -d runs/roc-smoke-$t ] && mv runs/roc-smoke-$t runs/roc-smoke-$t-${slug%%/*}-failed; done
  done
  if [ -z "$chosen" ]; then echo "CTRL: no provider passed both smoke tests; nothing runs"
  else
    echo "== ctrl provider $chosen"
    model deepseek-ctrl deepseek/deepseek-v3.2 0.70 v3-roc-deepseek-ctrl $ARMS4; rc=$?
    if [ $rc = 3 ] || [ $rc = 6 ]; then echo "deepseek-ctrl exit $rc: deepseek-auth-ctrl not started"
    else model deepseek-auth-ctrl deepseek/deepseek-v3.2 0.50 v3-roc-deepseek-auth-ctrl $ARMS3 --authoritative; fi
  fi
fi
echo "ROC-DONE total=$(T cost 'roc-*') balance=$(T balance)"
