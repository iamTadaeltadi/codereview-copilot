"""Restore .source-cache for every task in the given benchmark files (raw GitHub, no token needed)."""
import sys
from concurrent.futures import ThreadPoolExecutor
from experiments.benchmark import load_crossfile
from experiments.evidence import sources_for

tasks = [t for f in sys.argv[1:] for t in load_crossfile(f)]
print(f"{len(tasks)} tasks", flush=True)
def one(t):
    try:
        return len(sources_for(t))
    except Exception as e:
        return f"error {e}"
with ThreadPoolExecutor(max_workers=8) as pool:
    for i, r in enumerate(pool.map(one, tasks), 1):
        if i % 25 == 0 or isinstance(r, str):
            print(i, r, flush=True)
print("done", flush=True)
