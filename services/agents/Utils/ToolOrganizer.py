"""One retrieval tool per condition, one payload shape for every condition.

Every condition's tool takes the same seeds (one query per line), returns the
same JSON fields, and delivers each retrieved entity the same way: its id, name,
type, path and its source trimmed to its line range. Only the selection of
entities differs between conditions. No payload carries a line range or
metadata of any entity, seed or neighbour; an earlier version let the graph
condition alone carry the seed's span, and that result was withdrawn.
"""

import json
import logging
import os
import random
import re
from collections import Counter

from langchain.tools import tool

from codecontext.retriever import (
    _find_target_node,
    entity_source,
    find_seed_nodes,
    retrieve_node_context,
    split_queries,
    stripped_entry,
)

from .ContextBudget import DEFAULT_BUDGET_TOKENS, estimate_tokens

logger = logging.getLogger(__name__)

CONDITION_NONE = "A"
CONDITION_GRAPH = "B"
CONDITION_RANDOM = "C"
CONDITION_LEXICAL = "D"
CONDITION_WHOLE_FILE = "E"
CONDITION_ORACLE = "F"
CONDITION_DENSE = "G"

CONDITIONS = (
    CONDITION_NONE,
    CONDITION_GRAPH,
    CONDITION_RANDOM,
    CONDITION_LEXICAL,
    CONDITION_WHOLE_FILE,
    CONDITION_ORACLE,
    CONDITION_DENSE,
)

DEFAULT_MAX_DEPTH = 2
DEFAULT_MAX_NEIGHBORS = 12
DEFAULT_ENTITY_LINES = 40

ENTRY_FIELDS = ("id", "name", "type", "relative_path", "source")
PAYLOAD_FIELDS = ("query", "found", "node", "seeds", "condition", "neighbors", "budget")


def _node_entry(graph, node_id, max_lines=DEFAULT_ENTITY_LINES):
    """id, name, type, path and the entity's source: the one entry shape."""
    entry = stripped_entry(graph, node_id)
    entry["source"] = entity_source(graph, node_id, max_lines)
    return entry


def _payload(graph, condition, node_query):
    seed_ids = [s for s in find_seed_nodes(graph, node_query) if s is not None]
    seeds = [stripped_entry(graph, s) for s in seed_ids]
    return {
        "query": node_query,
        "found": bool(seed_ids),
        "node": seeds[0] if seeds else None,
        "seeds": seeds,
        "condition": condition,
    }, seed_ids


def _budgeted(payload, entries, budget_tokens):
    """Fit the *delivered string* inside the budget, not the entries inside it.

    Each condition wraps its entries in the same envelope now, but the cap is
    still applied to the serialised payload the model actually receives, and
    entries are dropped from the end until the whole string fits.
    """
    kept = list(entries)
    while True:
        payload["neighbors"] = kept
        payload["budget"] = {
            "budget_tokens": budget_tokens,
            "entries_kept": len(kept),
            "entries_offered": len(entries),
        }
        rendered = json.dumps(payload)
        used = estimate_tokens(rendered)
        if used <= budget_tokens or not kept:
            payload["budget"]["used_tokens"] = used
            payload["budget"]["entries_rejected"] = len(entries) - len(kept)
            return json.dumps(payload)
        overshoot = used - budget_tokens
        step = max(1, int(len(kept) * overshoot / max(used, 1)))
        kept = kept[: max(0, len(kept) - step)]


def _pool(graph, seed_ids, entity_types):
    seeds = set(seed_ids)
    return [n for n in graph.nodes
            if n not in seeds and (not entity_types or graph.nodes[n].get("type") in entity_types)]


def build_retrieve_graph_tool(
    graph,
    graph_folder_path,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    prefer_cross_file: bool = False,
    strip_seed: bool = True,
    entity_types=None,
    max_entity_lines: int = DEFAULT_ENTITY_LINES,
):
    """Condition B. `strip_seed` is accepted for the old command line and
    ignored: the seed is always reduced to id, name, type and path."""
    @tool
    def retrieve_graph(node: str) -> str:
        """
        Retrieve grounded repository graph context for a code entity.

        The node identifier should follow:
            "relative_file_path::identifier::name"
        """
        logger.debug("Retrieving graph context for %s", node)
        graph_path = os.path.join(graph_folder_path, "graph.pkl")
        walk = retrieve_node_context(
            graph, graph_path, node, max_neighbors=max_neighbors, max_depth=max_depth,
            prefer_cross_file=prefer_cross_file, entity_types=entity_types,
        )
        seeds = walk.get("seeds")
        if seeds is None:
            seeds = [walk["node"]] if walk.get("node") else []
        payload = {
            "query": node,
            "found": bool(walk.get("found")),
            "node": seeds[0] if seeds else None,
            "seeds": seeds,
            "condition": CONDITION_GRAPH,
        }
        entries = [_node_entry(graph, n["id"], max_entity_lines) for n in walk.get("neighbors", [])]
        return _budgeted(payload, entries, budget_tokens)

    return retrieve_graph


def build_random_context_tool(
    graph,
    graph_folder_path,
    seed: int = 0,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    match_types: bool = True,
    other_files_only: bool = False,
    max_depth: int = DEFAULT_MAX_DEPTH,
    prefer_cross_file: bool = False,
    entity_types=None,
    max_entity_lines: int = DEFAULT_ENTITY_LINES,
):
    """Random type-matched entities; with other_files_only, drawn from files
    other than the seeds'. The type mix is taken from the graph condition's own
    walk with the same parameters, so the two differ only in which entities."""
    @tool
    def retrieve_graph(node: str) -> str:
        """
        Retrieve grounded repository graph context for a code entity.

        The node identifier should follow:
            "relative_file_path::identifier::name"
        """
        logger.debug("Retrieving random context for %s", node)
        payload, seed_ids = _payload(graph, CONDITION_RANDOM, node)
        if not seed_ids:
            return _budgeted(payload, [], budget_tokens)

        rng = random.Random(f"{seed}:{node}")
        pool = _pool(graph, seed_ids, entity_types)
        if other_files_only:
            homes = {graph.nodes[s].get("relative_path") for s in seed_ids}
            pool = [n for n in pool if graph.nodes[n].get("relative_path") not in homes] or pool

        if match_types:
            reference = retrieve_node_context(
                graph, "", node, max_neighbors=max_neighbors, max_depth=max_depth,
                prefer_cross_file=prefer_cross_file, entity_types=entity_types,
            )
            wanted = Counter(n.get("type") for n in reference["neighbors"])
            by_type = {}
            for candidate in pool:
                by_type.setdefault(graph.nodes[candidate].get("type"), []).append(candidate)
            picked = []
            for node_type, count in wanted.items():
                bucket = by_type.get(node_type, [])
                rng.shuffle(bucket)
                picked.extend(bucket[:count])
            rng.shuffle(picked)
        else:
            rng.shuffle(pool)
            picked = pool[:max_neighbors]

        return _budgeted(payload, [_node_entry(graph, n, max_entity_lines) for n in picked], budget_tokens)

    return retrieve_graph


def _tokenize_query(node_query: str):
    words = []
    for query in split_queries(node_query) or [node_query]:
        tail = query.split("::")[-1]
        for part in re.split(r"[^A-Za-z0-9]+", tail):
            words.extend(re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", part))
    return [w.lower() for w in words if w]


def build_lexical_context_tool(
    graph,
    graph_folder_path,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    entity_types=None,
    max_entity_lines: int = DEFAULT_ENTITY_LINES,
):
    @tool
    def retrieve_graph(node: str) -> str:
        """
        Retrieve grounded repository graph context for a code entity.

        The node identifier should follow:
            "relative_file_path::identifier::name"
        """
        logger.debug("Retrieving lexical context for %s", node)
        payload, seed_ids = _payload(graph, CONDITION_LEXICAL, node)
        terms = _tokenize_query(node)
        if not terms:
            return _budgeted(payload, [], budget_tokens)

        scored = []
        for candidate in _pool(graph, seed_ids, entity_types):
            name = (graph.nodes[candidate].get("name") or "").lower()
            if not name:
                continue
            score = sum(1 for term in terms if term in name)
            if score:
                scored.append((score, len(name), str(candidate), candidate))
        scored.sort(key=lambda row: (-row[0], row[1], row[2]))

        entries = [_node_entry(graph, c, max_entity_lines) for _, _, _, c in scored[:max_neighbors]]
        return _budgeted(payload, entries, budget_tokens)

    return retrieve_graph


def _node_document(graph, node_id) -> str:
    data = graph.nodes[node_id]
    return " ".join(
        str(part)
        for part in (data.get("name"), data.get("type"), data.get("relative_path"))
        if part
    )


def hashing_embedder(text: str, dimensions: int = 256) -> list[float]:
    """A deterministic character-ngram hashing embedder.

    This is a stand-in so the dense condition is runnable and testable without a
    model download or a network call. A real run injects a trained embedder via
    the embed_fn argument, and the paper reports which one was used — the
    default here is a baseline, not the thing being claimed.
    """
    vector = [0.0] * dimensions
    lowered = text.lower()
    for size in (3, 4):
        for index in range(max(0, len(lowered) - size + 1)):
            gram = lowered[index : index + size]
            slot = hash((size, gram)) % dimensions
            vector[slot] += 1.0
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _cosine(left, right) -> float:
    return sum(a * b for a, b in zip(left, right))


def build_dense_context_tool(
    graph,
    graph_folder_path,
    embed_fn=None,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    entity_types=None,
    max_entity_lines: int = DEFAULT_ENTITY_LINES,
):
    embed = embed_fn or hashing_embedder

    @tool
    def retrieve_graph(node: str) -> str:
        """
        Retrieve grounded repository graph context for a code entity.

        The node identifier should follow:
            "relative_file_path::identifier::name"
        """
        logger.debug("Retrieving dense context for %s", node)
        payload, seed_ids = _payload(graph, CONDITION_DENSE, node)
        query_vector = embed(" ".join(_tokenize_query(node)) or node)
        scored = []
        for candidate in _pool(graph, seed_ids, entity_types):
            document = _node_document(graph, candidate)
            if not document:
                continue
            score = _cosine(query_vector, embed(document))
            scored.append((score, str(candidate), candidate))
        scored.sort(key=lambda row: (-row[0], row[1]))
        entries = [_node_entry(graph, c, max_entity_lines) for _, _, c in scored[:max_neighbors]]
        return _budgeted(payload, entries, budget_tokens)

    return retrieve_graph


def _spans_overlap(line_range, line, tolerance: int) -> bool:
    if not line_range or line is None:
        return False
    try:
        start, end = int(line_range[0]), int(line_range[1])
    except (TypeError, ValueError, IndexError):
        return False
    return start - tolerance <= line <= end + tolerance


def build_oracle_context_tool(
    graph,
    graph_folder_path,
    targets=None,
    tolerance: int = 0,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    max_entity_lines: int = DEFAULT_ENTITY_LINES,
):
    """Condition F: the FAULT-LOCATION oracle.

    It returns the graph entities whose line range spans the ground-truth
    defect line. That is not an evidence oracle and must not be described as
    one; it is a reference condition, never a competitor. Nothing that reads
    `targets` may ever run in a condition being compared honestly.
    """
    targets = list(targets or [])

    @tool
    def retrieve_graph(node: str) -> str:
        """
        Retrieve grounded repository graph context for a code entity.

        The node identifier should follow:
            "relative_file_path::identifier::name"
        """
        logger.debug("Retrieving oracle context for %s", node)
        payload, seed_ids = _payload(graph, CONDITION_ORACLE, node)
        payload["oracle_targets"] = len(targets)
        entries = []
        seen = set(seed_ids)
        for candidate in graph.nodes:
            if candidate in seen:
                continue
            data = graph.nodes[candidate]
            for target in targets:
                if data.get("relative_path") != target.get("path"):
                    continue
                if _spans_overlap(data.get("line_range"), target.get("line"), tolerance):
                    seen.add(candidate)
                    entries.append(_node_entry(graph, candidate, max_entity_lines))
                    break
            if len(entries) >= max_neighbors:
                break
        return _budgeted(payload, entries, budget_tokens)

    return retrieve_graph


def build_tools(
    graph,
    graph_folder_path,
    condition: str = CONDITION_GRAPH,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    seed: int = 0,
    embed_fn=None,
    oracle_targets=None,
    prefer_cross_file: bool = False,
    strip_seed: bool = True,
    entity_types=None,
    max_entity_lines: int = DEFAULT_ENTITY_LINES,
):
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}, expected one of {CONDITIONS}")

    if condition in (CONDITION_NONE, CONDITION_WHOLE_FILE):
        return []

    if condition == CONDITION_RANDOM:
        return [
            build_random_context_tool(
                graph, graph_folder_path, seed=seed, max_neighbors=max_neighbors,
                budget_tokens=budget_tokens, other_files_only=prefer_cross_file,
                max_depth=max_depth, prefer_cross_file=prefer_cross_file,
                entity_types=entity_types, max_entity_lines=max_entity_lines,
            )
        ]

    if condition == CONDITION_DENSE:
        return [
            build_dense_context_tool(
                graph, graph_folder_path, embed_fn=embed_fn, max_neighbors=max_neighbors,
                budget_tokens=budget_tokens, entity_types=entity_types,
                max_entity_lines=max_entity_lines,
            )
        ]

    if condition == CONDITION_ORACLE:
        return [
            build_oracle_context_tool(
                graph, graph_folder_path, targets=oracle_targets, max_neighbors=max_neighbors,
                budget_tokens=budget_tokens, max_entity_lines=max_entity_lines,
            )
        ]

    if condition == CONDITION_LEXICAL:
        return [
            build_lexical_context_tool(
                graph, graph_folder_path, max_neighbors=max_neighbors,
                budget_tokens=budget_tokens, entity_types=entity_types,
                max_entity_lines=max_entity_lines,
            )
        ]

    return [
        build_retrieve_graph_tool(
            graph, graph_folder_path, max_depth=max_depth, max_neighbors=max_neighbors,
            budget_tokens=budget_tokens, prefer_cross_file=prefer_cross_file,
            strip_seed=strip_seed, entity_types=entity_types, max_entity_lines=max_entity_lines,
        )
    ]


retrieve_graph_tool = build_retrieve_graph_tool
toolOrganizer = build_tools
