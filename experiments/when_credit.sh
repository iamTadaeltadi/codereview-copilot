#!/bin/sh
# Runs that wait on API credit, in order of value per dollar. Run from the repo root.
set -e
export PYTHONPATH="$PWD:$PWD/services/graph:$PWD/services/agents"
# 26 Oct 2026: crossfile-v2 is withdrawn (results/WITHDRAWN-v2-structure.md). Everything
# below runs on v3, which is regenerated with the fixed generator from the same pools.
# Estimated total for the four cheap runs on all arms plus twins: $2-5 at observed prices.
# DO NOT RUN until the author has approved the spend.
B=data/crossfile-v3.jsonl
T=data/crossfile-v3-twins.jsonl
# 1. Four base runs, every arm (incl. 2b), on v3: ~$1.60
for spec in "tag openai/gpt-4o-mini v3-tag-gpt4omini" "flat openai/gpt-4o-mini v3-flat-gpt4omini" "tag deepseek/deepseek-v3.2 v3-tag-deepseek" "tag meta-llama/llama-3.3-70b-instruct v3-tag-llama"; do
  set -- $spec
  .venv/bin/python -u experiments/run_structure.py --limit 400 --encoding "$1" --model "$2" --name "$3" --benchmark $B
done
# 2. Twins on v3, two models: ~$0.60
.venv/bin/python -u experiments/run_structure.py --limit 400 --encoding tag --model openai/gpt-4o-mini --name v3twins-tag-gpt4omini --benchmark $T
.venv/bin/python -u experiments/run_structure.py --limit 400 --encoding tag --model deepseek/deepseek-v3.2 --name v3twins-tag-deepseek --benchmark $T
# 3. Neutral prompt (no "assume there is something to find"), twins then defects, gpt-4o-mini: ~$0.50
.venv/bin/python -u experiments/run_structure.py --limit 400 --encoding tag --model openai/gpt-4o-mini --neutral-prompt --arms 1-diff,2-evidence,3-topology,5-attributed,7-random --name v3twins-neutral-gpt4omini --benchmark $T
.venv/bin/python -u experiments/run_structure.py --limit 400 --encoding tag --model openai/gpt-4o-mini --neutral-prompt --arms 1-diff,2-evidence,3-topology,5-attributed,7-random --name v3-neutral-gpt4omini --benchmark $B
# 4. Judges on every new run (both families), then analysis, figures, paper:
# for r in runs/v3*; do .venv/bin/python experiments/judge_mechanism.py $r/structure.jsonl --strict; .venv/bin/python experiments/judge_mechanism.py $r/structure.jsonl --strict --model google/gemini-2.5-flash --suffix gemini; done
# 5. Only if the structure result survives on v3: one frontier model, tag, all arms (~$5-40 depending on model).
# .venv/bin/python -u experiments/run_structure.py --limit 400 --encoding tag --model anthropic/claude-sonnet-5.5 --name v3-tag-sonnet --benchmark $B
# --- the pre-review queue (v2) is kept below for the record and must not be run ---
: <<'OLD_V2_QUEUE'
B=data/crossfile-v2.jsonl
# 0. Neutral prompt (no "assume there is something to find"; empty list allowed), twins then defects,
#    gpt-4o-mini, tag encoding, arms 1/3/5/6/7: ~$0.30. Shows how much of the twin flag rate the prompt causes.
.venv/bin/python -u experiments/run_structure.py --limit 400 --encoding tag --model openai/gpt-4o-mini --neutral-prompt --arms 1-diff,3-topology,5-attributed,6-corrupted,7-random --name v2twins-neutral-gpt4omini --benchmark data/crossfile-v2-twins.jsonl
.venv/bin/python -u experiments/run_structure.py --limit 400 --encoding tag --model openai/gpt-4o-mini --neutral-prompt --arms 1-diff,3-topology,5-attributed,6-corrupted,7-random --name v2-neutral-gpt4omini --benchmark $B
# 1. Arm 2b (snippets, no metadata block) on the four base runs: ~$0.40
for spec in "tag openai/gpt-4o-mini v2-tag-gpt4omini" "flat openai/gpt-4o-mini v2-flat-gpt4omini" "tag deepseek/deepseek-v3.2 v2-tag-deepseek" "tag meta-llama/llama-3.3-70b-instruct v2-tag-llama"; do
  set -- $spec
  .venv/bin/python -u experiments/run_structure.py --limit 400 --encoding "$1" --model "$2" --arms 2b-snippets --name "$3" --benchmark $B
done
# 2. One frontier model, eight arms, tag encoding: ~$5-10 (pick one; prices on openrouter.ai/models)
# .venv/bin/python -u experiments/run_structure.py --limit 400 --encoding tag --model anthropic/claude-sonnet-5 --name v2-tag-sonnet --benchmark $B
# 3. c-CRAB second model, same pipeline: ~$3
# for c in A B C D; do extra=""; [ $c = B ] && extra="--prefer-cross-file"; [ $c = C ] && extra="--prefer-cross-file"; .venv/bin/python -u experiments/run.py --conditions $c $extra --depth 3 --hops 3 --limit 300 --model deepseek/deepseek-v3.2 --name ccrab-$c-deepseek; done
# Afterwards: judge the new rows (both judges), re-run paper/make_figures.py and paper/build_paper.py.
# .venv/bin/python experiments/judge_mechanism.py runs/<name>/structure.jsonl --strict
# .venv/bin/python experiments/judge_mechanism.py runs/<name>/structure.jsonl --strict --model google/gemini-2.5-flash --suffix gemini
OLD_V2_QUEUE
