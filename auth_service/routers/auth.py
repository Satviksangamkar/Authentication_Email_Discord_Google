import random
import logging
import uuid
import secrets
import time
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from fastapi.responses import RedirectResponse

from utils import discord
from config import settings
from dependencies import oauth2_scheme, get_redis, get_current_user, validate_token_version, get_discord_user, get_google_user_from_redis
from utils.security import hash_password, verify_password, create_jwt, decode_jwt
from utils.email import send_otp_email, send_password_reset_email
from utils.discord import generate_discord_login_url, exchange_code, get_discord_user, create_auth_token
from utils.google import generate_google_login_url, exchange_google_code, get_google_user

router = APIRouter(tags=["Authentication"])
logger = logging.getLogger(__name__)

# --- Pydantic Models ---
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class UpdatePasswordRequest(BaseModel):
    email: EmailStr
    old_password: str
    new_password: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class DiscordLoginRequest(BaseModel):
    redirect_uri: Optional[str] = None

class DiscordCallbackRequest(BaseModel):
    code: str
    state: str

# --- Helper Functions ---
def user_key(uid: int) -> str:
    return f"user:{uid}"

def get_user(r, uid: int) -> dict:
    try:
        return r.hgetall(user_key(uid))
    except Exception as e:
        logger.error(f"Redis error: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, 
            "Database error"
        )

def get_user_by_email(r, email: str) -> dict:
    try:
        uid = r.hget("email_to_id", email)
        if uid:
            return get_user(r, int(uid))
        return {}
    except Exception as e:
        logger.error(f"Redis error: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, 
            "Database error"
        )

def save_user(r, uid: int, data: dict):
    try:
        r.hset(user_key(uid), mapping=data)
        r.hset("email_to_id", data["email"], uid)
    except Exception as e:
        logger.error(f"Redis error: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, 
            "Database error"
        )

def discord_state_key(state: str) -> str:
    return f"discord_state:{state}"

def discord_user_key(discord_id: str) -> str:
    return f"discord_user:{discord_id}"

def clear_competing_tokens(response: RedirectResponse, keep_cookie: str = None):
    """Clear all auth cookies except the current one"""
    cookies_to_clear = ["access_token", "discord_access_token", "google_access_token"]
    
    for cookie in cookies_to_clear:
        if cookie != keep_cookie:
            response.delete_cookie(cookie, path="/")
    
    return response

# --- API Endpoints ---
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    data: RegisterRequest, 
    bg: BackgroundTasks,
    r = Depends(get_redis)
):
    # Check password length
    if len(data.password) < 8:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Password must be at least 8 characters"
        )
    
    if get_user_by_email(r, data.email):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Email already registered"
        )

    # Create new user
    uid = r.incr("user:next_id")
    hashed_pw = hash_password(data.password)
    user = {
        "id": uid,
        "email": data.email,
        "hashed_pw": hashed_pw,
        "is_active": "0",
        "token_version": "1" 
    }
    save_user(r, uid, user)

    # Generate and store OTP
    otp = f"{random.randint(0, 999999):06d}"
    r.setex(f"otp_reg:{data.email}", 300, otp)  # 5 minutes expiration

    # Send OTP by email in background
    bg.add_task(send_otp_email, data.email, otp)

    return {"message": "OTP sent to email", "email": data.email}

@router.post("/verify-registration-otp")
async def verify_registration_otp(
    req: OTPVerifyRequest,
    r = Depends(get_redis)
):
    # Retrieve OTP from Redis
    stored_otp = r.get(f"otp_reg:{req.email}")
    if not stored_otp:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "OTP expired or invalid"
        )
    
    if req.otp != stored_otp:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid OTP"
        )
    
    # Delete the OTP key
    r.delete(f"otp_reg:{req.email}")
    
    # Activate the user
    user = get_user_by_email(r, req.email)
    if not user:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "User not found"
        )
    
    user["is_active"] = "1"
    save_user(r, int(user["id"]), user)
    
    return {"message": "Account activated successfully"}

@router.post("/token")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    r = Depends(get_redis)
):
    user = get_user_by_email(r, form.username)
    if not user or user.get("is_active") != "1":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Inactive or unknown account"
        )
    
    if not verify_password(form.password, user["hashed_pw"]):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid credentials"
        )
    
    # Get current token version
    token_version = user.get("token_version", "1")
    
    token_data = {
        "sub": user["id"], 
        "ver": token_version
    }
    token = create_jwt(token_data)
    
    print("Login successful")
    return {"access_token": token, "token_type": "bearer"}

@router.post("/forgot-password")
async def forgot_password(
    req: ForgotPasswordRequest,
    bg: BackgroundTasks,
    r=Depends(get_redis)
):
    # Always return success to prevent email enumeration
    user = get_user_by_email(r, req.email)
    if not user:
        logger.info(f"Password reset requested for unknown email: {req.email}")
        return {"message": "If the email exists, a reset link has been sent"}

    # Generate unique token
    reset_token = str(uuid.uuid4())
    token_data = {
        "user_id": user["id"],
        "exp": time.time() + 900  # 15 minutes expiration
    }
    jwt_token = create_jwt(token_data)

    # Store in Redis (token as key, user ID as value)
    r.setex(f"pwd_reset:{reset_token}", 900, user["id"])

    # Send email in background
    reset_link = f"https://yourapp.com/reset-password?token={reset_token}"
    bg.add_task(send_password_reset_email, req.email, reset_link)
    
    return {"message": "If the email exists, a reset link has been sent"}

@router.post("/reset-password")
async def reset_password(
    req: ResetPasswordRequest,
    r=Depends(get_redis)
):
    # Validate password length
    if len(req.new_password) < 8:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Password must be at least 8 characters"
        )
    
    # Verify token
    user_id = r.get(f"pwd_reset:{req.token}")
    if not user_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid or expired reset token"
        )
    
    # Get user
    user = get_user(r, int(user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    
    # Update password
    user["hashed_pw"] = hash_password(req.new_password)
    
    # Increment token version - convert to int first
    try:
        current_version = int(user.get("token_version", "0"))
        user["token_version"] = str(current_version + 1)
    except ValueError:
        logger.error(f"Invalid token version for user {user_id}")
        user["token_version"] = "1"
    
    logger.info(
        f"Password reset for user {user_id}. "
        f"Token version updated from {user.get('token_version')} "
        f"to {int(user.get('token_version', '0')) + 1}"
    )
    
    # Save user and delete token
    save_user(r, int(user_id), user)
    r.delete(f"pwd_reset:{req.token}")
    
    return {"message": "Password updated successfully"}

@router.get("/protected")
async def protected_route(token: str = Depends(oauth2_scheme)):
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user_id": payload.get("sub"), "message": "Protected content"}

# Discord OAuth Routes
@router.get("/discord/login")
def discord_login(redirect_uri: Optional[str] = None, r=Depends(get_redis)):
    try:
        # IMPORTANT: OAuth callback is ALWAYS your server endpoint
        oauth_callback = settings.DISCORD_REDIRECT_URI  # http://localhost:8000/auth/discord/callback
        
        # Final destination is where user goes AFTER successful auth
        final_destination = redirect_uri or "http://localhost:8000/"
        
        state = secrets.token_urlsafe(32)
        
        # Store the final destination in state
        state_data = {
            "redirect_uri": final_destination,
            "timestamp": time.time()
        }
        
        logger.info(f"🔄 Discord login initiated")
        logger.info(f"   OAuth callback: {oauth_callback}")
        logger.info(f"   Final destination: {final_destination}")
        logger.info(f"   State: {state}")
        
        # Store in Redis
        redis_key = f"discord_state:{state}"
        try:
            result = r.setex(redis_key, 600, json.dumps(state_data))  # 10 minutes
            
            # Verify storage
            verification = r.get(redis_key)
            if not verification:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to store authentication state"
                )
            
            logger.info(f"✅ State stored successfully")
        except Exception as e:
            logger.error(f"Redis error storing state: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store authentication state"
            )
        
        # Generate Discord auth URL
        auth_url = generate_discord_login_url(state, oauth_callback)
        logger.info(f"🌐 Redirecting to Discord: {auth_url}")
        
        return RedirectResponse(url=auth_url, status_code=307)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Discord login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate Discord login"
        )

@router.get("/auth/discord/callback")
def discord_callback(code: str, state: str, r=Depends(get_redis)):
    try:
        logger.info(f"🔄 Processing Discord callback")
        logger.info(f"   Code: {code[:20]}...")
        logger.info(f"   State: {state}")
        
        # Get state data from Redis
        state_key = f"discord_state:{state}"
        state_data_json = r.get(state_key)
        
        if not state_data_json:
            logger.error(f"❌ Invalid or expired state: {state}")
            
            # Debug: Check existing states
            existing_states = r.keys("discord_state:*")
            logger.info(f"   Existing states in Redis: {len(existing_states)}")
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state parameter"
            )
        
        # Parse state data
        try:
            state_data = json.loads(state_data_json)
            final_destination = state_data.get("redirect_uri", "http://localhost:8000/")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse state data: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid state data format"
            )
        
        # Clean up state immediately
        r.delete(state_key)
        logger.info("🧹 State cleaned up from Redis")
        
        # Exchange code for token using the CORRECT redirect_uri
        logger.info(f"🔄 Exchanging code for token")
        logger.info(f"   Using redirect_uri: {settings.DISCORD_REDIRECT_URI}")
        
        try:
            token_data = exchange_code(code, settings.DISCORD_REDIRECT_URI)
            logger.info("✅ Token exchange successful")
        except Exception as e:
            logger.error(f"❌ Token exchange failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code"
            )
        
        # Get access token
        access_token = token_data.get("access_token")
        if not access_token:
            logger.error("❌ No access_token in Discord response")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid token response from Discord"
            )
        
        # Get Discord user info
        try:
            discord_user = get_discord_user(access_token)
            logger.info(f"✅ Retrieved Discord user: {discord_user.get('username', 'Unknown')}")
        except Exception as e:
            logger.error(f"❌ Failed to get Discord user info: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve user information from Discord"
            )
        
        discord_id = str(discord_user["id"])
        
        # Store Discord user data
        user_data = {
            "id": discord_id,
            "username": discord_user.get("username", ""),
            "email": discord_user.get("email", ""),
            "avatar": discord_user.get("avatar", ""),
            "verified": str(discord_user.get("verified", False)),
            "token_version": "1"
        }
        
        try:
            r.hmset(f"discord_user:{discord_id}", user_data)
            r.expire(f"discord_user:{discord_id}", 3600)  # 1 hour
            logger.info(f"✅ Stored Discord user data for {discord_id}")
        except Exception as e:
            logger.error(f"❌ Failed to store Discord user data: {e}")
            # Continue anyway
        
        # Create JWT token
        try:
            jwt_token = create_auth_token(discord_id)
            logger.info("✅ Created JWT token")
        except Exception as e:
            logger.error(f"❌ Failed to create JWT token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create authentication token"
            )
        
        # Print success message
        print("Login successful")
        
        # Simple success response instead of redirect
        return {
            "message": "Discord authentication successful",
            "user_id": discord_id,
            "username": discord_user.get("username", "")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Discord callback error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Discord authentication failed"
        )

@router.get("/login/google")
def google_login(
    redirect_uri: Optional[str] = None,
    r=Depends(get_redis)
):
    """Initiate Google OAuth login"""
    try:
        # Use configured redirect URI
        oauth_callback = settings.GOOGLE_REDIRECT_URI
        final_destination = redirect_uri or "http://localhost:8000/"
        
        state = secrets.token_urlsafe(32)
        state_data = {
            "redirect_uri": final_destination,
            "timestamp": time.time()
        }
        
        # Store state in Redis
        redis_key = f"google_state:{state}"
        r.setex(redis_key, 600, json.dumps(state_data))  # 10 minutes
        
        # Generate Google auth URL
        auth_url = generate_google_login_url(state, oauth_callback)
        return RedirectResponse(url=auth_url, status_code=307)
    
    except Exception as e:
        logger.error(f"Google login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate Google login"
        )

@router.get("/authorize")
def google_callback(
    code: str,
    state: str,
    r=Depends(get_redis)
):
    """Google OAuth callback handler"""
    try:
        logger.info(f"🔄 Processing Google callback with state: {state}")
        
        # Retrieve state from Redis
        state_key = f"google_state:{state}"
        state_data_json = r.get(state_key)
        
        if not state_data_json:
            logger.error(f"❌ Invalid or expired state: {state}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state parameter"
            )
        
        # Parse state data
        state_data = json.loads(state_data_json)
        final_destination = state_data.get("redirect_uri", "http://localhost:8000/")
        
        # Clean up state
        r.delete(state_key)
        logger.info("🧹 Google state cleaned from Redis")
        
        # Exchange code for tokens
        token_data = exchange_google_code(code, settings.GOOGLE_REDIRECT_URI)
        access_token = token_data.get("access_token")
        
        if not access_token:
            logger.error("❌ No access_token in Google response")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid token response from Google"
            )
        
        # Get Google user info
        google_user = get_google_user(access_token)
        google_id = google_user["sub"]
        
        # Store Google user data
        user_data = {
            "id": google_id,
            "email": google_user.get("email", ""),
            "name": google_user.get("name", ""),
            "picture": google_user.get("picture", ""),
            "verified": str(google_user.get("email_verified", False)),
            "source": "google"
        }
        
        try:
            r.hmset(f"google_user:{google_id}", user_data)
            r.expire(f"google_user:{google_id}", 3600)  # 1 hour
            logger.info(f"✅ Stored Google user data for {google_id}")
        except Exception as e:
            logger.error(f"❌ Failed to store Google user data: {e}")
        
        # Create JWT token
        token_payload = {
            "sub": google_id,
            "source": "google",
            "ver": str(uuid.uuid4())
        }
        jwt_token = create_jwt(token_payload)
        logger.info(f"✅ Created JWT token for Google user {google_id}")
        
        # Print success message
        print("Login successful")
        
        # Simple success response instead of redirect
        return {
            "message": "Google authentication successful",
            "user_id": google_id,
            "email": google_user.get("email", ""),
            "name": google_user.get("name", "")
        }
    
    except Exception as e:
        logger.error(f"❌ Google callback error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google authentication failed"
        )

# Profile route for users
@router.get("/profile")
def get_profile(token: str = Depends(oauth2_scheme), r=Depends(get_redis)):
    """Get user profile information"""
    # Decode and validate token
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validate token version
    if not validate_token_version(payload, r):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user source and data
    source = payload.get("source", "regular")
    user_id = payload.get("sub")
    
    # Get user data based on source
    if source == "google":
        user = get_google_user_from_redis(r, user_id)
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
        return {
            "user_id": user.get("id"),
            "name": user.get("name"),
            "email": user.get("email"),
            "picture": user.get("picture"),
            "verified": user.get("verified"),
            "source": "google"
        }
    elif source == "discord":
        user = get_discord_user(r, user_id)
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
        return {
            "user_id": user.get("id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "avatar": user.get("avatar"),
            "verified": user.get("verified"),
            "source": "discord"
        }
    else:
        # Regular user
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid user")
        user_data = r.hgetall(f"user:{user_id}")
        user = {k.decode(): v.decode() for k, v in user_data.items()} if user_data else None
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
        return {
            "user_id": user.get("id"),
            "email": user.get("email"),
            "is_active": user.get("is_active"),
            "source": "regular"
        }

# Logout endpoint to clear all auth cookies
@router.get("/logout")
def logout():
    """Logout and clear authentication"""
    print("Logout successful")
    return {"message": "Logged out successfully"}
