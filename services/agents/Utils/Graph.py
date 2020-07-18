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
