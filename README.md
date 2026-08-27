# CodeReview Copilot

CodeReview Copilot is a graph-grounded, agentic code review platform built as a
small monorepo: a Django API service, a React web client, a LangGraph-based agent
runtime, and a repository graph service for structural code retrieval.

The core design choice is that review quality should not depend only on an LLM
reading a diff. The platform builds a repository graph with the graph service,
retrieves exact code entities and relationships, and feeds that grounded context
into specialized review agents — closer to graph-grounded, agentic review than to
a thin prompt wrapper around a model.

## What It Does

- receives repository, pull request, and commit events
- triggers automated review through background tasks
- runs multi-step review agents for syntax, standards, bug analysis, vulnerability analysis, and fix generation
- stores review results, discussion threads, and feedback
- supports follow-up re-review on the same thread instead of restarting from scratch

## Repository Structure

```
services/
  api/      Django API: GitHub OAuth, webhooks, review persistence, Celery tasks,
            and the LangGraph client integration
  agents/   LangGraph review and feedback workflows, agent coordination, prompt
            logic, and memory-aware re-review
  graph/    repository graph construction and exact code-context retrieval (the
            `codecontext` Poetry package)
web/        React dashboard for repositories, pull requests, commits, reviews,
            and discussion threads
tests/      Python integration tests spanning the services
scripts/    test, coverage, deploy, and submission-verification tooling
```

## Architecture Position

This project sits between several known approaches:

- rule-based review tools, which are deterministic but shallow
- pure LLM review tools, which are flexible but can hallucinate
- graph-based retrieval systems, which improve structural grounding
- multi-agent review systems, which split analysis into focused review tasks

The platform combines the last two: graph-grounded context plus multi-agent review orchestration.

## Getting Started

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
bash scripts/test.sh
```

`requirements-dev.txt` is the union of the three service manifests and is what
CI installs, so it is the dependency set that is actually verified.

To run the services, copy `.env.example` to `.env`, fill in the required keys,
and run `docker compose up`.

## Verification

- API, agent, graph, and web checks are documented in `TESTING.md`
- run the full suite with `bash scripts/test.sh`
- measure backend coverage with `bash scripts/coverage.sh`
- CI runs the same suites on every push and pull request

## License and Attribution

This project is licensed under the Apache License 2.0 — see `LICENSE`.

The repository graph service (`services/graph/codecontext/`) is **derived from
RepoGraph** (https://github.com/ozyyshr/RepoGraph, Apache-2.0), described in
*RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph*,
arXiv:2410.14684, ICLR 2025. `NOTICE` lists the required attribution and the
changes made to the upstream code. Work building on this repository should cite
RepoGraph as prior art.
