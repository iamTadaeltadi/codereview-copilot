import networkx as nx

def find_file_by_name(G, filename):
    """
    Return the node-id of a file node whose 'name' equals `filename`.
    """
    for node_id in G.nodes:
        data = G.nodes[node_id]
        if data["type"] == "file" and data["name"] == filename:
            return node_id
    return None

def find_class_by_name(G, classname, file_node_id=None):
    """
    Return a list of node-ids for class nodes named `classname`.
    Optionally, if file_node_id is given, only search classes in that file.
    """
    results = []
    for node_id in G.nodes:
        data = G.nodes[node_id]
        if data["type"] == "class" and data["name"] == classname:
            if file_node_id:
                if data["relative_path"] == G.nodes[file_node_id]["relative_path"]:
                    results.append(node_id)
            else:
                results.append(node_id)
    return results

def find_function_by_name(G, funcname, file_node_id=None):
    """
    Return a list of node-ids for function nodes named `funcname`.
    Optionally, restrict to a specific file node.
    """
    results = []
    for node_id in G.nodes:
        data = G.nodes[node_id]
        if data["type"] == "function" and data["name"] == funcname:
            if file_node_id:
                if data["relative_path"] == G.nodes[file_node_id]["relative_path"]:
                    results.append(node_id)
            else:
                results.append(node_id)
    return results

def find_variable_by_name(G, varname, file_node_id=None):
    """
    Return a list of node-ids for variable nodes named `varname`.
    Optionally, restrict to a specific file.
    """
    results = []
    for node_id in G.nodes:
        data = G.nodes[node_id]
        if data["type"] == "variable" and data["name"] == varname:
            if file_node_id:
                if data["relative_path"] == G.nodes[file_node_id]["relative_path"]:
                    results.append(node_id)
            else:
                results.append(node_id)
    return results

# ----------------------------------------------------------------------
# FILE-LEVEL QUERIES
# ----------------------------------------------------------------------

def files_that_import(G, target_file_node_id):
    """
    Which files import or include a certain file/module (given by node_id)?
    """
    results = []
    for (src, dst, edge_data) in G.edges(data=True):
        if edge_data.get("label") == "imports" and dst == target_file_node_id:
            results.append(src)
    return results

