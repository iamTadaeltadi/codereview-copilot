import json
import logging
from typing import Dict, Any
import uuid
from celery import shared_task
from django.conf import settings
import asyncio
from ..models import Review, Repository, PullRequest, LLMUsage, User, Commit, Thread
from core.langgraph_client.client import LangGraphClient
from core.services import GitHubService

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def process_webhook_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
    """Process webhook events asynchronously by dispatching to specific task handlers."""
    logger.info(f"Received webhook event: {event_type} with action {event_data.get('action')}")
    try:
        if event_type == 'pull_request':
            repo_data = event_data.get('repository', {})
            pr_data = event_data.get('pull_request', {})
            action = event_data.get('action')

            if not repo_data or not pr_data or not action:
                logger.error("Missing repository, pull_request, or action data in PR webhook event.")
                return

            repo_full_name = repo_data.get('full_name')
            pr_number = pr_data.get('number')

            if not repo_full_name or not pr_number:
                logger.error(f"Missing repo_full_name or pr_number for PR event. Data: {event_data}")
                return
            
            try:
                repo = Repository.objects.get(repo_name=repo_full_name)
                pr, pr_created = PullRequest.objects.update_or_create(
                    repository=repo,
                    pr_number=pr_number,
                    defaults={
                        'url': pr_data.get('html_url'),
                        'title': pr_data.get('title'),
                        # 'pr_author': pr_data.get('user', {}).get('login'),
                        'author_github_id': pr_data.get('user', {}).get('id'),
                        'body': pr_data.get('body'),
                        'status': pr_data.get('state'),
                        'pr_github_id': str(pr_data.get('id')),
                        'head_sha': pr_data.get('head', {}).get('sha'),
                        'base_sha': pr_data.get('base', {}).get('sha'),
                        # 'updated_at_gh': pr_data.get('updated_at'),
                    }
                )
                if pr_created:
                    logger.info(f"PR #{pr_number} for repo {repo_full_name} CREATED in DB via webhook task.")
                else:
                    logger.info(f"PR #{pr_number} for repo {repo_full_name} UPDATED in DB via webhook task.")

                if action in ['opened', 'reopened', 'synchronize']:
                    review, review_created = Review.objects.get_or_create(
                        repository=repo,
                        pull_request=pr,
                        status__in=['pending', 'in_progress'],
                        defaults={
                            'status': 'pending',
                            'review_data': {'message': f'Review initiated by webhook action: {action}.'}
                        }
                    )
                    if review_created:
                        logger.info(f"PENDING review record CREATED for PR {pr.id}. Enqueuing process_pr_review.")
                        process_pr_review.delay(event_data, repo.id, pr.id, triggering_user_id=repo.owner.id)
                    elif review.status == 'pending':
                        logger.info(f"PENDING review record already exists for PR {pr.id}. Enqueuing process_pr_review.")
                        process_pr_review.delay(event_data, repo.id, pr.id, triggering_user_id=repo.owner.id)
                    else:
                        logger.info(f"Review for PR {pr.id} already in progress or completed. Status: {review.status}")
                else:
                    logger.info(f"Skipping AI review for PR action '{action}' on PR {pr.id}")
            except Repository.DoesNotExist:
                logger.warning(f"Repository {repo_full_name} not found in DB. Cannot process PR event.")
