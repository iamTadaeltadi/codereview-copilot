from django.http import HttpResponseRedirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    User
)

from .services import (
    generate_oauth_state,
    validate_oauth_state,
    get_github_oauth_redirect_url,
    exchange_code_for_github_token,
    get_github_user_info,
)
import requests
import urllib.parse
from django.conf import settings
from urllib.parse import urlencode
import logging
logger = logging.getLogger(__name__)


class GitHubLoginView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        state = generate_oauth_state(request)
        redirect_url = get_github_oauth_redirect_url(state)
        return HttpResponseRedirect(redirect_url)

class GitHubLoginRedirectView(APIView):
    permission_classes = [AllowAny]

    async def get(self, request, *args, **kwargs):
        state = generate_oauth_state()  # Assuming this service function exists
        request.session['github_oauth_state'] = state
        # Assuming get_github_oauth_redirect_url service constructs the full URL
        # It would need GITHUB_CLIENT_ID and GITHUB_SCOPES from settings
        try:
            redirect_url = get_github_oauth_redirect_url(state) # This service might need to be async if it does I/O
            return HttpResponseRedirect(redirect_url)
        except Exception as e:
            error_message = urlencode({"message": "Failed to initiate GitHub login."})
            return HttpResponseRedirect(f"{settings.FRONTEND_URL}/auth/error?{error_message}")

class GitHubCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        code = request.GET.get('code')
        state_from_callback = request.GET.get('state')


        if not code or not state_from_callback:
            error_url = f"{settings.FRONTEND_URL}/auth/error?message={urllib.parse.quote('Missing code or state from GitHub callback.')}"
            return HttpResponseRedirect(error_url)

        if not validate_oauth_state(request, state_from_callback):
            error_url = f"{settings.FRONTEND_URL}/auth/error?message={urllib.parse.quote('Invalid OAuth state.')}"
            return HttpResponseRedirect(error_url)

        try:
            github_token = exchange_code_for_github_token(code)
            if not github_token:
                raise Exception("Failed to retrieve GitHub access token.")

            github_user_info = get_github_user_info(github_token)
            
            # Ensure email is present, if not, try to get it or handle missing email
            user_email = github_user_info.get("email")
