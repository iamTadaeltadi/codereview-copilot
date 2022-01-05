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
        with self.assertRaises(ValueError):
            await GitHubService().get_user_info()

    async def test_get_repositories_requires_token(self):
        with self.assertRaises(ValueError):
            await GitHubService().get_repositories()


class GitHubServiceHttpTests(unittest.IsolatedAsyncioTestCase):
    def _patch_session(self, payload):
        session = _FakeSession(_FakeResponse(payload))
        return patch("core.services.aiohttp.ClientSession", return_value=session)

    async def test_get_user_info_returns_payload(self):
        with self._patch_session({"login": "dev"}):
            result = await GitHubService(user_token="t").get_user_info()
        self.assertEqual(result["login"], "dev")

    async def test_get_repositories_returns_payload(self):
        with self._patch_session([{"name": "repo"}]):
            result = await GitHubService(user_token="t").get_repositories()
        self.assertEqual(result[0]["name"], "repo")

    async def test_get_pull_request_returns_payload(self):
        with self._patch_session({"number": 7}):
            result = await GitHubService(user_token="t").get_pull_request("octo", "repo", 7)
        self.assertEqual(result["number"], 7)

    async def test_get_commit_returns_payload(self):
        with self._patch_session({"sha": "abc"}):
            result = await GitHubService(user_token="t").get_commit("octo", "repo", "abc")
        self.assertEqual(result["sha"], "abc")

    async def test_post_pr_comment_returns_payload(self):
        with self._patch_session({"id": 1}):
            result = await GitHubService(user_token="t").post_pr_comment("octo", "repo", 7, "hi")
        self.assertEqual(result["id"], 1)

    async def test_post_commit_comment_returns_payload(self):
        with self._patch_session({"id": 2}):
            result = await GitHubService(user_token="t").post_commit_comment("octo", "repo", "abc", "hi")
        self.assertEqual(result["id"], 2)


class VerifyWebhookSignatureTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_signature_passes(self):
        secret = "shh"
        payload = b'{"event": "push"}'
        digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"sha256={digest}"

        self.assertTrue(
            await GitHubService().verify_webhook_signature(payload, signature, secret)
        )

    async def test_invalid_signature_fails(self):
        self.assertFalse(
            await GitHubService().verify_webhook_signature(b"data", "sha256=bogus", "shh")
        )


if __name__ == "__main__":
    unittest.main()
