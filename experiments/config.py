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
CONDITION_ORACLE = "F"
CONDITION_DENSE = "G"

CONDITION_LABELS = {
    CONDITION_NONE: "no context",
    CONDITION_GRAPH: "graph retrieval",
    CONDITION_RANDOM: "random nodes, type-matched",
    CONDITION_LEXICAL: "lexical retrieval",
    CONDITION_WHOLE_FILE: "whole file, unbounded",
    CONDITION_ORACLE: "oracle, the benchmark answer key",
    CONDITION_DENSE: "dense embedding retrieval",
}

BUDGETED_CONDITIONS = (
    CONDITION_NONE,
    CONDITION_GRAPH,
    CONDITION_RANDOM,
    CONDITION_LEXICAL,
    CONDITION_DENSE,
    CONDITION_ORACLE,
)

# F cheats by construction: it reads the benchmark's answer key. It is a
# ceiling, never a competitor, and is reported separately from the honest arms.
REFERENCE_CONDITIONS = (CONDITION_ORACLE, CONDITION_WHOLE_FILE)


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

    @property
    def family(self) -> str:
        """Who trained the model, not who serves it.

        Both models are reached through OpenRouter, so the provider is the same
        gateway for each. What has to differ for the generalisability claim is
        the family: AACR-Bench reports that model choice significantly changes
        automated review results, and two OpenRouter endpoints onto the same
        family would not answer that.
        """
        return self.name.split("/")[0] if "/" in self.name else self.provider.lower()


# Chosen by measurement, not by reputation. Five candidates were run against
# three real tasks through the same prompt: anthropic/claude-3.5-haiku and
# google/gemini-2.0-flash-001 returned finish_reason "error" on every call and
# were dropped; qwen/qwen-2.5-coder-32b-instruct did the same, which is why the
# first pilot recorded zero findings everywhere. The two below completed every
# call, come from different model families, and cost within 10% of each other.
MODELS = {
    "primary": ModelSpec(
        key="primary",
        provider="OPENROUTER",
        name="openai/gpt-4o-mini",
        input_cost_per_1k=0.00015,
        output_cost_per_1k=0.0006,
    ),
    "secondary": ModelSpec(
        key="secondary",
        provider="OPENROUTER",
        name="meta-llama/llama-3.3-70b-instruct",
        input_cost_per_1k=0.00013,
        output_cost_per_1k=0.0004,
    ),
}

# Measured on real tasks rather than assumed: a review averages about 3,500
# input and 350 output tokens once the diff and the budgeted context are in.
MEASURED_INPUT_TOKENS = 3500
MEASURED_OUTPUT_TOKENS = 350


@dataclass(frozen=True)
class RunMatrix:
    conditions: tuple = BUDGETED_CONDITIONS + (CONDITION_WHOLE_FILE,)
    models: tuple = ("primary", "secondary")
    budget_tokens: int = 1500
    depths: tuple = (1, 2, 3)
    # One candidate cap for every condition. An earlier version gave the graph
    # arm 60 candidates and the others 12, which is unequal by construction: the
    # budget can only be the binding constraint if every condition is allowed to
    # offer enough entries to reach it. The token budget does the limiting; this
    # only stops a pathological neighbourhood from being serialised in full.
    candidate_cap: int = 80
    temperature: float = 0.1
    seeds: tuple = (0,)
    tasks: int = 339
    prompt_version: str = "v1"
    embedder: str = "hashing-baseline"

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
                                    "max_nodes": self.candidate_cap,
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
                                "max_nodes": self.candidate_cap,
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
    avg_input_tokens: int = MEASURED_INPUT_TOKENS,
    avg_output_tokens: int = MEASURED_OUTPUT_TOKENS,
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
