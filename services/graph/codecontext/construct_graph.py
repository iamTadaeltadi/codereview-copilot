import os
import random
import sys
import re
import warnings
from collections import defaultdict, namedtuple
from pathlib import Path
import networkx as nx
from tree_sitter import Language, Parser
from codecontext.utils import create_structure
import pickle
import json

# Load the tree-sitter parsers using standard packages
try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_java as tsjava
    import tree_sitter_c as tsc
    
    PY_LANGUAGE = Language(tspython.language())
    JS_LANGUAGE = Language(tsjavascript.language())
    JAVA_LANGUAGE = Language(tsjava.language())
    C_LANGUAGE = Language(tsc.language())
except ImportError:
    # Fallback: create dummy languages if tree-sitter packages not available
    print("Warning: Tree-sitter language packages not found. Code parsing will be limited.")
    PY_LANGUAGE = None
    JS_LANGUAGE = None
    JAVA_LANGUAGE = None
    C_LANGUAGE = None

parser = Parser()

LANGUAGE_MAP = {
    ".py": PY_LANGUAGE,
    ".js": JS_LANGUAGE,
    ".java": JAVA_LANGUAGE,
    ".c": C_LANGUAGE,
}

def set_language_for_file(file_extension):
    """Set the parser language based on file extension."""
    if file_extension in LANGUAGE_MAP and LANGUAGE_MAP[file_extension] is not None:
        parser.set_language(LANGUAGE_MAP[file_extension])
        return True
    else:
        # If language not available, skip parsing
        return False

# Named tuple for intermediate tag storage
Tag = namedtuple("Tag", "rel_fname fname line name kind category info".split())

class CodeGraph:
    """
    This class constructs a graph from source code, extracting classes, functions,
    imports, variables, etc. Then we store them as nodes/edges in an NX graph.
    """

    def __init__(
        self,
        map_tokens=1024,
        root=None,
        main_model=None,
        io=None,
        repo_content_prefix=None,
        verbose=False,
        max_context_window=None,
    ):
        self.io = io
        self.verbose = verbose

        if not root:
            root = os.getcwd()
        self.root = root

        self.max_map_tokens = map_tokens
        self.max_context_window = max_context_window

