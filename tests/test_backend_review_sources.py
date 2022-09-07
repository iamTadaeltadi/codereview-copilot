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
            url="https://github.com/owner/repo/commit/abc123",
            timestamp=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        )
        self.review = Review.objects.create(repository=self.repo, pull_request=self.pull_request, status="completed")
        self.thread = Thread.objects.create(review=self.review, thread_id="pr-thread", created_by=self.owner, title="Owner thread")
        self.other_thread = Thread.objects.create(review=self.review, thread_id="pr-thread-2", created_by=self.collaborator, title="Collaborator thread")
        LLMUsage.objects.create(review=self.review, user=self.owner, llm_model="gpt-test", input_tokens=10, output_tokens=5, cost=1.25)
        LLMUsage.objects.create(review=self.review, user=self.collaborator, llm_model="claude-test", input_tokens=7, output_tokens=8, cost=0.75)

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_pull_request_list_requires_repo_id(self):
        self.authenticate(self.owner)
        response = self.client.get("/api/v1/pull-requests/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pull_request_list_rejects_invalid_repo_id(self):
        self.authenticate(self.owner)
        response = self.client.get("/api/v1/pull-requests/?repo_id=abc")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pull_request_list_rejects_unauthorized_user(self):
        self.authenticate(self.outsider)
        response = self.client.get(f"/api/v1/pull-requests/?repo_id={self.repo.id}")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("core.pr_view.get_repository_pull_requests_from_github")
    def test_pull_request_list_merges_db_and_github_results(self, mock_get_prs):
        self.authenticate(self.owner)
        mock_get_prs.return_value = [
            {
                "id": 999,
                "number": 9,
                "title": "GitHub PR",
                "body": "From GitHub",
                "html_url": "https://github.com/owner/repo/pull/9",
                "created_at": "2026-05-01T00:00:00Z",
                "updated_at": "2026-05-02T00:00:00Z",
                "closed_at": None,
                "merged_at": None,
                "state": "open",
                "user": {"id": 500, "login": "gh-user", "avatar_url": "https://img.test/u.png"},
                "head": {"sha": "head-9"},
                "base": {"sha": "base-9"},
            }
        ]
        response = self.client.get(f"/api/v1/pull-requests/?repo_id={self.repo.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        numbers = {item["pr_number"]: item["source"] for item in response.data}
        self.assertEqual(numbers[7], "db")
        self.assertEqual(numbers[9], "github")

    def test_pull_request_list_without_github_token_returns_db_only(self):
        self.owner.github_access_token = None
        self.owner.save(update_fields=["github_access_token"])
        self.authenticate(self.owner)
        response = self.client.get(f"/api/v1/pull-requests/?repo_id={self.repo.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["pr_number"], 7)

    def test_pull_request_my_threads_returns_only_current_user_threads(self):
        self.authenticate(self.owner)
        response = self.client.get(f"/api/v1/pull-requests/{self.pull_request.id}/my-threads/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["thread_id"], "pr-thread")

    def test_pull_request_trigger_review_requires_fields(self):
        self.authenticate(self.owner)
        response = self.client.post("/api/v1/pull-requests/trigger-review/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pull_request_trigger_review_rejects_invalid_pr_number(self):
        self.authenticate(self.owner)
        response = self.client.post(
            "/api/v1/pull-requests/trigger-review/",
            {"repository_id": self.repo.id, "pr_number": "abc"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pull_request_trigger_review_returns_conflict_for_existing_review(self):
        self.authenticate(self.owner)
        response = self.client.post(
            "/api/v1/pull-requests/trigger-review/",
            {"repository_id": self.repo.id, "pr_number": self.pull_request.pr_number},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["review_id"], self.review.id)

    @patch("core.pr_view.process_pr_review.delay")
    @patch("core.pr_view.get_single_pull_request_from_github")
    def test_pull_request_trigger_review_fetches_missing_pr_and_creates_review(self, mock_get_pr, mock_delay):
        self.authenticate(self.owner)
        mock_get_pr.return_value = {
            "id": 2222,
            "number": 22,
            "title": "Fetched PR",
            "body": "Fetched body",
            "html_url": "https://github.com/owner/repo/pull/22",
            "state": "open",
            "user": {"id": 42, "login": "owner"},
            "head": {"sha": "head-22"},
            "base": {"sha": "base-22"},
        }
        response = self.client.post(
            "/api/v1/pull-requests/trigger-review/",
            {"repository_id": self.repo.id, "pr_number": 22},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Review.objects.filter(pull_request__pr_number=22).exists())
        mock_delay.assert_called_once()

    def test_commit_list_requires_repo_id(self):
        self.authenticate(self.owner)
        response = self.client.get("/api/v1/commits/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_commit_list_rejects_invalid_repo_id(self):
        self.authenticate(self.owner)
        response = self.client.get("/api/v1/commits/?repo_id=abc")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_commit_list_rejects_unauthorized_user(self):
        self.authenticate(self.outsider)
        response = self.client.get(f"/api/v1/commits/?repo_id={self.repo.id}")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("core.commit_view.get_repository_commits_from_github")
    def test_commit_list_merges_db_and_github_results(self, mock_get_commits):
        self.authenticate(self.owner)
        mock_get_commits.return_value = [
            {
                "sha": "def456",
                "html_url": "https://github.com/owner/repo/commit/def456",
                "commit": {
                    "message": "GitHub commit",
                    "author": {"name": "Owner", "email": "owner@example.com", "date": "2026-05-03T00:00:00Z"},
                    "committer": {"name": "Owner", "email": "owner@example.com", "date": "2026-05-03T01:00:00Z"},
                },
                "author": {"id": 1},
                "committer": {"id": 1},
            }
        ]
        response = self.client.get(f"/api/v1/commits/?repo_id={self.repo.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        hashes = {item["commit_hash"]: item["source"] for item in response.data}
        self.assertEqual(hashes["abc123"], "db")
        self.assertEqual(hashes["def456"], "github")

    def test_commit_list_without_github_token_returns_db_only(self):
        self.owner.github_access_token = None
        self.owner.save(update_fields=["github_access_token"])
        self.authenticate(self.owner)
        response = self.client.get(f"/api/v1/commits/?repo_id={self.repo.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["commit_hash"], "abc123")

    def test_commit_trigger_review_requires_fields(self):
        self.authenticate(self.owner)
        response = self.client.post("/api/v1/commits/trigger-review/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_commit_trigger_review_rejects_invalid_repository_id(self):
        self.authenticate(self.owner)
        response = self.client.post(
            "/api/v1/commits/trigger-review/",
            {"repository_id": "abc", "commit_hash": "abc123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_commit_trigger_review_returns_conflict_for_existing_review(self):
        Review.objects.create(repository=self.repo, commit=self.commit, status="pending")
        self.authenticate(self.owner)
        response = self.client.post(
            "/api/v1/commits/trigger-review/",
            {"repository_id": self.repo.id, "commit_hash": self.commit.commit_hash},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_commit_trigger_review_requires_github_token_for_missing_commit(self):
        self.owner.github_access_token = None
        self.owner.save(update_fields=["github_access_token"])
        self.authenticate(self.owner)
        response = self.client.post(
            "/api/v1/commits/trigger-review/",
            {"repository_id": self.repo.id, "commit_hash": "missing"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("core.commit_view.process_commit_review.delay")
    @patch("core.commit_view.get_single_commit_from_github")
    def test_commit_trigger_review_fetches_missing_commit_and_creates_review(self, mock_get_commit, mock_delay):
        self.authenticate(self.owner)
        mock_get_commit.return_value = {
            "sha": "newsha",
            "html_url": "https://github.com/owner/repo/commit/newsha",
            "commit": {
                "message": "Fetched commit",
                "author": {"date": "2026-05-05T00:00:00Z"},
            },
            "author": {"id": 1},
            "committer": {"id": 1},
        }
        response = self.client.post(
            "/api/v1/commits/trigger-review/",
            {"repository_id": self.repo.id, "commit_hash": "newsha"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Review.objects.filter(commit__commit_hash="newsha").exists())
        mock_delay.assert_called_once()

    def test_llm_usage_list_returns_summary_for_collaborator(self):
        self.authenticate(self.collaborator)
        response = self.client.get("/api/v1/llm-usage/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_usage"]["total_input"], 17)
        self.assertEqual(len(response.data["usage_by_model"]), 2)

    def test_llm_usage_summary_returns_summary_for_admin(self):
        self.authenticate(self.admin)
        response = self.client.get("/api/v1/llm-usage/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_usage"]["total_output"], 13)
        models = {item["llm_model"] for item in response.data["usage_by_model"]}
        self.assertEqual(models, {"gpt-test", "claude-test"})


if __name__ == "__main__":
    unittest.main()

