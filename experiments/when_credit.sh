#!/bin/sh
# Runs that wait on API credit, in order of value per dollar. Run from the repo root.
set -e
export PYTHONPATH="$PWD:$PWD/services/graph:$PWD/services/agents"
B=data/crossfile-v2.jsonl
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
