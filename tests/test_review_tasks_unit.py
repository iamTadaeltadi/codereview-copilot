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
