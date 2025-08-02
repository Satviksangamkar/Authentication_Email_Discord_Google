import requests
import urllib.parse
import uuid  
import logging
from jose import jwt
from utils.security import create_jwt
from config import settings
from utils import discord
logger = logging.getLogger(__name__)

def generate_discord_login_url(state: str, custom_redirect_uri: str = None) -> str:
    """Generate Discord OAuth2 authorization URL with consistent redirect_uri"""
    # Use the same redirect_uri that will be used for token exchange
    redirect_uri = custom_redirect_uri or settings.DISCORD_REDIRECT_URI
    
    params = {
        'client_id': settings.DISCORD_CLIENT_ID,
        'redirect_uri': redirect_uri,  # This must match token exchange
        'response_type': 'code',
        'scope': settings.DISCORD_AUTH_SCOPES,
        'state': state,
        'prompt': 'consent'
    }
    
    auth_url = f"https://discord.com/api/oauth2/authorize?{urllib.parse.urlencode(params)}"
    logger.info(f"Generated Discord auth URL: {auth_url}")
    logger.info(f"Using redirect_uri: {redirect_uri}")
    
    return auth_url


def exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for access token with custom redirect_uri"""
    data = {
        'client_id': settings.DISCORD_CLIENT_ID,
        'client_secret': settings.DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri
    }
        
    response = requests.post(
        'https://discord.com/api/oauth2/token',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Discord token exchange failed: {e.response.text}")
        raise

def get_discord_user(access_token: str) -> dict:
    """Get Discord user information"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    response = requests.get(
        'https://discord.com/api/users/@me',
        headers=headers
    )
    response.raise_for_status()
    return response.json()

def create_auth_token(discord_id: str) -> str:
    """Create JWT token for Discord user with versioning"""
    version = str(uuid.uuid4())
    return create_jwt({
        "sub": discord_id, 
        "source": "discord",
        "ver": version
    })