import os
import uuid
from config import Config
from Utils import get_pr_diff, get_pr_metadata,clone_repo,generate_code_graph,print_graph_info,save_graph
from codecontext.retriever import retrieve_node_context
import json
import pickle
def preProcessingStep(user, repo, branch_name):
    repo_folder_path = clone_repo(user, repo, branch_name)
    graph_folder_path = os.path.join(".", "tmp", "graph", f"{repo}-{branch_name}-{uuid.uuid4()}")
    G = generate_code_graph(repo_folder_path)
    print_graph_info(G, repo_folder_path)
    save_graph(graph_folder_path, G)
    return graph_folder_path, repo_folder_path


if __name__ == "__main__":
    user = "Ram-95"
    repo = "to_do_app"
    PR_ID = 21
    diff = get_pr_diff(user, repo, PR_ID, "thought", {"headers": ""})
    metadata = get_pr_metadata(user, repo, PR_ID, "thought", {"headers": ""})
    branch = metadata["head"]["ref"]
    user = metadata["head"]["user"]
    graph_folder_path, repo_folder_path = preProcessingStep(user, repo, branch)
    with open(os.path.join(graph_folder_path, "graph.pkl"), "rb") as f:
        G = pickle.load(f)
    print(json.dumps(retrieve_node_context(G,os.path.join(graph_folder_path, "graph.pkl"), "users/models.py::class::Profile"), indent=4))