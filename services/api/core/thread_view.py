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
