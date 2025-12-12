"""
Azure AD Authentication - Simplified Direct Backend
No APIM Gateway - Direct Frontend to Backend Communication

Features:
- HTTP-only secure cookies
- State parameter validation (CSRF protection)
- Session-based authentication
- Automatic token refresh
- Direct communication (no API gateway)
"""

import os
import secrets
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
import httpx
from dotenv import load_dotenv

from core.logging import get_logger

load_dotenv()
logger = get_logger(__name__)

# Azure AD Configuration
TENANT_ID = os.environ.get("AZURE_AD_TENANT_ID", "")
CLIENT_ID = os.environ.get("AZURE_AD_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("AZURE_AD_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get(
    "AZURE_AD_REDIRECT_URI",
    "http://localhost:8000/auth/callback"
)

# Azure AD Endpoints
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
AUTHORIZE_URL = f"{AUTHORITY}/oauth2/v2.0/authorize"
TOKEN_URL = f"{AUTHORITY}/oauth2/v2.0/token"
JWKS_URL = f"{AUTHORITY}/discovery/v2.0/keys"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"

# Scopes
SCOPES = ["openid", "profile", "email", "offline_access"]

# Frontend URL
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Cookie settings
COOKIE_NAME = "session_token"
COOKIE_MAX_AGE = 3600  # 1 hour
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Session store (use Redis in production)
sessions: Dict[str, Dict[str, Any]] = {}


def create_session(state: str = None) -> str:
    """Create a new session."""
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "state": state,
        "tokens": None,
        "user": None,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(seconds=COOKIE_MAX_AGE),
    }
    return session_id


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session if it exists and hasn't expired."""
    session = sessions.get(session_id)
    if not session:
        return None
    
    if datetime.utcnow() > session["expires_at"]:
        del sessions[session_id]
        return None
    
    return session


def update_session(session_id: str, data: Dict[str, Any]):
    """Update session data."""
    if session_id in sessions:
        sessions[session_id].update(data)
        sessions[session_id]["expires_at"] = datetime.utcnow() + timedelta(seconds=COOKIE_MAX_AGE)


def delete_session(session_id: str):
    """Delete a session."""
    if session_id in sessions:
        del sessions[session_id]


def cleanup_expired_sessions():
    """Clean up expired sessions."""
    now = datetime.utcnow()
    expired = [sid for sid, sess in sessions.items() if sess["expires_at"] < now]
    for sid in expired:
        del sessions[sid]
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")


@router.get("/login")
async def login(response: Response):
    """Initiate OAuth 2.0 login flow."""
    state = secrets.token_urlsafe(32)
    session_id = create_session(state=state)
    
    response = RedirectResponse(url="placeholder")
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=600,
        domain=COOKIE_DOMAIN,
    )
    
    from urllib.parse import urlencode
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        "scope": " ".join(SCOPES),
        "state": state,
        "prompt": "select_account",
    }
    
    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
    logger.info(f"Login initiated, state: {state[:10]}...")
    
    response.status_code = 302
    response.headers["location"] = auth_url
    return response


@router.get("/callback")
async def auth_callback(code: str, state: str, request: Request, response: Response):
    """OAuth 2.0 callback - exchange code for tokens."""
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        logger.error("No session cookie in callback")
        raise HTTPException(400, "No session found. Please try again.")
    
    session = get_session(session_id)
    if not session:
        logger.error(f"Session {session_id[:10]}... not found")
        raise HTTPException(400, "Session expired. Please try again.")
    
    # Validate state (CSRF protection)
    stored_state = session.get("state")
    if not stored_state or stored_state != state:
        logger.error(f"State mismatch")
        delete_session(session_id)
        raise HTTPException(400, "Invalid state. Possible CSRF attack.")
    
    logger.info(f"State validated for session {session_id[:10]}...")
    
    # Exchange code for tokens
    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
    }
    
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(TOKEN_URL, data=token_data)
            
            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                raise HTTPException(400, f"Token exchange failed: {token_response.text}")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            id_token = tokens.get("id_token")
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 3600)
            
            logger.info("Tokens obtained from Azure AD")
            
            # Extract user info from ID token
            user_info = jwt.get_unverified_claims(id_token)
            
            # Store in session
            update_session(session_id, {
                "tokens": {
                    "access_token": access_token,
                    "id_token": id_token,
                    "refresh_token": refresh_token,
                    "expires_in": expires_in,
                    "obtained_at": datetime.utcnow().isoformat(),
                },
                "user": {
                    "id": user_info.get("oid"),
                    "sub": user_info.get("sub"),
                    "name": user_info.get("name"),
                    "email": user_info.get("preferred_username") or user_info.get("email"),
                },
                "state": None,
            })
            
            logger.info(f"User authenticated: {user_info.get('email')}")
            
            # Redirect to frontend
            response = RedirectResponse(url=FRONTEND_URL)
            response.set_cookie(
                key=COOKIE_NAME,
                value=session_id,
                httponly=True,
                secure=COOKIE_SECURE,
                samesite="lax",
                max_age=COOKIE_MAX_AGE,
                domain=COOKIE_DOMAIN,
            )
            return response
    
    except httpx.HTTPError as e:
        logger.error(f"HTTP error: {e}")
        delete_session(session_id)
        raise HTTPException(500, f"Authentication failed: {str(e)}")


@lru_cache()
def get_jwks() -> Dict[str, Any]:
    """Fetch Azure AD's public keys."""
    import requests
    logger.info(f"Fetching JWKS from {JWKS_URL}")
    response = requests.get(JWKS_URL)
    response.raise_for_status()
    return response.json()


async def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Get current authenticated user from session.
    Use as dependency for protected endpoints.
    """
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        raise HTTPException(401, "Not authenticated")
    
    session = get_session(session_id)
    if not session:
        raise HTTPException(401, "Session expired")
    
    tokens = session.get("tokens")
    if not tokens:
        raise HTTPException(401, "Not authenticated")
    
    # Check token expiration and refresh if needed
    obtained_at = datetime.fromisoformat(tokens.get("obtained_at"))
    expires_in = tokens.get("expires_in", 3600)
    
    if datetime.utcnow() > obtained_at + timedelta(seconds=expires_in - 60):
        refresh_token = tokens.get("refresh_token")
        if refresh_token:
            logger.info(f"Refreshing token for session {session_id[:10]}...")
            try:
                new_tokens = await refresh_tokens(refresh_token)
                update_session(session_id, {"tokens": new_tokens})
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                delete_session(session_id)
                raise HTTPException(401, "Session expired")
        else:
            delete_session(session_id)
            raise HTTPException(401, "Session expired")
    
    user = session.get("user")
    if not user:
        raise HTTPException(401, "User info not found")
    
    return user


async def refresh_tokens(refresh_token: str) -> Dict[str, Any]:
    """Refresh access token using refresh token."""
    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": " ".join(SCOPES),
    }
    
    async with httpx.AsyncClient() as client:
        token_response = await client.post(TOKEN_URL, data=token_data)
        
        if token_response.status_code != 200:
            raise HTTPException(400, "Token refresh failed")
        
        tokens = token_response.json()
        return {
            "access_token": tokens.get("access_token"),
            "id_token": tokens.get("id_token"),
            "refresh_token": tokens.get("refresh_token", refresh_token),
            "expires_in": tokens.get("expires_in", 3600),
            "obtained_at": datetime.utcnow().isoformat(),
        }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout user."""
    session_id = request.cookies.get(COOKIE_NAME)
    if session_id:
        delete_session(session_id)
        logger.info(f"User logged out: {session_id[:10]}...")
    
    response.delete_cookie(key=COOKIE_NAME, domain=COOKIE_DOMAIN)
    
    logout_url = f"{AUTHORITY}/oauth2/v2.0/logout?post_logout_redirect_uri={FRONTEND_URL}"
    return RedirectResponse(url=logout_url)


@router.get("/me")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "authenticated": True,
        "user": current_user,
    }


@router.get("/session")
async def check_session(request: Request):
    """Check if user has valid session."""
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        return {"authenticated": False}
    
    session = get_session(session_id)
    if not session or not session.get("tokens"):
        return {"authenticated": False}
    
    return {
        "authenticated": True,
        "user": session.get("user"),
    }


async def periodic_session_cleanup():
    """Background task to clean expired sessions."""
    import asyncio
    while True:
        await asyncio.sleep(300)  # 5 minutes
        cleanup_expired_sessions()