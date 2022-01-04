import os
import pickle
import tempfile
import unittest

from codecontext.retriever import retrieve_node_context


class FakeNodeView:
    def __init__(self, data):
        self._data = data

    def __call__(self, data=False):
        return list(self._data.items()) if data else list(self._data)

    def __getitem__(self, key):
        return self._data[key]


class FakeGraph:
    def __init__(self):
        self._nodes = {
            'module.py::function::process': {
                'name': 'process',
                'type': 'function',
                'relative_path': 'src/module.py',
                'line_range': [10, 18],
                'metadata': {'params': ['payload']},
            },
            'module.py::class::Processor': {
                'name': 'Processor',
                'type': 'class',
                'relative_path': 'src/module.py',
                'line_range': [1, 30],
                'metadata': {},
            },
            'module.py::function::helper': {
                'name': 'helper',
                'type': 'function',
                'relative_path': 'src/module.py',
                'line_range': [20, 24],
                'metadata': {},
            },
        }
        self.nodes = FakeNodeView(self._nodes)
        self._pred = {'module.py::function::process': ['module.py::class::Processor']}
        self._succ = {'module.py::function::process': ['module.py::function::helper']}

    def predecessors(self, node_id):
        return iter(self._pred.get(node_id, []))

    def successors(self, node_id):
        return iter(self._succ.get(node_id, []))


class RetrieveNodeContextLoadingTests(unittest.TestCase):
    def test_loads_graph_from_disk_when_graph_object_is_none(self):
        graph = FakeGraph()
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = os.path.join(tmpdir, 'graph.pkl')
            with open(graph_path, 'wb') as handle:
                pickle.dump(graph, handle)

            result = retrieve_node_context(None, graph_path, 'src/module.py::function::process')

        self.assertTrue(result['found'])
        self.assertEqual(result['node']['name'], 'process')

    def test_limits_neighbors_to_requested_bound(self):
        graph = FakeGraph()

        result = retrieve_node_context(graph, '', 'src/module.py::function::process', max_neighbors=1)

        self.assertTrue(result['found'])
        self.assertEqual(len(result['neighbors']), 1)

    def test_raises_for_missing_graph_file(self):
        with self.assertRaises(FileNotFoundError):
            retrieve_node_context(None, '/tmp/does-not-exist-graph.pkl', 'src/module.py::function::process')


if __name__ == '__main__':
    unittest.main()
