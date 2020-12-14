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


