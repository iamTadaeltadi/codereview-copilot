# Discussion

## Why might context not help?

Our data does not settle the mechanism, but it constrains the candidates.

**It is not that retrieval is imperfect.** The oracle condition is handed the
entities spanning the ground-truth location and performs like no context at all.
Any explanation resting on "the retriever fetched the wrong thing" is ruled out
by that arm.

**It is not that the graph radius was wrong.** One hop and three hops score
identically.

**It is not that the budget was too small.** The whole-file arm supplies a
hundred times the budget — a mean of 102,459 characters — for +0.9 points with
an interval spanning zero.

What remains is that **the diff already contains what these models can use.**
Defect localisation from a diff appears to be limited by whether the model
recognises the pattern in front of it, not by what surrounds it. Additional
context is neither used nor harmful; it is inert.

The quieting effect is consistent with this. Every retrieval arm reports fewer
findings than the baseline while hitting the same number of true defects — up to
30% fewer on llama. Context appears to make the model more cautious, suppressing
reports it would otherwise have made, and the reports it suppresses are
apparently as likely to be right as wrong.

## What this implies for practice

Automated review systems that fetch repository context pay for it in tokens,
latency, and infrastructure. On this task and these models that cost bought
nothing measurable. Whole-file context in particular cost 6.3× more per true
finding, and failed outright on files exceeding the context window.

We would not conclude that context is useless for code review in general — only
that its benefit for *localising demonstrated defects* is smaller than the
current sample can detect, and that anyone claiming a benefit should show it
against a no-context baseline at matched budget.

## What we would do next

**Resolution rather than localisation.** We measure whether a review points at
the defect, not whether acting on it fixes the defect. Context may matter more
for writing a correct fix than for spotting a problem. c-CRAB's resolution
endpoint tests exactly this and requires per-instance containers.

**Stronger models.** Both models here are small and cheap. A frontier model may
have the capacity to exploit context that these cannot.

**Whole-repository graphs.** Bandwidth forced sparse graphs built from changed
files plus one import hop. The oracle result argues against this being the
explanation — perfect local context did not help either — but it should be ruled
out directly.

**The second review round.** Our schema supports linking a re-review to its
parent. Whether context pays off once a model has already seen and been
corrected on a file is a different question, and unasked.
