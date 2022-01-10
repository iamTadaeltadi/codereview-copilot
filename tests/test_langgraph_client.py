"""Unit tests for the LangGraph client wrapper.

The langgraph-sdk and langsmith network clients are mocked so the review and
feedback flows can be exercised without contacting a live LangGraph server.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import django

django.setup()

from core.langgraph_client import client as client_module
from core.langgraph_client.client import LangGraphClient


def _build_client():
    with patch.object(client_module, "get_client") as get_client:
        get_client.return_value = MagicMock()
        instance = LangGraphClient()
    return instance


class InitializeTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_fetches_assistants(self):
        instance = _build_client()
        instance.client.assistants.get = AsyncMock(side_effect=[{"assistant_id": "review"}, {"assistant_id": "feedback"}])

        with patch.object(client_module, "Client") as langsmith_cls:
            langsmith_cls.return_value = MagicMock()
            await instance.initialize()

        self.assertEqual(instance.review_agent, {"assistant_id": "review"})
        self.assertEqual(instance.feedback_agent, {"assistant_id": "feedback"})

    async def test_initialize_handles_errors(self):
        instance = _build_client()
        instance.client.assistants.get = AsyncMock(side_effect=RuntimeError("boom"))

        await instance.initialize()

        self.assertIsNone(instance.review_agent)
        self.assertIsNone(instance.feedback_agent)


class GetUserTokenTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_token_for_known_user(self):
        instance = _build_client()
        user = MagicMock(github_access_token="gho_token")
        with patch.object(client_module, "User") as user_cls:
            user_cls.objects.aget = AsyncMock(return_value=user)
            token = await instance._get_user_github_token("gh-1")
        self.assertEqual(token, "gho_token")

    async def test_returns_none_for_missing_user(self):
        instance = _build_client()
        with patch.object(client_module, "User") as user_cls:
            user_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
            user_cls.objects.aget = AsyncMock(side_effect=user_cls.DoesNotExist)
            token = await instance._get_user_github_token("missing")
        self.assertIsNone(token)


class GenerateReviewTests(unittest.IsolatedAsyncioTestCase):
    def _wire_client(self, instance):
        instance.review_agent = {"assistant_id": "review"}
        instance.langsmith_client = MagicMock()
        instance.langsmith_client.read_run.return_value = MagicMock(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        )
        instance.client.threads.create = AsyncMock(return_value={"thread_id": "t1"})
        instance.client.runs.create = AsyncMock(return_value={"run_id": "r1"})
        instance.client.runs.join = AsyncMock(return_value={})
        instance.client.threads.get_state = AsyncMock(return_value={"values": {"reviews": []}})
        instance._get_user_github_token = AsyncMock(return_value="gho_token")

    async def test_pull_request_review_returns_payload(self):
        instance = _build_client()
        self._wire_client(instance)
        pr_data = {"number": 7, "user": {"login": "dev"}, "base": {"repo": {"name": "repo"}}}

        with patch.object(client_module.time, "sleep"):
            result = await instance.generate_review(pr_data, {"coding_standards": []}, "gh-1")

        self.assertEqual(result["thread_id"], "t1")
        self.assertEqual(result["token_usage"]["input_tokens"], 10)
        instance.client.runs.create.assert_awaited_once()

    async def test_commit_review_extracts_commit_hash(self):
        instance = _build_client()
        self._wire_client(instance)
        pr_data = {
            "commit": {"sha": "abc123"},
            "repository": {"full_name": "octo/repo"},
        }

        with patch.object(client_module.time, "sleep"):
            result = await instance.generate_review(pr_data, {}, "gh-1")

        _, kwargs = instance.client.runs.create.call_args
        self.assertEqual(kwargs["input"]["commit_hash"], "abc123")
        self.assertEqual(result["review_data"], {"reviews": []})


class HandleFeedbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_feedback_returns_feedback_data(self):
        instance = _build_client()
        instance.feedback_agent = {"assistant_id": "feedback"}
        instance.langsmith_client = MagicMock()
        instance.langsmith_client.read_run.return_value = MagicMock(
            prompt_tokens=1, completion_tokens=1, total_tokens=2
        )
        instance.client.runs.create = AsyncMock(return_value={"run_id": "r9"})
        instance.client.runs.join = AsyncMock(return_value={})
        instance.client.threads.get_state = AsyncMock(return_value={"values": {"messages": []}})
        instance._get_user_github_token = AsyncMock(return_value="gho_token")

        with patch.object(client_module.time, "sleep"):
            result = await instance.handle_feedback("please fix", "thread-1", "gh-1")

        self.assertEqual(result["run_id"], "r9")
        self.assertEqual(result["feedback_data"], {"messages": []})


if __name__ == "__main__":
    unittest.main()
