import json, collections, random
from concurrent.futures import ThreadPoolExecutor
from experiments.benchmark import load_crossfile
from experiments.crossfile_score import score_review
from experiments.matcher import ReportedFinding
from experiments.sparse import collect_sources

tasks={t.task_id:t for t in load_crossfile("data/crossfile.jsonl")}
def has_caller(t):
    try:
        src=collect_sources(t.repo,t.review_commit,t.diff,max_files=120,import_hops=3)
    except Exception: return t.task_id,False
    c=t.metadata["caller_path"]
    return t.task_id,(c in src or any(p.endswith(c) for p in src))
with ThreadPoolExecutor(max_workers=16) as pool:
    reach=dict(pool.map(has_caller,tasks.values()))

raw=[json.loads(l) for l in open("results/crossfile/reviews.jsonl")]
conds=["A","B","C","D","F","G"]
seen=collections.defaultdict(set)
for d in raw: seen[d["task_id"]].add(d["condition"])
comp={k for k,v in seen.items() if set(conds)<=v}
sc=collections.defaultdict(dict)
for d in raw:
    t=tasks.get(d["task_id"])
    if not t or d["task_id"] not in comp: continue
    f=[ReportedFinding(str(i),x["path"],x["line"],"") for i,x in enumerate(d["findings"])]
    sc[d["task_id"]][d["condition"]]=score_review(t,d["condition"],f,tolerance=0)

LBL={"A":"no context","B":"graph","C":"RANDOM","D":"lexical","F":"fault-loc oracle","G":"dense"}
for label,ids in (("CALLER IN THE POOL — a fair retrieval test",
                   sorted(i for i in sc if reach.get(i))),
                  ("CALLER ABSENT — retrieval could not find it",
                   sorted(i for i in sc if not reach.get(i)))):
    if len(ids)<20: continue
    print(f"\n=== {label}  (n={len(ids)}) ===")
    for c in conds:
        r=sum(sc[i][c].precise for i in ids)/len(ids)
        print(f"  {LBL[c]:<18}{r:>6.0%}")
    def rate(s,c): return sum(sc[i][c].precise for i in s)/len(s)
    def boot(a,b,t=4000):
        rng=random.Random(0); pt=rate(ids,a)-rate(ids,b); d=[]
        for _ in range(t):
            s=[rng.choice(ids) for _ in ids]; d.append(rate(s,a)-rate(s,b))
        d.sort(); return pt,d[int(.025*t)],d[int(.975*t)]
    p,lo,hi=boot("B","C")
    print(f"  graph vs RANDOM: {p:+.1%} [{lo:+.1%}, {hi:+.1%}] {'EXCLUDES ZERO' if lo>0 or hi<0 else 'spans zero'}")
