import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.test_settings")
django.setup()

from django.core.management import call_command
from django.test.utils import setup_databases, setup_test_environment
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Commit, LLMUsage, PullRequest, RepoCollaborator, Repository, Review, Thread, User

try:
    setup_test_environment()
except RuntimeError:
    pass
_DB_CONFIG = setup_databases(verbosity=0, interactive=False, keepdb=False)


class ReviewSourceEndpointTests(unittest.TestCase):
    def setUp(self):
        call_command("flush", verbosity=0, interactive=False)
        self.client = APIClient()
        self.owner = User.objects.create_user(
            github_id="owner-1",
            username="owner",
            email="owner@example.com",
            github_access_token="owner-token",
        )
        self.collaborator = User.objects.create_user(
            github_id="collab-1",
            username="collab",
            email="collab@example.com",
            github_access_token="collab-token",
        )
        self.outsider = User.objects.create_user(
            github_id="outsider-1",
            username="outsider",
            email="outsider@example.com",
            github_access_token="outsider-token",
        )
        self.admin = User.objects.create_user(
            github_id="admin-1",
            username="admin",
            email="admin@example.com",
            is_staff=True,
        )
        self.repo = Repository.objects.create(
            owner=self.owner,
            github_native_id=123,
            repo_name="owner/repo",
            repo_url="https://github.com/owner/repo",
            webhook_secret="secret",
            webhook_url="http://localhost:8000/api/v1/webhook/github/",
            llm_preference="gpt-test",
        )
        RepoCollaborator.objects.create(repository=self.repo, user=self.owner, role="owner")
        RepoCollaborator.objects.create(repository=self.repo, user=self.collaborator, role="member")
        self.pull_request = PullRequest.objects.create(
            repository=self.repo,
            pr_github_id="555",
            pr_number=7,
            title="Existing PR",
            author_github_id=self.owner.github_id,
            status="open",
            url="https://github.com/owner/repo/pull/7",
            body="Body",
            head_sha="headsha",
            base_sha="basesha",
        )
        self.commit = Commit.objects.create(
            repository=self.repo,
            commit_hash="abc123",
            author_github_id=self.owner.github_id,
            committer_github_id=self.owner.github_id,
            message="Existing commit",
