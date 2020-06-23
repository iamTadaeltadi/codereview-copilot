from langgraph.graph import StateGraph, END
from typing import TypedDict

from Agents import CodeFixAgent,CodeReviewerAgent,\
    CodeSummarizerAgent,ErrorAnalysisAgent,RepoSummarizerAgent,\
        StandardCheckerAgent,SyntaxCheckerAgent
from Memory import MemoryManager
from Utils import get_pr_diff, get_pr_metadata, clone_repo, generate_code_graph, print_graph_info, save_graph, toolOrganizer
from config import Config
from LLM import CustomLLM
from langchain_community.callbacks.openai_info import OpenAICallbackHandler
import uuid
import os
class CodeReviewState(TypedDict):
    messages: list
    pr_id: str
    user: str
    repo: str
    llm_model: str
    standards: list
    metrics: list
    temperature: float
    max_tokens: int
    diffs: list
    current_diff: dict
    current_review: dict 
    reviews: dict
    repo_folder_path: str
    repo_summary: dict
    fixes: list
    max_tool_calls: int

class ReviewPipeline:
    def __init__(self):
        self.memory = MemoryManager()
        self.original_diffs = None
        self.graph = self._build_graph()
    def preprocess(self, state: CodeReviewState):
        """Handle all preprocessing to initialize the state."""
        user = state["user"]
        repo = state["repo"]
        pr_id = state["pr_id"]
        
        """Handle all preprocessing to initialize the state."""
        user = state["user"]
        repo = state["repo"]
        pr_id = state["pr_id"]
        # Initialize LLM,standards and metrics
        provider, model_name = state["llm_model"].split("::")

        provider_map = {
            "HYPERBOLIC": Config.HYPERBOLIC,
            "CEREBRAS": Config.CEREBRAS,
            "OPENROUTER": Config.OPENROUTER
        }

        selected_config = provider_map.get(provider, Config.CEREBRAS)
        api_key = selected_config["api_key"]
        api_base_url = selected_config["api_base_url"]
        self.llm = CustomLLM(
            openai_api_key=api_key,
