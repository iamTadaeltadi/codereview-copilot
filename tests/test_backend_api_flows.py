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

    @patch("core.review_view.LangGraphService.handle_feedback", side_effect=RuntimeError("boom"))
    def test_review_feedback_returns_server_error_when_processing_fails(self, _mock_handle_feedback):
        self.authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/reviews/{self.review.id}/feedback/",
            {"review": self.review.id, "rating": 2, "feedback": "Needs work"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("Error processing feedback", response.data["detail"])

    def test_review_threads_action_returns_threads_for_review(self):
        self.authenticate(self.owner)
        response = self.client.get(f"/api/v1/reviews/{self.review.id}/threads/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.thread.id)

    @patch("core.review_view.LangGraphClient")
    def test_review_create_thread_creates_thread_and_returns_payload(self, mock_langgraph_client):
        self.authenticate(self.owner)
        client_instance = mock_langgraph_client.return_value
        client_instance.initialize = AsyncMock()
        client_instance.client = MagicMock()
        client_instance.client.threads.create = AsyncMock(return_value={"thread_id": "lg-thread-1"})
        response = self.client.post(
            f"/api/v1/reviews/{self.review.id}/create_thread/",
            {"title": "Follow-up"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["thread_id"], "lg-thread-1")
        self.assertTrue(Thread.objects.filter(review=self.review, thread_id="lg-thread-1").exists())

    @patch("core.review_view.LangGraphClient")
    def test_review_create_thread_returns_bad_gateway_when_langgraph_fails(self, mock_langgraph_client):
        self.authenticate(self.owner)
        client_instance = mock_langgraph_client.return_value
        client_instance.initialize = AsyncMock(side_effect=RuntimeError("offline"))
        response = self.client.post(f"/api/v1/reviews/{self.review.id}/create_thread/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_review_re_review_requires_issue_list(self):
        self.authenticate(self.owner)
        response = self.client.post(f"/api/v1/reviews/{self.review.id}/re_review/", {"issues": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("core.review_view.process_pr_review.delay")
    def test_review_re_review_creates_child_review(self, mock_delay):
        self.authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/reviews/{self.review.id}/re_review/",
            {"issues": ["address comment"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        child_review = Review.objects.get(parent_review=self.review)
        self.assertEqual(response.data["review_id"], child_review.id)
        mock_delay.assert_called_once()

    def test_submit_ai_rating_validates_rating(self):
        self.authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/reviews/{self.review.id}/submit_ai_rating/",
            {"rating": 7, "feedback": "bad"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_ai_rating_requires_feedback_text(self):
        self.authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/reviews/{self.review.id}/submit_ai_rating/",
            {"rating": 4},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_ai_rating_creates_feedback_and_usage(self):
        self.authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/reviews/{self.review.id}/submit_ai_rating/",
            {"rating": 4, "feedback": "Useful overall"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rating"], 4)
        self.assertTrue(LLMUsage.objects.filter(review=self.review, user=self.owner, input_tokens=0).exists())

    def test_thread_reply_requires_message(self):
        self.authenticate(self.owner)
        response = self.client.post(f"/api/v1/threads/{self.thread.id}/reply/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_thread_reply_rejects_unknown_parent_comment(self):
        self.authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/threads/{self.thread.id}/reply/",
            {"message": "Follow-up", "parent_comment_id": 999999},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("core.thread_view.calculate_cost", return_value=0.25)
    @patch("core.thread_view.LangGraphClient")
    def test_thread_reply_creates_user_and_ai_comments(self, mock_langgraph_client, _mock_cost):
        self.authenticate(self.owner)
        client_instance = mock_langgraph_client.return_value
        client_instance.initialize = AsyncMock()
        client_instance.handle_feedback = AsyncMock(
            return_value={
                "feedback_data": {"messages": [("ai", "Here is an answer")]},
                "token_usage": {"input_tokens": 11, "output_tokens": 7},
            }
        )
        response = self.client.post(
            f"/api/v1/threads/{self.thread.id}/reply/",
            {"message": "Can you clarify?", "parent_comment_id": self.comment.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ai_response"]["comment"], "Here is an answer")
        self.assertEqual(Comment.objects.filter(thread=self.thread).count(), 3)
        self.assertTrue(LLMUsage.objects.filter(review=self.review, user=self.owner).exists())

    @patch("core.thread_view.LangGraphClient")
    def test_thread_reply_returns_error_payload_when_processing_fails(self, mock_langgraph_client):
        self.authenticate(self.owner)
        client_instance = mock_langgraph_client.return_value
        client_instance.initialize = AsyncMock()
        client_instance.handle_feedback = AsyncMock(side_effect=RuntimeError("service down"))
        response = self.client.post(
            f"/api/v1/threads/{self.thread.id}/reply/",
            {"message": "Please retry"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)
        self.assertTrue(Comment.objects.filter(thread=self.thread, type="note").exists())

    def test_admin_stats_requires_admin_user(self):
        self.authenticate(self.owner)
        response = self.client.get("/api/v1/admin/stats/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_stats_returns_aggregate_counts(self):
        self.authenticate(self.admin)
        response = self.client.get("/api/v1/admin/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["users"], 3)
        self.assertGreaterEqual(response.data["repositories"], 1)
