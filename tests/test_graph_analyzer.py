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
            "file.py::function::process": {
                "name": "process",
                "type": "function",
                "relative_path": "src/file.py",
                "line_range": [10, 20],
                "metadata": {"params": ["payload"]},
            },
            "file.py::class::Processor": {
                "name": "Processor",
                "type": "class",
                "relative_path": "src/file.py",
                "line_range": [1, 30],
                "metadata": {},
            },
        }
        self.nodes = FakeNodeView(self._nodes)
        self._pred = {"file.py::function::process": ["file.py::class::Processor"]}
        self._succ = {"file.py::function::process": []}

    def predecessors(self, node_id):
        return iter(self._pred.get(node_id, []))

    def successors(self, node_id):
        return iter(self._succ.get(node_id, []))


class RetrieveNodeContextTests(unittest.TestCase):
    def test_returns_matching_node_and_neighbors(self):
        graph = FakeGraph()

        result = retrieve_node_context(graph, "", "src/file.py::function::process")

        self.assertTrue(result["found"])
        self.assertEqual(result["node"]["name"], "process")
        self.assertEqual(result["neighbors"][0]["name"], "Processor")

    def test_returns_not_found_payload_for_missing_node(self):
        graph = FakeGraph()

        result = retrieve_node_context(graph, "", "src/missing.py::function::unknown")

        self.assertFalse(result["found"])
        self.assertIsNone(result["node"])
        self.assertEqual(result["neighbors"], [])


if __name__ == "__main__":
    unittest.main()
