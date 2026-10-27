"""Recompute every frozen analysis in results/ from its raw records and compare.

    python scripts/reproduce.py            # analyses only, no network, ~2 minutes
    python scripts/reproduce.py --figures  # also redraw paper/figures
    python scripts/reproduce.py --paper    # also rebuild paper/paper.pdf (needs Chrome)

For each results/<run>/analysis-*.txt the header names the input file, the
metric and the comparisons; the same analysis is run again and the per-arm
table and every difference line are compared. Judge metrics exist only for
hits, so files that counted misses as false are detected by trying both.
Exit status is the number of files that did not reproduce.
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from experiments.analyse_structure import report  # noqa: E402

HEAD = re.compile(r"^(file|metric):\s+(.*)$", re.M)
PAIR = re.compile(r"^([^:\n]+): (\S+) minus (\S+)  \(metric=", re.M)


def key_lines(text):
    """The per-arm table rows and the difference rows: the numbers the paper uses."""
    out = []
    for line in text.splitlines():
        if re.match(r"^[1-8]\S* +\d", line) or line.startswith("  difference") or line.startswith("  McNemar"):
            out.append(re.sub(r"\s+", " ", line.strip()))
    return out


def reproduce(path):
    frozen = path.read_text()
    head = dict(HEAD.findall(frozen))
    pairs = PAIR.findall(frozen)
    if not head.get("file") or not pairs:
        return "SKIP (no header)"
    primary = next(((a, b) for l, a, b in pairs if l == "primary"), None)
    secondary = next(((a, b) for l, a, b in pairs if l == "secondary"), None)
    extra = [(a, b) for l, a, b in pairs if l not in ("primary", "secondary")]
    want = key_lines(frozen)
    for missing in (False, True):
        got = report(ROOT / head["file"], metric=head["metric"], primary=primary, secondary=secondary,
                     extra_pairs=extra, missing_as_false=missing)
        if key_lines(got) == want:
            return "MATCH" + (" (missing-as-false)" if missing else "")
    return "DIFF"


def main(argv):
    files = sorted(ROOT.glob("results/v2*/analysis-*.txt")) + sorted(ROOT.glob("results/v3twins-*/analysis-*.txt")) + sorted(ROOT.glob("results/v3-ceiling/analysis-*.txt"))
    bad = 0
    for f in files:
        status = reproduce(f)
        bad += status == "DIFF"
        print(f"{status:<28}{f.relative_to(ROOT)}")
    # The stopped third-version run: the per-arm table in its README is recomputed from the records.
    ceiling = ROOT / "results/v3-ceiling/structure-gpt4omini-tag-partial.jsonl"
    if ceiling.exists():
        import collections, json
        rows = [json.loads(l) for l in ceiling.open() if l.strip()]
        by = collections.defaultdict(list)
        for r in rows: by[r["arm"]].append(r)
        want = [l for l in (ROOT / "results/v3-ceiling/README.md").read_text().splitlines() if l.startswith("| ") and l[2].isdigit()]
        got = [f"| {arm} | {len(rs)} | {sum(1 for r in rs if r['hit'])/len(rs):.1%} | {sum(1 for r in rs if r['precise'])/len(rs):.1%} | {sum(r['findings'] for r in rs)/len(rs):.2f} | {sum(r['flagged_distractors'] for r in rs)/len(rs):.2f} |" for arm, rs in sorted(by.items())]
        same = got == want
        bad += not same
        print(f"{'MATCH' if same else 'DIFF':<28}results/v3-ceiling/README.md (per-arm table)")
        files.append(ceiling)
    frozen = (ROOT / "results/ccrab-today/analysis.txt").read_text()
    fresh = subprocess.run([sys.executable, "experiments/analyse_ccrab.py"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout
    # Point estimates only: the frozen intervals came from an unseeded bootstrap.
    pct = lambda t: [m.group(1) for m in re.finditer(r"^\s+\S.*?([+-]?\d+\.\d%)", t, re.M)]
    same = all(p in pct(fresh) for p in pct(frozen))
    bad += not same
    print(f"{'MATCH' if same else 'DIFF':<28}results/ccrab-today/analysis.txt (point estimates)")
    print(f"\n{len(files) + 1} analyses checked, {bad} differ")
    if "--figures" in argv or "--paper" in argv:
        subprocess.run([sys.executable, "paper/make_figures.py"], cwd=ROOT, check=True)
    if "--paper" in argv:
        subprocess.run([sys.executable, "paper/build_paper.py"], cwd=ROOT, check=True)
    return bad


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
