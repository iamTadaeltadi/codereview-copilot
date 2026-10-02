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

# Figure 1: per-arm means for judge J1, judge J2 and precision, four runs
fig, axes = plt.subplots(3, 4, figsize=(11, 7.2), sharey="row")
for col, (run, title) in enumerate(RUNS):
    d = ROOT / "results" / run
    series = [("judge J1 (deepseek)", arms_from_analysis(d / "analysis-strict-judge.txt")),
              ("judge J2 (gemini)", arms_from_analysis(d / "analysis-gemini-judge.txt")),
              ("precision", arms_from_analysis(d / "analysis-precise.txt"))]
    for row, (name, vals) in enumerate(series):
        ax = axes[row][col]
        order = list(reversed(ARMS))  # diff only at the top, corrupted at the bottom
        ys = [vals.get(a, float("nan")) * 100 for a in order]
        palette = {"1-diff": "#8A939D", "8-header": "#8A939D", "7-random": "#8A939D", "2-evidence": "#0E6B63",
                   "3-topology": "#5EC2B6", "4-typed": "#5EC2B6", "5-attributed": "#5EC2B6", "6-corrupted": "#A4381F"}
        ax.barh(range(len(order)), ys, color=[palette[a] for a in order])
        ax.set_yticks(range(len(order)))
        if col == 0:
            ax.set_yticklabels([LABEL[a] for a in order])
        ax.set_xlim(0, 100)
        for i, y in enumerate(ys):
            if y == y: ax.text(y + 1, i, f"{y:.0f}", va="center", fontsize=7.5)
        if row == 0: ax.set_title(title, fontsize=9.5)
        if col == 0: ax.set_ylabel(name, fontsize=9)
        if row == 2: ax.set_xlabel("% of tasks")
fig.suptitle("Figure 1. Per-arm rates on the rebuilt benchmark (225–230 paired defects per run). Arms 2–6 see identical snippets.", fontsize=10, y=1.0)
fig.tight_layout(); fig.savefig(OUT / "fig1-arms.pdf"); fig.savefig(OUT / "fig1-arms.png", dpi=180); plt.close(fig)

# Figure 2: the primary comparison with intervals, two judges + precision, four runs
fig, ax = plt.subplots(figsize=(7.2, 3.4))
x = 0; ticks = []; labels = []
for run, title in RUNS:
    d = ROOT / "results" / run
    for name, f, c in (("J1", "analysis-strict-judge.txt", "#0E6B63"), ("J2", "analysis-gemini-judge.txt", "#5EC2B6"), ("precision", "analysis-precise.txt", "#8A5F12")):
        cell = cells_from_analysis(d / f).get(("3-topology", "2-evidence"))
        if cell:
            diff, lo, hi = (v * 100 for v in cell)
            ax.errorbar(x, diff, yerr=[[diff - lo], [hi - diff]], fmt="o", color=c, capsize=3, label=name if run == RUNS[0][0] else None)
        x += 1
    ticks.append(x - 2); labels.append(title); x += 1
ax.axhline(0, color="#999", lw=0.8); ax.set_xticks(ticks); ax.set_xticklabels(labels, fontsize=8.5)
ax.set_ylabel("bare link − scrambled control (points)"); ax.legend(frameon=False, fontsize=8)
ax.set_title("Figure 2. Topology against the density-matched control: 95% repository-clustered intervals.", fontsize=9.5)
fig.tight_layout(); fig.savefig(OUT / "fig2-primary.pdf"); fig.savefig(OUT / "fig2-primary.png", dpi=180); plt.close(fig)

# Figure 3: c-CRAB real defects, controlled comparison
t = (ROOT / "results" / "ccrab-today" / "analysis.txt").read_text()
rates = {}
for lab, key in (("diff only", "A  diff only (today)"), ("random, any file", "C  random nodes, same budget"), ("lexical", "D  lexical, same budget"),
                 ("graph, repaired", "B  graph, repaired retrieval"), ("random, other files only", "random, other files only")):
    m = re.search(re.escape(key) + r"\s+([0-9.]+)%", t)
    if m: rates[lab] = float(m.group(1))
order = ["diff only", "random, any file", "random, other files only", "lexical", "graph, repaired"]
fig, ax = plt.subplots(figsize=(6.2, 3.0))
ax.bar(range(len(order)), [rates[o] for o in order], color=["#8A939D", "#8A939D", "#8A939D", "#8A939D", "#0E6B63"])
for i, o in enumerate(order): ax.text(i, rates[o] + 1, f"{rates[o]:.1f}", ha="center", fontsize=8.5)
ax.set_xticks(range(len(order))); ax.set_xticklabels(order, fontsize=8, rotation=12); ax.set_ylim(0, 60); ax.set_ylabel("% of real defects localised")
ax.set_title("Figure 3. c-CRAB, 218 test-verified defects, one day, one pipeline, 1,500-token budget (gpt-4o-mini).", fontsize=9)
fig.tight_layout(); fig.savefig(OUT / "fig3-ccrab.pdf"); fig.savefig(OUT / "fig3-ccrab.png", dpi=180); plt.close(fig)

# Figure 4: twins
fig, ax = plt.subplots(figsize=(6.6, 3.0))
runs = [("v2twins-tag-gpt4omini", "gpt-4o-mini"), ("v2twins-tag-deepseek", "deepseek-v3.2"), ("v2twins-auth-gpt4omini", "gpt-4o-mini, 'every use' instruction")]
arms = ["1-diff", "2-evidence", "3-topology", "5-attributed", "6-corrupted", "7-random", "8-header"]
w = 0.26
for i, (run, lab) in enumerate(runs):
    v = arms_from_analysis(ROOT / "results" / run / "analysis-correct.txt")
    ax.bar([j + (i - 1) * w for j in range(len(arms))], [v.get(a, 0) * 100 for a in arms], width=w, label=lab)
ax.set_xticks(range(len(arms))); ax.set_xticklabels([LABEL[a] for a in arms], fontsize=7.5, rotation=15)
ax.set_ylabel("% of safe twins left unflagged"); ax.set_ylim(0, 50); ax.legend(frameon=False, fontsize=7.5)
ax.set_title("Figure 4. Safe twins: how often the model declines to flag a change the shown caller tolerates.", fontsize=9)
fig.tight_layout(); fig.savefig(OUT / "fig4-twins.pdf"); fig.savefig(OUT / "fig4-twins.png", dpi=180); plt.close(fig)
print("figures written:", sorted(p.name for p in OUT.iterdir()))
