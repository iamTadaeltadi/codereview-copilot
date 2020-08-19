import logging
import time
from typing import Dict, Any, Optional
from django.conf import settings
from langgraph_sdk import get_client
from langsmith import Client
from ..models import User
logger = logging.getLogger(__name__)

class LangGraphClient:
    def __init__(self):
        self.client = get_client(url=settings.LANGGRAPH_API_URL)
        self.assistants = None
        self.review_agent = None
        self.feedback_agent = None

    async def initialize(self):
        """Initialize the client and get assistants"""
        try:
            # Ensure client is initialized (it is in __init__ if url is present)
            # self.assistants = await self.client.assistants.search() # No longer searching all
            
            # Fetch specific assistants by ID or name from settings
            # assistants = await self.client.assistants.search()
            self.review_agent = await self.client.assistants.get(settings.LANGGRAPH_REVIEW_ASSISTANT_ID)
            self.feedback_agent = await self.client.assistants.get(settings.LANGGRAPH_FEEDBACK_ASSISTANT_ID)
            self.langsmith_client = Client(api_key=settings.LANGSMITH_API_KEY)
            if not self.review_agent:
                logger.error(f"Review agent with ID '{settings.LANGGRAPH_REVIEW_ASSISTANT_ID}' not found.")
            if not self.feedback_agent:
                logger.error(f"Feedback agent with ID '{settings.LANGGRAPH_FEEDBACK_ASSISTANT_ID}' not found.")
                
        except Exception as e:
            logger.error(f"Error initializing LangGraph client or fetching assistants: {str(e)}")
            # Depending on policy, you might want to set agents to None or re-raise
            self.review_agent = None
            self.feedback_agent = None
            # raise # Optionally re-raise if assistant presence is critical for startup
    async def _get_user_github_token(self, user_github_id: str) -> Optional[str]:
        """Retrieve the GitHub token for a user"""
        try:
            user = await User.objects.aget(github_id=user_github_id)
            return user.github_access_token
        except User.DoesNotExist:
            logger.warning(f"User with GitHub ID {user_github_id} not found in the database.")
            return None
        except Exception as e:
            logger.error(f"Error retrieving GitHub token for user {user_github_id}: {e}")
            return None
    async def generate_review(
        self,
        pr_data: Dict[str, Any],
        repo_settings: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Generate a code review for a pull request"""
        if not self.review_agent:
            await self.initialize()
        github_token = await self._get_user_github_token(user_id)
        try:
            # Create a new thread for the review
            thread = await self.client.threads.create()
            
            # Determine if this is a PR or commit review
            is_commit_review = 'commit' in pr_data and pr_data.get('commit') and isinstance(pr_data.get('commit'), dict)
            
            # Prepare input data for the review
            input_data = {
                "llm_model": repo_settings.get('llm_preference', 'CEREBRAS::llama-3.3-70b'),
                "standards": repo_settings.get('coding_standards', []),
                "metrics": repo_settings.get('code_metrics', []),
                "temperature": 0.3,
                "max_tokens": 32768,
                "max_tool_calls": 7,
                "user_github_token": github_token
