from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .tasks.review_tasks import process_commit_review
from .models import (
    User,
    Repository as DBRepository,
    Commit as CommitModel,
    Review as ReviewModel,
)
from .serializers import (
    CommitSerializer
)
from .services import (
    get_repository_commits_from_github,
    get_single_commit_from_github,
)
import requests
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
import logging
from .permissions import (CanAccessRepository)
from django.utils.dateparse import parse_datetime
logger = logging.getLogger(__name__)

class CommitViewSet(viewsets.ModelViewSet):
    serializer_class = CommitSerializer
    permission_classes = [IsAuthenticated] # Permissions checked in list method
    lookup_field = 'commit_hash'
    def get_queryset(self):
        # Base queryset, actual filtering by repository_id happens in list()
        return CommitModel.objects.all()

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

        db_items = CommitModel.objects.filter(repository=db_repo).order_by('-timestamp')
        
        serialized_db_items = self.get_serializer(db_items, many=True).data
        for item in serialized_db_items:
            item['source'] = 'db'

        combined_items_dict = {item['commit_hash']: item for item in serialized_db_items} # Use commit_hash

        if not request.user.github_access_token:
            logger.warning(f"User {request.user.id} has no GitHub token. Fetching commits from DB only for repo {db_repo.id}")
        else:
            try:
                page = int(request.query_params.get('page', 1))
                per_page = int(request.query_params.get('per_page', 30)) # Default to 30, can be adjusted

                owner_login = db_repo.owner.username
                repo_name_only = db_repo.repo_name.split('/')[-1]
                
                gh_items_raw = get_repository_commits_from_github(
                    github_token=request.user.github_access_token,
                    owner_login=owner_login,
                    repo_name=repo_name_only,
                    per_page=per_page,
                    page=page
                )

                for gh_commit in gh_items_raw:
                    # Use gh_commit['sha'] as the key for matching
                    if gh_commit['sha'] not in combined_items_dict:
                        commit_data = gh_commit.get('commit', {})
                        author_data = commit_data.get('author', {}) # Git author
                        committer_data = commit_data.get('committer', {}) # Git committer
                        
