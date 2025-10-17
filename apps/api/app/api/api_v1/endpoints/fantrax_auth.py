"""
Fantrax Authentication Endpoints (In-Browser Authentication)

Provides endpoints for server-side Selenium-based authentication
allowing users to log in to Fantrax through an in-browser flow.

@module fantrax_auth
@since 1.0.0
"""

from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import uuid
import logging

from app.db.database import get_db
from app.db.models import User
from app.api.deps import get_current_user
from app.services.fantrax_playwright_service import FantraxPlaywrightService  # Use Playwright instead of Selenium
from app.services.fantrax_login_service import FantraxLoginService
from app.schemas.fantrax import (
    AuthInitiateResponse,
    AuthStatusResponse,
    AuthCompleteResponse,
    AuthCancelResponse
)
from pydantic import BaseModel, EmailStr, Field

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory session storage (TODO: Move to Redis for production scaling)
active_auth_sessions: Dict[str, dict] = {}


@router.post("/initiate", response_model=AuthInitiateResponse, status_code=status.HTTP_201_CREATED)
async def initiate_fantrax_auth(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate server-side Selenium authentication session for Fantrax.

    Creates a headless Chrome browser session and navigates to Fantrax login page.
    User will log in through status polling, and cookies are captured on completion.

    **Premium users only**

    Args:
        current_user: Authenticated premium user from JWT token
        db: Database session for user lookups

    Returns:
        AuthInitiateResponse containing session_id and status polling URL

    Raises:
        HTTPException(429): If user has active session or rate limit exceeded
        HTTPException(503): If maximum concurrent sessions reached or Selenium unavailable
        HTTPException(500): If Selenium initialization fails

    Example:
        ```python
        response = await client.post("/api/fantrax/auth/initiate")
        session_id = response.json()["session_id"]
        ```

    Performance:
        - Typical initialization time: 5-15 seconds
        - Browser startup overhead: ~500MB RAM per session

    Since:
        1.0.0
    """
    try:
        # Check for existing active session for this user
        user_sessions = [
            sid for sid, session in active_auth_sessions.items()
            if session.get("user_id") == current_user.id
               and session.get("status") not in ["success", "failed", "timeout"]
        ]

        if user_sessions:
            logger.warning(f"User {current_user.id} attempted to create session while active session exists")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="You already have an active authentication session. Please wait for it to complete or cancel it."
            )

        # Check global concurrent session limit (max 10)
        active_count = len([
            s for s in active_auth_sessions.values()
            if s.get("status") not in ["success", "failed", "timeout", "cancelled"]
        ])

        if active_count >= 10:
            logger.warning(f"Concurrent session limit reached: {active_count}/10")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable due to high demand. Please try again in 1 minute."
            )

        # Create new auth session
        session_id = str(uuid.uuid4())
        logger.info(f"Initiating Fantrax auth session {session_id} for user {current_user.id}")

        # Initialize Playwright session (more reliable than Selenium)
        auth_service = FantraxPlaywrightService()
        playwright_session = await auth_service.create_auth_session(
            user_id=current_user.id,
            session_id=session_id
        )

        # Store session in memory
        active_auth_sessions[session_id] = {
            "user_id": current_user.id,
            "status": "initializing",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(seconds=90),
            "current_url": None,
            "playwright": playwright_session["playwright"],
            "browser": playwright_session["browser"],
            "context": playwright_session["context"],
            "page": playwright_session["page"]
        }

        # Start navigation to Fantrax (async)
        await auth_service.navigate_to_login(session_id, active_auth_sessions[session_id])

        return AuthInitiateResponse(
            session_id=session_id,
            status_url=f"/api/fantrax/auth/status/{session_id}",
            expires_in=90,
            message="Browser session initialized. Please log in to Fantrax."
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to initiate Fantrax auth: {type(e).__name__}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Browser authentication temporarily unavailable: {str(e)}"
        )


@router.get("/status/{session_id}", response_model=AuthStatusResponse)
async def get_auth_status(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Poll authentication session status.

    Returns current state of the Selenium browser session including
    authentication progress and current URL.

    **Premium users only**

    Args:
        session_id: UUID of the authentication session
        current_user: Authenticated user from JWT token

    Returns:
        AuthStatusResponse with current session status and details

    Raises:
        HTTPException(404): If session not found
        HTTPException(403): If user doesn't own this session
        HTTPException(410): If session has expired

    Example:
        ```python
        # Poll every 2 seconds
        response = await client.get(f"/api/fantrax/auth/status/{session_id}")
        if response.json()["status"] == "ready":
            print("Please log in to Fantrax")
        ```

    Performance:
        - Response time: <50ms (memory lookup)
        - Recommended polling interval: 2 seconds

    Since:
        1.0.0
    """
    # Validate session exists
    if session_id not in active_auth_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authentication session not found. It may have expired."
        )

    session = active_auth_sessions[session_id]

    # Verify user owns this session
    if session["user_id"] != current_user.id:
        logger.warning(f"User {current_user.id} attempted to access session {session_id} owned by user {session['user_id']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this authentication session."
        )

    # Check if session expired
    if datetime.utcnow() > session["expires_at"]:
        session["status"] = "timeout"
        logger.info(f"Session {session_id} timed out")
        # Cleanup will happen in background task
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Authentication session timed out. Please try again."
        )

    # Get current browser state
    auth_service = FantraxPlaywrightService()
    current_status = await auth_service.get_session_status(session_id, session)

    # Update session state
    session["status"] = current_status["status"]
    session["current_url"] = current_status.get("current_url")

    elapsed_seconds = (datetime.utcnow() - session["created_at"]).total_seconds()

    return AuthStatusResponse(
        session_id=session_id,
        status=session["status"],
        current_url=session.get("current_url"),
        elapsed_seconds=int(elapsed_seconds),
        expires_in=max(0, int((session["expires_at"] - datetime.utcnow()).total_seconds())),
        message=_get_status_message(session["status"])
    )


@router.post("/complete/{session_id}", response_model=AuthCompleteResponse)
async def complete_auth(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Complete authentication and capture cookies.

    Extracts cookies from the Selenium browser session, encrypts them,
    and stores in the user's database record. Cleans up browser session.

    **Premium users only**

    Args:
        session_id: UUID of the authentication session
        current_user: Authenticated user from JWT token
        db: Database session for storing cookies

    Returns:
        AuthCompleteResponse with success status and connection timestamp

    Raises:
        HTTPException(404): If session not found
        HTTPException(403): If user doesn't own session
        HTTPException(400): If session not in ready state or no cookies found
        HTTPException(500): If cookie storage fails

    Example:
        ```python
        response = await client.post(f"/api/fantrax/auth/complete/{session_id}")
        print(f"Connected at: {response.json()['connected_at']}")
        ```

    Performance:
        - Cookie extraction: 1-3 seconds
        - Database write: <100ms
        - Total: ~3-5 seconds

    Since:
        1.0.0
    """
    # Validate session
    if session_id not in active_auth_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authentication session not found."
        )

    session = active_auth_sessions[session_id]

    # Verify ownership
    if session["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to complete this authentication session."
        )

    try:
        # Capture cookies from browser
        auth_service = FantraxPlaywrightService()
        cookies = await auth_service.capture_cookies(session_id, session)

        if not cookies:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No Fantrax cookies found. Please ensure you logged in successfully."
            )

        # Store encrypted cookies in database
        success = await auth_service.store_user_cookies(
            db=db,
            user_id=current_user.id,
            cookies=cookies
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store Fantrax authentication. Please try again."
            )

        # Mark session as complete
        session["status"] = "success"
        connected_at = datetime.utcnow()

        logger.info(f"User {current_user.id} successfully authenticated with Fantrax (session {session_id})")

        # Cleanup browser (async, don't wait)
        await auth_service.cleanup_session(session_id, session)

        # Remove from active sessions
        del active_auth_sessions[session_id]

        return AuthCompleteResponse(
            success=True,
            message="Successfully connected to Fantrax!",
            connected_at=connected_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete Fantrax auth for session {session_id}: {str(e)}", exc_info=True)
        # Ensure cleanup happens
        try:
            auth_service = FantraxPlaywrightService()
            await auth_service.cleanup_session(session_id, session)
        except:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete authentication. Please try again."
        )


@router.delete("/cancel/{session_id}", response_model=AuthCancelResponse)
async def cancel_auth(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Cancel active authentication session.

    Stops the Selenium browser and cleans up resources.
    User can initiate a new session after cancellation.

    **Premium users only**

    Args:
        session_id: UUID of the authentication session
        current_user: Authenticated user from JWT token

    Returns:
        AuthCancelResponse confirming cancellation

    Raises:
        HTTPException(404): If session not found
        HTTPException(403): If user doesn't own session

    Example:
        ```python
        response = await client.delete(f"/api/fantrax/auth/cancel/{session_id}")
        print(response.json()["message"])  # "Authentication cancelled"
        ```

    Performance:
        - Browser cleanup: 1-2 seconds
        - Process termination: <500ms

    Since:
        1.0.0
    """
    # Validate session
    if session_id not in active_auth_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authentication session not found."
        )

    session = active_auth_sessions[session_id]

    # Verify ownership
    if session["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this authentication session."
        )

    try:
        # Cleanup browser
        auth_service = FantraxPlaywrightService()
        await auth_service.cleanup_session(session_id, session)

        # Mark as cancelled
        session["status"] = "cancelled"

        logger.info(f"User {current_user.id} cancelled auth session {session_id}")

        # Remove from active sessions
        del active_auth_sessions[session_id]

        return AuthCancelResponse(
            success=True,
            message="Authentication cancelled successfully."
        )

    except Exception as e:
        logger.error(f"Failed to cancel auth session {session_id}: {str(e)}", exc_info=True)
        # Best effort removal
        if session_id in active_auth_sessions:
            del active_auth_sessions[session_id]
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel authentication session."
        )


def _get_status_message(status: str) -> str:
    """
    Get user-friendly status message for authentication state.

    Args:
        status: Current session status

    Returns:
        Human-readable message describing current state

    Since:
        1.0.0
    """
    messages = {
        "initializing": "Initializing browser... (5-15 seconds)",
        "ready": "Please log in to Fantrax in the browser",
        "authenticating": "Detecting login... Please wait",
        "success": "Authentication successful!",
        "failed": "Authentication failed. Please try again.",
        "timeout": "Authentication timed out after 90 seconds.",
        "cancelled": "Authentication cancelled by user."
    }
    return messages.get(status, "Processing...")


# ============================================================================
# Cookie-Based Authentication (RECOMMENDED)
# ============================================================================

class FantraxCookieRequest(BaseModel):
    """Request model for Fantrax cookie-based authentication"""
    cookies_json: str = Field(
        description="JSON array of cookies exported from browser"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "cookies_json": '[{"name":"sessionid","value":"abc123","domain":".fantrax.com"}]'
            }
        }


class FantraxCookieResponse(BaseModel):
    """Response model for cookie authentication"""
    success: bool
    message: str
    cookie_count: Optional[int] = None


@router.post("/cookie-auth", response_model=FantraxCookieResponse)
async def authenticate_with_cookies(
    cookie_request: FantraxCookieRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate to Fantrax using manually exported cookies.

    **This is the RECOMMENDED authentication method** as it:
    - Works reliably in all environments (no Selenium/Chrome needed)
    - Bypasses Cloudflare bot protection
    - Simple and fast

    Users export cookies from their browser after logging into Fantrax.com:
    1. Install EditThisCookie (Chrome) or Cookie-Editor (Firefox)
    2. Log into Fantrax.com
    3. Click extension → Export cookies
    4. Paste JSON into this endpoint

    Args:
        cookie_request: JSON array of cookies from browser
        current_user: Authenticated user from JWT token
        db: Database session

    Returns:
        FantraxCookieResponse with success status

    Raises:
        HTTPException(400): If cookies are invalid JSON or missing required fields
        HTTPException(500): If storage fails

    Example:
        ```json
        POST /api/v1/fantrax/auth/cookie-auth
        {
            "cookies_json": "[{\"name\":\"sessionid\",\"value\":\"abc123\",\"domain\":\".fantrax.com\"}]"
        }
        ```

    Security:
        - Cookies are encrypted using Fernet symmetric encryption before storage
        - HTTPS required in production
        - Cookies expire after 30 days (Fantrax default)

    Performance:
        - Response time: <100ms
        - No external requests

    Since:
        1.0.0
    """
    import json
    from app.core.security import encrypt_value

    try:
        # Parse and validate cookies JSON
        try:
            cookies = json.loads(cookie_request.cookies_json)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON format for cookies"
            )

        if not isinstance(cookies, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cookies must be a JSON array"
            )

        if len(cookies) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No cookies provided"
            )

        # Validate cookie structure
        for cookie in cookies:
            if not isinstance(cookie, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each cookie must be an object with name, value, and domain"
                )

        logger.info(f"Storing {len(cookies)} Fantrax cookies for user {current_user.id}")

        # Encrypt and store cookies
        cookies_json_str = json.dumps(cookies)
        encrypted_cookies = encrypt_value(cookies_json_str)

        # Update user record
        from sqlalchemy import update
        stmt = (
            update(User)
            .where(User.id == current_user.id)
            .values(
                fantrax_cookies=encrypted_cookies,
                fantrax_connected_at=datetime.utcnow()
            )
        )
        await db.execute(stmt)
        await db.commit()

        logger.info(f"Successfully stored Fantrax cookies for user {current_user.id}")

        return FantraxCookieResponse(
            success=True,
            message="Successfully connected to Fantrax!",
            cookie_count=len(cookies)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store Fantrax cookies: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store cookies. Please try again."
        )


# ============================================================================
# Username/Password Authentication (DEPRECATED - Does Not Work)
# ============================================================================

class FantraxLoginRequest(BaseModel):
    """Request model for Fantrax username/password login"""
    email: EmailStr
    password: str


class FantraxLoginResponse(BaseModel):
    """Response model for Fantrax login"""
    success: bool
    message: str
    cookie_count: Optional[int] = None
    error: Optional[str] = None


@router.post("/login", response_model=FantraxLoginResponse, deprecated=True)
async def login_with_credentials(
    login_request: FantraxLoginRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate to Fantrax using username and password.

    **DEPRECATED: This endpoint does not work due to Cloudflare bot protection.**
    **Use /cookie-auth instead.**

    Fantrax.com uses Cloudflare's bot detection which blocks automated login attempts.
    The endpoint returns 405 Method Not Allowed due to Cloudflare challenges.

    Please use the cookie-based authentication endpoint instead:
    POST /api/v1/fantrax/auth/cookie-auth

    Args:
        login_request: User's Fantrax email and password
        current_user: Authenticated user from JWT token
        db: Database session

    Returns:
        FantraxLoginResponse with error message

    Raises:
        HTTPException(501): This endpoint is not implemented due to Cloudflare

    Since:
        1.0.0

    Deprecated:
        Use /cookie-auth instead
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Username/password authentication is not available due to Cloudflare protection. "
               "Please use cookie-based authentication: POST /api/v1/fantrax/auth/cookie-auth"
    )
