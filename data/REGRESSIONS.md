# Real cross-file regression candidates

96 candidates from 17 production repositories, mined by
`experiments/mine_regressions.py`.

## What these are

A commit whose later fix lands in a **different file** than the one that
introduced the fault. That gap is what makes the defect cross-file: the change
looked correct where it was made, and the code that proved it wrong lived
somewhere the author was not looking.

Example:

    FIX  Fix gr.LoginButton to work on custom domains (#11697)
    WAS  When authenticating with HF OAuth, stay in same tab (#7887)
    -->  evidence in login_button.py, code.py

## What these are **not**

**Verified regressions.** They are candidates, and the distinction matters.

Attribution is by `git blame` on the parent of the fix, which identifies the
commit that last touched each fixed line. That is a heuristic, not causation: a
line can be attributed to a commit that merely reformatted it, and a fix can
repair a fault that had been latent for years.

Before any of these carries a claim, each needs a human to confirm three
things: that the fix repairs a behavioural defect rather than adding a feature,
that the identified commit introduced it rather than exposing it, and that the
cross-file evidence is what makes it recognisable. The plan specifies two
independent annotators with reported agreement.

## The funnel

| Stage | Count |
|---|---|
| repositories cloned | 18 |
| raw candidates | 102 |
| after removing cosmetic fixes | **96** |
| issue-linked | 78 |
| revert commits | 1 |
| distinct fix commits | 91 |

## Filters applied

- test files excluded on both sides — a defect whose only victim is a test
  leaves production unaffected
- subjects prefixed `test`, `ci`, `docs`, `chore`, `style`, `build`,
  `refactor`, `bump` dropped
- typo, spelling, wording, comment, docstring, formatting and rename fixes
  dropped — blame attributes such lines to whichever commit last touched them,
  which is noise rather than causation
- the fix must touch 1–2 production files, the introducing commit 1–3; a larger
  commit is a refactor with a fix folded in, and the fault cannot be attributed
  to any single change within it
- one instance per fixed file rather than per blamed line
