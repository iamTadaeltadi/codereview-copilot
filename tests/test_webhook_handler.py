import unittest
from unittest.mock import AsyncMock, Mock, patch

import django

django.setup()

from core.webhooks.handlers import GitHubWebhookHandler


class GitHubWebhookHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_event_ignores_unsupported_event_types(self):
        handler = GitHubWebhookHandler()
        with patch.object(handler, 'handle_pull_request', new_callable=AsyncMock) as pull_request_handler:
            await handler.handle_event('issues', {'action': 'opened'})

        pull_request_handler.assert_not_called()

    @patch.object(GitHubWebhookHandler, 'handle_push', new_callable=AsyncMock)
    async def test_handle_event_dispatches_push_events(self, mock_handle_push):
        handler = GitHubWebhookHandler()

        await handler.handle_event('push', {'commits': []})

        mock_handle_push.assert_awaited_once()

    @patch.object(GitHubWebhookHandler, 'handle_member', new_callable=AsyncMock)
    async def test_handle_event_dispatches_member_events(self, mock_handle_member):
        handler = GitHubWebhookHandler()

        await handler.handle_event('member', {'action': 'added'})

        mock_handle_member.assert_awaited_once()

    @patch.object(GitHubWebhookHandler, 'handle_pull_request', new_callable=AsyncMock, side_effect=RuntimeError('boom'))
    async def test_handle_event_reraises_processing_errors(self, _mock_handle_pr):
        handler = GitHubWebhookHandler()

        with self.assertRaises(RuntimeError):
            await handler.handle_event('pull_request', {'action': 'opened'})

    @patch('core.webhooks.handlers.process_webhook_event.delay')
    @patch('core.webhooks.handlers.PullRequest.objects.aupdate_or_create', new_callable=AsyncMock)
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock)
    async def test_handle_pull_request_queues_review_for_opened_pr(self, mock_repo_get, mock_pr_update, mock_delay):
        handler = GitHubWebhookHandler()
        mock_repo_get.return_value = Mock()
        mock_pr_update.return_value = (Mock(), True)
        payload = {
            'action': 'opened',
            'pull_request': {
                'number': 17,
                'html_url': 'https://github.com/org/repo/pull/17',
                'title': 'Improve coverage',
                'user': {'id': 44},
                'state': 'open',
            },
            'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}},
        }

        await handler.handle_pull_request(payload)

        mock_repo_get.assert_awaited_once()
        mock_pr_update.assert_awaited_once()
        mock_delay.assert_called_once_with('pull_request', payload)

    @patch('core.webhooks.handlers.process_webhook_event.delay')
    @patch('core.webhooks.handlers.PullRequest.objects.aupdate_or_create', new_callable=AsyncMock)
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock)
    async def test_handle_pull_request_does_not_queue_closed_pr(self, mock_repo_get, mock_pr_update, mock_delay):
        handler = GitHubWebhookHandler()
        mock_repo_get.return_value = Mock()
        mock_pr_update.return_value = (Mock(), False)
        payload = {
            'action': 'closed',
            'pull_request': {
                'number': 18,
                'html_url': 'https://github.com/org/repo/pull/18',
                'title': 'Close review',
