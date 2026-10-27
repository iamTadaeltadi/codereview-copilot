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
import ast

# Names that resolve to the language runtime, never to a repository function.
# A call to one of these is not an edge, and it never creates a node.
PY_BUILTINS = frozenset("""
abs all any ascii bin bool bytearray bytes callable chr classmethod compile complex delattr dict dir divmod
enumerate eval exec filter float format frozenset getattr globals hasattr hash help hex id input int isinstance
issubclass iter len list locals map max memoryview min next object oct open ord pow print property range repr
reversed round set setattr slice sorted staticmethod str sum super tuple type vars zip
append extend insert remove pop clear index count sort reverse copy keys values items get update setdefault
popitem add discard union intersection difference join split rsplit strip lstrip rstrip replace startswith
endswith lower upper title capitalize encode decode find rfind isdigit isalpha isalnum isspace zfill ljust rjust
center read write readline readlines writelines close flush seek tell exists mkdir deepcopy now today utcnow
strftime strptime isoformat timestamp total_seconds group groups match search sub findall finditer
""".split())

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
        parser.language = LANGUAGE_MAP[file_extension]
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

    @staticmethod
    def _callee_of(node):
        """(callee name, receiver text or None) for a call node.

        The first version took the first `identifier` child of the call, which
        is only the bare form `f()`. Python calls are mostly `obj.m()`,
        `self.m()` and `pkg.mod.f()`, whose callee is an `attribute` node, so
        every method call and every module-qualified call was dropped before
        resolution began. The receiver is kept so that resolution can use it.
        """
        if node.type == "method_invocation":  # Java
            name = node.child_by_field_name("name")
            obj = node.child_by_field_name("object")
            return (name.text.decode("utf-8") if name is not None else None,
                    obj.text.decode("utf-8") if obj is not None else None)
        fn = node.child_by_field_name("function")
        if fn is None:
            return None, None
        if fn.type == "identifier":
            return fn.text.decode("utf-8"), None
        if fn.type == "attribute":  # Python
            attr = fn.child_by_field_name("attribute")
            obj = fn.child_by_field_name("object")
            return (attr.text.decode("utf-8") if attr is not None else None,
                    obj.text.decode("utf-8") if obj is not None else None)
        if fn.type == "member_expression":  # JavaScript
            prop = fn.child_by_field_name("property")
            obj = fn.child_by_field_name("object")
            return (prop.text.decode("utf-8") if prop is not None else None,
                    obj.text.decode("utf-8") if obj is not None else None)
        return None, None

    def extract_function_calls(self, node, rel_fname, current_function):
        """
        Recursively extract function call tags within a function/method node.
        We store 'fname=current_function' so 'fname' reflects the caller function name.
        """
        calls = []
        if node.type in ("call", "call_expression", "method_invocation"):
            callee_name, receiver = self._callee_of(node)
            if callee_name:
                calls.append(Tag(
                    rel_fname=rel_fname,
                    fname=current_function,  # The caller’s function name
                    line=[node.start_point[0] + 1, node.end_point[0] + 1],
                    name=callee_name,        # The callee name
                    kind="call",
                    category="function_call",
                    info={"receiver": receiver}
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

    # ------------------------------------------------------------ imports
    def _relative(self, path: str) -> str:
        path = str(path).replace(os.sep, "/")
        root = str(self.root).replace(os.sep, "/").rstrip("/") + "/"
        if path.startswith(root):
            path = path[len(root):]
        return path.lstrip("./") if path.startswith("./") else path

    def _module_file(self, module: str, level: int, importing_file: str):
        """The repository file a Python module reference names, or None.

        `import a.b.c` -> a/b/c.py or a/b/c/__init__.py, also under any root
        prefix the repository uses (src/a/b/c.py). `from ..x import y` resolves
        against the importing file's directory. The first version compared the
        first dotted segment with file basenames, so `from pkg.sub import f`
        looked for a file called pkg.py and found nothing.
        """
        files = self._rel_files
        parts = [p for p in (module or "").split(".") if p]
        if level:
            base = Path(importing_file).parent
            for _ in range(level - 1):
                base = base.parent
            stem = "/".join([*[p for p in base.parts if p not in (".", "")], *parts])
            for candidate in (f"{stem}.py", f"{stem}/__init__.py"):
                if candidate in files:
                    return candidate
            return None
        if not parts:
            return None
        stem = "/".join(parts)
        best = None
        for candidate in (f"{stem}.py", f"{stem}/__init__.py"):
            if candidate in files:
                return candidate
            suffix = "/" + candidate
            for path in files:
                if path.endswith(suffix) and (best is None or len(path) < len(best)):
                    best = path
        return best

    def _build_import_table(self, tags):
        """{file: {"files": [imported files], "names": {local name: (file, name|None)}}}

        `names` maps what a file calls a thing to where the thing is defined:
        `import a.b as x` gives x -> (a/b.py, None); `from a.b import f as g`
        gives g -> (a/b.py, "f"); `from . import m` gives m -> (dir/m.py, None).
        A name that an imported file itself re-exports is followed at
        resolution time, one hop at a time.
        """
        table = {}
        for tag in tags:
            if tag.category != "import" or not tag.rel_fname.endswith(".py"):
                continue
            entry = table.setdefault(tag.rel_fname, {"files": [], "names": {}})
            try:
                tree = ast.parse(tag.name)
            except SyntaxError:
                continue
            for stmt in tree.body:
                if isinstance(stmt, ast.Import):
                    for alias in stmt.names:
                        target = self._module_file(alias.name, 0, tag.rel_fname)
                        if target is None:
                            continue
                        entry["names"][alias.asname or alias.name] = (target, None)
                        if target not in entry["files"]:
                            entry["files"].append(target)
                elif isinstance(stmt, ast.ImportFrom):
                    package = self._module_file(stmt.module or "", stmt.level, tag.rel_fname)
                    for alias in stmt.names:
                        if alias.name == "*":
                            if package and package not in entry["files"]:
                                entry["files"].append(package)
                            continue
                        # `from pkg import mod` names a submodule as often as a symbol.
                        sub = self._module_file(
                            ((stmt.module + ".") if stmt.module else "") + alias.name, stmt.level, tag.rel_fname
                        )
                        if sub is not None:
                            entry["names"][alias.asname or alias.name] = (sub, None)
                            if sub not in entry["files"]:
                                entry["files"].append(sub)
                        elif package is not None:
                            entry["names"][alias.asname or alias.name] = (package, alias.name)
                            if package not in entry["files"]:
                                entry["files"].append(package)
        return table

    def _definition_in(self, G, file, name, kind):
        key = f"{file}::{kind}::{name}"
        return key if key in self._defined and G.has_node(key) else None

    def _via_file(self, G, file, name, kind, hops: int = 4):
        """A definition of `name` in `file`, or wherever `file` imports it from."""
        if file is None:
            return None
        found = self._definition_in(G, file, name, kind)
        if found is not None or hops == 0:
            return found
        target = self._imports.get(file, {}).get("names", {}).get(name)
        if target is not None:
            tfile, tname = target
            if tname is None:
                # `from . import mod`: the name is a module, not a definition.
                return None
            return self._via_file(G, tfile, tname, kind, hops - 1)
        return None

    def _parent_files(self, G, class_key, seen=None):
        """Files of the classes this class inherits from, nearest first."""
        seen = seen if seen is not None else set()
        out = []
        if class_key is None or class_key in seen or not G.has_node(class_key):
            return out
        seen.add(class_key)
        for parent in G.nodes[class_key].get("metadata", {}).get("parent_classes", []) or []:
            if G.has_node(parent):
                out.append(G.nodes[parent].get("relative_path"))
                out.extend(self._parent_files(G, parent, seen))
        return out

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
        self._rel_files = {self._relative(p) for p in (self.all_source_files or [])}
        self._rel_files |= {t.rel_fname for t in tags}
        self._imports = self._build_import_table(tags)
        self._defined = {self._get_node_key(t) for t in tags
                         if t.kind in ("def", "method") and t.category in ("class", "function")}
        self._defined_classes_by_file = {}
        for t in tags:
            if t.kind == "def" and t.category == "class":
                self._defined_classes_by_file.setdefault(t.rel_fname, {})[t.name] = True

        # 1) Create a node for each file we see in tags, and keep its text so a
        #    retrieved entity can be delivered as code trimmed to its line range.
        G.graph["sources"] = {}
        all_files = set(t.rel_fname for t in tags)
        for f in all_files:
            try:
                with open(os.path.join(self.root, f), "r", encoding="utf-8", errors="ignore") as handle:
                    G.graph["sources"][f] = handle.read()
            except OSError:
                pass
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
                        "variables": [],
                    }
                elif node_type == "function":
                    node_data["metadata"] = {
                        "parameters": [],
                        "parent_class": None,
                        "calls": [],
                        "reads": [],
                        "writes": [],
                    }
                elif node_type == "variable":
                    is_attr = (isinstance(tag.info, dict) and tag.info.get("is_attribute")) or False
                    node_data["metadata"] = {
                        "is_attribute": is_attr,
                        "accessed_by": [],
                        "modified_by": [],
                    }

                G.add_node(node_key, **node_data)

        # 3) file -> class/function edges (containment)
        for tag in tags:
            if tag.kind == 'def' and tag.category in ['class', 'function']:
                file_node = tag.rel_fname
                node_key = self._get_node_key(tag)
                if G.has_node(file_node) and G.has_node(node_key):
                    G.add_edge(file_node, node_key, label='contains')


        # 4) class -> method edges. Also link method’s parent_class
        for tag in tags:
            if tag.category == 'class':
                class_key = self._get_node_key(tag)
                # Check method tags that lie within the class range
                for possible_method in tags:
                    if possible_method.kind == 'method' and possible_method.rel_fname == tag.rel_fname:
                        # If method lines are inside the class lines
                        if (possible_method.line[0] >= tag.line[0]) and (possible_method.line[1] <= tag.line[1]):
                            method_key = self._get_node_key(possible_method)
                            if G.has_node(class_key) and G.has_node(method_key):
                                G.add_edge(class_key, method_key, label='contains')
                                # Also record parent_class in method's metadata
                                G.nodes[method_key]["metadata"]["parent_class"] = tag.name

        # 5) file->file edges from imports
        for tag in tags:
            if tag.category == 'import':
                importing_file_node = tag.rel_fname
                imported_module_string = tag.name

                # Skip external (Python is decided by the import table below)
                if not importing_file_node.endswith(".py") and not self.is_local_import(imported_module_string):
                    continue

                # For C #include "...":
                if imported_module_string.startswith("#include"):
                    match = re.search(r'#include\s+"([^"]+)"', imported_module_string)
                    if match:
                        local_header_basename = os.path.splitext(match.group(1))[0]
                        for f in G.nodes:
                            if G.nodes[f].get('type') == 'file':
                                base = os.path.splitext(os.path.basename(f))[0]
                                if base == local_header_basename:
                                    G.add_edge(importing_file_node, f, label='imports')
                                    G.nodes[importing_file_node]["metadata"]["dependencies"].append(f)
                elif importing_file_node.endswith(".py"):
                    for dep in self._imports.get(importing_file_node, {}).get("files", []):
                        if G.has_node(dep) and dep not in G.nodes[importing_file_node]["metadata"]["dependencies"]:
                            G.add_edge(importing_file_node, dep, label='imports')
                            G.nodes[importing_file_node]["metadata"]["dependencies"].append(dep)
                else:
                    # JS/Java
                    base_match = re.match(
                        r'(?:from\s+([\w\.]+)\s+import)|(?:import\s+([\w\.]+))',
                        imported_module_string
                    )
                    if base_match:
                        mod_name = base_match.group(1) or base_match.group(2)
                        mod_name = mod_name.split('.')[0]
                        for f in G.nodes:
                            if G.nodes[f].get('type') == 'file':
                                base = os.path.splitext(os.path.basename(f))[0]
                                if base == mod_name:
                                    G.add_edge(importing_file_node, f, label='imports')
                                    G.nodes[importing_file_node]["metadata"]["dependencies"].append(f)

        # 6) class inheritance edges (before calls, so `self.m()` can look in parents)
        for tag in tags:
            if tag.kind == 'inherits' and tag.category == 'class_inheritance':
                child_cls = tag.info.get("child_class")
                parent_cls = tag.info.get("parent_class")
                if not child_cls or not parent_cls:
                    continue
                child_key = self._get_class_node_key(tag.rel_fname, child_cls)
                parent_key = self._resolve_class(G, tag.rel_fname, parent_cls)
                if parent_key is None or not G.has_node(child_key) or parent_key == child_key:
                    continue
                G.add_edge(child_key, parent_key, label='inherits_from')
                G.nodes[child_key]["metadata"]["parent_classes"].append(parent_key)

        # 7) function->function edges from calls
        for tag in tags:
            if tag.kind == 'call' and tag.category == 'function_call':
                caller = tag.fname
                callee = tag.name
                if not caller or not callee:
                    continue
                receiver = (tag.info or {}).get("receiver") if isinstance(tag.info, dict) else None
                caller_node_key = self._get_func_node_key(tag.rel_fname, caller)
                if not G.has_node(caller_node_key):
                    G.add_node(
                        caller_node_key,
                        relative_path=tag.rel_fname,
                        file_name=os.path.basename(tag.rel_fname),
                        name=caller,
                        type="function",
                        line_range=[tag.line[0], tag.line[1]],
                        metadata={"parameters": [], "parent_class": None, "calls": [], "reads": [], "writes": []},
                    )
                parent_class = G.nodes[caller_node_key]["metadata"].get("parent_class")
                caller_class = self._get_class_node_key(tag.rel_fname, parent_class) if parent_class else None
                callee_node_key = self._resolve_callee(G, tag.rel_fname, callee, receiver, caller_class)
                if callee_node_key is None or callee_node_key == caller_node_key:
                    G.nodes[caller_node_key]["metadata"].setdefault("unresolved_calls", []).append(
                        f"{receiver}.{callee}" if receiver else callee)
                    continue
                G.add_edge(caller_node_key, callee_node_key, label='calls')
                G.nodes[caller_node_key]["metadata"]["calls"].append(callee_node_key)

        # 8) var dependencies: function->variable
        for tag in tags:
            if tag.category == 'var_dependency':
                func_name = tag.fname
                var_name = tag.name
                access_type = tag.kind  # read/write
                if not func_name or not var_name:
                    continue

                func_key = self._get_func_node_key(tag.rel_fname, func_name)
                var_key = self._get_var_node_key(tag.rel_fname, var_name)


                if not G.has_node(func_key):
                    G.add_node(
                        func_key,
                        relative_path=tag.rel_fname,
                        file_name=os.path.basename(tag.rel_fname),
                        name=func_name,
                        type="function",
                        line_range=[tag.line[0], tag.line[1]],
                        metadata={
                            "parameters": [],
                            "parent_class": None,
                            "calls": [],
                            "reads": [],
                            "writes": [],
                        }
                    )
                if not G.has_node(var_key):
                    is_attr = (isinstance(tag.info, dict) and tag.info.get("is_attribute")) or False
                    G.add_node(
                        var_key,
                        relative_path=tag.rel_fname,
                        file_name=os.path.basename(tag.rel_fname),
                        name=var_name,
                        type="variable",
                        line_range=[tag.line[0], tag.line[1]],
                        metadata={
                            "is_attribute": is_attr,
                            "accessed_by": [],
                            "modified_by": [],
                        }
                    )

                label = 'reads' if access_type == 'read' else 'writes'
                G.add_edge(func_key, var_key, label=label)

                # Update function's reads/writes
                if label == 'reads':
                    if var_key not in G.nodes[func_key]["metadata"]["reads"]:
                        G.nodes[func_key]["metadata"]["reads"].append(var_key)
                else:
                    if var_key not in G.nodes[func_key]["metadata"]["writes"]:
                        G.nodes[func_key]["metadata"]["writes"].append(var_key)

                # Update variable's usage
                if label == 'reads':
                    G.nodes[var_key]["metadata"]["accessed_by"].append(func_key)
                else:
                    G.nodes[var_key]["metadata"]["modified_by"].append(func_key)

        return G

    def _get_node_key(self, tag):
        """Return a unique key for the node based on category/kind/name."""
        if tag.kind == "def" and tag.category == "class":
            return f"{tag.rel_fname}::class::{tag.name}"
        if tag.kind in ["def", "method"] and tag.category == "function":
            return self._get_func_node_key(tag.rel_fname, tag.name)
        if tag.kind in ["read", "write"]:
            return self._get_var_node_key(tag.rel_fname, tag.name)
        return f"{tag.rel_fname}::{tag.category}::{tag.name}"

    def _get_func_node_key(self, rel_fname, func_name):
        return f"{rel_fname}::function::{func_name}"

    def _resolve_definition(self, G, rel_fname, name, kind, receiver=None, caller_class=None):
        """Find where `name` is actually defined, which is often another file.

        Keys are namespaced by file, so looking a callee up in the caller's own
        file invents a phantom node whenever the definition lives elsewhere.
        Every call and every inheritance edge then stays inside one file, and a
        repository graph with no edges between files cannot supply the
        cross-file context it exists to supply.

        Resolution order, most specific first: what the receiver names (an
        imported module or class), the alias the file imported the name under,
        the caller's own file, the parent classes for `self.m()`, the files
        the caller imports, then a definition that is unique across the graph.
        Re-exports are followed through `__init__` files. Names of the Python
        runtime and ambiguous names outside the import set are left unresolved
        rather than guessed, and an unresolved call creates no node: the first
        version made a phantom function node in the caller's own file for
        every miss, a quarter of all function nodes in the cached graphs.
        """
        names = self._imports.get(rel_fname, {}).get("names", {})
        deps = list(self._imports.get(rel_fname, {}).get("files", []))
        if G.has_node(rel_fname):
            for dep in G.nodes[rel_fname].get("metadata", {}).get("dependencies", []) or []:
                if dep not in deps:
                    deps.append(dep)

        receiver = (receiver or "").strip() or None
        if receiver is not None:
            # `pkg.mod.f()` / `alias.f()` / `Cls.m()`: a receiver that names an
            # imported module or class pins the file.
            head = receiver.split("(")[0].split("[")[0]
            target = names.get(head)
            if target is not None:
                tfile, tname = target
                found = (self._via_file(G, tfile, name, kind) if tname is None
                         else None)
                if found is None and tname is not None:
                    # receiver is an imported class: look for its method
                    cls = self._via_file(G, tfile, tname, "class")
                    if cls is not None:
                        found = self._via_file(G, G.nodes[cls]["relative_path"], name, kind)
                if found is not None:
                    return found
            if head in self._defined_classes_by_file.get(rel_fname, {}):
                # `LocalClass.m()`
                found = self._definition_in(G, rel_fname, name, kind)
                if found is not None:
                    return found
        local = self._definition_in(G, rel_fname, name, kind)
        if local is not None and receiver in (None, "self", "cls", "super()"):
            return local

        if receiver is None:
            target = names.get(name)
            if target is not None:
                tfile, tname = target
                found = self._via_file(G, tfile, tname or name, kind)
                if found is not None:
                    return found

        if receiver in ("self", "cls", "super()") and caller_class is not None:
            for pfile in self._parent_files(G, caller_class):
                found = self._via_file(G, pfile, name, kind)
                if found is not None:
                    return found

        if local is not None:
            return local

        for dependency in deps:
            found = self._via_file(G, dependency, name, kind)
            if found is not None:
                return found

        if name in PY_BUILTINS and rel_fname.endswith(".py"):
            return None

        matches = [key for key in self._defined
                   if key.split("::")[-2] == kind and key.split("::")[-1] == name and G.has_node(key)]
        if len(matches) == 1:
            return matches[0]
        return None

    def _resolve_callee(self, G, rel_fname, name, receiver=None, caller_class=None):
        return self._resolve_definition(G, rel_fname, name, "function", receiver, caller_class)

    def _resolve_class(self, G, rel_fname, name):
        return self._resolve_definition(G, rel_fname, name, "class")

    def _get_var_node_key(self, rel_fname, var_name):
        return f"{rel_fname}::var::{var_name}"

    def _get_class_node_key(self, rel_fname, cls_name):
        return f"{rel_fname}::class::{cls_name}"

    def _parse_import_path(self, import_string):
        if import_string.startswith("#include"):
            match = re.search(r'#include\s+"([^"]+)"', import_string)
            if match:
                return match.group(1)
            return import_string
        match = re.match(r'(?:from\s+([\w\.]+)\s+import)|(?:import\s+([\w\.]+))', import_string)
        if match:
            return match.group(1) or match.group(2)
        return import_string

    def get_rel_fname(self, fname):
        return os.path.relpath(fname, self.root)

    def find_src_files(self, directory):
        """Return all source files under the given directory."""
        if not os.path.isdir(directory):
            return [directory]

        src_files = []
        for root_dir, dirs, files in os.walk(directory):
            for file in files:
                if os.path.splitext(file)[1] in LANGUAGE_MAP.keys():
                    src_files.append(os.path.join(root_dir, file))
        return src_files


    def find_files(self, dirs):
        """Given a list of paths or directories, return all valid source file paths."""
        chat_fnames = []
        for dir in dirs:
            p = Path(dir)
            if p.is_dir():
                chat_fnames += self.find_src_files(dir)
            elif os.path.splitext(dir)[1] in LANGUAGE_MAP.keys():
                chat_fnames.append(dir)
        return chat_fnames

if __name__ == "__main__":
    # If run directly, we parse a local directory path from sys.argv
    if len(sys.argv) < 2:
        print("Usage: python construct_graph.py <directory_path>")
        sys.exit(1)

    dir_name = sys.argv[1]
    code_graph = CodeGraph(root=dir_name)
    all_src_files = code_graph.find_files([dir_name])
    tags, G = code_graph.get_code_graph(all_src_files)

    if G is None:
        print("No graph constructed (possibly no valid source files).")
        sys.exit(0)

    print("---------------------------------")
    print(f"Successfully constructed the code graph for repo directory {dir_name}")
    print(f"   Number of nodes: {len(G.nodes)}")
    print(f"   Number of edges: {len(G.edges)}")
    print("---------------------------------")

    # **Step 1: Cache File Contents**
    # To improve efficiency, cache the lines of each file.
    file_contents_cache = {}
    for file_path in all_src_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                file_contents_cache[file_path] = lines
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            file_contents_cache[file_path] = []

    # Now produce the final metadata JSON
    final_nodes = []
    for node_id in G.nodes:
        data = G.nodes[node_id]
        node_type = data["type"]

        # Common fields
        out = {
            "Node_id": node_id,
            "Node_type": node_type,
            "name": data["name"],
            "filepath": data["relative_path"],
            "start_line": data["line_range"][0],
            "end_line": data["line_range"][1],
            "Info": {
                "Number_of_line": data["metadata"].get("total_lines", 0),
                "Language": data["metadata"].get("language", ""),
                "relatedfiles": []
            }
        }

        # **Step 2: Extract Related Files**
        if node_type == "file":
            dep_ids = data["metadata"].get("dependencies", [])  # node IDs
            related_files = []
            for dep_id in dep_ids:
                if dep_id in G.nodes:
                    related_files.append(G.nodes[dep_id]["name"])
            out["Info"]["relatedfiles"] = related_files

        elif node_type == "class":
            meta = data["metadata"]
            parent_names = []
            for parent_id in meta.get("parent_classes", []):
                if parent_id in G.nodes:
                    parent_names.append(G.nodes[parent_id]["name"])

            # Gather methods by checking edges or metadata
            method_names = []
            for succ in G.successors(node_id):
                if G.nodes[succ]["type"] == "function":
                    # It's a method if the parent_class is this class name
                    if G.nodes[succ]["metadata"].get("parent_class") == data["name"]:
                        method_names.append(G.nodes[succ]["name"])

            var_names = list(set(meta.get("variables", [])))  # Adapt if you store class-level vars

            out["Info"].update({
                "Inheritance": parent_names,
                "methods": method_names,
                "variables": var_names
            })

        elif node_type == "function":
            meta = data["metadata"]
            call_names = []
            for callee_id in meta.get("calls", []):
                if callee_id in G.nodes:
                    call_names.append(G.nodes[callee_id]["name"])


    def find_files(self, dirs):
        """Given a list of paths or directories, return all valid source file paths."""
        chat_fnames = []
        for dir in dirs:
            p = Path(dir)
            if p.is_dir():
                chat_fnames += self.find_src_files(dir)
            elif os.path.splitext(dir)[1] in LANGUAGE_MAP.keys():
                chat_fnames.append(dir)
        return chat_fnames

if __name__ == "__main__":
    # If run directly, we parse a local directory path from sys.argv
    if len(sys.argv) < 2:
        print("Usage: python construct_graph.py <directory_path>")
        sys.exit(1)

    dir_name = sys.argv[1]
    code_graph = CodeGraph(root=dir_name)
    all_src_files = code_graph.find_files([dir_name])
    tags, G = code_graph.get_code_graph(all_src_files)

    if G is None:
        print("No graph constructed (possibly no valid source files).")
        sys.exit(0)

    print("---------------------------------")
    print(f"Successfully constructed the code graph for repo directory {dir_name}")
    print(f"   Number of nodes: {len(G.nodes)}")
    print(f"   Number of edges: {len(G.edges)}")
    print("---------------------------------")

    # **Step 1: Cache File Contents**
    # To improve efficiency, cache the lines of each file.
    file_contents_cache = {}
    for file_path in all_src_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                file_contents_cache[file_path] = lines
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            file_contents_cache[file_path] = []

    # Now produce the final metadata JSON
    final_nodes = []
    for node_id in G.nodes:
        data = G.nodes[node_id]
        node_type = data["type"]

        # Common fields
        out = {
            "Node_id": node_id,
            "Node_type": node_type,
            "name": data["name"],
            "filepath": data["relative_path"],
            "start_line": data["line_range"][0],
            "end_line": data["line_range"][1],
            "Info": {
                "Number_of_line": data["metadata"].get("total_lines", 0),
                "Language": data["metadata"].get("language", ""),
                "relatedfiles": []
            }
        }

        # **Step 2: Extract Related Files**
        if node_type == "file":
            dep_ids = data["metadata"].get("dependencies", [])  # node IDs
            related_files = []
            for dep_id in dep_ids:
                if dep_id in G.nodes:
                    related_files.append(G.nodes[dep_id]["name"])
            out["Info"]["relatedfiles"] = related_files

        elif node_type == "class":
            meta = data["metadata"]
            parent_names = []
            for parent_id in meta.get("parent_classes", []):
                if parent_id in G.nodes:
                    parent_names.append(G.nodes[parent_id]["name"])

            # Gather methods by checking edges or metadata
            method_names = []
            for succ in G.successors(node_id):
                if G.nodes[succ]["type"] == "function":
                    # It's a method if the parent_class is this class name
                    if G.nodes[succ]["metadata"].get("parent_class") == data["name"]:
                        method_names.append(G.nodes[succ]["name"])

            var_names = list(set(meta.get("variables", [])))  # Adapt if you store class-level vars

            out["Info"].update({
                "Inheritance": parent_names,
                "methods": method_names,
                "variables": var_names
            })

        elif node_type == "function":
            meta = data["metadata"]
            call_names = []
            for callee_id in meta.get("calls", []):
                if callee_id in G.nodes:
                    call_names.append(G.nodes[callee_id]["name"])


            out["Info"].update({
                "Parameter": meta.get("parameters", []),
                "IsMethodof": meta.get("parent_class"),
                "calls": call_names
            })

        elif node_type == "variable":
            meta = data["metadata"]
            used_by = set(meta.get("accessed_by", []) + meta.get("modified_by", []))
            calls = []
            for used_id in used_by:
                if used_id in G.nodes:
                    used_node = G.nodes[used_id]
                    if used_node["type"] == "function":
                        func_name = used_node["name"]
                        parent_cls = used_node["metadata"].get("parent_class", None)
                        if parent_cls:
                            calls.append(parent_cls)
                        calls.append(func_name)
                    elif used_node["type"] == "class":
                        calls.append(used_node["name"])
                    else:
                        calls.append(used_node["name"])
            out["Info"].update({"calls": list(set(calls))})

        # **Step 3: Extract Code Snippet**
        # Only add code snippets for node types other than "file" and "class"
        if node_type not in ["file", "class"]:
            file_path = os.path.join(code_graph.root, data["relative_path"])
            lines = file_contents_cache.get(file_path, [])
            start = max(data["line_range"][0] - 1, 0)  # Convert to 0-based index
            end = data["line_range"][1]  # Exclusive in slicing
            # Ensure end does not exceed the number of lines
            end = min(end, len(lines))
            code_snippet = ''.join(lines[start:end]).strip()
            out["Info"]["code"] = code_snippet

        final_nodes.append(out)

    # Write out as one JSON array
    tags_json_path = os.path.join(os.getcwd(), "tags.json")
    with open(tags_json_path, "w", encoding="utf-8") as f:
        json.dump(final_nodes, f, indent=2)

    # Also cache the graph if needed
    graph_pkl_path = os.path.join(os.getcwd(), "graph.pkl")
    with open(graph_pkl_path, 'wb') as f:
        pickle.dump(G, f)

    print(f"Successfully wrote updated metadata to {tags_json_path}")
