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
        
        repo_folder_path = None
        diffs = []
        
        # Determine mode: local, commit, or PR
        if files_content and supplied_diff:
            # Local mode
            print("--- Preprocessing: Local Mode ---")
            if not isinstance(files_content, dict):
                raise ValueError("For local mode, 'files' must be a dictionary of path:content.")
            if not isinstance(supplied_diff, str):
                 raise ValueError("For local mode, 'diff_str' must be a string of formatted diffs.")
            
            repo_folder_path = setup_local_repo_from_files(files_content)
            diffs = DiffFormatter(supplied_diff).parse_and_format() # Assumes diff_list is in the format expected by DiffFormatter

        elif commit_hash and user and repo:
            # Commit mode
            print(f"--- Preprocessing: Commit Mode (commit: {commit_hash}) ---")
            
            # Dynamically fetch the default branch
            try:
                default_branch_to_clone = get_repo_default_branch(user, repo, user_github_token)
                print(f"Determined default branch for {user}/{repo}: {default_branch_to_clone}")
            except Exception as e:
                print(f"Error fetching default branch for {user}/{repo}: {e}. Falling back to 'main'.")
                # Fallback or re-raise, depending on desired strictness
                default_branch_to_clone = "main" # Or raise ValueError("Could not determine default branch and no fallback.")

            repo_folder_path = clone_repo(user, repo, default_branch_to_clone, user_github_token, commit_hash=commit_hash)
            
            diffs = get_commit_diff(user, repo, commit_hash, user_github_token)
            metadata_user = user
            metadata_branch = f"commit-{commit_hash[:7]}"


        elif pr_id and user and repo:
            # PR mode
            print(f"--- Preprocessing: PR Mode (PR: {pr_id}) ---")
            # Pass user_github_token to these functions
            diffs = get_pr_diff(user, repo, pr_id, user_github_token=user_github_token)
            metadata = get_pr_metadata(user, repo, pr_id, user_github_token=user_github_token)
            metadata_branch = metadata["head"]["ref"]
            metadata_user = metadata["head"]["user"] # This is GitHub user from PR head
            # Clone repo (pass user_github_token)
            repo_folder_path = clone_repo(metadata_user, repo, metadata_branch, user_github_token=user_github_token)
        else:
            raise ValueError("Insufficient information for preprocessing. Provide PR details, commit details, or local files+diffs.")

        if not repo_folder_path or not os.path.exists(repo_folder_path):
             raise ValueError(f"Repository folder path not established or does not exist: {repo_folder_path}")

        # Generate graph (common for all modes with a repo_folder_path)
        # Ensure graph_folder_path is unique for each run type
        mode_identifier = "local"
        if pr_id: mode_identifier = f"pr-{pr_id}"
        elif commit_hash: mode_identifier = f"commit-{commit_hash[:7]}"
        
        graph_repo_id = repo if repo else "local" # Handle case where repo might be None for local
        graph_folder_path = os.path.join(".", "tmp", "graph", f"{graph_repo_id}-{mode_identifier}-{uuid.uuid4()}")
        
        G = generate_code_graph(repo_folder_path)
        print_graph_info(G, repo_folder_path)
        save_graph(graph_folder_path, G)

        # Initialize tools with the graph folder path
        self.tools = toolOrganizer(G,graph_folder_path)

        # Update state with computed values
        state["user_github_token"] = "" # user github token is not used in the pipeline after this, so should be empty so that it won't get exposed later
        state["files"] = ""  # Reset files as they are not used after preprocessing
        state["diff_str"] = "" # Reset diff_str as it is not used after preprocessing
        state["diffs"] = diffs
        state["current_diff"] = None
        state["current_review"] = {"syntax": [], "standards": [], "error_analysis": []}
        state["reviews"] = {}
        state["repo_folder_path"] = repo_folder_path
        state["fixes"] = []
        state["max_tool_calls"] = state.get("max_tool_calls", 3)
        state["messages"] = [f"Preprocessed PR {pr_id} for {user}/{repo}"]
        
        self.original_diffs = diffs.copy()  # Store original diffs
        return state
    def repo_summary_node(self, state: CodeReviewState):
        repo_folder_path = state.get("repo_folder_path")  # Set in preprocess or code clone step
        summarizer = RepoSummarizerAgent(self.llm)
        repo_summary = summarizer.summarize_repository(repo_folder_path)
        state["repo_summary"] = repo_summary
        return state
    def start_node(self, state: CodeReviewState):
        if state["diffs"]:
            state["current_diff"] = state["diffs"].pop(0)
        return state

    def _build_graph(self):
        builder = StateGraph(CodeReviewState)
        
        # Add preprocessing node as entry point
        builder.add_node("preprocess", self.preprocess)
        # Add repo summary node
        builder.add_node("repoSummary", self.repo_summary_node)
        # Use the start_node that assigns current_diff before continuing.
        builder.add_node("start", self.start_node)
        
        # Group 1: Run syntax_check, standard_check, and error_analysis in parallel
        builder.add_node("syntax_check", self.run_syntax_check)
        builder.add_node("standard_check", self.run_standard_check)
        builder.add_node("error_analysis", self.run_error_analysis)
        # Create join node for Group 1
        builder.add_node("merge_1", lambda state: state)
        builder.add_edge("preprocess", "repoSummary")
        builder.add_edge("repoSummary", "start")
        builder.add_edge("start", "syntax_check")
        builder.add_edge("start", "standard_check")
        builder.add_edge("start", "error_analysis")
        builder.add_edge(["syntax_check", "standard_check", "error_analysis"], "merge_1")
        
        # Group 2: Run generate_fix and generate_review in parallel
        builder.add_node("generate_fix", self.generate_fix)
        builder.add_node("generate_review", self.generate_review)

        builder.add_edge("merge_1", "generate_review")
        builder.add_edge("generate_review", "generate_fix")
        
        # Conditional step: loop if diffs remain, else generate summary.
        builder.add_conditional_edges("generate_fix", self.should_continue,
                                    {"continue": "restart", END: "final_summary"})
        builder.add_node("restart", lambda state: state)
        builder.add_edge("restart", "start")
        builder.add_node("final_summary", self.generate_summary)
        
        builder.set_entry_point("preprocess")
        return builder.compile()

    def run_syntax_check(self, state: CodeReviewState):
        syntax_checker = SyntaxCheckerAgent(self.llm)
        # Use the current_diff already set by start_node.
        result = syntax_checker.analyze(state["current_diff"])
        state["current_review"]["syntax"] = [result]
        if "syntax" not in state["reviews"]:
            state["reviews"]["syntax"] = []
        state["reviews"]["syntax"].append(result)
        return state

    def run_standard_check(self, state: CodeReviewState):
        standard_checker = StandardCheckerAgent(self.llm, self.standards)
        result = standard_checker.check_compliance(state["current_diff"])
        state["current_review"]["standards"] = [result]
        if "standards" not in state["reviews"]:
            state["reviews"]["standards"] = []
        state["reviews"]["standards"].append(result)
        return state

    def run_error_analysis(self, state: CodeReviewState):
        error_agent = ErrorAnalysisAgent(self.llm, self.tools, max_tool_calls=state["max_tool_calls"])
        result = error_agent.graph.invoke({
            "messages": [],
            "issues":[],
            "current_diff": state["current_diff"],
            "total_tool_calls" : 0,
            "repo_summary": state["repo_summary"],
            "bug_state":{"issues": [], "tool_calls_made": [], "tool_call_count": 0},
            "vuln_state":{"issues": [], "tool_calls_made": [], "tool_call_count": 0},
        })
        state["current_review"]["error_analysis"] = [
            {
                "messages": result["messages"],
                "issues": result["issues"],
                "current_diff": state["current_diff"],
                "total_tool_calls": result["total_tool_calls"],
            }
        ]
        if "error_analysis" not in state["reviews"]:
            state["reviews"]["error_analysis"] = []
        state["reviews"]["error_analysis"].append({
                "messages": result["messages"],
                "issues": result["issues"],
                "current_diff": state["current_diff"],
                "total_tool_calls": result["total_tool_calls"],
                "tool_calls": result["bug_state"]["tool_calls_made"] + result["vuln_state"]["tool_calls_made"]
            })
        return state

    def generate_fix(self, state: CodeReviewState):
        fix_agent = CodeFixAgent(self.llm)
        fix = fix_agent.generate_fix(state["current_diff"], state["current_review"], state["repo_summary"])
        state["fixes"].append(fix)
        return state

    def generate_review(self, state: CodeReviewState):
        reviewer = CodeReviewerAgent(self.llm, self.metrics)
        review = reviewer.generate_review(state["current_review"],state["repo_summary"])
        if "final" not in state["reviews"]:
            state["reviews"]["final"] = []
        state["reviews"]["final"].append(*review)
        return state

    def generate_summary(self, state: CodeReviewState):
        summarizer = CodeSummarizerAgent(self.llm)
        summary = summarizer.summarize_pr(self.original_diffs)
        unique_id = str(uuid.uuid4())
        self.memory.save_review(unique_id, {
            "review": state["reviews"],
            "fixes": state["fixes"],
            "summary": summary
        })
        # self.memory.save_to_file(state["pr_id"])
        result = self.memory.get_pr_state(unique_id)
        return {"final_result": result}

    def should_continue(self, state: CodeReviewState):
        if len(state["diffs"]) > 0:
            return "continue"
        return END

# Initialize pipeline without tools initially (computed in preprocess)
pipeline = ParallelReviewPipeline()
graph = pipeline.graph


# Usage
# user = "Sourcery-ai-experiments"
# repo = "atari-rl"
# PR_ID = 1
# # Initialize the callback handler
# callback_handler = OpenAICallbackHandler()
# # Invoke with minimal input
# result = pipeline.graph.invoke({
#     "user": user,
#     "repo": repo,
#     "pr_id": PR_ID,
#     "llm_model": Config.LLM_MODEL_NAME,
#     "standards": Config.CODING_STANDARDS,
#     "metrics": Config.REVIEW_METRICS,
#     "temperature": Config.TEMPERATURE,
#     "max_tokens": Config.MAX_TOKENS,
#     "max_tool_calls": 5
# }, {"recursion_limit": 99999999,"callbacks":[callback_handler]})

# # Access and print the token usage information
# print(f"Total Tokens Used: {callback_handler.total_tokens}")
# print(f"Prompt Tokens: {callback_handler.prompt_tokens}")
# print(f"Completion Tokens: {callback_handler.completion_tokens}")
# print(f"Reasoning Tokens: {callback_handler.reasoning_tokens}")
# print(f"Successful Requests: {callback_handler.successful_requests}")
# print(f"Total Cost (USD): ${callback_handler.total_cost}")

