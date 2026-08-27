"""The run matrix, pinned in one place so the paper can quote it.

Every axis that could change a result is named here rather than read from the
environment at call time. A run that is not reproducible from this file plus a
seed is not a result.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


CONDITION_NONE = "A"
CONDITION_GRAPH = "B"
CONDITION_RANDOM = "C"
CONDITION_LEXICAL = "D"
CONDITION_WHOLE_FILE = "E"

CONDITION_LABELS = {
    CONDITION_NONE: "no context",
    CONDITION_GRAPH: "graph retrieval",
    CONDITION_RANDOM: "random nodes, type-matched",
    CONDITION_LEXICAL: "lexical retrieval",
    CONDITION_WHOLE_FILE: "whole file, unbounded",
}

BUDGETED_CONDITIONS = (
    CONDITION_NONE,
    CONDITION_GRAPH,
    CONDITION_RANDOM,
    CONDITION_LEXICAL,
)


@dataclass(frozen=True)
class ModelSpec:
    key: str
    provider: str
    name: str
    input_cost_per_1k: float
    output_cost_per_1k: float

    @property
    def model_string(self) -> str:
        return f"{self.provider}::{self.name}"


MODELS = {
    "primary": ModelSpec(
        key="primary",
        provider="CEREBRAS",
        name="deepseek-r1-distill-llama-70b",
        input_cost_per_1k=0.0006,
        output_cost_per_1k=0.0024,
    ),
    "secondary": ModelSpec(
        key="secondary",
        provider="OPENROUTER",
        name="qwen/qwen-2.5-coder-32b-instruct",
        input_cost_per_1k=0.0002,
        output_cost_per_1k=0.0006,
    ),
}


@dataclass(frozen=True)
class RunMatrix:
    conditions: tuple = BUDGETED_CONDITIONS + (CONDITION_WHOLE_FILE,)
    models: tuple = ("primary", "secondary")
    budget_tokens: int = 1500
    depths: tuple = (1, 2, 3)
    depth_ablation_max_nodes: int = 60
    default_max_nodes: int = 12
    temperature: float = 0.1
    seeds: tuple = (0,)
    tasks: int = 184
    prompt_version: str = "v1"

    def cells(self) -> list[dict]:
        rows = []
        for model in self.models:
            for seed in self.seeds:
                for condition in self.conditions:
                    if condition == CONDITION_GRAPH:
                        for depth in self.depths:
                            rows.append(
                                {
                                    "condition": condition,
                                    "model": model,
                                    "seed": seed,
                                    "depth": depth,
                                    "max_nodes": self.depth_ablation_max_nodes,
                                    "budget_tokens": self.budget_tokens,
                                }
                            )
                    else:
                        rows.append(
                            {
                                "condition": condition,
                                "model": model,
                                "seed": seed,
                                "depth": None,
                                "max_nodes": self.default_max_nodes,
                                "budget_tokens": None
                                if condition == CONDITION_WHOLE_FILE
                                else self.budget_tokens,
                            }
                        )
        return rows

    def total_runs(self) -> int:
        return len(self.cells()) * self.tasks

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class CostEstimate:
    runs: int
    input_tokens: int
    output_tokens: int
    usd: float


def estimate_cost(
    matrix: RunMatrix,
    avg_input_tokens: int = 6000,
    avg_output_tokens: int = 1200,
) -> CostEstimate:
    total_usd = 0.0
    total_in = 0
    total_out = 0
    for cell in matrix.cells():
        spec = MODELS[cell["model"]]
        cell_in = avg_input_tokens * matrix.tasks
        cell_out = avg_output_tokens * matrix.tasks
        total_in += cell_in
        total_out += cell_out
        total_usd += (cell_in / 1000) * spec.input_cost_per_1k
        total_usd += (cell_out / 1000) * spec.output_cost_per_1k
    return CostEstimate(matrix.total_runs(), total_in, total_out, total_usd)


if __name__ == "__main__":
    matrix = RunMatrix()
    estimate = estimate_cost(matrix)
    print(f"cells in the matrix : {len(matrix.cells())}")
    print(f"tasks per cell      : {matrix.tasks}")
    print(f"total LLM runs      : {estimate.runs:,}")
    print(f"input tokens        : {estimate.input_tokens:,}")
    print(f"output tokens       : {estimate.output_tokens:,}")
    print(f"estimated cost      : ${estimate.usd:,.2f}")
    print()
    single = RunMatrix(models=("primary",))
    single_estimate = estimate_cost(single)
    print(f"one model only      : {single_estimate.runs:,} runs, ${single_estimate.usd:,.2f}")
