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
                        
                        # GitHub user objects (can be different from git author/committer)
                        gh_author_user = gh_commit.get('author') # GitHub user who authored
                        gh_committer_user = gh_commit.get('committer') # GitHub user who committed

                        transformed_gh_item = {
                            'commit_hash': gh_commit.get('sha'),
                            'message': commit_data.get('message'),
                            
                            'author_name': author_data.get('name'),
                            'author_email': author_data.get('email'),
                            # 'author_date': author_data.get('date'), # Replaced by timestamp
                            
                            'committer_name': committer_data.get('name'),
                            'committer_email': committer_data.get('email'),
                            'committed_date': committer_data.get('date'), # Keep this for committer specific date
                            
                            'url': gh_commit.get('html_url'),
                            'source': 'github',
                            'id': None, 
                            'repository_id': db_repo.id,
                            'created_at': None, 
                            'updated_at': None,

                            # Align with model fields
                            'timestamp': author_data.get('date'), # Use git author date for the main commit timestamp
                            'author_github_id': str(gh_author_user.get('id')) if gh_author_user else None,
                            'committer_github_id': str(gh_committer_user.get('id')) if gh_committer_user else None,
                        }
                        # Use serializer to ensure consistent output structure, passing instance=transformed_gh_item
                        # This is tricky if serializer expects a model instance.
                        # For now, we construct a dict and assume client handles it.
                        # A better way might be to have a different serializer for GitHub-only objects
                        # or make the main serializer flexible.
                        serializer_instance = self.get_serializer(data=transformed_gh_item)
                        
                        if serializer_instance.is_valid():
                            validated_data = serializer_instance.data
                            # Ensure 'source' is present if it's part of read_only_fields but you want it in output
                            validated_data['source'] = 'github' 
                            combined_items_dict[gh_commit['sha']] = validated_data
                        else:
                             logger.error(f"GitHub commit data for {gh_commit['sha']} not valid for serializer: {serializer_instance.errors}")
                             # If not valid, store the raw transformed dict but ensure it's what you want
                             # Adding repository_id for context if it was missing and causing validation error
                             transformed_gh_item['repository_id'] = db_repo.id # Ensure this is set
                             transformed_gh_item['source'] = 'github' # Explicitly set source
                             combined_items_dict[gh_commit['sha']] = transformed_gh_item


            except requests.exceptions.RequestException as e:
                logger.error(f"GitHub API error while fetching commits for repo {db_repo.id}: {e}")
                # Proceed with DB items, or return error
            except Exception as e:
                logger.error(f"Unexpected error while fetching GitHub commits for repo {db_repo.id}: {e}")


        final_list = list(combined_items_dict.values())
        # Optionally, re-sort if mixing sources changed order
        # final_list.sort(key=lambda x: x.get('committed_date') or x.get('author_date'), reverse=True)
        return Response(final_list)

    @action(detail=False,url_path='trigger-review', methods=['post'])
    def trigger_review(self, request):
        """
        Manually trigger an AI review for a commit.
        If the commit doesn't exist in the DB, it's fetched from GitHub and created.
        Requires 'repository_id' and 'commit_hash' in the request body.
        """
        repository_id_str = request.data.get('repository_id')
        commit_hash_from_request = request.data.get('commit_hash')

        if not repository_id_str or not commit_hash_from_request:
            return Response(
                {"detail": "repository_id and commit_hash are required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            repository_id = int(repository_id_str)
        except ValueError:
