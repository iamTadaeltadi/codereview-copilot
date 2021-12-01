from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .tasks.review_tasks import calculate_cost
from .models import (
    User,
    Thread as ThreadModel,
    Comment as CommentModel,
    LLMUsage as LLMUsageModel,
)
from .serializers import (
    ReviewSerializer, ThreadSerializer, CommentSerializer
)
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
import logging
from core.langgraph_client.client import LangGraphClient
import asyncio
from .permissions import (CanAccessRepository, IsAssignedReviewerForThread)
logger = logging.getLogger(__name__)

class ThreadViewSet(viewsets.ModelViewSet):
    serializer_class = ThreadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ThreadModel.objects.filter(
            Q(review__repository__owner=self.request.user) |
            Q(review__repository__collaborators__user=self.request.user)
        ).distinct()
    @action(detail=True, methods=['post'], url_path='reply', permission_classes=[IsAuthenticated])
    def reply(self, request, pk=None):
        """
        Reply to a thread and get an AI response.
        
        Args:
            pk: The ID of the Thread model instance
            
        Request body:
            message: str - The user's reply message
            
        Returns:
            Response with user comment and AI response
        """
        thread = self.get_object()
        # Validate the input
        message = request.data.get('message')
        parent_comment_id = request.data.get('parent_comment_id')  # Add this
         # Get parent comment if specified
        parent_comment = None
        if parent_comment_id:
            try:
                parent_comment = CommentModel.objects.get(id=parent_comment_id, thread=thread)
            except CommentModel.DoesNotExist:
                return Response(
                    {"detail": "Parent comment not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        if not message:
            return Response(
                {"detail": "Message is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user's comment
        user_comment = CommentModel.objects.create(
            thread=thread,
            user=request.user,
            comment=message,
            type='request',  # This is a request for AI feedback
            parent_comment=parent_comment
        )
        
        # Get AI user (create if not exists)
        ai_user, _ = User.objects.get_or_create(
            username="ai_assistant",
            defaults={
                "github_id": "ai_assistant",
                "is_staff": True,
                "is_ai_user": True
            }
        )
        
        # If no AI user ID is configured, use the first admin user
        if not ai_user and not settings.AI_USER_ID:
            ai_user = User.objects.filter(is_staff=True).first()
            if not ai_user:
                logger.error("No AI user or admin user found for AI responses")
                return Response(
                    {"detail": "Server configuration error: No AI user available"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        elif settings.AI_USER_ID and not ai_user:
            try:
                ai_user = User.objects.get(id=settings.AI_USER_ID)
            except User.DoesNotExist:
                logger.error(f"AI_USER_ID {settings.AI_USER_ID} not found")
                # Continue with admin user
        # Manage asyncio event loop explicitly
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Process user's message with LangGraph
        try:
            # Get thread history to provide context for the conversation
            thread_comments = CommentModel.objects.filter(thread=thread).order_by('created_at')
            conversation_history = []
            # Add the current user message
            conversation_history.append(("user", message))
            
            # Get LangGraph service
            langgraph_client_instance = LangGraphClient()
            loop.run_until_complete(langgraph_client_instance.initialize())
            # async_to_sync(langgraph_client_instance.initialize)()
            # Determine if this is the first message in the thread
            is_first_message_in_thread = thread_comments.count() <= 1 # Only our new comment
            # Fetch review data and repo settings for context if it's the first message
            review_model_instance = thread.review
            review_data_for_lg = {}
            repo_settings_for_lg = {}
