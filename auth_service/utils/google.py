import requests
import logging
from urllib.parse import urlencode
from config import settings

logger = logging.getLogger(__name__)

# Google OAuth endpoints
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

def generate_google_login_url(state: str, redirect_uri: str) -> str:
    """Generate Google OAuth2 authorization URL"""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": redirect_uri,
        "state": state,
        "access_type": "offline",
        "prompt": "consent"
    }
    return f"{AUTHORIZATION_BASE_URL}?{urlencode(params)}"

def exchange_google_code(code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for access token"""
    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    response = requests.post(TOKEN_URL, data=data)
    response.raise_for_status()
    return response.json()

def get_google_user(access_token: str) -> dict:
    """Get Google user information using access token"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(USER_INFO_URL, headers=headers)
    response.raise_for_status()
    return response.json()