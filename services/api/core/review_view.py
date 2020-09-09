from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .tasks.review_tasks import process_pr_review
from .models import (
    Review as ReviewModel,
    Thread as ThreadModel,
    LLMUsage as LLMUsageModel,
    ReviewFeedback,
)
from .serializers import (
    ReviewSerializer, ThreadSerializer, ReviewFeedbackSerializer
)
from .services import (
    LangGraphService
)
from django.conf import settings
from django.db.models import Q 
import logging
from .permissions import (CanAccessRepository)
from core.langgraph_client.client import LangGraphClient
import asyncio
logger = logging.getLogger(__name__)

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'],url_path='history', permission_classes=[IsAuthenticated, CanAccessRepository])
    def history(self, request, pk=None):
        """
        Get review history for a PR or commit with thread information.
        """
        context_param = request.query_params.get('context')  # 'pr' or 'commit'
        item_id = request.query_params.get('id')  # PR or Commit ID
        
        if not context_param or not item_id:
            return Response(
                {"detail": "Context and ID parameters are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reviews_qs = ReviewModel.objects.none()
        if context_param == 'pr':
            reviews_qs = ReviewModel.objects.filter(pull_request_id=item_id)
        elif context_param == 'commit':
            reviews_qs = ReviewModel.objects.filter(commit__commit_hash=item_id)
        else:
            return Response(
                {"detail": "Invalid context. Must be 'pr' or 'commit'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reviews_qs = reviews_qs.prefetch_related('threads', 'threads__comments')
        
        # Use default serializer context, ReviewSerializer includes threads by default if present in Meta
        serializer_context = self.get_serializer_context()
        serializer = self.get_serializer(reviews_qs.order_by('-created_at'), many=True, context=serializer_context)
        
        response_data = serializer.data # This is a list of serialized review objects
        
        fields_to_remove_from_each_review = [
            'repository', 
            'pull_request', 
            'review_data', 
            'threads',
            'thread_count' # Also remove thread_count as it's related to threads
        ]
        
        cleaned_response_data = []
        for review_item_data in response_data:
            for key_to_remove in fields_to_remove_from_each_review:
                review_item_data.pop(key_to_remove, None)
