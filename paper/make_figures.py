"""Figures from the frozen results. No numbers are typed by hand here."""
import json, re, collections, pathlib
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "paper" / "figures"; OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

def arms_from_analysis(path):
    """arm -> mean metric, from an analyse_structure report."""
    out = {}
    for line in pathlib.Path(path).read_text().splitlines():
        m = re.match(r"^(\d-[a-z]+)\s+\d+\s+\d+\s+([0-9.]+)", line)
        if m: out[m.group(1)] = float(m.group(2))
    return out

def cells_from_analysis(path):
    """(a,b) -> (diff, lo, hi) for every comparison in a report."""
    t = pathlib.Path(path).read_text(); out = {}
    for m in re.finditer(r"(?:primary|secondary|extra \d+): (\S+) minus (\S+).*?\n\s+difference\s+(\S+)\s+repo-clustered 95% CI \[\s*(\S+),\s+(\S+)\]", t, re.S):
        out[(m.group(1), m.group(2))] = tuple(float(x) for x in m.group(3, 4, 5))
    return out

ARMS = ["1-diff", "8-header", "7-random", "2-evidence", "3-topology", "4-typed", "5-attributed", "6-corrupted"]
LABEL = {"1-diff": "diff only", "8-header": "header only", "7-random": "foreign code", "2-evidence": "evidence (control)",
         "3-topology": "+ bare link", "4-typed": "+ typed link", "5-attributed": "+ attributed", "6-corrupted": "+ corrupted"}
RUNS = [("v2-tag-gpt4omini", "gpt-4o-mini, tag"), ("v2-flat-gpt4omini", "gpt-4o-mini, flat"),
        ("v2-tag-deepseek", "deepseek-v3.2, tag"), ("v2-tag-llama", "llama-3.3-70b, tag")]


# Figure 1: the partial-input ceiling, diff-only hit rate per benchmark version and on real defects
bars = []
m = re.search(r"^1-diff\s+\d+\s+\d+\s+([0-9.]+)", (ROOT / "results" / "v2-tag-gpt4omini" / "analysis-hit.txt").read_text(), re.M)
if m: bars.append(("second version\n(withdrawn)", float(m.group(1)) * 100))
v3 = [json.loads(l) for l in (ROOT / "results" / "v3-ceiling" / "structure-gpt4omini-tag-partial.jsonl").open() if l.strip()]
d = [r for r in v3 if r["arm"] == "1-diff"]
bars.append(("third version\n(stopped at %d)" % len(d), 100 * sum(1 for r in d if r["hit"]) / len(d)))
t = (ROOT / "results" / "ccrab-today" / "analysis.txt").read_text()
m = re.search(re.escape("A  diff only (today)") + r"\s+([0-9.]+)%", t)
bars.append(("c-CRAB real defects\n(n=219)", float(m.group(1))))
fig, ax = plt.subplots(figsize=(6.2, 2.8))
ax.bar(range(len(bars)), [b[1] for b in bars], color=["#8A939D", "#8A939D", "#0E6B63"][:len(bars)])
for i, (lab, v) in enumerate(bars): ax.text(i, v + 1.5, f"{v:.1f}", ha="center", fontsize=8.5)
ax.axhline(95, ls=":", lw=0.8, color="#A4381F"); ax.text(len(bars) - 0.5, 96, "stop rule 95%", fontsize=7.5, color="#A4381F", ha="right")
ax.set_xticks(range(len(bars))); ax.set_xticklabels([b[0] for b in bars], fontsize=8); ax.set_ylim(0, 110)
ax.set_ylabel("% defect lines found, diff only")
fig.tight_layout(); fig.savefig(OUT / "fig1-ceiling.pdf"); fig.savefig(OUT / "fig1-ceiling.png", dpi=180); plt.close(fig)

# Figure 2: c-CRAB real defects, controlled comparison
t = (ROOT / "results" / "ccrab-today" / "analysis.txt").read_text()
rates = {}
for lab, key in (("diff only", "A  diff only (today)"), ("random, any file", "C  random nodes, same budget"), ("lexical", "D  lexical, same budget"),
                 ("graph, as reported\n(withdrawn)", "B  graph, repaired retrieval"), ("random, other files only", "random, other files only"),
                 ("graph, seed span removed", "Bs graph, seed stripped")):
    m = re.search(re.escape(key) + r"\s+([0-9.]+)%", t)
    if m: rates[lab] = float(m.group(1))
order = ["diff only", "random, any file", "random, other files only", "lexical", "graph, seed span removed", "graph, as reported\n(withdrawn)"]
order = [o for o in order if o in rates]
fig, ax = plt.subplots(figsize=(7.4, 3.2))
ax.bar(range(len(order)), [rates[o] for o in order], color=["#8A939D"] * (len(order) - 1) + ["#A4381F"])
for i, o in enumerate(order): ax.text(i, rates[o] + 1, f"{rates[o]:.1f}", ha="center", fontsize=8.5)
ax.set_xticks(range(len(order))); ax.set_xticklabels(order, fontsize=7.5, rotation=12); ax.set_ylim(0, 60); ax.set_ylabel("% of real defects localised, 5-line tolerance")
fig.tight_layout(); fig.savefig(OUT / "fig2-ccrab.pdf"); fig.savefig(OUT / "fig2-ccrab.png", dpi=180); plt.close(fig)

# Figure 3: safe twins on the third benchmark (drawn only once both runs are frozen)
runs = [("v3twins-tag-gpt4omini", "gpt-4o-mini"), ("v3twins-tag-deepseek", "deepseek-v3.2"), ("v3twins-neutral-gpt4omini", "gpt-4o-mini, neutral prompt")]
if all((ROOT / "results" / r / "analysis-correct.txt").exists() for r, _ in runs):
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    arms = ["1-diff", "8-header", "7-random", "2-evidence", "3-topology", "4-typed", "6-corrupted", "5-attributed"]
    w = 0.27
    for i, (run, lab) in enumerate(runs):
        v = arms_from_analysis(ROOT / "results" / run / "analysis-correct.txt")
        ax.bar([j + (i - 0.5) * w for j in range(len(arms))], [v.get(a, 0) * 100 for a in arms], width=w, label=lab, color=["#0E6B63", "#5EC2B6", "#A4381F"][i])
    ax.set_xticks(range(len(arms))); ax.set_xticklabels([LABEL[a] for a in arms], fontsize=7.5, rotation=15)
    ax.set_ylabel("% of safe twins left unflagged"); ax.set_ylim(0, 100); ax.legend(frameon=False, fontsize=7.5)
    fig.tight_layout(); fig.savefig(OUT / "fig3-twins.pdf"); fig.savefig(OUT / "fig3-twins.png", dpi=180); plt.close(fig)
for old in ("fig1-arms", "fig2-primary", "fig3-ccrab", "fig4-twins"):
    for ext in ("pdf", "png"):
        f = OUT / f"{old}.{ext}"
        if f.exists(): f.unlink()
print("figures written:", sorted(p.name for p in OUT.iterdir()))
