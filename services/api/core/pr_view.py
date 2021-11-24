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
            try:
                page = int(request.query_params.get('page', 1))
                per_page = int(request.query_params.get('per_page', 30)) # Default to 30

                owner_login = db_repo.owner.username
                repo_name_only = db_repo.repo_name.split('/')[-1]
                
                gh_items_raw = get_repository_pull_requests_from_github(
                    github_token=request.user.github_access_token,
                    owner_login=owner_login,
                    repo_name=repo_name_only,
                    state="all",
                    per_page=per_page,
                    page=page
                )
                
                for gh_pr in gh_items_raw:
                    # Use gh_pr['number'] as the key for matching
                    if gh_pr['number'] not in combined_items_dict:
                        user_data = gh_pr.get('user', {})
                        head_data = gh_pr.get('head', {})
                        base_data = gh_pr.get('base', {})
                        transformed_gh_item = {
                            'pr_github_id': gh_pr.get('id'),
                            'pr_number': gh_pr.get('number'),
                            'title': gh_pr.get('title'),
                            'body': gh_pr.get('body'),
                            'user_login': user_data.get('login'),
                            'user_avatar_url': user_data.get('avatar_url'),
                            'url': gh_pr.get('html_url'),
                            'created_at_gh': gh_pr.get('created_at'),
                            'updated_at_gh': gh_pr.get('updated_at'),
                            'closed_at_gh': gh_pr.get('closed_at'),
                            'merged_at_gh': gh_pr.get('merged_at'),
                            'source': 'github',
                            'id': None,
                            'repository_id': db_repo.id, 
                            'created_at': None, 
                            'updated_at': None,

                            # Align with model fields
                            'author_github_id': str(user_data.get('id')) if user_data else None,
                            'status': gh_pr.get('state'),
                            'head_sha': head_data.get('sha'),
                            'base_sha': base_data.get('sha'),
                        }
                        # Similar to commits, using serializer for consistency if possible
                        serialized_gh_pr = self.get_serializer(data=transformed_gh_item)
                        if serialized_gh_pr.is_valid():
                            validated_data = serialized_gh_pr.data
                            validated_data['source'] = 'github'
                            combined_items_dict[gh_pr['number']] = validated_data
                        else:
                            logger.error(f"GitHub PR data for #{gh_pr['number']} not valid for serializer: {serialized_gh_pr.errors}")
                            transformed_gh_item['repository_id'] = db_repo.id # Add repository_id for context
                            combined_items_dict[gh_pr['number']] = transformed_gh_item


            except requests.exceptions.RequestException as e:
                logger.error(f"GitHub API error while fetching PRs for repo {db_repo.id}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error while fetching GitHub PRs for repo {db_repo.id}: {e}")

        final_list = list(combined_items_dict.values())
        # final_list.sort(key=lambda x: x.get('number'), reverse=True)
        return Response(final_list)

    @action(detail=False, methods=['post'], url_path='trigger-review') # MODIFIED
    def trigger_review(self, request): # MODIFIED: removed pk=None
        """
        Manually trigger an AI review for a pull request.
        
        Args:
            pk: The ID of the PullRequest model instance
        
