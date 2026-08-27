"""Run one review of one task under one condition, and parse what came back.

The prompt differs across conditions in exactly one way: whether it mentions a
retrieval tool, and conditions A and E have no tool to mention. Everything else
is byte-identical, so a difference in results cannot be attributed to prompt
wording. Condition A's variant is written separately rather than produced by
deleting a sentence, because a prompt with a dangling reference to a tool that
does not exist is a different prompt, not a control.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from experiments.config import (
    CONDITION_NONE,
    CONDITION_ORACLE,
    CONDITION_WHOLE_FILE,
)
from experiments.llm import Usage
from experiments.matcher import ReportedFinding


SYSTEM_PROMPT = (
    "You are an experienced code reviewer examining a pull request. Your job is "
    "to find defects: logic errors, incorrect conditions, off-by-one mistakes, "
    "unhandled cases, wrong API usage, resource leaks, and behaviour that "
    "contradicts what the surrounding code expects.\n\n"
    "This diff has already been reviewed by humans, and they found real problems "
    "in it. Assume there is something to find and look carefully. Report each "
    "defect against the file and line it occurs on. Do not summarise the change "
    "and do not comment on formatting."
)

OUTPUT_CONTRACT = """
Reply with JSON only, in exactly this shape:

{"findings": [{"path": "relative/file.py", "line": 42, "message": "what is wrong"}]}

Use the file paths exactly as they appear in the diff, and line numbers from the
new version of the file. Report your best candidates even when you are not
certain — a plausible defect that turns out to be wrong is more useful here than
silence. Return an empty list only if you genuinely cannot identify anything.
Never wrap the JSON in prose.
""".strip()

TOOL_CLAUSE = """
A tool named retrieve_graph is available. Given "relative/path.py::type::name"
it returns related code entities from the repository. Use it when the diff alone
does not tell you whether something is a defect.
""".strip()


@dataclass
class ReviewResult:
    task_id: str
    condition: str
    model: str
    findings: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    raw_text: str = ""
    parse_failed: bool = False
    error: str = ""


def build_messages(task, condition: str, context_text: str = "") -> list:
    parts = [
        f"Repository: {task.repo}",
        f"Language: {task.language}",
        "",
        "Pull request diff:",
        "```diff",
        task.diff,
        "```",
    ]
    if context_text:
        parts += ["", "Repository context:", "```json", context_text, "```"]
    if condition not in (CONDITION_NONE, CONDITION_WHOLE_FILE, CONDITION_ORACLE):
        parts += ["", TOOL_CLAUSE]
    parts += ["", OUTPUT_CONTRACT]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(parts)},
    ]


def _extract_json(text: str):
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : index + 1])
                    except Exception:
                        break
        start = text.find("{", start + 1)
    return None


def parse_findings(text: str, task_id: str, condition: str):
    payload = _extract_json(text)
    if payload is None:
        return [], True
    raw = payload.get("findings") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return [], True

    findings = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        line = item.get("line")
        try:
            line = int(line) if line is not None else None
        except (TypeError, ValueError):
            line = None
        findings.append(
            ReportedFinding(
                finding_id=f"{task_id}:{condition}:{index}",
                path=str(item.get("path") or item.get("file") or ""),
                line=line,
                message=str(item.get("message") or item.get("description") or ""),
            )
        )
    return findings, False


def review_once(client, model: str, task, condition: str, context_text: str = "",
                temperature: float = 0.1, seed=None, max_tokens: int = 4096) -> ReviewResult:
    messages = build_messages(task, condition, context_text)
    result = ReviewResult(task_id=task.task_id, condition=condition, model=model)
    try:
        completion = client.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
        )
    except Exception as error:
        result.error = str(error)
        return result

    result.raw_text = completion.text
    result.usage = completion.usage
    result.findings, result.parse_failed = parse_findings(
        completion.text, task.task_id, condition
    )
    if result.parse_failed and completion.text.lstrip().startswith("{"):
        # Output that begins as JSON and fails to parse is a cut-off reply, not
        # a reviewer that found nothing. Recording it as zero findings would put
        # a network failure into the results.
        result.error = "reply began as JSON but did not parse — treating as truncated"
    return result
