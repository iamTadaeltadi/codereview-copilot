import json
import logging
import os
import random
import re
from collections import Counter

from langchain.tools import tool

from codecontext.retriever import retrieve_node_context, _find_target_node

from .ContextBudget import ContextBudget, DEFAULT_BUDGET_TOKENS, estimate_tokens

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
    """Fit the *delivered string* inside the budget, not the entries inside it.

    Budgeting the entry list alone is not budget parity: each condition wraps
    its entries in a different envelope and B's entries carry extra fields, so
    an identical entry budget still delivered B roughly twice the text of G.
    That is precisely the confound this study exists to remove, so the cap is
    applied to the serialised payload the model actually receives, and entries
    are dropped from the end until the whole string fits.
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
        # drop proportionally when far over, one at a time when close
        overshoot = used - budget_tokens
        step = max(1, int(len(kept) * overshoot / max(used, 1)))
        kept = kept[: max(0, len(kept) - step)]


def build_retrieve_graph_tool(
    graph,
    graph_folder_path,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    prefer_cross_file: bool = False,
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
            graph, graph_path, node, max_neighbors=max_neighbors, max_depth=max_depth,
            prefer_cross_file=prefer_cross_file,
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
        node_id = _find_target_node(graph, node)
        payload = {
            "query": node,
            "found": node_id is not None,
            "condition": CONDITION_DENSE,
            "node": _node_entry(graph, node_id) if node_id is not None else None,
        }

        query_vector = embed(" ".join(_tokenize_query(node)) or node)
        scored = []
        for candidate in graph.nodes:
            if candidate == node_id:
                continue
            document = _node_document(graph, candidate)
            if not document:
                continue
            score = _cosine(query_vector, embed(document))
            scored.append((score, str(candidate), candidate))
        scored.sort(key=lambda row: (-row[0], row[1]))

        entries = []
        for score, _, candidate in scored[:max_neighbors]:
            entry = _node_entry(graph, candidate)
            entry["score"] = round(score, 6)
            entries.append(entry)
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
):
    """Condition F: the FAULT-LOCATION oracle.

    It returns the graph entities whose line range spans the ground-truth
    defect line — the class, the function, the variables *at the fault site*.

    That is not an evidence oracle and must not be described as one. A defect on
    a changed line can still require another file to recognise: the fault is the
    changed `raise ValueError`, the evidence is the `except TypeError` in a file
    this condition never returns. Supplying more of the fault site supplies more
    of what the model could already see, so this condition performing like no
    context at all says only that enlarging the visible fault site does not help.
    It says nothing about whether useful repository context exists.

    A real evidence oracle supplies the minimal external code that proves the
    change is wrong. That is a separate condition and is not implemented here.

    Nothing that reads `targets` may ever run in a condition being compared
    honestly.
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
        node_id = _find_target_node(graph, node)
        payload = {
            "query": node,
            "found": node_id is not None,
            "condition": CONDITION_ORACLE,
            "node": _node_entry(graph, node_id) if node_id is not None else None,
            "oracle_targets": len(targets),
        }

        entries = []
        seen = set()
        for candidate in graph.nodes:
            if candidate == node_id or candidate in seen:
                continue
            data = graph.nodes[candidate]
            for target in targets:
                if data.get("relative_path") != target.get("path"):
                    continue
                if _spans_overlap(data.get("line_range"), target.get("line"), tolerance):
                    seen.add(candidate)
                    entries.append(_node_entry(graph, candidate))
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

    if condition == CONDITION_DENSE:
        return [
            build_dense_context_tool(
                graph,
                graph_folder_path,
                embed_fn=embed_fn,
                max_neighbors=max_neighbors,
                budget_tokens=budget_tokens,
            )
        ]

    if condition == CONDITION_ORACLE:
        return [
            build_oracle_context_tool(
                graph,
                graph_folder_path,
                targets=oracle_targets,
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
            prefer_cross_file=prefer_cross_file,
        )
    ]


retrieve_graph_tool = build_retrieve_graph_tool
toolOrganizer = build_tools
