from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .models import (
    Repository as DBRepository,
    RepoCollaborator,
    PullRequest as PRModel,
    Commit as CommitModel,
    WebhookEventLog
)
from .serializers import (
    RepositorySerializer, RepoCollaboratorSerializer, 
    GitHubCollaboratorSerializer,
    PRSerializer, CommitSerializer
)
from .services import (
    get_repo_collaborators_from_github,
    get_single_commit_from_github,
    get_single_pull_request_from_github,
)
import hashlib
import os
import requests
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
import logging
from .permissions import (IsRepositoryOwner,CanAccessRepository)
logger = logging.getLogger(__name__)

class RepositoryViewSet(viewsets.ModelViewSet):
    queryset = DBRepository.objects.all()
    serializer_class = RepositorySerializer
    permission_classes = [IsAuthenticated] # Base permission for all actions

    def get_queryset(self):
        # Users can list repositories they own or are collaborators on.
        return DBRepository.objects.filter(
            Q(owner=self.request.user) | Q(collaborators__user=self.request.user, collaborators__role__in=['member', 'admin']) # Assuming 'member', 'admin' roles
        ).distinct()

    def perform_create(self, serializer):
        # Generate a unique webhook secret
        webhook_secret = hashlib.sha256(os.urandom(32)).hexdigest()

        # Construct the webhook URL
        # Ensure 'github-webhook' is the correct name of your webhook URL pattern in core/urls.py
        full_webhook_url = None
        try:
            # Assuming your webhook URL is named 'github-webhook' in your urls.py
            webhook_path = reverse('github-webhook') 
            base_url = self.request.build_absolute_uri('/').rstrip('/')
            full_webhook_url = f"{base_url}{webhook_path}"
        except Exception as e:
            logger.error(f"Could not reverse URL for 'github-webhook': {e}. Webhook URL will be null for new repo.")
            # Depending on policy, you might want to prevent repo creation if webhook URL cannot be formed.
            # For now, it will proceed with webhook_url as None.

        # Save the instance with the owner, generated secret, and webhook_url
        instance = serializer.save(
            owner=self.request.user,
            webhook_secret=webhook_secret,
            webhook_url=full_webhook_url # Pass the generated URL to be saved
        )
        
        # Add owner as a collaborator
        RepoCollaborator.objects.create(repository=instance, user=self.request.user, role='owner')

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy', 'regenerate_webhook_secret', 'webhook_status']:
            self.permission_classes = [IsAuthenticated, IsRepositoryOwner]
        elif self.action in ['retrieve', 'collaborators', 'registered_collaborators']:
            self.permission_classes = [IsAuthenticated, CanAccessRepository]
        elif self.action == 'by_github_id':
            # now allow owners _and_ collaborators
            self.permission_classes = [IsAuthenticated, CanAccessRepository]
        # Remove webhook_status from here if it's handled by the more specific action decorator path
        # Remove regenerate_webhook_secret from here if it's handled by the more specific action decorator path
        else: # list, create
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

    @action(detail=True, methods=['post'], url_path='webhook/regenerate-secret')
    def regenerate_webhook_secret(self, request, pk=None):
        """Regenerate the webhook secret for this repository."""
        repository = self.get_object() # Applies object-level permissions (IsRepositoryOwner)
        new_secret = hashlib.sha256(os.urandom(32)).hexdigest()
        repository.webhook_secret = new_secret
        repository.save(update_fields=['webhook_secret'])
        return Response({"status": "webhook secret regenerated", "new_secret_hint": "New secret stored. Update your Git provider if necessary."})

    @action(detail=True, methods=['get'], url_path='webhook/status')
    def webhook_status(self, request, pk=None):
        """Check webhook status (e.g., last event received)."""
        repository = self.get_object() # Applies object-level permissions (IsRepositoryOwner or CanAccessRepository based on get_permissions)
        # The permission is currently set to IsRepositoryOwner in get_permissions for 'webhook_status'.

        # Fetch last 5 webhook events for this repository as an example
        recent_events = WebhookEventLog.objects.filter(repository=repository).order_by('-created_at')[:5]
        # You might want to serialize these events if you send them
        # For now, just a summary
        last_event_summary = None
        if recent_events.exists():
            last_event = recent_events.first()
            last_event_summary = {
                "type": last_event.event_type,
                "timestamp": last_event.processed_at.isoformat(),
                "status_code": last_event.status # Assuming you add status_code to WebhookEventLog
            }

        status_data = {
            "webhook_id": repository.webhook_url, # Assuming you store webhook_id from GitHub
            "webhook_url": f"{settings.FRONTEND_URL}/api/webhook/github/", # The URL they should configure
            "secret_configured": bool(repository.webhook_secret),
            "secret": repository.webhook_secret, # Don't send this in production!
            "is_active_on_github": None, # This would require a GitHub API call to check actual status
            "last_event_received": last_event_summary,
            "recent_event_count": WebhookEventLog.objects.filter(repository=repository).count()
        }
        return Response(status_data)

    def list(self, request, *args, **kwargs):
        """List repositories for which the current user is an owner or collaborator."""
        # Get repos owned by the user
        owned_repos = DBRepository.objects.filter(owner=request.user)
        # Get repos where the user is a collaborator
        collaborating_repo_ids = RepoCollaborator.objects.filter(user=request.user).values_list('repository_id', flat=True)
        collaborating_repos = DBRepository.objects.filter(id__in=collaborating_repo_ids)
        # Combine and remove duplicates
        queryset = (owned_repos | collaborating_repos).distinct()
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def collaborators(self, request, pk=None):
        """Get collaborators from GitHub for this repository."""
