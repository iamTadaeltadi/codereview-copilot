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
        if self._needs_setup(state):
            updates.update(self._setup_repository(state))
        else:
            if self.tools is None and state.get("graph_folder_path"):
                with open(os.path.join(state["graph_folder_path"], 'graph.pkl'), 'rb') as f:
                    G = pickle.load(f)
                self.tools = toolOrganizer(G, state["graph_folder_path"])
                updates.update(self._log_action("preprocess", {"status": "Skipped setup, tools checked/re-initialized"}))
        
        # Reset review state
        updates.update(self._reset_review_state())
        return updates

    def _initialize_state(self, state: FeedbackState) -> dict:
        if state.get("action_log") is None:
            return self._log_action("preprocess", {"status": "Initializing thread state"})
        return {}

    def _needs_setup(self, state: FeedbackState) -> bool:
        repo_folder_path = state.get("repo_folder_path")
        graph_folder_path = state.get("graph_folder_path")
        return not (repo_folder_path and os.path.exists(repo_folder_path) and 
                   graph_folder_path and os.path.exists(graph_folder_path))

    def _setup_repository(self, state: FeedbackState) -> dict:
        updates = {}
        user = state["user"]
        repo = state["repo"]
        pr_id = state["pr_id"]
        commit_hash = state.get("commit_hash")
        files_json_string = state.get("files")
        if not files_json_string:  # Handles if files_json_string is None or an empty string ""
            files_json_string = "{}" # Default to an empty JSON object string
        files_content = json.loads(files_json_string)
        supplied_diff = state.get("diff_str","")
        user_github_token = state.get("user_github_token")
        
        repo_folder_path = None
        diffs_data = [] # This will hold the formatted diffs list
        
        # Determine mode: local, commit, or PR
        if files_content and supplied_diff:
            # Local mode
            print("--- Preprocessing: Local Mode ---")
            if not isinstance(files_content, dict):
                raise ValueError("For local mode, 'files' must be a dictionary of path:content.")
            if not isinstance(supplied_diff, str):
                 raise ValueError("For local mode, 'diff_str' must be a string of formatted diffs.")
            repo_folder_path = setup_local_repo_from_files(files_content)
            diffs_data = DiffFormatter(supplied_diff).parse_and_format()

        elif commit_hash and user and repo:
            print(f"--- Feedback Setup: Commit Mode (commit: {commit_hash}) ---")

             # Dynamically fetch the default branch
            try:
                default_branch_to_clone = get_repo_default_branch(user, repo, user_github_token)
                print(f"Determined default branch for {user}/{repo}: {default_branch_to_clone}")
            except Exception as e:
                print(f"Error fetching default branch for {user}/{repo}: {e}. Falling back to 'main'.")
                # Fallback or re-raise, depending on desired strictness
                default_branch_to_clone = "main" # Or raise ValueError("Could not determine default branch and no fallback.")
            
            repo_folder_path = clone_repo(user, repo, default_branch_to_clone, user_github_token, commit_hash=commit_hash)
            
            diffs_data = get_commit_diff(user, repo, commit_hash, user_github_token)
            metadata_user_for_clone = user # For potential future use, not directly for clone_repo here
            branch_for_clone_or_checkout = f"commit-{commit_hash[:7]}"


        elif pr_id and user and repo:
            print(f"--- Feedback Setup: PR Mode (PR: {pr_id}) ---")
            # Pass user_github_token
            metadata = get_pr_metadata(user, repo, pr_id, user_github_token=user_github_token)
            branch_for_clone_or_checkout = metadata["head"]["ref"]
            metadata_user_for_clone = metadata["head"]["user"]
            
            repo_folder_path = clone_repo(metadata_user_for_clone, repo, branch_for_clone_or_checkout, user_github_token=user_github_token)
            diffs_data = get_pr_diff(user, repo, pr_id, user_github_token=user_github_token)
        else:
            raise ValueError("Insufficient information for repository setup. Provide PR, commit, or local files+diffs.")

        if not repo_folder_path or not os.path.exists(repo_folder_path):
             raise ValueError(f"Repository folder path not established or does not exist: {repo_folder_path}")

        # Generate and save code graph (common logic)
        # Ensure graph_folder_path is unique
        mode_identifier = "local"
        graph_repo_id = repo if repo else "local_project"
        if pr_id: mode_identifier = f"pr-{pr_id}"
        elif commit_hash: mode_identifier = f"commit-{commit_hash[:7]}"

        G = generate_code_graph(repo_folder_path)
        # graph_folder_path needs to be unique and stored in state if _needs_setup is false later
        # The original logic used repo-branch-uuid. Let's try to stick to that pattern.
        graph_folder_path_name_part = branch_for_clone_or_checkout if branch_for_clone_or_checkout else mode_identifier
        graph_folder_path = os.path.join(".", "tmp", "graph", f"{graph_repo_id}-{graph_folder_path_name_part}-{uuid.uuid4()}")
        
        print_graph_info(G, repo_folder_path)
        save_graph(graph_folder_path, G)
        
        # Initialize tools and get repo summary
        self.tools = toolOrganizer(G, graph_folder_path)
        summarizer = RepoSummarizerAgent(self.llm)
        repo_summary = summarizer.summarize_repository(repo_folder_path)
        
        # Get PR diffs
        diffs = diffs_data
        diff_map = {diff["file_path"]: (i, diff) for i, diff in enumerate(diffs)}
        
        updates.update({
            "user_github_token": "", # user github token is not used in the pipeline after this, so should be empty so that it won't get exposed later 
            "files": "", # files are not used after this, so should be empty so that it won't get exposed later
            "diff_str": "", # diff_str is not used after this, so should be empty so that it won't get exposed later
            "repo_folder_path": repo_folder_path,
            "graph_folder_path": graph_folder_path,
            "repo_summary": repo_summary,
            "diff_map": diff_map,
            "reviews": {
                "syntax": [None] * len(diffs),
                "standards": [None] * len(diffs),
                "error_analysis": [None] * len(diffs),
                "final": [None] * len(diffs)
            },
            "fixes": [None] * len(diffs)
        })
        
        return updates

    def _initialize_llm(self, state: FeedbackState) -> dict:
        provider, model_name = state["llm_model"].split("::")
        provider_map = {
            "HYPERBOLIC": Config.HYPERBOLIC,
            "CEREBRAS": Config.CEREBRAS,
            "OPENROUTER": Config.OPENROUTER
        }
        selected_config = provider_map.get(provider, Config.CEREBRAS)
        
        self.llm = CustomLLM(
            openai_api_key=selected_config["api_key"],
            model=model_name,
            openai_api_base=selected_config["api_base_url"],
            temperature=state["temperature"],
            max_tokens=state["max_tokens"]
        )
        self.standards = state["standards"]
        self.metrics = state["metrics"]
        
        return {}

    def _reset_review_state(self) -> dict:
        return {
            "re_run_plan": None,
            "instructions": None,
            "feedback_status": None,
            "feedback_explanation": None,
            "feedback_suggestion": None,
            "sufficiency": None,
            "sufficiency_explanation": None,
            "sufficiency_suggestion": None,
        }

    @with_error_handling(default_value={"sufficiency": "insufficient", "sufficiency_explanation": "Error during check", "sufficiency_suggestion": "Please try again"})
    def sufficiency_checker(self, state: FeedbackState):
        print("--- Running Sufficiency Checker ---")
        feedback = state["feedback"]
        current_review = state.get("updated_review", state.get("original_review", {}))
        
        config = self._get_episodic_config(state)
        episodic_query = f"Feedback and actions for thread {state['thread_id']} in {state['repo']}"
        episodic_results = self.episodic_search_tool.invoke(
            {"query": episodic_query},
            config=config
        )
        episodic_context = episodic_results if episodic_results else []
        episodic_context = json.loads(episodic_context)
        
        sufficiency_checker = SufficiencyCheckerAgent(self.llm)
        result = sufficiency_checker.sufficiency_checker(
            feedback=feedback,
            original_review=current_review,
            episodic_context="\n".join([episode.get('value', {}).get('content', '') for episode in episodic_context])
        )
        
        updates = {}
        if result:
            updates["sufficiency"] = result.get("classification", "insufficient")
            updates["sufficiency_explanation"] = result.get("explanation", "No explanation provided.")
            updates["sufficiency_suggestion"] = result.get("suggestion", "")
        else:
            updates["sufficiency"] = "insufficient"
            updates["sufficiency_explanation"] = "Failed to parse sufficiency response."
            updates["sufficiency_suggestion"] = "Include specific files or issues to address."
        
        updates.update(self._log_action("sufficiency_checker", {
            "status": updates["sufficiency"],
            "feedback_snippet": feedback[:50]
        }))
        return updates

    @with_error_handling(default_value={"instructions": {}})
    def instruction_generator(self, state: FeedbackState):
        print("--- Running Instruction Generator ---")
        re_run_plan = state.get("re_run_plan", {})
        feedback = state.get("feedback")
        current_review = state.get("updated_review", state.get("original_review", {}))

        # Retrieve relevant episodic memory
        episodic_config = self._get_episodic_config(state)
        episodic_query = f"Previous review actions and feedback for PR {state['pr_id']} in thread {state['thread_id']}"
        episodic_results = self.episodic_search_tool.invoke(
            {"query": episodic_query, "limit": 5},
            config=episodic_config
        )
        episodic_context = episodic_results if episodic_results else []
        episodic_context = json.loads(episodic_context)
        
        # Extract relevant context from episodic memory
        episodic_summary = self._process_episodic_memory(episodic_context)

        # Retrieve analyzed preferences
        ltm_config = self._get_ltm_config(state)
        preferences = self.long_term_search_tool.invoke(
            {"query": "user preferences and review style", "limit": 10},
            config=ltm_config
        )
        
        # Prepare preference context
        preference_context = self._process_preferences(json.loads(preferences))
        
        rereview_instruction_generator = ReReviewInstructionGeneratorAgent(self.llm)
        instructions = rereview_instruction_generator.re_review_instruction_generator(
            re_run_plan=re_run_plan,
            feedback=feedback,
            original_review=current_review,
