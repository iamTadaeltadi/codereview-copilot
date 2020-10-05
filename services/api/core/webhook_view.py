from django.http import HttpResponse

from .tasks.review_tasks import process_webhook_event
from .models import (
    Repository as DBRepository,
    WebhookEventLog
)
import hashlib
import hmac
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import logging
from django.views.decorators.http import require_POST
import json
logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
async def github_webhook(request):
    """Handle GitHub webhook events"""
    signature = request.headers.get('X-Hub-Signature-256')
    event_type = request.headers.get('X-GitHub-Event')
    delivery_id = request.headers.get('X-GitHub-Delivery')

    if not all([signature, event_type, delivery_id]):
        logger.warning("Webhook request missing required headers (Signature, Event, Delivery ID).")
        return HttpResponse('Missing required headers', status=400)

    # Find repository for this webhook
    repository = None
    try:
        payload = json.loads(request.body.decode('utf-8'))
        repo_full_name = payload.get('repository', {}).get('full_name')
        if repo_full_name:
            try:
                repository = await DBRepository.objects.aget(repo_name=repo_full_name)
            except DBRepository.DoesNotExist:
                logger.warning(f"Repository {repo_full_name} not found in the database.")
    except json.JSONDecodeError:
        logger.warning("Could not parse request body as JSON to identify repository.")

    log_entry, created = await WebhookEventLog.objects.aupdate_or_create(
        event_id=delivery_id,
        defaults={
            'repository':repository,
            'event_type': event_type,
            'payload': {'message': 'Event received, pending verification.'}, # Store raw body initially if possible
            'headers': dict(request.headers),
            'status': 'received'
        }
    )
    if not created:
        log_entry.status = 'received'
        log_entry.repository = repository
        log_entry.error_message = None
        log_entry.processed_at = None
        log_entry.payload = {'message': 'Event re-received, pending verification.'}
        log_entry.headers = dict(request.headers)
        await log_entry.asave()

    # Extract repo info from payload to find the correct secret
    try:
