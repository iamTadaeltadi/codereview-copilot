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
        parser.set_language(LANGUAGE_MAP[file_extension])
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
