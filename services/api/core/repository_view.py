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
