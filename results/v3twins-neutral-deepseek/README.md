# Neutral prompt on the 165 third-version twins, deepseek-v3.2

Run 27 Oct 2026 with `experiments/run_structure.py --limit 400 --encoding tag
--model deepseek/deepseek-v3.2 --neutral-prompt`, the same per-call settings as
`v3twins-neutral-gpt4omini/`. Under the neutral prompt this model reasons three
to four times longer than under the presuming prompt, so the sequential run was
stopped after one task (`structure-sequential-start-8-rows.jsonl`, kept, not
used) and the twin file was split into three interleaved shards
(`crossfile-v3-twins.jsonl` rows 0,3,6,..., 1,4,7,..., 2,5,8,...) run in
parallel; `structure-shard{0,1,2}.jsonl` are the records, read together by
`analyse_structure.py`. 158 twins answered on all nine arms, 0 parse failures
in 1,422 replies, $0.55 against a $1.50 stop rule. The manipulation checks
(`manipulation-shard*.jsonl`) fall on every eighth task of each shard.
