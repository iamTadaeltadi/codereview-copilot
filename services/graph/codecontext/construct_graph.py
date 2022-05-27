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

        self.repo_content_prefix = repo_content_prefix
        # Create a hierarchical structure of the codebase (optional usage)
        self.structure = create_structure(self.root)

        # Precompute all source files in the repo for local-import checks
        self.all_source_files = self.find_src_files(self.root)

    def parse_tree(self, code, file_extension):
        """Parse the code (string) using tree-sitter."""
        if not set_language_for_file(file_extension):
            # Language not available, return None
            return None
        tree = parser.parse(bytes(code, "utf-8"))
        return tree

    def parse_code_string(self, code_string, rel_fname):
        """
        Parse the given code string in-memory using tree-sitter
        and return the extracted tags (like classes, functions, imports, etc.).
        """
        file_extension = os.path.splitext(rel_fname)[1]
        tree = self.parse_tree(code_string, file_extension)
        if tree is None:
            # Language not available, return empty tags
            return []
        def_tags = self.extract_tags(tree.root_node, rel_fname)
        import_tags = self.extract_imports(tree.root_node, file_extension, rel_fname)
        return def_tags + import_tags

    def extract_function_calls(self, node, rel_fname, current_function):
        """
        Recursively extract function call tags within a function/method node.
        We store 'fname=current_function' so 'fname' reflects the caller function name.
        """
        calls = []
        if node.type in ("call", "call_expression", "method_invocation"):
            func_name_node = next((c for c in node.children if c.type == "identifier"), None)
            if func_name_node:
                callee_name = func_name_node.text.decode("utf-8")
                calls.append(Tag(
                    rel_fname=rel_fname,
                    fname=current_function,  # The caller’s function name
                    line=[node.start_point[0] + 1, node.end_point[0] + 1],
                    name=callee_name,        # The callee name
                    kind="call",
                    category="function_call",
                    info={}
                ))

        for child in node.children:
            calls.extend(self.extract_function_calls(child, rel_fname, current_function))
        return calls


    def extract_variable_attributes(self, node, rel_fname, current_function, inside_assignment=False):
        """
        Recursively walk the AST to find variable/attribute references inside a function.
        We'll store 'fname=current_function' so 'fname' reflects the enclosing function name.
        """
        dependencies = []

        if node.type in ("assignment", "augmented_assignment_expression"):
            # Typically child[0] => left side (writes), child[-1] => right side (reads)
            if len(node.children) >= 2:
                lhs = node.children[0]
                rhs = node.children[-1]
                dependencies.extend(
                    self.extract_variable_attributes(lhs, rel_fname, current_function, inside_assignment=True)
                )
                dependencies.extend(
                    self.extract_variable_attributes(rhs, rel_fname, current_function, inside_assignment=False)
                )

        elif node.type == "identifier":
            var_name = node.text.decode("utf-8")
            kind = "write" if inside_assignment else "read"
            dependencies.append(
                Tag(
                    rel_fname=rel_fname,
                    fname=current_function,  # The enclosing function’s name
                    line=[node.start_point[0] + 1, node.end_point[0] + 1],
                    name=var_name,
                    kind=kind,               # "read" or "write"
                    category="var_dependency",
                    info={}
                )
            )

        elif node.type == "attribute":
            # e.g. "self.x" or "obj.prop" in Python
            var_name = node.text.decode("utf-8")
            kind = "write" if inside_assignment else "read"
            dependencies.append(
                Tag(
                    rel_fname=rel_fname,
                    fname=current_function,  # The enclosing function’s name
                    line=[node.start_point[0] + 1, node.end_point[0] + 1],
                    name=var_name,
                    kind=kind,
                    category="var_dependency",
                    info={"is_attribute": True}
                )
            )

        # Recurse further if we're not specifically dividing assignment left/right
        if node.type not in ("assignment", "augmented_assignment_expression"):
            for child in node.children:
                dependencies.extend(
                    self.extract_variable_attributes(child, rel_fname, current_function, inside_assignment)
                )

        return dependencies

    def extract_inheritance_tags(self, class_node, file_extension, rel_fname, class_name):
        """
        Detect class inheritance. Returns a list of Tag objects representing 'inherits_from'.
        """
        inheritance_tags = []

        if file_extension == ".py":
            arg_list_node = next((c for c in class_node.children if c.type == "argument_list"), None)
            if arg_list_node:
                parent_ids = [c.text.decode("utf-8") for c in arg_list_node.children if c.type == "identifier"]
                for parent_cls in parent_ids:
                    inheritance_tags.append(
                        Tag(
                            rel_fname=rel_fname,
                            fname=None,
                            line=[class_node.start_point[0] + 1, class_node.end_point[0] + 1],
                            name=f"{class_name}->{parent_cls}",
                            kind="inherits",
                            category="class_inheritance",
                            info={"child_class": class_name, "parent_class": parent_cls}
                        )
                    )


        elif file_extension == ".java":
            superclass_node = next((c for c in class_node.children if c.type == "superclass"), None)
            if superclass_node:
                type_identifier = next((c for c in superclass_node.children if c.type == "type_identifier"), None)
                if type_identifier:
                    parent_cls = type_identifier.text.decode("utf-8")
                    inheritance_tags.append(
                        Tag(
                            rel_fname=rel_fname,
                            fname=None,
                            line=[class_node.start_point[0] + 1, class_node.end_point[0] + 1],
                            name=f"{class_name}->{parent_cls}",
                            kind="inherits",
                            category="class_inheritance",
                            info={"child_class": class_name, "parent_class": parent_cls}
                        )
                    )

        elif file_extension == ".js":
