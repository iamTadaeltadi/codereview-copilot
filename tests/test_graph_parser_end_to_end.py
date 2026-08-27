import os
import tempfile
import unittest

try:
    from codecontext.construct_graph import CodeGraph, set_language_for_file
    from codecontext.retriever import retrieve_node_context

    _GRAPH_AVAILABLE = True
except Exception:
    _GRAPH_AVAILABLE = False


SAMPLE_PY = '''
class Calculator:
    def add(self, left, right):
        return helper(left) + right


def helper(value):
    return value * 2
'''

SAMPLE_JS = '''
function greet(name) {
  return "hi " + name;
}
'''


@unittest.skipUnless(_GRAPH_AVAILABLE, "graph service deps not installed")
class LanguageBindingTests(unittest.TestCase):
    def test_parser_accepts_every_supported_extension(self):
        for extension in (".py", ".js", ".java", ".c"):
            with self.subTest(extension=extension):
                self.assertTrue(set_language_for_file(extension))

    def test_unsupported_extension_is_rejected_without_raising(self):
        self.assertFalse(set_language_for_file(".rs"))


@unittest.skipUnless(_GRAPH_AVAILABLE, "graph service deps not installed")
class GraphConstructionTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        with open(os.path.join(self.root, "calc.py"), "w", encoding="utf-8") as handle:
            handle.write(SAMPLE_PY)
        with open(os.path.join(self.root, "greet.js"), "w", encoding="utf-8") as handle:
            handle.write(SAMPLE_JS)

    def _build(self):
        graph_builder = CodeGraph(root=self.root)
        graph_builder.all_source_files = ["calc.py", "greet.js"]
        tags = []
        for name in ("calc.py", "greet.js"):
            with open(os.path.join(self.root, name), encoding="utf-8") as handle:
                tags.extend(graph_builder.parse_code_string(handle.read(), name))
        return graph_builder.tag_to_graph(tags)

    def test_parsing_produces_class_and_function_nodes(self):
        graph = self._build()
        names = {
            (data.get("type"), data.get("name"))
            for _, data in graph.nodes(data=True)
        }
        self.assertIn(("class", "Calculator"), names)
        self.assertIn(("function", "add"), names)
        self.assertIn(("function", "helper"), names)

    def test_parsing_covers_more_than_one_language(self):
        graph = self._build()
        paths = {data.get("relative_path") for _, data in graph.nodes(data=True)}
        self.assertIn("calc.py", paths)
        self.assertIn("greet.js", paths)

    def test_retriever_finds_a_parsed_class_and_returns_neighbors(self):
        graph = self._build()
        result = retrieve_node_context(graph, "", "calc.py::class::Calculator")
        self.assertTrue(result["found"])
        self.assertEqual(result["node"]["name"], "Calculator")
        self.assertGreater(len(result["neighbors"]), 0)


if __name__ == "__main__":
    unittest.main()
