# v3 neutral prompt on google/gemini-2.5-flash — PARTIAL (29 October 2026)

`experiments/run_structure.py --limit 400 --encoding tag --model google/gemini-2.5-flash
--neutral-prompt --arms 1-diff,2-evidence,5-attributed,7-random`, thinking off, on
`data/crossfile-v3.jsonl` (this folder) and `data/crossfile-v3-twins.jsonl`
(`../v3twins-neutral-gemini/`). Recorded before the API key's $5.00 cap stopped every request
with HTTP 403: 80 defects and 80 twins (the first tasks in file order), 21 repositories. Spend
on the two streams $0.27. A relaunch with the same names resumes.

`analysis-signal-detection.txt` (H = hit rate on defects, F = flag rate on twins, d', c) and
`analysis-balanced-with-twins.txt`:

| arm | H | F | d' | c | balanced |
|---|---|---|---|---|---|
| 1-diff | 0.667 | 0.630 | 0.10 | −0.38 | 0.525 |
| 2-evidence | 0.850 | 0.802 | 0.19 | −0.94 | 0.525 |
| 5-attributed | 0.887 | 0.815 | 0.32 | −1.05 | 0.537 |
| 7-random | 0.675 | 0.550 | 0.33 | −0.29 | 0.562 |

On this partial set gemini-2.5-flash flags most twins even with the diff alone (F 0.63), so c is
already negative for the diff and falls further with attributed evidence (c − c(diff) −0.67
[−0.95, −0.48]); d' differences from the diff all span zero. Balanced accuracy 0.52 to 0.56,
attributed − diff +0.013 [−0.083, +0.118].
