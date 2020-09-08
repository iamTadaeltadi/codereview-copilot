from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .tasks.review_tasks import process_pr_review
from .models import (
    User,
    Repository as DBRepository,
    PullRequest as PRModel,
    Review as ReviewModel,
    Thread as ThreadModel,
)
from .serializers import (
    PRSerializer, ThreadSerializer
)
from .services import (
    get_repository_pull_requests_from_github,
    get_single_pull_request_from_github,
)
import requests
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
import logging
from .permissions import (CanAccessRepository)
logger = logging.getLogger(__name__)

class PullRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PRSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['get'], url_path='my-threads')
    def my_threads(self, request, pk=None):
        """
        Get threads created by the current user for this pull request.
        pk here is the PullRequest ID.
        """
        pr = self.get_object()
        threads_qs = ThreadModel.objects.filter(
            review__pull_request=pr,
            created_by=request.user
        ).order_by('-created_at')
        
        page = self.paginate_queryset(threads_qs)
        if page is not None:
            serializer = ThreadSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = ThreadSerializer(threads_qs, many=True, context={'request': request})
        return Response(serializer.data)
    def get_queryset(self):
        return PRModel.objects.all()

    def list(self, request, *args, **kwargs):
        repository_id = request.query_params.get('repo_id')
        if not repository_id:
            return Response({"detail": "repository_id query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            db_repo = get_object_or_404(DBRepository, pk=repository_id)
        except ValueError:
            return Response({"detail": "Invalid repository_id format."}, status=status.HTTP_400_BAD_REQUEST)

        if not CanAccessRepository().has_object_permission(request, self, db_repo):
            raise PermissionDenied("You do not have permission to access this repository.")

        db_items = PRModel.objects.filter(repository=db_repo).order_by('-pr_number')
        serialized_db_items = self.get_serializer(db_items, many=True).data
        for item in serialized_db_items:
            item['source'] = 'db'
        
        combined_items_dict = {item['pr_number']: item for item in serialized_db_items} # Use pr_number

        if not request.user.github_access_token:
            logger.warning(f"User {request.user.id} has no GitHub token. Fetching PRs from DB only for repo {db_repo.id}")
        else:
