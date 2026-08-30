import os, sys
_H=os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [x for x in sys.path if os.path.abspath(x or os.getcwd()) != _H]
_R=os.path.dirname(_H)
if _R not in sys.path: sys.path.insert(0,_R)
import json, collections
from experiments.benchmark import load_crossfile
from experiments.crossfile_score import score_review
from experiments.matcher import ReportedFinding

tasks={t.task_id:t for t in load_crossfile("data/crossfile.jsonl")}
raw=[json.loads(l) for l in open("runs/crossfile-fixed/raw.jsonl")]
conds=["A","B","C","D","G"]
seen=collections.defaultdict(set)
for d in raw: seen[d["task_id"]].add(d["condition"])
comp={k for k,v in seen.items() if set(conds)<=v}

sc=collections.defaultdict(dict); rawby=collections.defaultdict(dict)
for d in raw:
    t=tasks.get(d["task_id"])
    if not t or d["task_id"] not in comp: continue
    f=[ReportedFinding(str(i),x["path"],x["line"],"") for i,x in enumerate(d["findings"])]
    sc[d["task_id"]][d["condition"]]=score_review(t,d["condition"],f,tolerance=0)
    rawby[d["task_id"]][d["condition"]]=d
ids=sorted(sc)
LBL={"A":"diff only","B":"graph","C":"random","D":"lexical","G":"dense"}

print("=== CRITICISM 2: is the +9 a response-policy effect? ===")
print(f"{'cond':<12}{'exactly right':>14}{'findings/review':>17}{'confirmed FP/review':>21}")
for c in conds:
    n=len(ids)
    findings=sum(len(rawby[i][c]["findings"]) for i in ids)/n
    fp=sum(sc[i][c].flagged_distractors for i in ids)/n
    print(f"{LBL[c]:<12}{sum(sc[i][c].precise for i in ids)/n:>13.0%}{findings:>17.2f}{fp:>21.2f}")

print("\n=== CRITICISM 3: paired table, graph vs random ===")
tab=collections.Counter()
for i in ids:
    tab[(sc[i]["B"].precise, sc[i]["C"].precise)] += 1
print(f"{'':<16}{'random right':>14}{'random wrong':>14}")
print(f"{'graph right':<16}{tab[(True,True)]:>14}{tab[(True,False)]:>14}")
print(f"{'graph wrong':<16}{tab[(False,True)]:>14}{tab[(False,False)]:>14}")
disc=tab[(True,False)]+tab[(False,True)]
print(f"\n  discordant pairs: {disc} of {len(ids)} ({disc/len(ids):.0%})")
print(f"  they disagree on {disc} tasks — identical marginals, different behaviour")
