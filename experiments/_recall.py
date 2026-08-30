import os, sys
_H=os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [x for x in sys.path if os.path.abspath(x or os.getcwd()) != _H]
_R=os.path.dirname(_H)
for _p in (_R, os.path.join(_R,'services','agents'), os.path.join(_R,'services','graph')):
    if _p not in sys.path: sys.path.insert(0,_p)
import json, collections
from concurrent.futures import ThreadPoolExecutor
from experiments.benchmark import load_crossfile
from experiments.sparse import collect_sources, graph_from_sources
from experiments.run import _seed_query
from Utils.ToolOrganizer import build_tools

tasks=load_crossfile("data/crossfile.jsonl")

def recall(t):
    try: src=collect_sources(t.repo,t.review_commit,t.diff,max_files=120,import_hops=3)
    except Exception: return None
    caller=t.metadata["caller_path"]
    if not any(p==caller or p.endswith(caller.split('/')[-1]) for p in src): return None
    g=graph_from_sources(src); q=_seed_query(t,g)
    out={}
    for cond,kw in (("B",dict(prefer_cross_file=True,max_depth=3)),
                    ("C",dict(seed=1)), ("D",{}), ("G",{})):
        tools=build_tools(g,"/tmp",condition=cond,max_neighbors=80,budget_tokens=1500,**kw)
        try: r=json.loads(tools[0].invoke({"node": q}))
        except Exception: r={"neighbors":[]}
        paths={n["relative_path"] for n in r["neighbors"]}
        out[cond]=any(p==caller or (p and caller.endswith(p.split('/')[-1])) for p in paths)
    return out

with ThreadPoolExecutor(max_workers=12) as pool:
    res=[r for r in pool.map(recall, tasks[:100]) if r]
LBL={"B":"graph","C":"random","D":"lexical","G":"dense"}
print("EVIDENCE RECALL — did the retriever return the file the defect depends on?")
print(f"measured on {len(res)} tasks where that file is in the pool\n")
for c in ("B","C","D","G"):
    k=sum(1 for r in res if r[c])
    print(f"  {LBL[c]:<10}{k:>3}/{len(res)}  {k/len(res):>5.0%}")
