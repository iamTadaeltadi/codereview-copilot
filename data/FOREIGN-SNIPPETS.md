# foreign-snippets.jsonl

Python function windows from repositories that are NOT in the benchmark (none of these repos appear in `crossfile.jsonl` or `regressions-candidates.jsonl`). Fetched 2026-10-01 from raw.githubusercontent.com at the default branch.
- psf/requests @ main: src/requests/utils.py, src/requests/models.py, src/requests/sessions.py
- pallets/click @ main: src/click/types.py, src/click/utils.py, src/click/parser.py
- Textualize/rich @ master: rich/text.py, rich/table.py, rich/segment.py

Each record is one `def` with >= 6 body lines: the def line plus up to 24 following lines (stop at function end; text >= 150 chars). Keys: repo, branch, path, start_line, end_line, function, label (`{stem}:{def_line}`), text. 256 records; 83% parse with `ast.parse` after dedent (the rest are cut mid-block by the window).
This file exists so a "random code" control arm can draw from outside the benchmark's own repositories. The previous random arm drew its snippets from the two relevant files of each case and therefore had evidence recall as high as targeted retrieval; sampling from here gives a genuinely unrelated-code control.
Regenerate by re-fetching the files above and re-running the extraction (window=24, min body lines=6, min chars=150). Validated by `tests/test_foreign_snippets.py`.
