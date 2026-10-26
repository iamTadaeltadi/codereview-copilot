"""Re-check a generated benchmark with the fixed generator checks.

    python experiments/audit_v2.py [defects.jsonl] [twins.jsonl] [--label v3]

For each task: does the caller's import resolve to the mutated module (strict
resolver; re-exports are followed through the repository pool in .pool-cache
when one is cached, else only within the two cached files); does every
distractor leave the definition file's syntax tree unchanged; for twins, does
either cached file hold a call the mutation would break. Writes
results/audit/v2-recheck.txt.
"""
import ast, glob, json, re, sys
from collections import Counter
from experiments.benchmark import load_crossfile
from experiments.evidence import sources_for
from experiments.crossfile import _resolves, _dependent_call_anywhere, _detail, _functions, VERIFIERS, _parents, _calls

def hunks(diff):
    return [(int(a), b, c) for a, b, c in re.findall(r"@@ -(\d+),1 \+\d+,1 @@\n-(.*)\n\+(.*)", diff)]

_POOLS = {}

def pool_sources(repo):
    """Every cached source file of the repository (the generator's own view)."""
    if repo not in _POOLS:
        hits = glob.glob(f".pool-cache/{repo.replace('/', '__')}@*.json")
        _POOLS[repo] = json.load(open(hits[0])) if hits else {}
    return _POOLS[repo]

def check(task, is_twin):
    meta = task.metadata; d = task.defects[0]
    src = sources_for(task)
    pool = pool_sources(meta.get("repo") or task.task_id.split("::")[1].replace("__", "/"))
    src = {**pool, **src}
    def find(p):
        return next((src[k] for k in src if k == p or k.endswith(p) or p.endswith(k)), None)
    dsrc, csrc = find(d.path), find(meta["caller_path"])
    out = {"task": task.task_id, "kind": meta.get("kind")}
    if dsrc is None or csrc is None:
        out["status"] = "sources missing"; return out
    try:
        ctree, dtree = ast.parse(csrc), ast.parse(dsrc)
    except SyntaxError:
        out["status"] = "unparseable"; return out
    name = task.task_id.split("::")[3]
    bound = _resolves(ctree, name, d.path, meta["caller_path"], src)
    out["import_resolves"] = bound is not None
    # distractors
    lines = dsrc.split("\n"); base = ast.dump(dtree); bad = 0
    for ln, before, after in hunks(task.diff):
        if ln == d.line: continue
        trial = list(lines)
        if trial[ln - 1] != before: bad += 1; continue
        trial[ln - 1] = after
        try:
            if ast.dump(ast.parse("\n".join(trial))) != base: bad += 1
        except SyntaxError: bad += 1
    out["distractors_changing_tree"] = bad
    out["defect_last"] = all(ln < d.line for ln, _, _ in hunks(task.diff) if ln != d.line)
    if is_twin:
        fn = next((f for f in _functions(dtree, lines) if f.name == name and f.lineno <= d.line <= getattr(f, "end_lineno", 10**9)), None)
        raw = RAW.get(task.task_id, {})
        detail = _detail(meta["kind"], fn, raw.get("before", ""), raw.get("after", "")) if fn else None
        if fn is None or detail is None:
            out["twin_check"] = "no detail"
        else:
            parsed = {d.path: (dtree, lines, dsrc), meta["caller_path"]: (ctree, csrc.split("\n"), csrc)}
            dep = _dependent_call_anywhere(parsed, {d.path: dsrc, meta["caller_path"]: csrc}, fn, name, d.path, meta["kind"], detail)
            out["twin_unsafe"] = bool(dep); out["twin_where"] = dep
    return out

rows = []
args = [a for a in sys.argv[1:] if not a.startswith("--")]
label = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else "v2"
files = ((args[0] if args else "data/crossfile-v2.jsonl", False),
         (args[1] if len(args) > 1 else "data/crossfile-v2-twins.jsonl", True))
for path, is_twin in files:
    RAW = {json.loads(l)["task_id"]: json.loads(l) for l in open(path) if l.strip()}
    tasks = load_crossfile(path)
    res = [check(t, is_twin) for t in tasks]
    rows += [(path, r) for r in res]
    n = len(res)
    print(f"== {path}: {n} tasks")
    print("  import does not resolve to the mutated module:", sum(1 for r in res if r.get("import_resolves") is False), "/", n)
    print("  tasks with a tree-changing distractor:", sum(1 for r in res if r.get("distractors_changing_tree", 0) > 0), "/", n)
    print("  defect is the last change:", sum(1 for r in res if r.get("defect_last")), "/", n)
    if is_twin:
        print("  twins unsafe within the two files:", sum(1 for r in res if r.get("twin_unsafe")), "/", n,
              " (no detail:", sum(1 for r in res if r.get("twin_check") == "no detail"), ")")
    print("  by kind, import fails:", Counter(r["kind"] for r in res if r.get("import_resolves") is False))
    print("  other statuses:", Counter(r.get("status") for r in res if r.get("status")))
with open(f"results/audit/{label}-recheck.jsonl", "w") as h:
    for p, r in rows: h.write(json.dumps({"file": p, **r}) + "\n")
