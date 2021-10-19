import os
from codecontext.construct_graph import CodeGraph

def gather_files(directory, exts):
        all_paths = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                all_paths.append(os.path.relpath(os.path.join(root, file), directory))
        code_files = [p for p in all_paths if os.path.splitext(p)[1] in exts]
        return all_paths, code_files

def parse_code_files(code_graph, directory, files):
        all_tags = []
        for path in files:
            try:
                with open(os.path.join(directory, path), "r", encoding="utf-8") as f:
                    code_string = f.read()
            except Exception as e:
                print(f"Error reading content for {path}: {e}")
                continue
            all_tags.extend(code_graph.parse_code_string(code_string, path))
        return all_tags
def generate_code_tags(G):
    tags = []
    for node_id in G.nodes:
        data = G.nodes[node_id]
        node_type = data["type"]
        out = {
            "Node_id": node_id,
            "Node_type": node_type,
            "name": data["name"],
            "filepath": data["relative_path"],
            "start_line": data["line_range"][0],
            "end_line": data["line_range"][1],
            "Info": {}
        }

        if node_type == "file":
            dep_ids = data["metadata"]["dependencies"]
            related_files = [
                G.nodes[dep_id]["relative_path"]
                if G.nodes[dep_id]["relative_path"] else G.nodes[dep_id]["name"]
                for dep_id in dep_ids if dep_id in G.nodes
            ]
            out["Info"] = {
                "Number_of_lines": data["metadata"].get("total_lines", 0),
                "Language": data["metadata"].get("language", ""),
                "related_files": related_files
            }

        elif node_type == "class":
            meta = data["metadata"]
            parent_names = [
                G.nodes[parent_id]["name"] for parent_id in meta["parent_classes"] if parent_id in G.nodes
            ]
            method_names = [
                G.nodes[succ]["name"] for succ in G.successors(node_id)
                if G.nodes[succ]["type"] == "function" and G.nodes[succ]["metadata"]["parent_class"] == data["name"]
            ]
            out["Info"] = {
                "Inheritance": parent_names,
                "methods": method_names,
                "variables": list(set(meta["variables"]))
            }

        elif node_type == "function":
            meta = data["metadata"]
            call_names = [G.nodes[callee_id]["name"] for callee_id in meta["calls"] if callee_id in G.nodes]
            unique_params, seen = [], set()
            for param in meta.get("parameters", []):
                param_key = tuple(
                    (k, tuple(v) if isinstance(v, list) else v)
                    for k, v in sorted(param.items())
                )
                if param_key not in seen:
                    seen.add(param_key)
                    unique_params.append(param)
            out["Info"] = {
                "Parameters": unique_params,
                "IsMethodof": meta["parent_class"],
                "calls": list(set(call_names)),
                "reads": {key: list(meta.get("reads")[key]) for key in meta.get("reads", {})},
                "writes": {key: list(meta.get("writes")[key]) for key in meta.get("writes", {})},
            }

        elif node_type == "variable":
            meta = data["metadata"]
            used_by = meta["accessed_by"].union(meta["modified_by"])
            calls = []
            for used_id in used_by:
                if used_id in G.nodes:
                    used_node = G.nodes[used_id]
                    calls.append(used_node["name"])
                    if used_node["type"] == "function" and "parent_class" in used_node["metadata"]:
                        calls.append(used_node["metadata"]["parent_class"])
            out["Info"] = {
                "calls": list(set(calls)),
                "var_type": meta.get("var_type", ""),
                "modified_by": list(meta.get("modified_by", [])),
                "accessed_by": list(meta.get("accessed_by", []))
            }

        tags.append(out)
    return tags

def generate_code_graph(repo_folder_path):
    repo_dir = os.path.join(os.getcwd(), repo_folder_path.lstrip("./"))
    valid_exts = {".py", ".js", ".java", ".c"}

    all_paths, code_paths = gather_files(repo_dir, valid_exts)
    code_graph = CodeGraph(root=repo_dir)
    code_graph.all_source_files = [p for p in all_paths if os.path.splitext(p)[1]]

    all_tags = parse_code_files(code_graph, repo_dir, code_paths)

    G = code_graph.tag_to_graph(all_tags)
    
    return G
def print_graph_info(G, dir_name):
    print("---------------------------------")
    print(f"Successfully constructed the code graph for repo directory {dir_name}")
    print(f"   Number of nodes: {len(G.nodes)}")
    print(f"   Number of edges: {len(G.edges)}")
    print("---------------------------------")