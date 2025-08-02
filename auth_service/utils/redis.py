import redis
import json
import logging
from config import settings

logger = logging.getLogger(__name__)

def create_redis_client():
    """Create and test Redis connection"""
    try:
        if not settings.REDIS_HOST:
            raise RuntimeError("Redis configuration is incomplete")
        
        logger.info(f"Connecting to Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        
        # Build connection pool with more robust settings
        pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            username=settings.REDIS_USERNAME or None,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
            socket_connect_timeout=10,
            socket_timeout=10,
            health_check_interval=30,
            max_connections=10
        )
        
        # Create client
        client = redis.Redis(connection_pool=pool)
        
        # Test connection
        ping_result = client.ping()
        if not ping_result:
            raise ConnectionError("Redis ping returned False")
        
        logger.info(f"✅ Redis connection successful - ping result: {ping_result}")
        
        # Test basic operations
        test_key = "test_connection"
        client.set(test_key, "test_value", ex=10)
        test_value = client.get(test_key)
        if test_value != "test_value":
            raise ConnectionError("Redis read/write test failed")
        client.delete(test_key)
        
        logger.info("✅ Redis read/write test successful")
        return client
        
    except (redis.ConnectionError, redis.AuthenticationError) as e:
        logger.error(f"Redis connection failed: {e}")
        raise RuntimeError(f"Redis connection failed: {e}") from e
    except Exception as e:
        logger.error(f"Redis initialization error: {e}")
        raise


# Initialize Redis client
try:
    redis_client = create_redis_client()
    logger.info("Redis client initialized successfully")
except Exception as e:
    logger.critical(f"Failed to initialize Redis: {e}")
    raise
# ADD THE NEW HELPER FUNCTIONS HERE:
def save_discord_state(r, state: str, data: dict):
    """Save Discord state with better error handling"""
    try:
        key = f"discord_state:{state}"
        result = r.setex(key, 600, json.dumps(data))  # 10 minutes
        
        # Verify immediately
        verification = r.get(key)
        if not verification:
            raise RuntimeError("State not saved properly")
            
        logger.info(f"✅ Discord state saved: {key}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save Discord state: {e}")
        raise


def get_discord_state(r, state: str):
    """Get Discord state with better error handling"""
    try:
        key = f"discord_state:{state}"
        data = r.get(key)
        
        if not data:
            # Check if key existed but expired
            exists = r.exists(key)
            logger.error(f"State not found: {key}, exists: {exists}")
            return None
            
        logger.info(f"✅ Discord state retrieved: {key}")
        return json.loads(data)
    except Exception as e:
        logger.error(f"❌ Failed to get Discord state: {e}")
        return None


def delete_discord_state(r, state: str):
    """Delete Discord state with logging"""
    try:
        key = f"discord_state:{state}"
        result = r.delete(key)
        if result:
            logger.info(f"✅ Discord state deleted: {key}")
        else:
            logger.warning(f"⚠️ Discord state already deleted: {key}")
        return result
    except Exception as e:
        logger.error(f"❌ Failed to delete Discord state: {e}")
        return False


