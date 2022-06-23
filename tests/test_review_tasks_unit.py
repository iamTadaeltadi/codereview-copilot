"""Unit tests for the Celery review task module.

These cover the synchronous webhook dispatch logic, the asynchronous PR/commit
review tasks (with the LangGraph client and ORM mocked out), and the pure
``calculate_cost`` helper. The ORM is mocked so the suite does not require a
live database for this module.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import django

django.setup()

from core.tasks import review_tasks


def _exception_class(name):
    return type(name, (Exception,), {})


class CalculateCostTests(unittest.TestCase):
    def test_uses_model_specific_pricing(self):
        cost = review_tasks.calculate_cost(
            {"input_tokens": 1000, "output_tokens": 2000}, "gpt-4"
        )
        expected = round(1000 * 0.00003 + 2000 * 0.00006, 6)
        self.assertEqual(cost, expected)

    def test_matches_partial_model_name(self):
        cost = review_tasks.calculate_cost(
            {"input_tokens": 100, "output_tokens": 100},
            "cerebras::llama-3.3-70b-instruct",
        )
        expected = round(100 * 0.0000026 + 100 * 0.0000035, 6)
        self.assertEqual(cost, expected)

    def test_falls_back_to_default_pricing(self):
        cost = review_tasks.calculate_cost(
            {"input_tokens": 500, "output_tokens": 500}, "some-unknown-model"
        )
        expected = round(500 * 0.00001 + 500 * 0.00002, 6)
        self.assertEqual(cost, expected)

    def test_handles_missing_token_counts(self):
        self.assertEqual(review_tasks.calculate_cost({}, "default"), 0.0)


class ProcessWebhookEventTests(unittest.TestCase):
    def _pr_event(self, action="opened"):
        return {
            "repository": {"full_name": "octo/repo"},
            "pull_request": {
                "number": 7,
                "id": 9001,
                "html_url": "https://github.com/octo/repo/pull/7",
                "title": "Add feature",
                "body": "body",
                "state": "open",
                "user": {"id": 11, "login": "dev"},
                "head": {"sha": "headsha"},
                "base": {"sha": "basesha"},
            },
            "action": action,
        }

    @patch("core.tasks.review_tasks.process_pr_review")
    @patch("core.tasks.review_tasks.Review")
    @patch("core.tasks.review_tasks.PullRequest")
    @patch("core.tasks.review_tasks.Repository")
    def test_opened_pull_request_enqueues_review(self, repo_cls, pr_cls, review_cls, proc):
        repo = MagicMock(id=1)
        repo.owner.id = 42
        repo_cls.objects.get.return_value = repo
        repo_cls.DoesNotExist = _exception_class("DoesNotExist")
        pr = MagicMock(id=5)
        pr_cls.objects.update_or_create.return_value = (pr, True)
        review_cls.objects.get_or_create.return_value = (MagicMock(status="pending"), True)

        review_tasks.process_webhook_event("pull_request", self._pr_event())

        proc.delay.assert_called_once()

    @patch("core.tasks.review_tasks.process_pr_review")
    @patch("core.tasks.review_tasks.Review")
    @patch("core.tasks.review_tasks.PullRequest")
    @patch("core.tasks.review_tasks.Repository")
    def test_closed_pull_request_does_not_enqueue(self, repo_cls, pr_cls, review_cls, proc):
        repo_cls.objects.get.return_value = MagicMock(id=1)
        repo_cls.DoesNotExist = _exception_class("DoesNotExist")
        pr_cls.objects.update_or_create.return_value = (MagicMock(id=5), False)

        review_tasks.process_webhook_event("pull_request", self._pr_event(action="closed"))

        proc.delay.assert_not_called()
        review_cls.objects.get_or_create.assert_not_called()

    @patch("core.tasks.review_tasks.Repository")
    def test_unknown_repository_is_logged_and_skipped(self, repo_cls):
        repo_cls.DoesNotExist = _exception_class("DoesNotExist")
        repo_cls.objects.get.side_effect = repo_cls.DoesNotExist

        # Should not raise.
        review_tasks.process_webhook_event("pull_request", self._pr_event())

    def test_missing_pull_request_data_returns_early(self):
        review_tasks.process_webhook_event("pull_request", {"action": "opened"})

    @patch("core.tasks.review_tasks.Commit")
    @patch("core.tasks.review_tasks.Repository")
    def test_push_event_records_commits(self, repo_cls, commit_cls):
        repo_cls.objects.get.return_value = MagicMock(id=1)
        repo_cls.DoesNotExist = _exception_class("DoesNotExist")
        commit_cls.objects.update_or_create.return_value = (MagicMock(commit_hash="abcdef1234567"), True)

        event = {
            "repository": {"full_name": "octo/repo"},
            "commits": [
                {
                    "id": "abcdef1234567",
                    "message": "fix",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "url": "https://github.com/octo/repo/commit/abcdef1234567",
                    "author": {"id": 3, "name": "Dev", "username": "dev"},
                }
            ],
        }
        review_tasks.process_webhook_event("push", event)

        commit_cls.objects.update_or_create.assert_called_once()

    def test_unconfigured_event_type_is_ignored(self):
        # No patching needed; the branch only logs.
        review_tasks.process_webhook_event("issues", {"action": "opened"})


class ProcessPrReviewTests(unittest.TestCase):
    def _review_result(self):
        return {
            "review_data": {"reviews": [{"file": "a.py"}], "final_result": "ok"},
            "thread_id": "thread-1",
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

    @patch("core.tasks.review_tasks.GitHubService")
    @patch("core.tasks.review_tasks.LLMUsage")
    @patch("core.tasks.review_tasks.Thread")
    @patch("core.tasks.review_tasks.User")
    @patch("core.tasks.review_tasks.LangGraphClient")
    @patch("core.tasks.review_tasks.Review")
    @patch("core.tasks.review_tasks.PullRequest")
    @patch("core.tasks.review_tasks.Repository")
    def test_happy_path_completes_review(
        self, repo_cls, pr_cls, review_cls, client_cls, user_cls, thread_cls, usage_cls, gh_cls
    ):
        repo = MagicMock(
            coding_standards=[], code_metrics=[], llm_preference="gpt-4", repo_name="octo/repo"
        )
        repo.owner.id = 42
        repo_cls.objects.get.return_value = repo
        repo_cls.DoesNotExist = _exception_class("RepoMissing")
        pr_cls.objects.get.return_value = MagicMock(id=5, pr_number=7)
        pr_cls.DoesNotExist = _exception_class("PrMissing")
        review = MagicMock(id=3, status="in_progress")
        review_cls.objects.get_or_create.return_value = (review, True)

        client = client_cls.return_value
        client.initialize = AsyncMock()
        client.review_agent = MagicMock()
        client.generate_review = AsyncMock(return_value=self._review_result())

        user_cls.objects.get.return_value = MagicMock(username="dev")

        with patch.object(review_tasks, "settings") as settings_mock:
            settings_mock.FRONTEND_URL = "https://app.example.com"
            settings_mock.DEFAULT_LLM_MODEL = "gpt-4"
            event = {"pull_request": {"user": {"id": 11, "login": "dev"}}}
            review_tasks.process_pr_review(event, 1, 5, triggering_user_id=42)

        self.assertEqual(review.status, "completed")
        review.save.assert_called()
        thread_cls.objects.create.assert_called_once()
        usage_cls.objects.create.assert_called_once()

    @patch("core.tasks.review_tasks.Repository")
    def test_missing_repository_is_handled(self, repo_cls):
        repo_cls.DoesNotExist = _exception_class("RepoMissing")
        repo_cls.objects.get.side_effect = repo_cls.DoesNotExist

        # Should not raise even though the repository is missing.
        review_tasks.process_pr_review({"pull_request": {}}, 1, 5)


class ProcessCommitReviewTests(unittest.TestCase):
    @patch("core.tasks.review_tasks.GitHubService")
    @patch("core.tasks.review_tasks.LLMUsage")
    @patch("core.tasks.review_tasks.Thread")
    @patch("core.tasks.review_tasks.User")
    @patch("core.tasks.review_tasks.LangGraphClient")
    @patch("core.tasks.review_tasks.Review")
    @patch("core.tasks.review_tasks.Commit")
    @patch("core.tasks.review_tasks.Repository")
    def test_happy_path_completes_commit_review(
        self, repo_cls, commit_cls, review_cls, client_cls, user_cls, thread_cls, usage_cls, gh_cls
    ):
        repo = MagicMock(
            coding_standards=[], code_metrics=[], llm_preference="gpt-4",
            repo_name="octo/repo", github_native_id="gh-1",
        )
        repo.owner.username = "dev"
        repo.owner.github_id = "gh-99"
        repo_cls.objects.get.return_value = repo
        repo_cls.DoesNotExist = _exception_class("RepoMissing")
        commit = MagicMock(id=2, commit_hash="abcdef1234567", message="msg", url="u", author_github_id="gh-3")
        commit.timestamp = None
        commit_cls.objects.get.return_value = commit
        commit_cls.DoesNotExist = _exception_class("CommitMissing")
        review = MagicMock(id=8, status="in_progress")
        review_cls.objects.get_or_create.return_value = (review, True)

        client = client_cls.return_value
        client.initialize = AsyncMock()
        client.review_agent = MagicMock()
        client.generate_review = AsyncMock(
            return_value={
                "review_data": {"reviews": []},
