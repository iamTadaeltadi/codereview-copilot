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
                'user': {'id': 55},
                'state': 'closed',
            },
            'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}},
        }

        await handler.handle_pull_request(payload)

        mock_delay.assert_not_called()

    @patch('core.webhooks.handlers.process_webhook_event.delay')
    @patch('core.webhooks.handlers.PullRequest.objects.aupdate_or_create', new_callable=AsyncMock)
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock)
    async def test_handle_pull_request_queues_review_for_reopened_pr(self, mock_repo_get, mock_pr_update, mock_delay):
        handler = GitHubWebhookHandler()
        mock_repo_get.return_value = Mock()
        mock_pr_update.return_value = (Mock(), False)
        payload = {
            'action': 'reopened',
            'pull_request': {
                'number': 19,
                'html_url': 'https://github.com/org/repo/pull/19',
                'title': 'Reopened review',
                'user': {'id': 66},
                'state': 'open',
            },
            'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}},
        }

        await handler.handle_pull_request(payload)

        mock_delay.assert_called_once_with('pull_request', payload)

    @patch('core.webhooks.handlers.logger')
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock, side_effect=Exception('missing repo'))
    async def test_handle_pull_request_logs_processing_errors(self, _mock_repo_get, mock_logger):
        handler = GitHubWebhookHandler()
        payload = {
            'action': 'opened',
            'pull_request': {'number': 20, 'html_url': 'url', 'title': 'PR', 'user': {'id': 1}, 'state': 'open'},
            'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}},
        }

        with self.assertRaises(Exception):
            await handler.handle_pull_request(payload)

        self.assertTrue(mock_logger.error.called)

    @patch('core.webhooks.handlers.Commit.objects.aupdate_or_create', new_callable=AsyncMock)
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock)
    async def test_handle_push_updates_each_commit(self, mock_repo_get, mock_commit_update):
        handler = GitHubWebhookHandler()
        mock_repo_get.return_value = Mock()
        payload = {
            'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}},
            'commits': [
                {'id': 'abc', 'author': {'id': 1}, 'message': 'First', 'url': 'https://github.com/org/repo/commit/abc', 'timestamp': '2026-05-19T10:00:00Z'},
                {'id': 'def', 'author': {'id': 2}, 'message': 'Second', 'url': 'https://github.com/org/repo/commit/def', 'timestamp': '2026-05-19T11:00:00Z'},
            ],
        }

        await handler.handle_push(payload)

        self.assertEqual(mock_commit_update.await_count, 2)

    @patch('core.webhooks.handlers.logger')
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock, side_effect=Exception('missing repo'))
    async def test_handle_push_logs_processing_errors(self, _mock_repo_get, mock_logger):
        handler = GitHubWebhookHandler()
        payload = {'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}}, 'commits': []}

        with self.assertRaises(Exception):
            await handler.handle_push(payload)

        self.assertTrue(mock_logger.error.called)

    @patch('core.webhooks.handlers.RepoCollaborator.objects.aupdate_or_create', new_callable=AsyncMock)
    @patch('core.webhooks.handlers.User.objects.aget_or_create', new_callable=AsyncMock)
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock)
    async def test_handle_member_added_creates_collaborator(self, mock_repo_get, mock_user_get_or_create, mock_collab_update):
        handler = GitHubWebhookHandler()
        mock_repo = Mock()
        mock_user = Mock()
        mock_repo_get.return_value = mock_repo
        mock_user_get_or_create.return_value = (mock_user, True)
        payload = {
            'action': 'added',
            'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}},
            'member': {'id': 77, 'login': 'new-reviewer', 'avatar_url': 'https://avatars.example/new-reviewer'},
        }

        await handler.handle_member(payload)

        mock_user_get_or_create.assert_awaited_once()
        mock_collab_update.assert_awaited_once()
        _args, kwargs = mock_collab_update.await_args
        self.assertIs(kwargs['user'], mock_user)
        self.assertNotIsInstance(kwargs['user'], tuple)

    @patch('core.webhooks.handlers.User.objects.aget_or_create', new_callable=AsyncMock)
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock)
    async def test_handle_member_added_passes_stringified_github_id(self, mock_repo_get, mock_user_get_or_create):
        handler = GitHubWebhookHandler()
        mock_repo_get.return_value = Mock()
        mock_user_get_or_create.return_value = (Mock(), True)
        payload = {
            'action': 'added',
            'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}},
            'member': {'id': 12345, 'login': 'new-reviewer', 'avatar_url': 'https://avatars.example/new-reviewer'},
        }

        with patch('core.webhooks.handlers.RepoCollaborator.objects.aupdate_or_create', new_callable=AsyncMock):
            await handler.handle_member(payload)

        _args, kwargs = mock_user_get_or_create.await_args
        self.assertEqual(kwargs['github_id'], '12345')

    @patch('core.webhooks.handlers.RepoCollaborator.objects.filter')
    @patch('core.webhooks.handlers.User.objects.aget', new_callable=AsyncMock)
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock)
    async def test_handle_member_removed_deletes_collaborator(self, mock_repo_get, mock_user_get, mock_filter):
        handler = GitHubWebhookHandler()
        mock_repo_get.return_value = Mock()
        mock_user_get.return_value = Mock()
        filtered = Mock()
        filtered.adelete = AsyncMock()
        mock_filter.return_value = filtered
        payload = {
            'action': 'removed',
            'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}},
            'member': {'id': 88, 'login': 'former-reviewer'},
        }

        await handler.handle_member(payload)

        filtered.adelete.assert_awaited_once()

    @patch('core.webhooks.handlers.logger')
    @patch('core.webhooks.handlers.User.objects.aget', new_callable=AsyncMock, side_effect=Exception('missing user'))
    @patch('core.webhooks.handlers.Repository.objects.aget', new_callable=AsyncMock)
    async def test_handle_member_removed_logs_missing_user_errors(self, mock_repo_get, _mock_user_get, mock_logger):
        handler = GitHubWebhookHandler()
        mock_repo_get.return_value = Mock()
        payload = {
            'action': 'removed',
            'repository': {'name': 'repo', 'full_name': 'org/repo', 'owner': {'login': 'org'}},
            'member': {'id': 99, 'login': 'missing-user'},
        }

        with self.assertRaises(Exception):
            await handler.handle_member(payload)

        self.assertTrue(mock_logger.error.called)


if __name__ == '__main__':
    unittest.main()
