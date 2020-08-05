import logging
import os
import pickle

logger = logging.getLogger(__name__)


def save_graph(graph_folder_path, graph):
    os.makedirs(graph_folder_path, exist_ok=True)
    graph_path = os.path.join(graph_folder_path, 'graph.pkl')
    with open(graph_path, 'wb') as handle:
        pickle.dump(graph, handle)

    logger.info("Cached code graph at %s", graph_path)
