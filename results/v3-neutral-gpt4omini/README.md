# Neutral prompt on the 277 third-version defects, gpt-4o-mini

Run 27 Oct 2026 with `experiments/run_structure.py --limit 400 --encoding tag
--model openai/gpt-4o-mini --neutral-prompt --benchmark data/crossfile-v3.jsonl`,
the same settings as `v3twins-neutral-gpt4omini/`. 277 defects; 6 had no
evidence set (fewer than three snippets) and were skipped, 271 answered on all
nine arms, 0 parse failures in 2,439 replies, $0.38. Stop rule was $1.50.

- `structure.jsonl` — one record per (defect, arm), `manipulation.jsonl` the read-back checks
- `analysis-hit.txt`, `analysis-precise.txt` — detection within tolerance and on the exact line
- `analysis-balanced-with-twins.txt` — this file and `v3twins-neutral-gpt4omini/structure.jsonl`
  read as one dataset: balanced accuracy = (hit rate on defects + clear rate on twins) / 2,
  per arm and per comparison, repository-clustered paired bootstrap
- `run.log`, `cost.log` — the run's console output and the cost watcher's samples

- `analysis-signal-detection.txt` — per arm, H = hit rate on the defects, F = flag rate on the twins
  (`v3twins-neutral-gpt4omini/structure.jsonl`), d' = z(H) − z(F), c = −(z(H)+z(F))/2, repository
  bootstrap (`experiments/signal_detection.py`). c falls from +0.71 (diff) to −1.07 (attributed);
  every arm with caller code or dependency metadata has d' at or below the diff's 0.37.
