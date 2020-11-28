import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.test_settings")
django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test.utils import setup_databases, setup_test_environment, teardown_databases, teardown_test_environment
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Comment, LLMUsage, PullRequest, RepoCollaborator, Repository, Review, Thread, User

setup_test_environment()
_DB_CONFIG = setup_databases(verbosity=0, interactive=False, keepdb=False)


class BackendApiFlowTests(unittest.TestCase):
    def setUp(self):
        call_command("flush", verbosity=0, interactive=False)
        self.client = APIClient()
        self.owner = User.objects.create_user(
            github_id="owner-1",
            username="owner",
            email="owner@example.com",
        )
        self.collaborator = User.objects.create_user(
            github_id="collab-1",
            username="collaborator",
            email="collab@example.com",
            github_access_token="gho_token",
        )
        self.admin = User.objects.create_user(
            github_id="admin-1",
            username="admin",
            email="admin@example.com",
            is_staff=True,
        )
        self.repo = Repository.objects.create(
            owner=self.owner,
            github_native_id=101,
            repo_name="owner/repo",
            repo_url="https://github.com/owner/repo",
            llm_preference="gpt-test",
            coding_standards=["pep8"],
            code_metrics=["complexity"],
            webhook_secret="secret",
            webhook_url="http://localhost:8000/api/v1/webhook/github/",
        )
        RepoCollaborator.objects.create(repository=self.repo, user=self.owner, role="owner")
        RepoCollaborator.objects.create(repository=self.repo, user=self.collaborator, role="member")
        self.pull_request = PullRequest.objects.create(
            repository=self.repo,
            pr_github_id="pr-100",
            pr_number=12,
            title="Improve review flow",
            author_github_id=self.owner.github_id,
            status="open",
            url="https://github.com/owner/repo/pull/12",
            body="PR body",
            head_sha="headsha",
            base_sha="basesha",
        )
        self.review = Review.objects.create(
            repository=self.repo,
            pull_request=self.pull_request,
            status="completed",
            review_data={"summary": "initial"},
        )
