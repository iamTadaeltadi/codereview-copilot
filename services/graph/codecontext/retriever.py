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


def _bounded_neighbors(graph, node_id, max_nodes: int = 12, max_depth: int = 2):
    if max_depth < 1 or max_nodes < 1:
        return []

    visited = {node_id}
    queue = deque([(node_id, 0)])
    neighbors = []
    while queue and len(neighbors) < max_nodes:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for candidate in list(graph.predecessors(current)) + list(graph.successors(current)):
            if candidate in visited:
                continue
            visited.add(candidate)
            queue.append((candidate, depth + 1))
            neighbors.append((candidate, depth + 1))
            if len(neighbors) >= max_nodes:
                break
    return neighbors


def _rank(graph, node_id, neighbours, prefer_cross_file: bool):
    """Order neighbours before the cap applies.

    Insertion order decides which neighbours survive the cap, and a file node is
    a hub, so a breadth-first walk fills the budget with the defect's own file
    before it reaches anything else. Measured on the cross-file benchmark: the
    depended-upon caller sits within two hops for 76% of tasks and was returned
    for 15% of them.

    Preferring neighbours in other files spends the same budget on the part of
    the neighbourhood a same-file search could not have found. Ties keep the
    original breadth-first order, so nearer neighbours still come first.
    """
    if not prefer_cross_file:
        return neighbours
    home = graph.nodes[node_id].get("relative_path")
    return sorted(
        neighbours,
        key=lambda item: (graph.nodes[item[0]].get("relative_path") == home, item[1]),
    )


def retrieve_node_context(
    graph,
    graph_path: str,
    node_query: str,
    max_neighbors: int = 12,
    max_depth: int = 2,
    prefer_cross_file: bool = False,
) -> dict:
    if graph is None:
        if not graph_path or not os.path.exists(graph_path):
            raise FileNotFoundError(f"graph file not found: {graph_path}")
        with open(graph_path, "rb") as handle:
            graph = pickle.load(handle)

    node_id = _find_target_node(graph, node_query)
    if node_id is None:
        return {
            "query": node_query,
            "found": False,
            "max_depth": max_depth,
            "node": None,
            "neighbors": [],
        }

    node = graph.nodes[node_id]
    neighbors = []
    # Ranking cannot promote what the walk never reached. Capping the walk by
    # node count fills it with one-hop neighbours from the defect's own file and
    # stops before the cross-file neighbours two hops out, so when ranking is
    # requested the walk is bounded by depth alone and the cap applies after.
    walk_cap = 100_000 if prefer_cross_file else max_neighbors
    walked = _bounded_neighbors(graph, node_id, walk_cap, max_depth)
    for neighbor_id, depth in _rank(graph, node_id, walked, prefer_cross_file)[:max_neighbors]:
        neighbor = graph.nodes[neighbor_id]
        neighbors.append(
            {
                "id": neighbor_id,
                "name": neighbor.get("name"),
                "type": neighbor.get("type"),
                "relative_path": neighbor.get("relative_path"),
                "depth": depth,
            }
        )

    return {
        "query": node_query,
        "found": True,
        "max_depth": max_depth,
        "prefer_cross_file": prefer_cross_file,
        "node": {
            "id": node_id,
            "name": node.get("name"),
            "type": node.get("type"),
            "relative_path": node.get("relative_path"),
            "line_range": node.get("line_range"),
            "metadata": node.get("metadata", {}),
        },
        "neighbors": neighbors,
    }
