import unittest
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlparse

from django.test import RequestFactory

from core import services


class OAuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_generate_and_validate_oauth_state(self):
        request = self.factory.get('/')
        request.session = {}

        state = services.generate_oauth_state(request)

        self.assertEqual(request.session['oauth_state'], state)
        self.assertTrue(services.validate_oauth_state(request, state))
        self.assertNotIn('oauth_state', request.session)

    def test_validate_oauth_state_rejects_mismatch(self):
        request = self.factory.get('/')
        request.session = {'oauth_state': 'expected'}

        self.assertFalse(services.validate_oauth_state(request, 'different'))
        self.assertNotIn('oauth_state', request.session)

    @patch.object(services.settings, 'GITHUB_CLIENT_ID', 'client-123')
    @patch.object(services.settings, 'GITHUB_CALLBACK_URL', 'https://app.example.com/callback')
    def test_get_github_oauth_redirect_url_contains_expected_params(self):
        redirect_url = services.get_github_oauth_redirect_url('state-xyz')
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, 'https')
        self.assertEqual(parsed.netloc, 'github.com')
        self.assertEqual(params['client_id'], ['client-123'])
        self.assertEqual(params['redirect_uri'], ['https://app.example.com/callback'])
        self.assertEqual(params['state'], ['state-xyz'])
        self.assertIn('repo', params['scope'][0])


class GitHubApiServiceTests(unittest.TestCase):
    @patch('core.services.requests.post')
    def test_exchange_code_for_github_token_returns_access_token(self, mock_post):
        response = Mock()
        response.json.return_value = {'access_token': 'gho_abc'}
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        token = services.exchange_code_for_github_token('oauth-code')

        self.assertEqual(token, 'gho_abc')
        mock_post.assert_called_once()

    @patch('core.services.requests.get')
    def test_get_github_user_info_prefers_verified_primary_email(self, mock_get):
        user_response = Mock()
        user_response.raise_for_status.return_value = None
        user_response.json.return_value = {'id': 1, 'login': 'tadael'}

        email_response = Mock()
        email_response.status_code = 200
        email_response.json.return_value = [
            {'email': 'secondary@example.com', 'primary': False, 'verified': True},
            {'email': 'primary@example.com', 'primary': True, 'verified': True},
        ]

        mock_get.side_effect = [user_response, email_response]

        result = services.get_github_user_info('token-123')

