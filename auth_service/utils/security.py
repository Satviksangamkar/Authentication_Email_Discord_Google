import time
from jose import jwt
from passlib.context import CryptContext
from config import settings

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# Add token version to JWT creation
def create_jwt(data: dict, ttl: int = settings.ACCESS_TTL) -> str:
    # Ensure version is included in token
    if "ver" not in data:
        data["ver"] = "1"  # Default version
    
    payload = {**data, "exp": time.time() + ttl}
    return jwt.encode(payload, settings.JWT_SECRET, settings.JWT_ALG)
# Update decode_jwt function
def decode_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, [settings.JWT_ALG])
        
        # Check expiration
        if payload.get("exp", 0) < time.time():
            return {}
            
        # Validate required claims
        if not payload.get("sub"):
            return {}
            
        return payload
    except jwt.JWTError:
        return {}