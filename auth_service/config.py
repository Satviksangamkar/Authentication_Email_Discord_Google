import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file in project root
current_dir = Path(__file__).resolve().parent
env_path = current_dir / '.env'

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logger.info(f"Loaded environment variables from {env_path}")
else:
    logger.warning(f".env file not found at {env_path}")

class Settings:
    # Server
    HOST = os.getenv("SERVER_HOST", "127.0.0.1")
    PORT = int(os.getenv("SERVER_PORT", 8000))
    
    # JWT
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me-for-prod")
    JWT_ALG = os.getenv("JWT_ALG", "HS256")
    ACCESS_TTL = int(os.getenv("ACCESS_TTL", 3600))
    
    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 13632))
    REDIS_USERNAME = os.getenv("REDIS_USERNAME", "")
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
    
    # SMTP
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    EMAIL_FROM = os.getenv("EMAIL_FROM")
    
    # Discord
    DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
    DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
    DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://127.0.0.1:8000/auth/discord/callback")
    DISCORD_AUTH_SCOPES = os.getenv("DISCORD_AUTH_SCOPES", "identify email")
    # Add to Settings class
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/authorize")

   
    @classmethod
    def validate(cls):
        """Validate required environment variables"""
        missing = []
        if not cls.REDIS_HOST:
            missing.append("REDIS_HOST")
        if not cls.DISCORD_CLIENT_ID:
            missing.append("DISCORD_CLIENT_ID") 
        if not cls.DISCORD_CLIENT_SECRET:
            missing.append("DISCORD_CLIENT_SECRET")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        logger.info("Configuration validated successfully")
        logger.info(f"Redis: {cls.REDIS_HOST}:{cls.REDIS_PORT}")
        logger.info(f"Discord Client ID: {cls.DISCORD_CLIENT_ID[:10]}...")
        logger.info(f"Discord Redirect URI: {cls.DISCORD_REDIRECT_URI}")

# Create an instance of Settings
settings = Settings()

# Validate configuration on import (optional - you might want to do this elsewhere)
try:
    settings.validate()
except ValueError as e:
    logger.error(f"Configuration validation failed: {e}")
    