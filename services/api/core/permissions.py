from rest_framework.permissions import BasePermission

from .models import (
    RepoCollaborator,
    Thread as ThreadModel,
)

from .services import (
    get_repo_collaborators_from_github,
    get_single_pull_request_from_github,
)
import logging
logger = logging.getLogger(__name__)

class IsRepositoryOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user

class IsAssignedReviewerForThread(BasePermission):
    message = "You are not an assigned reviewer for this review thread."

    def has_object_permission(self, request, view, obj):
        # Only apply this permission to ThreadModel instances
        if not isinstance(obj, ThreadModel):
            return False

        # Get the pull request linked to this thread
        pr = obj.review.pull_request
        if not pr:
            return False

        # Ensure the user has a GitHub token
        token = getattr(request.user, "github_access_token", None)
        if not token:
            return False

        try:
            # Derive owner login and repository name
            owner_login = pr.repository.owner.username
            repo_name = pr.repository.repo_name.split("/", 1)[1]

            # Fetch the PR from GitHub to inspect requested reviewers
            gh_pr_data = get_single_pull_request_from_github(
                github_token=token,
                owner_login=owner_login,
                repo_name=repo_name,
                pr_number=pr.pr_number
            )

            # Check if the current user is in the requested reviewers list
            reviewers = gh_pr_data.get("requested_reviewers", [])
            for r in reviewers:
                if (str(r.get("id")) == str(request.user.github_id)
                        or r.get("login") == request.user.username):
                    return True
        except Exception:
            logger.warning(
                f"Could not verify assigned reviewers for user {request.user.id} on PR #{pr.pr_number}"
            )
