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
            # self.store = PostgresStore(self.pool_store)
            # self.store.setup()
            # print("PostgresSaver initialized.")
            self.memory = MemorySaver()
            self.store = InMemoryStore()
        except Exception as e:
            print(f"FATAL: Failed to initialize PostgreSQL checkpointer: {e}")
            raise
        # Initialize LangMem tools with namespaces
        self._initialize_memory_tools()
        self.graph_app = self._build_graph()
    def _initialize_memory_tools(self):
        self.episodic_manage_tool = create_manage_memory_tool(
            namespace=("episodic","{thread_id}"),
            store=self.store
        )
        self.episodic_search_tool = create_search_memory_tool(
            namespace=("episodic","{thread_id}"),
            store=self.store
        )
        self.long_term_search_tool = create_search_memory_tool(
            namespace=("long_term","{reviewer_id}","{user}","{repo}"),
            store=self.store
        )
        self.long_term_manage_tool = create_manage_memory_tool(
            namespace=("long_term","{reviewer_id}","{user}","{repo}"),
            store=self.store
    )
    def _get_ltm_config(self, state: FeedbackState) -> dict:
        return {
            "configurable": {
                "reviewer_id": state["reviewer_id"],
                "user": state["user"],
                "repo": state["repo"]
            }
        }
    def _get_episodic_config(self, state: FeedbackState) -> dict:
        return {
            "configurable": {
                "thread_id": state["thread_id"]
            }
        }
    def close_pools(self):
        closed_any = False
        if hasattr(self, 'pool_checkpoint') and self.pool_checkpoint:
            print("Closing PostgreSQL connection pool for Checkpointer.")
            self.pool_checkpoint.close()
            closed_any = True
        if hasattr(self, 'pool_store') and self.pool_store:
            print("Closing PostgreSQL connection pool for Key-Value Store.")
            self.pool_store.close()
            closed_any = True
        if not closed_any:
            print("No connection pools were found to close.")

    def _build_graph(self):
        builder = StateGraph(FeedbackState)
        builder.add_node("preprocess", self.preprocess)
        builder.add_node("guardrail_checker", self.guardrail_checker)
        builder.add_node("sufficiency_checker", self.sufficiency_checker)
        builder.add_node("plan_generator", self.plan_generator)
        builder.add_node("instruction_generator", self.instruction_generator)
        builder.add_node("dynamic_review_executor", self.dynamic_review_executor)
        builder.add_node("review_integrator", self.review_integrator)
        builder.add_node("chat_responder", self.chat_responder)
        builder.add_node("log_memory", self.log_memory)
        builder.set_entry_point("preprocess")
        builder.add_edge("preprocess", "guardrail_checker")
        builder.add_conditional_edges(
            "guardrail_checker",
            self.route_after_guardrail,
            {"chat_responder": "chat_responder", "sufficiency_checker": "sufficiency_checker"}
        )
        builder.add_conditional_edges(
            "sufficiency_checker",
            self.route_after_sufficiency,
            {"chat_responder": "chat_responder", "plan_generator": "plan_generator"}
        )
        builder.add_edge("plan_generator", "instruction_generator")
        builder.add_edge("instruction_generator", "dynamic_review_executor")
        builder.add_edge("dynamic_review_executor", "review_integrator")
        builder.add_edge("review_integrator", "chat_responder")
        builder.add_edge("chat_responder", "log_memory")
        builder.add_edge("log_memory", END)
        return builder.compile(checkpointer=self.memory,store=self.store)
    def _log_action(self, node_name: str, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to create a standardized log entry."""
        return {
            "action_log": [{
                "node": node_name,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                **summary
            }]
        }
     # Helper methods to process memory data
    def _process_episodic_memory(self, episodic_context: List[dict]) -> List[str]:
        episodic_summary = []
        for memory in episodic_context:
            memory = memory.get("value",{})
            if "content" in memory:
                try:
                    content = json.loads(memory.get("content",{}))
                    if "feedback_received" in content:
                        episodic_summary.append(f"Previous feedback: {content['feedback_received']}")
                    if "ai_response_snippet" in content:
                        episodic_summary.append(f"Previous response: {content['ai_response_snippet']}")
                except json.JSONDecodeError:
                    continue
        return episodic_summary

    def _process_preferences(self, preferences: List[dict]) -> List[str]:
        preference_context = []
        for pref in preferences:
            pref = pref.get("value",{})
            if "content" in pref:
                try:
                    content = json.loads(pref["content"])
                    if content.get("type") == "preference":
                        pref_data = json.loads(content["data"]) if isinstance(content["data"],str) else content["data"]
                        if pref_data["confidence"] > 0.7:  # Only use high-confidence preferences
                            preference_context.append(
                                f"User prefers {pref_data['preference']} "
                                f"(Category: {pref_data['category']}, "
                                f"Context: {pref_data['context']})"
                            )
                except json.JSONDecodeError:
                    continue
        return preference_context
    def with_error_handling(default_value: Any):
        def decorator(func):
            def wrapper(self, state: FeedbackState, *args, **kwargs):
                try:
                    return func(self, state, *args, **kwargs)
                except Exception as e:
                    import traceback
                    stack_trace = traceback.format_exc()
                    print(f"Error in {func.__name__}: {e}")
                    print(f"Stack trace:\n{stack_trace}")
                    updates = default_value
                    updates.update(self._log_action(func.__name__, {
                        "status": "error",
                        "error": str(e),
                        "stack_trace": stack_trace
                    }))
                    return updates
            return wrapper
        return decorator
    @with_error_handling(default_value={})
    def preprocess(self, state: FeedbackState):
        print("--- Running Preprocess ---")
        updates = {}
        
        # Initialize state
        updates.update(self._initialize_state(state))
        # Initialize LLM
        updates.update(self._initialize_llm(state))
        
        # Setup repository and tools if needed
