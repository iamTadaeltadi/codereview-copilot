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
            extends_clause_node = next((c for c in class_node.children if c.type == "extends_clause"), None)
            if extends_clause_node:
                parent_identifier = next((c for c in extends_clause_node.children if c.type == "identifier"), None)
                if parent_identifier:
                    parent_cls = parent_identifier.text.decode("utf-8")
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
        # C has no built-in class inheritance
        return inheritance_tags

    def extract_tags(self, node, rel_fname):
        """
        Recursively extract tags (classes, functions, calls, var_deps, etc.) from a tree-sitter node.
        """
        tags = []
        for child in node.children:
            # Identify classes or functions
            if child.type in [
                "class",
                "class_definition",
                "function",
                "function_definition",
                "function_declaration",
                "class_declaration",
                "method_declaration",
            ]:
                name_node = next((c for c in child.children if c.type == "identifier"), None)
                name = name_node.text.decode("utf-8") if name_node else "unknown"
                start_line, end_line = child.start_point[0] + 1, child.end_point[0] + 1

                kind = (
                    "class"
                    if child.type in ["class", "class_definition", "class_declaration"]
                    else "function"
                )

                # Tag for the class or function definition
                tags.append(Tag(
                    rel_fname=rel_fname,
                    fname=None,
                    line=[start_line, end_line],
                    name=name,
                    kind="def",
                    category=kind,
                    info=""
                ))

                # If it's a class, handle inheritance + gather methods
                if kind == "class":
                    file_extension = os.path.splitext(rel_fname)[1]
                    inheritance_tags = self.extract_inheritance_tags(child, file_extension, rel_fname, name)
                    tags.extend(inheritance_tags)


                    # Recursively gather method definitions inside the class
                    methods = self.extract_tags(child, rel_fname)
                    # Mark them as "method" (but also keep them as "function" category)
                    for method in methods:
                        if method.category == "function":
                            method_info = {"name": method.name}
                            tags.append(Tag(
                                rel_fname=rel_fname,
                                fname=None,
                                line=method.line,
                                name=method.name,
                                kind="method",
                                category="function",
                                info=method_info
                            ))
                    tags.extend(methods)
                else:
                    # If it's a function, extract function calls & var/attr dependencies
                    calls = self.extract_function_calls(child, rel_fname, current_function=name)
                    tags.extend(calls)

                    var_deps = self.extract_variable_attributes(child, rel_fname, current_function=name)
                    tags.extend(var_deps)

            # Recurse deeper
            tags.extend(self.extract_tags(child, rel_fname))

        return tags

    def extract_imports(self, node, file_extension, rel_fname):
        """
        Recursively extract import statements (#include in C or import in others).
        """
        imports = []
        for child in node.children:
            if file_extension == ".py":
                if child.type in ["import_statement", "import_from_statement"]:
                    imported_mod = child.text.decode("utf-8").strip()
                    imports.append(
                        Tag(
                            rel_fname=rel_fname,
                            fname=None,
                            line=[child.start_point[0] + 1, child.end_point[0] + 1],
                            name=imported_mod,
                            kind="import",
                            category="import",
                            info={}
                        )
                    )
            elif file_extension == ".js":
                if child.type == "import_statement":
                    imported_mod = child.text.decode("utf-8").strip()
                    imports.append(
                        Tag(
                            rel_fname=rel_fname,
                            fname=None,
                            line=[child.start_point[0] + 1, child.end_point[0] + 1],
                            name=imported_mod,
                            kind="import",
                            category="import",
                            info={}
                        )
                    )
            elif file_extension == ".java":
                if child.type == "import_declaration":
                    imported_mod = child.text.decode("utf-8").strip()
                    imports.append(
                        Tag(
                            rel_fname=rel_fname,
                            fname=None,
                            line=[child.start_point[0] + 1, child.end_point[0] + 1],
                            name=imported_mod,
                            kind="import",
                            category="import",
                            info={}
                        )
                    )
            elif file_extension == ".c":
                if child.type == "preproc_include":
                    imported_mod = child.text.decode("utf-8").strip()
                    imports.append(
                        Tag(
                            rel_fname=rel_fname,
                            fname=None,
                            line=[child.start_point[0] + 1, child.end_point[0] + 1],
                            name=imported_mod,
                            kind="import",
                            category="import",
                            info={}

                        )
                    )

            # Recurse deeper
            imports.extend(self.extract_imports(child, file_extension, rel_fname))

        return imports

    def get_tags(self, fname, rel_fname):
        """Get tags for a given file by reading it from disk and parsing."""
        try:
            with open(fname, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            print(f"Error reading file {fname}: {e}")
            return []

        file_extension = os.path.splitext(fname)[1]
        tree = self.parse_tree(code, file_extension)
        if tree is None:
            # Language not available, return empty tags
            return []

        def_tags = self.extract_tags(tree.root_node, rel_fname)
        import_tags = self.extract_imports(tree.root_node, file_extension, rel_fname)
        return def_tags + import_tags

    def get_code_graph(self, other_files, mentioned_fnames=None):
        """Build a code graph from extracted tags for the given list of file paths."""
        if self.max_map_tokens <= 0 or not other_files:
            return None, None
        if not mentioned_fnames:
            mentioned_fnames = set()

        tags = []
        for file_path in other_files:
            rel_fname = self.get_rel_fname(file_path)
            tags.extend(self.get_tags(file_path, rel_fname))

        code_graph = self.tag_to_graph(tags)
        return tags, code_graph

    def is_local_import(self, imported_module: str) -> bool:
        """
        Check if this 'imported_module' is local vs. built-in/external.
        """
        # Case: C #include "something.h"
        if imported_module.startswith("#include") and '"' in imported_module:
            match = re.search(r'#include\s+"([^"]+)"', imported_module)
            if match:
                possible_local_header = match.group(1).split(".")[0]
                for fpath in self.all_source_files:
                    base = os.path.splitext(os.path.basename(fpath))[0]
                    if base == possible_local_header:
                        return True
            return False

        # Case: Python import or from import
        match = re.match(r'(?:from\s+([\w\.]+)\s+import)|(?:import\s+([\w\.]+))', imported_module)
        if not match:
            return False

        mod_name = match.group(1) or match.group(2)
        mod_name = mod_name.split('.')[0]

        for fpath in self.all_source_files:
            base = os.path.splitext(os.path.basename(fpath))[0]
            if base == mod_name:
                return True
        return False

    def tag_to_graph(self, tags):
        """
        Convert extracted tags into a NetworkX graph.

        We do NOT directly write the final JSON here.
        Instead, we store enough info in the graph so we can later
        produce the final metadata structure.
        """
        G = nx.MultiDiGraph()

        # 1) Create a node for each file we see in tags
        all_files = set(t.rel_fname for t in tags)
        for f in all_files:
            abs_path = os.path.join(self.root, f)
            file_name = os.path.basename(abs_path)
            try:
                size = os.path.getsize(abs_path)
                created_at = os.path.getctime(abs_path)
                updated_at = os.path.getmtime(abs_path)
                with open(abs_path, "r", encoding="utf-8") as temp_f:
                    total_lines = sum(1 for _ in temp_f)
            except:
                size = 0
                created_at = 0
                updated_at = 0
                total_lines = 0


            # Add as a "file" node
            node_data = {
                "relative_path": f,
                "file_name": file_name,
                "name": file_name,
                "type": "file",
                "line_range": [1, total_lines if total_lines else 1],
                "metadata": {
                    "language": os.path.splitext(file_name)[1].lstrip('.'),
                    "size": size,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "dependencies": [],
                    "total_lines": total_lines
                },
            }
            G.add_node(f, **node_data)

        # 2) Create nodes for classes, functions, variables, etc.
        for tag in tags:
            # Skip external imports from being nodes
            if tag.category == 'import' and not self.is_local_import(tag.name):
                continue

            node_key = self._get_node_key(tag)
            # Some ephemeral tags (inherits, call, etc.) might only be edges
            if tag.kind in ["inherits", "call"]:
                continue

            if not G.has_node(node_key):
                # Determine node "type"
                if tag.kind in ["def", "method"] and tag.category == "class":
                    node_type = "class"
                elif tag.kind in ["def", "method"] and tag.category == "function":
                    node_type = "function"
                elif tag.kind == "import":
                    # We'll only add file->file edges for imports
                    continue
                elif tag.kind in ["write", "read"]:
                    node_type = "variable"
                else:
                    node_type = "unknown"

                relative_path = tag.rel_fname
                file_name = os.path.basename(tag.rel_fname)
                start_line, end_line = tag.line if tag.line else [1, 1]

                node_data = {
                    "relative_path": relative_path,
                    "file_name": file_name,
                    "name": tag.name,
                    "type": node_type,
                    "line_range": [start_line, end_line],
                    "metadata": {}
                }

                if node_type == "class":
                    node_data["metadata"] = {
                        "parent_classes": [],
                        "methods": [],
