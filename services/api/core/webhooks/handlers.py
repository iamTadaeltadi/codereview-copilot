import json
import logging
from typing import Dict, Any
from django.conf import settings
from ..models import RepoCollaborator, Repository, PullRequest, Commit, User
from ..tasks.review_tasks import process_webhook_event

logger = logging.getLogger(__name__)

class GitHubWebhookHandler:
    def __init__(self):
        self.supported_events = ['pull_request', 'push', 'member']

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Main handler for GitHub webhook events"""
        if event_type not in self.supported_events:
            logger.warning(f"Unsupported event type: {event_type}")
            return

        try:
            if event_type == 'pull_request':
                await self.handle_pull_request(event_data)
            elif event_type == 'push':
                await self.handle_push(event_data)
            elif event_type == 'member':
                await self.handle_member(event_data)
        except Exception as e:
            logger.error(f"Error handling {event_type} event: {str(e)}")
            raise

    async def handle_pull_request(self, event_data: Dict[str, Any]) -> None:
        """Handle pull request events"""
        action = event_data.get('action')
        pr_data = event_data.get('pull_request', {})
        repo_data = event_data.get('repository', {})
        
        try:
            repo = await Repository.objects.aget(
                repo_name=f"{repo_data['owner']['login']}/{repo_data['name']}"
            )
            
            pr, created = await PullRequest.objects.aupdate_or_create(
                repository=repo,
                pr_number=pr_data['number'],
                defaults={
                    'url': pr_data['html_url'],
                    'title': pr_data['title'],
                    'author_github_id': pr_data['user']['id'],
                    'status': pr_data['state'],
                }
            )

            # Trigger review for new or reopened PRs
            if action in ['opened', 'reopened']:
                process_webhook_event.delay('pull_request', event_data)

        except Repository.DoesNotExist:
            logger.info(f"Repository not registered: {repo_data['full_name']}")
        except Exception as e:
            logger.error(f"Error processing PR event: {str(e)}")
            raise

    async def handle_push(self, event_data: Dict[str, Any]) -> None:
        """Handle push events"""
        repo_data = event_data.get('repository', {})
        commits = event_data.get('commits', [])
        
        try:
