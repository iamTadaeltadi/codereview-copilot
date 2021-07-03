# Architecture

## Overview

The platform is organized as four cooperating services:

1. `services/api`
   Owns API endpoints, persistence, webhook ingestion, and asynchronous review job orchestration.
2. `web`
   Provides the operator-facing and reviewer-facing UI for repositories, pull requests, commits, and review results.
3. `services/agents`
   Runs the multi-agent code review workflows. It coordinates specialized review agents, prompts, memory, and graph-aware tool usage.
4. `services/graph`
   Builds code graphs and retrieves node-local context so the review pipeline can reason across repository structure instead of reviewing files in isolation.

## Data Flow

1. A repository or pull request is registered in the API service.
2. Source-control events arrive through webhook endpoints.
3. The API service schedules review tasks and invokes the agent runtime.
4. The agent runtime queries the graph service to construct or load repository context.
5. Agents produce review artifacts and feedback summaries.
6. The API service stores results and exposes them to the web client.

## Why The Split Matters

- `services/api` stays focused on system-of-record concerns and API contracts.
- `web` stays focused on workflow and presentation.
- `services/agents` can evolve independently as orchestration logic grows.
- `services/graph` stays reusable as a lower-level analysis package consumed by the pipeline.

## Monorepo Goal

The monorepo structure exists for coherence:

- one root Git history
- one product story
- shared documentation
- clear boundaries between review orchestration, persistence, UI, and graph analysis
