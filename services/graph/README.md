# codecontext — repository graph construction and retrieval

`codecontext` parses a repository with tree-sitter, builds a directed graph of
files, classes, functions, and variables with networkx, and resolves a code
entity to its bounded neighbourhood in that graph.

## Provenance

This package is **derived from RepoGraph** (https://github.com/ozyyshr/RepoGraph,
Apache-2.0), described in *RepoGraph: Enhancing AI Software Engineering with
Repository-level Code Graph*, arXiv:2410.14684, ICLR 2025.

See the repository-root `NOTICE` file for the required attribution and for the
list of changes made to the upstream code. `retriever.py` is original to this
project; `construct_graph.py` and `utils.py` are adapted from upstream.

## Query format

    "relative/path/to/file.py::class::ClassName"
    "relative/path/to/file.py::function::function_name"
    "relative/path/to/file.py"

## Supported languages

`.py`, `.js`, `.java`, `.c`
