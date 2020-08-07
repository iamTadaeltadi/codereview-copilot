import json
import logging
import os

from langchain.tools import tool

from codecontext.retriever import retrieve_node_context

logger = logging.getLogger(__name__)


def build_retrieve_graph_tool(graph, graph_folder_path):
    @tool
    def retrieve_graph(node: str) -> str:
        """
        Retrieve grounded repository graph context for a code entity.

        The node identifier should follow:
            "relative_file_path::identifier::name"
        """
        logger.debug("Retrieving graph context for %s", node)
        graph_path = os.path.join(graph_folder_path, "graph.pkl")
        return json.dumps(retrieve_node_context(graph, graph_path, node))

    return retrieve_graph


def build_tools(graph, graph_folder_path):
    return [build_retrieve_graph_tool(graph, graph_folder_path)]


# Backwards-compatible aliases for existing imports.
retrieve_graph_tool = build_retrieve_graph_tool
toolOrganizer = build_tools
