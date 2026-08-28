"""An agentic reviewer: it can search and read the repository itself.

The one-shot conditions answer whether supplied context helps. This answers a
harder question. An agent with search does not need context supplied — it can
go and find the caller. So the interesting measurement is not whether it *can*
but whether it *does*.

A cross-file defect looks correct on its own. Nothing in the diff suggests that
anything elsewhere depends on it, so an agent has no reason to search, and an
ability it never exercises is worth nothing. Every tool call is recorded, so a
review that found nothing can be separated into "searched and missed" and
"never looked".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from experiments.llm import LLMError, Usage
from experiments.matcher import ReportedFinding
from experiments.review import OUTPUT_CONTRACT, parse_findings


SYSTEM_PROMPT = (
    "You are an experienced code reviewer examining a pull request in a large "
    "repository. Your job is to find defects: logic errors, incorrect "
    "conditions, unhandled cases, wrong API usage, and behaviour that "
    "contradicts what the surrounding code expects.\n\n"
    "This diff has already been reviewed by humans, and they found a real "
    "problem in it. Assume there is something to find and look carefully.\n\n"
    "You have tools for searching and reading the repository. Use them when the "
    "diff alone does not tell you whether something is correct."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": (
                "Search the repository for a string and return matching lines "
                "with their file and line number."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "text to search for"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the repository by its path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "repository-relative path"}
                },
                "required": ["path"],
            },
        },
    },
]

MAX_MATCHES = 25
MAX_FILE_CHARS = 6000


@dataclass
class AgentResult:
    task_id: str
    condition: str
    model: str
    findings: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    tool_calls: int = 0
    searches: int = 0
    reads: int = 0
    searched_at_all: bool = False
    found_the_caller: bool = False
    turns: int = 0
    raw_text: str = ""
    error: str = ""
    parse_failed: bool = False


def run_search(sources, query: str) -> str:
    if not query:
        return "no query given"
    out = []
    for path, text in sources.items():
        for index, line in enumerate(text.split("\n"), 1):
            if query in line:
                out.append(f"{path}:{index}: {line.strip()[:160]}")
                if len(out) >= MAX_MATCHES:
                    return "\n".join(out) + f"\n... (truncated at {MAX_MATCHES} matches)"
    return "\n".join(out) if out else f"no matches for {query!r}"


def run_read(sources, path: str) -> str:
    if path in sources:
        text = sources[path]
    else:
        candidates = [p for p in sources if p.endswith(path) or path.endswith(p)]
        if not candidates:
            return f"file not found: {path}. Files available: " + ", ".join(sorted(sources)[:40])
        text = sources[candidates[0]]
        path = candidates[0]
    if len(text) > MAX_FILE_CHARS:
        text = text[:MAX_FILE_CHARS] + f"\n... (truncated, {len(sources[path])} chars total)"
    return f"# {path}\n{text}"


def review_with_agent(client, model: str, task, sources, condition: str = "AGENT",
                      preloaded_context: str = "", max_turns: int = 8,
                      temperature: float = 0.1) -> AgentResult:
    result = AgentResult(task_id=task.task_id, condition=condition, model=model)
    caller_path = (task.metadata or {}).get("caller_path", "")

    user = [
        f"Repository: {task.repo}",
        "",
        "Pull request diff:",
        "```diff",
        task.diff,
        "```",
    ]
    if preloaded_context:
        user += ["", "Repository context (already retrieved for you):", "```json",
                 preloaded_context, "```"]
    user += ["", OUTPUT_CONTRACT]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user)},
    ]

    for turn in range(max_turns):
        result.turns = turn + 1
        try:
            completion = client.complete(
                model=model, messages=messages, temperature=temperature,
                max_tokens=2048, tools=TOOLS,
            )
        except LLMError as error:
            result.error = str(error)
            return result

        result.usage.add(completion.usage)

        if not completion.tool_calls:
            result.raw_text = completion.text
            result.findings, result.parse_failed = parse_findings(
                completion.text, task.task_id, condition
            )
            return result

        messages.append({
            "role": "assistant",
            "content": completion.text or None,
            "tool_calls": completion.tool_calls,
        })

        for call in completion.tool_calls:
            function = (call.get("function") or {})
            name = function.get("name")
            try:
                args = json.loads(function.get("arguments") or "{}")
            except Exception:
                args = {}

            result.tool_calls += 1
            if name == "search_code":
                result.searches += 1
                result.searched_at_all = True
                output = run_search(sources, args.get("query", ""))
                if caller_path and caller_path in output:
                    result.found_the_caller = True
            elif name == "read_file":
                result.reads += 1
                path = args.get("path", "")
                output = run_read(sources, path)
                if caller_path and (path.endswith(caller_path) or caller_path.endswith(path)):
                    result.found_the_caller = True
            else:
                output = f"unknown tool: {name}"

            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id"),
                "name": name,
                "content": output[:8000],
            })

    result.error = f"did not finish within {max_turns} turns"
    return result
