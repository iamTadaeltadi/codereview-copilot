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
            model=model_name,
            openai_api_base=api_base_url,
            temperature=state["temperature"],
            max_tokens=state["max_tokens"]
        )
        self.standards = state["standards"]
        self.metrics = state["metrics"]
        
        # Fetch PR diffs and metadata
        diffs = get_pr_diff(user, repo, pr_id, "thought", {"headers": ""})
        metadata = get_pr_metadata(user, repo, pr_id, "thought", {"headers": ""})
        branch = metadata["head"]["ref"]
        user = metadata["head"]["user"]

        # Clone repo and generate graph
        repo_folder_path = clone_repo(user, repo, branch)
        graph_folder_path = os.path.join(".", "tmp", "graph", f"{repo}-{branch}-{uuid.uuid4()}")
        G = generate_code_graph(repo_folder_path)
        print_graph_info(G, repo_folder_path)
        save_graph(graph_folder_path, G)

        # Initialize tools with the graph folder path
        self.tools = toolOrganizer(G,graph_folder_path)

        # Update state with computed values
        state["diffs"] = diffs
        state["current_diff"] = None
        state["current_review"] = {"syntax": [], "standards": [], "error_analysis": []}
        state["reviews"] = {}
        state["repo_folder_path"] = repo_folder_path
        state["fixes"] = []
        state["max_tool_calls"] = state.get("max_tool_calls",3)  # Default value, configurable if needed
        state["messages"] = [f"Preprocessed PR {pr_id} for {user}/{repo}"]
        
        self.original_diffs = diffs.copy()  # Store original diffs
        return state
    def repo_summary_node(self, state: CodeReviewState):
        repo_folder_path = state.get("repo_folder_path")  # Set in preprocess or code clone step
        summarizer = RepoSummarizerAgent(self.llm)
        repo_summary = summarizer.summarize_repository(repo_folder_path)
        state["repo_summary"] = repo_summary
        return state
    def _build_graph(self):
        builder = StateGraph(CodeReviewState)

        # Add preprocessing node as entry point
        builder.add_node("preprocess", self.preprocess)
        # Add repo summary node
        builder.add_node("repoSummary", self.repo_summary_node)
        
        # Add nodes
        builder.add_node("syntax_check", self.run_syntax_check)
        builder.add_node("standard_check", self.run_standard_check)
        builder.add_node("error_analysis", self.run_error_analysis)
        builder.add_node("generate_fix", self.generate_fix)
        builder.add_node("generate_review", self.generate_review)
        builder.add_node("final_summary", self.generate_summary)

        # Main flow
        builder.add_edge("preprocess", "repoSummary")
        builder.add_edge("repoSummary", "syntax_check")
