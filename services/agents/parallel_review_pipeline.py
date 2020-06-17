from langgraph.graph import StateGraph, END
from typing import Dict, List, Optional, TypedDict, Annotated
from Agents import CodeFixAgent,CodeReviewerAgent,\
    CodeSummarizerAgent,ErrorAnalysisAgent,RepoSummarizerAgent,\
        StandardCheckerAgent,SyntaxCheckerAgent
from Memory import MemoryManager
from Utils import get_pr_diff, get_pr_metadata,\
                clone_repo, generate_code_graph,\
                get_commit_diff, get_commit_metadata, \
                print_graph_info, save_graph, toolOrganizer, \
                setup_local_repo_from_files, DiffFormatter, get_repo_default_branch
from config import Config
from LLM import CustomLLM
from langchain_community.callbacks.openai_info import OpenAICallbackHandler
from langchain_core.runnables import RunnableConfig
import uuid
import os
import json
class CodeReviewState(TypedDict):
    messages: Annotated[list, lambda old, new: new]
    pr_id: Annotated[str, lambda old, new: new]
    user: Annotated[str, lambda old, new: new]
    repo: Annotated[str, lambda old, new: new]
    llm_model: Annotated[str, lambda old, new: new]
    standards: Annotated[list, lambda old, new: new]
    metrics: Annotated[list, lambda old, new: new]
    temperature: Annotated[float, lambda old, new: new]
    max_tokens: Annotated[int, lambda old, new: new]
    diffs: Annotated[list, lambda old, new: new]
    current_diff: Annotated[dict, lambda old, new: new]
    current_review: Annotated[dict, lambda old, new: new] 
    reviews: Annotated[dict, lambda old, new: new]
    repo_folder_path: Annotated[str, lambda old, new: new]
    repo_summary: Annotated[dict, lambda old, new: new]
    fixes: Annotated[list, lambda old, new: new]
    max_tool_calls: Annotated[int, lambda old, new: new]
    final_result: Annotated[dict, lambda old, new: new]
    # New fields To handle commits and files
    commit_hash: Annotated[Optional[str], lambda old, new: new]
    files: Annotated[Optional[str], lambda old, new: new]="{}" # file_path: content dict passed as JSON string
    diff_str: Annotated[Optional[str], lambda old, new: new]="" # str of diff text coming from VScode extension
    user_github_token: Annotated[Optional[str], lambda old, new: new]
class ParallelReviewPipeline:
    def __init__(self):
        self.memory = MemoryManager()
        self.original_diffs = None
        self.graph = self._build_graph()
    def preprocess(self, state: CodeReviewState,config:RunnableConfig):
        """Handle all preprocessing to initialize the state."""
        user = state["user"]
        repo = state["repo"]
        pr_id = state["pr_id"]
        commit_hash = state.get("commit_hash")
        files_content = json.loads(state.get("files","{}"))
        # files_content = json.loads(config.get("configurable").get("files"))  # Expecting a dictionary of file paths and their content
        supplied_diff = state.get("diff_str","")
        user_github_token = state.get("user_github_token")
        
        # Initialize LLM,standards and metrics
        provider, model_name = state["llm_model"].split("::")

        provider_map = {
            "HYPERBOLIC": Config.HYPERBOLIC,
            "CEREBRAS": Config.CEREBRAS,
            "OPENROUTER": Config.OPENROUTER
        }
