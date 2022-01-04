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

        self.assertEqual(result['login'], 'tadael')
        self.assertEqual(result['email'], 'primary@example.com')
        self.assertEqual(mock_get.call_count, 2)

    @patch('core.services.requests.get')
    def test_get_all_repo_collaborators_handles_pagination(self, mock_get):
        first_page = Mock()
        first_page.raise_for_status.return_value = None
        first_page.json.return_value = [{'id': i} for i in range(100)]

        second_page = Mock()
        second_page.raise_for_status.return_value = None
        second_page.json.return_value = [{'id': 101}, {'id': 102}]

        mock_get.side_effect = [first_page, second_page]

        collaborators = services.get_all_repo_collaborators_from_github('owner', 'repo', 'token-123')

        self.assertEqual(len(collaborators), 102)
        self.assertEqual(collaborators[-1]['id'], 102)
        self.assertEqual(mock_get.call_count, 2)

    @patch('core.services.requests.get')
    def test_get_user_repos_from_github_passes_pagination_params(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [{'id': 1, 'full_name': 'owner/repo'}]
        mock_get.return_value = response

        result = services.get_user_repos_from_github('token-123', page=2, per_page=50)

        self.assertEqual(result[0]['full_name'], 'owner/repo')
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs['params']['page'], 2)
        self.assertEqual(kwargs['params']['per_page'], 50)


if __name__ == '__main__':
    unittest.main()


class GitHubApiServiceEdgeCaseTests(unittest.TestCase):
    @patch('core.services.requests.get')
    def test_get_github_user_info_falls_back_to_first_email_when_no_primary_verified(self, mock_get):
        user_response = Mock()
        user_response.raise_for_status.return_value = None
        user_response.json.return_value = {'id': 2, 'login': 'fallback-user'}

        email_response = Mock()
        email_response.status_code = 200
        email_response.json.return_value = [
            {'email': 'fallback@example.com', 'primary': False, 'verified': False}
        ]
        mock_get.side_effect = [user_response, email_response]

        result = services.get_github_user_info('token-456')

        self.assertEqual(result['email'], 'fallback@example.com')

    @patch('core.services.requests.get')
    def test_get_github_user_info_keeps_missing_email_when_email_lookup_fails(self, mock_get):
        user_response = Mock()
        user_response.raise_for_status.return_value = None
        user_response.json.return_value = {'id': 3, 'login': 'no-email-user'}

        email_response = Mock()
        email_response.status_code = 403
        email_response.json.return_value = []
        mock_get.side_effect = [user_response, email_response]

        result = services.get_github_user_info('token-789')

        self.assertNotIn('email', result)

    @patch('core.services.requests.get')
