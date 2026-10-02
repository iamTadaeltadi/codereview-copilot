"""Assemble paper/0*.md into one typeset HTML and a PDF (Chrome headless).

    .venv/bin/python paper/build_paper.py

Citations written as [arXiv:2509.05980] (possibly several per bracket) become
numbered references in order of first appearance, resolved from
paper/references.json when present. Figures are inserted at fixed anchors.
"""
import html, json, re, subprocess, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent
ORDER = ["00-abstract.md", "01-intro.md", "02-related.md", "03-method.md", "04-results.md",
         "05-discussion.md", "07-limitations.md", "06-artifact.md"]
AUTHOR = "Tadael Shewarega Gebre"; AFFIL = "Independent researcher, Addis Ababa"
EMAIL = "tadaelshewaregagebre30@gmail.com"
FIGS = {  # anchor substring in a heading -> (file, caption)
    "4.3 Does stating the structure": [("fig1-arms.png", "Figure 2. Per-arm rates on the rebuilt benchmark, four runs, three metrics (J1 is deepseek-v3.2, which is also the reviewed model in the third column; see 3.6). Arms 2–6 see identical snippets; only the metadata block differs."),
                                       ("fig2-primary.png", "Figure 3. The primary comparison, bare link against the scrambled control, with 95% repository-clustered intervals for two judges and for precision.")],
    "4.6 Real defects": [("fig3-ccrab.png", "Figure 4. c-CRAB: real test-verified defects, five conditions run on one day with one pipeline, model and budget; 219 defects for the first four conditions and 218 for the random-other-files control.")],
    "4.1 The three diagnostics": [("fig4-twins.png", "Figure 1. Safe twins: the share the model leaves unflagged, by arm, on two models and under the authoritative-callers instruction.")],
}

refs = {}
try:
    for r in json.loads((ROOT / "references.json").read_text()):
        refs[r.get("arxiv_id") or r["key"]] = r
        refs[r["key"]] = r
except Exception:
    pass
order = []  # citation keys in order of first appearance

def cite(m):
    keys = [k.strip() for k in m.group(1).split(",")]
    nums = []
    for k in keys:
        k = k.replace("arXiv:", "").replace("ref:", "")
        if k not in order: order.append(k)
        nums.append(str(order.index(k) + 1))
    return "[" + ", ".join(nums) + "]"

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\[((?:(?:arXiv|ref):[\w.]+)(?:,\s*(?:arXiv|ref):[\w.]+)*)\]", cite, s)
    codes = []
    def keep(m):
        codes.append(m.group(1)); return f"\x00{len(codes)-1}\x00"
    s = re.sub(r"`([^`]+)`", keep, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", s)
    s = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", s)
    return s

def table(lines):
    rows = [l.strip().strip("|").split("|") for l in lines if not re.match(r"^\s*\|?\s*-{3,}", l)]
    out = ["<table>"]
    for i, r in enumerate(rows):
        tag = "th" if i == 0 else "td"
        out.append("<tr>" + "".join(f"<{tag}>{inline(c.strip())}</{tag}>" for c in r) + "</tr>")
    out.append("</table>"); return "\n".join(out)

def convert(md, section_number):
    out, buf, tbl = [], [], []
    def flush():
        if buf: out.append("<p>" + inline(" ".join(buf)) + "</p>"); buf.clear()
    def flush_tbl():
        if tbl: out.append(table(tbl)); tbl.clear()
    lines = md.split("\n")
    for line in lines:
        if line.startswith("|"):
            flush(); tbl.append(line); continue
        flush_tbl()
        if line.startswith("# "):
            continue  # file title; the first file's H1 is the paper title
        if line.startswith("## "):
            flush(); text = line[3:].strip()
            if text == "Abstract":
                out.append("<h2 class='abstract'>Abstract</h2>"); continue
            text = re.sub(r"^\d+(\.\d+)?\.?\s*", "", text)
            out.append(f"<h2>{section_number[0]} {inline(text)}</h2>")
            for anchor, figs in FIGS.items():
                if anchor.split(" ", 1)[1] in line:
                    for f, cap in figs:
                        out.append(f"<figure><img src='figures/{f}' alt=''><figcaption>{inline(cap)}</figcaption></figure>")
            continue
        if line.startswith("### "):
            flush(); out.append(f"<h3>{inline(line[4:].strip())}</h3>"); continue
        if line.startswith("- "):
            flush(); out.append(f"<ul><li>{inline(line[2:].strip())}</li></ul>"); continue
        if line.startswith("*") and line.endswith("*") and len(line) > 2 and not line.startswith("**"):
            flush(); out.append(f"<p class='note'>{inline(line.strip('*'))}</p>"); continue
        if not line.strip():
            flush(); continue
        buf.append(line.strip())
    flush(); flush_tbl()
    return "\n".join(out).replace("</ul>\n<ul>", "\n")

parts = []; title = ""; sec = 0
for i, name in enumerate(ORDER):
    md = (ROOT / name).read_text()
    h1 = re.search(r"^# (.+)$", md, re.M).group(1)
    md = md.replace("# " + h1, "", 1)
    if i == 0:
        title = h1
        parts.append(convert(md, [0])); continue
    sec += 1
    body = convert(md, [sec])
    # '##' inside a file are subsections of that file's section: renumber as S.k
    k = 0; lines = []
    for line in body.split("\n"):
        m = re.match(r"<h2>\d+ (.*)</h2>", line)
        if m:
            k += 1; text = re.sub(r"^\d+\.\s*", "", m.group(1)); line = f"<h3>{sec}.{k} {text}</h3>"
        lines.append(line)
    body = "\n".join(lines)
    parts.append(f"<h2>{sec}. {html.escape(h1)}</h2>\n" + body)
html_sections = "\n".join(parts)

def ref_html(k, n):
    r = refs.get(k)
    if not r:
        return f"<li id='ref{n}'>[{n}] arXiv:{k}. <a href='https://arxiv.org/abs/{k}'>https://arxiv.org/abs/{k}</a></li>"
    authors = r.get("authors") or []
    a = ", ".join(authors[:6]) + (" et al" if len(authors) > 6 else "")
    venue = f" {r['venue']}." if r.get("venue") else ""
    link = r.get("url") or ("https://arxiv.org/abs/" + k)
    tag = f"arXiv:{r['arxiv_id']}" if r.get("arxiv_id") else link.replace("https://", "")
    return f"<li id='ref{n}'>[{n}] {html.escape(a)}. {html.escape(r.get('title',''))}. {r.get('year','')}.{html.escape(venue)} <a href='{link}'>{html.escape(tag)}</a></li>"
references = "\n".join(ref_html(k, i + 1) for i, k in enumerate(order))

page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
@page {{ size: A4; margin: 22mm 20mm 24mm 20mm; }}
body {{ font-family: "Times New Roman", Times, serif; font-size: 10.5pt; line-height: 1.38; color: #111; margin: 0; }}
.wrap {{ max-width: 170mm; margin: 0 auto; }}
h1 {{ font-size: 17pt; line-height: 1.2; margin: 0 0 6pt; text-align: center; }}
.byline {{ text-align: center; font-size: 10.5pt; margin: 0 0 2pt; }}
.affil {{ text-align: center; font-size: 9.5pt; color: #333; margin: 0 0 14pt; }}
h2 {{ font-size: 12.5pt; margin: 16pt 0 5pt; }}
h2.abstract {{ font-size: 11pt; text-align: center; margin-top: 4pt; }}
h3 {{ font-size: 10.8pt; margin: 11pt 0 3pt; }}
p {{ margin: 0 0 6pt; text-align: justify; }}
p.note {{ font-style: italic; color: #444; }}
ul {{ margin: 0 0 6pt 16pt; padding: 0; }} li {{ margin-bottom: 2pt; }}
code {{ font-family: Menlo, Consolas, monospace; font-size: 9pt; }}
table {{ border-collapse: collapse; margin: 6pt auto 9pt; font-size: 9.2pt; }}
th, td {{ border-top: 1px solid #999; border-bottom: 1px solid #999; padding: 2.5pt 7pt; text-align: left; vertical-align: top; }}
th {{ font-weight: 600; border-bottom: 1.5px solid #111; }}
figure {{ margin: 8pt 0 10pt; text-align: center; page-break-inside: avoid; }}
figure img {{ max-width: 100%; }}
figcaption {{ font-size: 9pt; color: #333; text-align: left; margin-top: 3pt; }}
.refs {{ font-size: 9pt; }} .refs li {{ list-style: none; margin-bottom: 3pt; text-indent: -1.6em; padding-left: 1.6em; }}
.refs ul {{ margin-left: 0; }}
a {{ color: #0b4f6c; text-decoration: none; }}
.meta {{ text-align: center; font-size: 9pt; color: #555; margin-bottom: 12pt; }}
</style></head><body><div class="wrap">
<h1>{html.escape(title)}</h1>
<p class="byline">{AUTHOR}</p>
<p class="affil">{AFFIL} · {EMAIL}</p>
<p class="meta">Preprint, {datetime.date.today().strftime('%d %B %Y')}. Code, data and frozen results: github.com/iamTadaeltadi/codereview-copilot.</p>
{html_sections}
<h2>References</h2>
<div class="refs"><ul>{references}</ul></div>
</div></body></html>"""
(ROOT / "paper.html").write_text(page)
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
pdf = ROOT / "paper.pdf"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", str(ROOT / "paper.html")],
               capture_output=True, text=True, timeout=180)
print(f"sections: {sec}, references: {len(order)} ({len(refs)} resolved), html {len(page):,} bytes, pdf {'ok ' + str(pdf.stat().st_size // 1024) + ' KB' if pdf.exists() else 'FAILED'}")
