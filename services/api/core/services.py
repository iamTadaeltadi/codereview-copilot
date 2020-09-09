import requests
from django.conf import settings
import secrets
import urllib.parse
import aiohttp
import hmac
import hashlib

GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_USER_URL = "https://api.github.com/user"
GITHUB_API_BASE_URL = "https://api.github.com"

# GitHub OAuth scopes needed (mirroring your FastAPI setup)
GITHUB_SCOPES = [
    "read:user",
    "user:email",
    "repo",
    "repo:status",
    "repo_deployment",
    "public_repo",
    "read:org",
    "repo:invite",
    "security_events"
]

def generate_oauth_state(request):
    """Generate a random state string and store it in the session."""
    state = secrets.token_urlsafe(32)
    request.session['oauth_state'] = state
    return state

def validate_oauth_state(request, state_from_callback):
    """Validate the state from callback against the one stored in session."""
    state_in_session = request.session.pop('oauth_state', None)
    return state_in_session is not None and state_in_session == state_from_callback

def get_github_oauth_redirect_url(state):
    """Constructs the GitHub OAuth redirect URL."""
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_CALLBACK_URL,
        "scope": " ".join(GITHUB_SCOPES),
        "state": state,
    }
    return f"{GITHUB_OAUTH_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

def exchange_code_for_github_token(code):
    """Exchanges the authorization code for a GitHub access token."""
    payload = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
    }
    headers = {"Accept": "application/json"}
    response = requests.post(GITHUB_OAUTH_TOKEN_URL, data=payload, headers=headers)
    response.raise_for_status()  # Raise an exception for bad status codes
    return response.json().get("access_token")

def get_github_user_info(github_token):
    """Fetches user information from GitHub API using the access token."""
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    response = requests.get(GITHUB_API_USER_URL, headers=headers)
    response.raise_for_status()
    
    user_data = response.json()
    
    # Attempt to get primary email if available
    email_data = requests.get(f"{GITHUB_API_USER_URL}/emails", headers=headers)
    if email_data.status_code == 200:
