import os
import pickle
from collections import deque


def _normalize_query(node_query: str) -> tuple[str, str, str | None]:
    parts = node_query.split("::")
    if len(parts) == 1:
        return parts[0], "", None
    if len(parts) == 2:
        return parts[0], parts[1], None
    return parts[0], parts[1], parts[2]


def _matches_node(data: dict, rel_path: str, node_type: str, name: str | None) -> bool:
    if data.get("relative_path") != rel_path:
        return False
    if node_type and data.get("type") != node_type:
        return False
    if name is not None and data.get("name") != name:
        return False
    return True


def _find_target_node(graph, node_query: str):
    rel_path, node_type, name = _normalize_query(node_query)
    for node_id, data in graph.nodes(data=True):
        if _matches_node(data, rel_path, node_type, name):
            return node_id
    return None


def split_queries(node_query: str) -> list[str]:
    """Several seeds travel in one string, one per line."""
    return [q.strip() for q in (node_query or "").split("\n") if q.strip()]


def find_seed_nodes(graph, node_query: str) -> list:
    """The node for each seed query, in query order, None where not found."""
    return [_find_target_node(graph, q) for q in split_queries(node_query)]


def _has(graph, node_id) -> bool:
    try:
        graph.nodes[node_id]
    except (KeyError, TypeError, IndexError):
        return False
    return True


def stripped_entry(graph, node_id) -> dict:
    """What any condition may say about an entity: where it is and what it is
    called. No line range and no metadata, for seeds and neighbours alike."""
    data = graph.nodes[node_id]
    return {
        "id": node_id,
        "name": data.get("name"),
        "type": data.get("type"),
        "relative_path": data.get("relative_path"),
    }


def entity_source(graph, node_id, max_lines: int | None = None) -> str | None:
    """The entity's source, trimmed to its line range, from the file text the
    builder kept in graph.graph["sources"]. None when the text is not held."""
    data = graph.nodes[node_id]
    text = ((getattr(graph, "graph", None) or {}).get("sources") or {}).get(data.get("relative_path"))
    if text is None:
        return None
    span = data.get("line_range") or []
    try:
        lo, hi = int(span[0]), int(span[1])
    except (TypeError, ValueError, IndexError):
        return None
    lines = text.splitlines()
    lo = max(lo, 1)
    hi = min(hi, len(lines))
    if hi < lo:
        return None
    chunk = lines[lo - 1:hi]
    if max_lines is not None and len(chunk) > max_lines:
        chunk = chunk[:max_lines] + [f"    # ... {len(lines[lo - 1:hi]) - max_lines} more lines"]
    return "\n".join(chunk)


def _bounded_neighbors(graph, node_id, max_nodes: int = 12, max_depth: int = 2,
                       entity_types=None, exclude=()):
    """Breadth-first neighbourhood of one node; see _bounded_neighbors_multi."""
    return _bounded_neighbors_multi(graph, [node_id], max_nodes, max_depth, entity_types, exclude)


def _bounded_neighbors_multi(graph, seeds, max_nodes: int = 12, max_depth: int = 2,
                             entity_types=None, exclude=()):
    """Breadth-first walk from every seed at once, both edge directions.

    The depth of a neighbour is its distance to the nearest seed, and no seed
    is returned as a neighbour. With entity_types, only nodes of those types
    are returned or walked through: a file node is a hub that joins everything
    in a file, and a variable node is one identifier, so a walk that passes
    through them reaches the file's whole contents in two hops and calls that
    structure. Restricting the walk to functions and classes keeps it on the
    call, containment and inheritance edges that a graph exists to supply.
    """
    seeds = [s for s in seeds if s is not None and _has(graph, s)]
    if max_depth < 1 or max_nodes < 1 or not seeds:
        return []
    allowed = set(entity_types) if entity_types else None
    visited = set(seeds) | set(exclude)
    queue = deque((s, 0) for s in seeds)
    neighbors = []
    while queue and len(neighbors) < max_nodes:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for candidate in list(graph.predecessors(current)) + list(graph.successors(current)):
            if candidate in visited:
                continue
            visited.add(candidate)
            if allowed is not None and graph.nodes[candidate].get("type") not in allowed:
                continue
            queue.append((candidate, depth + 1))
            neighbors.append((candidate, depth + 1))
            if len(neighbors) >= max_nodes:
                break
    return neighbors


def _rank(graph, home_paths, neighbours, prefer_cross_file: bool):
    """Order neighbours before the cap applies.

    Insertion order decides which neighbours survive the cap. Preferring
    neighbours in files other than the seeds' spends the budget on the part of
    the neighbourhood a same-file search could not have found. Ties keep the
    breadth-first order, so nearer neighbours still come first.
    """
    if not prefer_cross_file:
        return neighbours
    home = set(home_paths)
    return sorted(
        neighbours,
        key=lambda item: (graph.nodes[item[0]].get("relative_path") in home, item[1]),
    )


def retrieve_node_context(
    graph,
    graph_path: str,
    node_query: str,
    max_neighbors: int = 12,
    max_depth: int = 2,
    prefer_cross_file: bool = False,
    entity_types=None,
    with_source: bool = False,
    max_source_lines: int | None = None,
) -> dict:
    """The ego-neighbourhood of one or more seed entities.

    node_query holds one seed, or several separated by newlines; every seed is
    walked and the neighbourhoods are merged. The seeds are reported as
    stripped entries (id, name, type, path) and nothing else: an earlier
    version returned the seed's line range and metadata here, which only the
    graph condition received, and that was withdrawn as a leak.
    """
    if graph is None:
        if not graph_path or not os.path.exists(graph_path):
            raise FileNotFoundError(f"graph file not found: {graph_path}")
        with open(graph_path, "rb") as handle:
            graph = pickle.load(handle)

    queries = split_queries(node_query)
    seed_ids = find_seed_nodes(graph, node_query)
    found = [s for s in seed_ids if s is not None]
    base = {
        "query": node_query,
        "queries": queries,
        "found": bool(found),
        "found_count": len(found),
        "max_depth": max_depth,
        "prefer_cross_file": prefer_cross_file,
        "node": stripped_entry(graph, found[0]) if found else None,
        "seeds": [stripped_entry(graph, s) for s in found],
    }
    if not found:
        return {**base, "neighbors": []}

    # Ranking cannot promote what the walk never reached, so when ranking is
    # requested the walk is bounded by depth alone and the cap applies after.
    walk_cap = 100_000 if prefer_cross_file else max_neighbors
    walked = _bounded_neighbors_multi(graph, found, walk_cap, max_depth, entity_types)
    homes = [graph.nodes[s].get("relative_path") for s in found]
    neighbors = []
    for neighbor_id, depth in _rank(graph, homes, walked, prefer_cross_file)[:max_neighbors]:
        entry = stripped_entry(graph, neighbor_id)
        entry["depth"] = depth
        if with_source:
            entry["source"] = entity_source(graph, neighbor_id, max_source_lines)
        neighbors.append(entry)
    return {**base, "neighbors": neighbors}
