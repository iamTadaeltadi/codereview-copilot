import os
from tree_sitter import Language, Parser

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
    else:
        # If language not available, skip parsing
        return False
    return True

def create_structure(directory_path):
    """
    Create a nested dictionary structure representing the repository.
    This function is optional and used by CodeGraph to gather top-level info.
    """
    structure = {}

    for root, dirs, files in os.walk(directory_path):
        relative_root = os.path.relpath(root, directory_path)
        curr_struct = structure

        # At the top-level directory
        if relative_root == ".":
            for file_name in files:
                file_extension = os.path.splitext(file_name)[1]
                if file_extension in LANGUAGE_MAP and LANGUAGE_MAP[file_extension] is not None:
                    file_path = os.path.join(root, file_name)
                    file_info = parse_file(file_path, file_extension)
                    try:
                        size = os.path.getsize(file_path)
                        created_at = os.path.getctime(file_path)
                        updated_at = os.path.getmtime(file_path)
                    except Exception as e:
                        print(f"Error getting metadata for {file_path}: {e}")
                        size = 0
                        created_at = 0
                        updated_at = 0

                    structure[file_name] = {
                        "file_info": file_info,
                        "metadata": {
                            "type": "file",
                            "path": os.path.relpath(file_path, directory_path),
                            "name": file_name,
                            "range": [1, 1],
                            "metadata": {
                                "size": size,
                                "language": file_extension[1:],
                                "created_at": created_at,
                                "updated_at": updated_at,
                                "dependencies": []
                            }
                        }
                    }
            # Proceed to the next iteration for subdirectories
            continue

        # Build a nested structure for subdirectories
        for part in relative_root.split(os.sep):
            if part not in curr_struct:
                curr_struct[part] = {}
            curr_struct = curr_struct[part]

        # Handle files in subdirectories
        for file_name in files:
            file_extension = os.path.splitext(file_name)[1]
            if file_extension in LANGUAGE_MAP and LANGUAGE_MAP[file_extension] is not None:
                file_path = os.path.join(root, file_name)
                file_info = parse_file(file_path, file_extension)
                try:
                    size = os.path.getsize(file_path)
                    created_at = os.path.getctime(file_path)
                    updated_at = os.path.getmtime(file_path)
                except Exception as e:
                    print(f"Error getting metadata for {file_path}: {e}")
                    size = 0
                    created_at = 0
                    updated_at = 0


                curr_struct[file_name] = {
                    "file_info": file_info,
                    "metadata": {
                        "type": "file",
                        "path": os.path.relpath(file_path, directory_path),
                        "name": file_name,
                        "range": [1, 1],
                        "metadata": {
                            "size": size,
                            "language": file_extension[1:],
                            "created_at": created_at,
                            "updated_at": updated_at,
                            "dependencies": []
                        }
                    }
                }
            else:
                curr_struct[file_name] = {}

        # If there are empty dirs, we simply keep them in the structure
        for dir_name in dirs:
            if dir_name not in curr_struct:
                curr_struct[dir_name] = {}

    return structure

def parse_file(file_path, file_extension):
    """Parse a file to extract high-level definitions (classes, functions)."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            file_content = file.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return {}

    # Check if language is available
    if not set_language_for_file(file_extension):
        print(f"Skipping parsing for {file_path}: language not available")
        return {"classes": [], "functions": []}

    tree = parser.parse(bytes(file_content, "utf-8"))
    root_node = tree.root_node

    if file_extension == ".py":
        return parse_python_like_file(root_node)
    elif file_extension == ".js":
        return parse_javascript_like_file(root_node)
    elif file_extension == ".java":
        return parse_java_like_file(root_node)
    elif file_extension == ".c":
        return parse_c_file(root_node)

    return {"classes": [], "functions": []}

def parse_python_like_file(root_node):
    """Parse Python-like files for classes and functions."""
    return extract_definitions(root_node, ["class_definition", "function_definition"])

def parse_javascript_like_file(root_node):
    """Parse JavaScript-like files for classes and functions."""
    return extract_definitions(root_node, ["class", "function"])

def parse_java_like_file(root_node):
    """Parse Java-like files for classes and methods."""
    return extract_definitions(root_node, ["class_declaration", "method_declaration"])

def parse_c_file(root_node):
    """Parse C files for function definitions."""
    return extract_definitions(root_node, ["function_definition"])

def extract_definitions(node, definition_types):
    """Extract class and function/method definitions from the syntax tree."""
    classes = []
    functions = []

    for child in node.children:
        if child.type in definition_types:
            name_node = next((c for c in child.children if c.type == "identifier"), None)
            name = name_node.text.decode("utf-8") if name_node else "unknown"
            start_line, end_line = child.start_point[0] + 1, child.end_point[0] + 1

            if child.type in ["class", "class_definition", "class_declaration"]:
                classes.append({
                    "name": name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "methods": extract_definitions(child, ["method_definition", "method_declaration"])["functions"],
                })
            elif child.type in ["function", "function_definition", "method_declaration"]:
                functions.append({
                    "name": name,
                    "start_line": start_line,
                    "end_line": end_line,
                })

        extracted = extract_definitions(child, definition_types)
        classes.extend(extracted.get("classes", []))
        functions.extend(extracted.get("functions", []))

    return {
        "classes": classes,
        "functions": functions
    }
