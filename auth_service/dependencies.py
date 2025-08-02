import redis
import logging
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from utils.security import decode_jwt
from utils.redis import redis_client

logger = logging.getLogger(__name__)

# Make OAuth2PasswordBearer optional for cookie-based auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def get_redis():
    """Dependency to get Redis client"""
    try:
        # Test the connection
        ping_result = redis_client.ping()
        if not ping_result:
            raise ConnectionError("Redis ping failed")
        return redis_client
    except Exception as e:
        logger.error(f"Redis connection error in dependency: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )

def validate_token_version(payload: dict, r: redis.Redis):
    """Validate token version against user's current version"""
    user_id = payload.get("sub")
    source = payload.get("source", "regular")
    
    if not user_id:
        logger.error("Token missing 'sub' claim")
        return False
        
    # Determine Redis key based on source
    if source == "discord":
        redis_key = f"discord_user:{user_id}"
    elif source == "google":
        redis_key = f"google_user:{user_id}"
    else:  # regular user
        try:
            user_id = int(user_id)  # Convert to integer for regular users
        except (ValueError, TypeError):
            logger.error(f"Invalid user_id format for regular user: {user_id}")
            return False
        redis_key = f"user:{user_id}"
        
    try:
        user = r.hgetall(redis_key)
    except Exception as e:
        logger.error(f"User lookup error: {e}")
        return False
        
    if not user:
        logger.error(f"User {user_id} not found")
        return False
        
    token_version = payload.get("ver")
    current_version = user.get("token_version", "1")
    
    # Handle bytes from Redis
    if isinstance(current_version, bytes):
        current_version = current_version.decode()
    
    # Add detailed logging for debugging
    logger.info(
        f"Token version check: user={user_id}, "
        f"token_ver={token_version}, current_ver={current_version}, "
        f"source={source}"
    )
    
    return str(token_version) == str(current_version)

def get_discord_user(r: redis.Redis, discord_id: str) -> dict:
    """Get Discord user data from Redis"""
    user_data = r.hgetall(f"discord_user:{discord_id}")
    
    # Convert bytes to strings if needed
    if user_data:
        return {k.decode() if isinstance(k, bytes) else k: 
                v.decode() if isinstance(v, bytes) else v 
                for k, v in user_data.items()}
    return {}

def get_google_user_from_redis(r: redis.Redis, google_id: str) -> dict:
    user_data = r.hgetall(f"google_user:{google_id}")
    if user_data:
        return {k.decode() if isinstance(k, bytes) else k: 
                v.decode() if isinstance(v, bytes) else v 
                for k, v in user_data.items()}
    return {}

def get_current_user(request: Request, r=Depends(get_redis)):
    # Extract token from cookies
    token = (
        request.cookies.get("google_access_token") or
        request.cookies.get("discord_access_token") or
        request.cookies.get("access_token")
    )
    
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    
    try:
        # Decode JWT token
        payload = decode_jwt(token)
    except Exception as e:
        logger.error(f"Token decode error: {e}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    
    # Validate token version
    if not validate_token_version(payload, r):
        logger.warning(f"Token version mismatch for user {payload.get('sub')}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    
    # Get user source from payload
    source = payload.get("source", "regular")
    user_id = payload.get("sub")
    
    # Retrieve user data based on source
    if source == "discord":
        user = get_discord_user(r, user_id)
    elif source == "google":
        user = get_google_user_from_redis(r, user_id)
    else:  # regular email login
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid user_id format: {user_id}")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid user")
        user_data = r.hgetall(f"user:{user_id}")
        user = {k.decode(): v.decode() for k, v in user_data.items()} if user_data else None
    
    if not user:
        logger.error(f"User {user_id} not found in database")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    
    # Add source to user object for later reference
    user["source"] = source
    
    # Print success message ONLY on initial login
    if request.url.path == "/login":
        print("Login successful")  # Simple success message
    
    return user