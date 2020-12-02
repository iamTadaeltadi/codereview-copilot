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
