"""Unit tests for the GitHub service client in ``core.services``.

The aiohttp session is replaced with a lightweight async-context-manager fake so
the HTTP methods can be exercised without real network calls.
"""

import hashlib
import hmac
import unittest
from unittest.mock import patch

import django

django.setup()

from core.services import GitHubService


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    async def json(self):
        return self._data


class _FakeSession:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def get(self, *args, **kwargs):
        return self._response

    def post(self, *args, **kwargs):
        return self._response


class GitHubServiceAuthTests(unittest.TestCase):
    def test_token_sets_authorization_header(self):
        service = GitHubService(user_token="gho_token")
        self.assertEqual(service.headers["Authorization"], "token gho_token")

    def test_no_token_has_no_authorization_header(self):
        service = GitHubService()
        self.assertNotIn("Authorization", service.headers)


class GitHubServiceTokenRequiredTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_user_info_requires_token(self):
