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
        self.thread = Thread.objects.create(
            review=self.review,
            thread_id="thread-123",
            created_by=self.owner,
            title="Main thread",
            status="open",
        )
        self.comment = Comment.objects.create(
            thread=self.thread,
            user=self.owner,
            comment="Initial issue",
            type="request",
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_review_history_requires_context_and_id(self):
        self.authenticate(self.owner)
        response = self.client.get("/api/v1/reviews/history/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("required", response.data["detail"])

    def test_review_history_rejects_invalid_context(self):
        self.authenticate(self.owner)
        response = self.client.get("/api/v1/reviews/history/?context=branch&id=12")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid context", response.data["detail"])

    def test_review_history_for_pull_request_returns_cleaned_payload(self):
        self.authenticate(self.owner)
        response = self.client.get(f"/api/v1/reviews/history/?context=pr&id={self.pull_request.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        record = response.data[0]
        self.assertEqual(record["id"], self.review.id)
        self.assertNotIn("repository", record)
        self.assertNotIn("threads", record)
        self.assertNotIn("thread_count", record)

    def test_review_retrieve_includes_threads(self):
        self.authenticate(self.owner)
        response = self.client.get(f"/api/v1/reviews/{self.review.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["threads"]), 1)
        self.assertEqual(response.data["threads"][0]["thread_id"], self.thread.thread_id)

    def test_review_feedback_returns_conflict_without_langgraph_thread(self):
        self.authenticate(self.owner)
        review_without_thread = Review.objects.create(
            repository=self.repo,
            pull_request=self.pull_request,
            status="completed",
        )
        response = self.client.post(
            f"/api/v1/reviews/{review_without_thread.id}/feedback/",
            {"review": review_without_thread.id, "rating": 4, "feedback": "Please revise"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    @patch("core.review_view.LangGraphService.handle_feedback")
    def test_review_feedback_returns_feedback_data_and_token_usage(self, mock_handle_feedback):
        self.authenticate(self.owner)
        mock_handle_feedback.return_value = {
            "feedback_data": {"status": "ok"},
            "token_usage": {"input_tokens": 3, "output_tokens": 5},
        }
        response = self.client.post(
            f"/api/v1/reviews/{self.review.id}/feedback/",
            {"review": self.review.id, "rating": 5, "feedback": "Looks good"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["feedback_data"]["status"], "ok")
        self.assertEqual(response.data["token_usage"]["output_tokens"], 5)
