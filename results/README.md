# Results

Frozen output of the experiment. Every number in the paper traces to a file here.

```
gpt-4o-mini/
  outcomes.jsonl   one row per ground-truth defect per condition: hit or miss,
                   with the task id the row clusters on
  reviews.jsonl    one row per review: condition, context size, findings
                   reported, token usage and cost, parse status
  analysis.txt     the output of experiments/analyse.py over that run
  config.json      the model, conditions, budget, tolerance and run matrix
```

Reproduce with:

```bash
python experiments/run.py --limit 400 --conditions A,B,C,D,E,F,G \
  --model openai/gpt-4o-mini --name replication
python experiments/analyse.py runs/replication --bootstrap 3000
```

Raw model replies are not committed: they are large, and every claim in the
paper is computed from `outcomes.jsonl` and `reviews.jsonl`. They are written
to `runs/<name>/raw.jsonl` by any run.
