import json
import logging
import os
import random
import re
from collections import Counter

from langchain.tools import tool

from codecontext.retriever import retrieve_node_context, _find_target_node

from .ContextBudget import ContextBudget, DEFAULT_BUDGET_TOKENS

logger = logging.getLogger(__name__)

CONDITION_NONE = "A"
CONDITION_GRAPH = "B"
CONDITION_RANDOM = "C"
CONDITION_LEXICAL = "D"
CONDITION_WHOLE_FILE = "E"

CONDITIONS = (
    CONDITION_NONE,
    CONDITION_GRAPH,
    CONDITION_RANDOM,
    CONDITION_LEXICAL,
    CONDITION_WHOLE_FILE,
)

DEFAULT_MAX_DEPTH = 2
DEFAULT_MAX_NEIGHBORS = 12


def _node_entry(graph, node_id, depth=None):
    data = graph.nodes[node_id]
    entry = {
        "id": node_id,
        "name": data.get("name"),
        "type": data.get("type"),
        "relative_path": data.get("relative_path"),
    }
    if depth is not None:
        entry["depth"] = depth
    return entry


def _budgeted(payload, entries, budget_tokens):
    budget = ContextBudget(max_tokens=budget_tokens)
    payload["neighbors"] = budget.fill(entries)
    payload["budget"] = budget.report()
    return json.dumps(payload)


def build_retrieve_graph_tool(
    graph,
    graph_folder_path,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
):
    @tool
    def retrieve_graph(node: str) -> str:
        """
        Retrieve grounded repository graph context for a code entity.

        The node identifier should follow:
            "relative_file_path::identifier::name"
        """
        logger.debug("Retrieving graph context for %s", node)
        graph_path = os.path.join(graph_folder_path, "graph.pkl")
        payload = retrieve_node_context(
            graph, graph_path, node, max_neighbors=max_neighbors, max_depth=max_depth
        )
        neighbors = payload.pop("neighbors", [])
        payload["condition"] = CONDITION_GRAPH
        return _budgeted(payload, neighbors, budget_tokens)

    return retrieve_graph


def build_random_context_tool(
    graph,
    graph_folder_path,
    seed: int = 0,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    match_types: bool = True,
):
    @tool
    def retrieve_graph(node: str) -> str:
        """
        Retrieve grounded repository graph context for a code entity.

        The node identifier should follow:
            "relative_file_path::identifier::name"
        """
        logger.debug("Retrieving random context for %s", node)
        node_id = _find_target_node(graph, node)
        payload = {
            "query": node,
            "found": node_id is not None,
            "condition": CONDITION_RANDOM,
            "node": _node_entry(graph, node_id) if node_id is not None else None,
        }
        if node_id is None:
            return _budgeted(payload, [], budget_tokens)

        rng = random.Random(f"{seed}:{node}")
        pool = [n for n in graph.nodes if n != node_id]

        if match_types:
            reference = retrieve_node_context(
                graph, "", node, max_neighbors=max_neighbors, max_depth=DEFAULT_MAX_DEPTH
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

        return _budgeted(payload, [_node_entry(graph, n) for n in picked], budget_tokens)

    return retrieve_graph


def _tokenize_query(node_query: str):
    tail = node_query.split("::")[-1]
    parts = re.split(r"[^A-Za-z0-9]+", tail)
    words = []
    for part in parts:
        words.extend(re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", part))
    return [w.lower() for w in words if w]


def build_lexical_context_tool(
    graph,
    graph_folder_path,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
):
    @tool
    def retrieve_graph(node: str) -> str:
        """
        Retrieve grounded repository graph context for a code entity.

        The node identifier should follow:
            "relative_file_path::identifier::name"
        """
        logger.debug("Retrieving lexical context for %s", node)
        node_id = _find_target_node(graph, node)
        payload = {
            "query": node,
            "found": node_id is not None,
            "condition": CONDITION_LEXICAL,
            "node": _node_entry(graph, node_id) if node_id is not None else None,
        }
        terms = _tokenize_query(node)
        if not terms:
            return _budgeted(payload, [], budget_tokens)

        scored = []
        for candidate in graph.nodes:
            if candidate == node_id:
                continue
            name = (graph.nodes[candidate].get("name") or "").lower()
            if not name:
                continue
            score = sum(1 for term in terms if term in name)
            if score:
                scored.append((score, len(name), candidate))
        scored.sort(key=lambda row: (-row[0], row[1], str(row[2])))

        entries = [_node_entry(graph, candidate) for _, _, candidate in scored[:max_neighbors]]
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
):
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}, expected one of {CONDITIONS}")

    if condition in (CONDITION_NONE, CONDITION_WHOLE_FILE):
        return []

    if condition == CONDITION_RANDOM:
        return [
            build_random_context_tool(
                graph,
                graph_folder_path,
                seed=seed,
                max_neighbors=max_neighbors,
                budget_tokens=budget_tokens,
            )
        ]

    if condition == CONDITION_LEXICAL:
        return [
            build_lexical_context_tool(
                graph,
                graph_folder_path,
                max_neighbors=max_neighbors,
                budget_tokens=budget_tokens,
            )
        ]

    return [
        build_retrieve_graph_tool(
            graph,
            graph_folder_path,
            max_depth=max_depth,
            max_neighbors=max_neighbors,
            budget_tokens=budget_tokens,
        )
    ]


retrieve_graph_tool = build_retrieve_graph_tool
toolOrganizer = build_tools
