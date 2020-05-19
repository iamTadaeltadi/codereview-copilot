import datetime
import json
import os
import uuid
from typing import TypedDict, List, Tuple, Annotated, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.postgres import PostgresStore
from langgraph.store.memory import InMemoryStore
from psycopg_pool import ConnectionPool
from langgraph.graph.message import add_messages
from langmem import create_search_memory_tool, create_manage_memory_tool
from Agents import RepoSummarizerAgent, DynamicReviewExecutorAgent, GuardrailCheckerAgent, \
                   ReReviewPlannerAgent, ReReviewInstructionGeneratorAgent, SufficiencyCheckerAgent, \
                   LongTermMemoryAgent
from config import Config
from LLM import CustomLLM
from Utils import clone_repo, generate_code_graph,\
        print_graph_info, save_graph, toolOrganizer,\
        get_pr_diff, get_pr_metadata, setup_local_repo_from_files,\
        get_commit_diff, get_commit_metadata, DiffFormatter, get_repo_default_branch
import pickle


class FeedbackState(TypedDict):
    feedback: str
    original_review: dict
    updated_review: dict
    messages: Annotated[List[Tuple[str, str]], add_messages]
    re_run_plan: Optional[dict]
    instructions: Optional[dict]
    feedback_status: Optional[str]
    feedback_explanation: Optional[str]
    feedback_suggestion: Optional[str]
    sufficiency: Optional[str]
    sufficiency_explanation: Optional[str]
    sufficiency_suggestion: Optional[str]
    reviews: Optional[dict]
    fixes: Optional[List[str]]
    thread_id: str
    reviewer_id: str
    # original_diffs: list
    repo_summary: Optional[dict]
    llm_model: str
    user: str
    repo: str
    pr_id: str
    repo_folder_path: Optional[str]
    graph_folder_path: Optional[str]
    diff_map: Optional[dict]
    standards: List[str]
    metrics: List[str]
    temperature: float
    max_tokens: int
    max_tool_calls: int
    action_log: Annotated[Optional[List[Dict[str, Any]]], lambda x, y: (x or []) + (y or [])]  # Add this
    # New fields To handle commits and files
    commit_hash: Annotated[Optional[str], lambda old, new: new]
    files: Annotated[Optional[str], lambda old, new: new]="{}" # file_path: content dictionary passed as string
    diff_str: Annotated[Optional[str], lambda old, new: new]="" # str of diffs coming from VScode extension
    user_github_token: Annotated[Optional[str], lambda old, new: new]
class FeedbackPipeline:
    def __init__(self, checkpoint_db="postgresql://langgraph:langgraph@db:5432/memory",store_db="postgresql://langgraph:langgraph@db:5432/store"):
        self.llm = None
        self.tools = None
        self.standards = None
        self.metrics = None
        print(checkpoint_db, store_db)
        try:
            # self.pool_checkpoint = ConnectionPool(
            #     conninfo=checkpoint_db,
            #     min_size=2,
            #     max_size=20,
            #     kwargs={"autocommit": False, "prepare_threshold": 0}
            # )
            # self.memory = PostgresSaver(self.pool_checkpoint)
            # self.memory.setup()
            # self.pool_store = ConnectionPool(conninfo=store_db,min_size=2,max_size=20,kwargs={"autocommit": False, "prepare_threshold": 0})
