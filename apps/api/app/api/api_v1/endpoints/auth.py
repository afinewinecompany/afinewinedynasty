from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, validator, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.security import create_access_token, create_refresh_token, is_password_complex, verify_refresh_token
from app.core.validation import validate_email_format, validate_password_input, validate_name_input
from app.services.user_service import authenticate_user, create_user, get_generic_error_message, get_user_by_email, create_user_session, revoke_user_session, revoke_all_user_sessions, is_session_valid
from app.api.deps import get_current_user
from app.models.user import UserLogin
from app.services.oauth_service import GoogleOAuthService
from app.services.password_reset_service import PasswordResetService
from app.db.database import get_db

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request with email and password"""
    email: EmailStr = Field(description="User's email address", example="user@example.com")
    password: str = Field(description="User's password", example="SecurePassword123!")

    @validator('email')
    def validate_email(cls, v):
        return validate_email_format(v)

    @validator('password')
    def validate_password(cls, v):
        return validate_password_input(v)

    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123!"
            }
        }


class LoginResponse(BaseModel):
    """Successful login response with JWT tokens"""
    access_token: str = Field(description="JWT access token for API requests")
    refresh_token: str = Field(description="JWT refresh token for token renewal")
    token_type: str = Field(description="Token type (Bearer)", example="Bearer")
    expires_in: int = Field(description="Access token expiry time in seconds", example=900)

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 900
            }
        }


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @validator('email')
    def validate_email(cls, v):
        return validate_email_format(v)

    @validator('password')
    def validate_password(cls, v):
        return validate_password_input(v)

    @validator('full_name')
    def validate_name(cls, v):
        return validate_name_input(v)


class RegisterResponse(BaseModel):
    message: str
    user_id: int


class GoogleOAuthRequest(BaseModel):
    code: str
    state: str = ""


class GoogleOAuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user_id: int
    is_new_user: bool


class AccountLinkRequest(BaseModel):
    email: EmailStr
    password: str
    google_code: str

    @validator('email')
    def validate_email(cls, v):
        return validate_email_format(v)

    @validator('password')
    def validate_password(cls, v):
        return validate_password_input(v)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class PasswordResetRequest(BaseModel):
    email: EmailStr

    @validator('email')
    def validate_email(cls, v):
        return validate_email_format(v)


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        return validate_password_input(v)


@router.post(
    "/login",
    response_model=LoginResponse,
    tags=["auth"],
    summary="User login",
    description="Authenticate user with email and password to receive JWT tokens",
    responses={
        200: {"description": "Successful authentication", "model": LoginResponse},
        401: {"description": "Invalid credentials"},
        429: {"description": "Too many login attempts"}
    }
)
# @limiter.limit(f"{settings.AUTH_RATE_LIMIT_ATTEMPTS}/{settings.AUTH_RATE_LIMIT_WINDOW // 60}minute")
async def login(request: Request, login_request: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    """
    Authenticate user and return JWT access tokens.

    Rate limit: 5 attempts per minute

    The access token expires in 15 minutes and should be included in the
    Authorization header for authenticated requests:
    ```
    Authorization: Bearer <access_token>
    ```

    Use the refresh token to obtain new access tokens when they expire.
    """
    # Authenticate user
    user = await authenticate_user(db, login_request.email, login_request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=get_generic_error_message(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access and refresh tokens
    access_token = create_access_token(subject=user.email)
    refresh_token = create_refresh_token(subject=user.email)

    # Create session for token revocation tracking
    expires_at = datetime.now() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    await create_user_session(db, user.email, refresh_token, expires_at)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/register", response_model=RegisterResponse)
# @limiter.limit(f"{settings.SENSITIVE_RATE_LIMIT_ATTEMPTS}/{settings.SENSITIVE_RATE_LIMIT_WINDOW // 3600}hour")
async def register(request: Request, register_request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    """Register a new user"""
    try:
        # Create user
        user = await create_user(
            db,
            email=register_request.email,
            password=register_request.password,
            full_name=register_request.full_name
        )

        return RegisterResponse(
            message="User registered successfully",
            user_id=user.id
        )
    except HTTPException as e:
        # Re-raise HTTPException as-is
        raise e
    except Exception as e:
        # Generic error message to prevent information disclosure
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User registration failed"
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
# @limiter.limit(f"{settings.AUTH_RATE_LIMIT_ATTEMPTS}/{settings.AUTH_RATE_LIMIT_WINDOW // 60}minute")
async def refresh_access_token(request: Request, refresh_request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)) -> RefreshTokenResponse:
    """Refresh access token using refresh token"""
    # Verify refresh token
    username = verify_refresh_token(refresh_request.refresh_token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if session is still valid (not revoked)
    session_valid = await is_session_valid(db, refresh_request.refresh_token)
    if not session_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    user = await get_user_by_email(db, username)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revoke the old session
    await revoke_user_session(db, refresh_request.refresh_token)

    # Create new access and refresh tokens
    new_access_token = create_access_token(subject=username)
    new_refresh_token = create_refresh_token(subject=username)

    # Create new session for token revocation tracking
    expires_at = datetime.now() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    await create_user_session(db, username, new_refresh_token, expires_at)

    return RefreshTokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(current_user: UserLogin = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Log out the current user and revoke all sessions"""
    # Revoke all user sessions
    revoked_count = await revoke_all_user_sessions(db, current_user.email)

    return {
        "message": f"Successfully logged out user: {current_user.email}",
        "sessions_revoked": revoked_count
    }


@router.post("/password-reset")
# @limiter.limit(f"{settings.SENSITIVE_RATE_LIMIT_ATTEMPTS}/{settings.SENSITIVE_RATE_LIMIT_WINDOW // 3600}hour")
async def request_password_reset(request: Request, reset_request: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    """Request a password reset"""
    try:
        success = await PasswordResetService.request_password_reset(reset_request.email, db)

        # Always return success to prevent user enumeration
        return {
            "message": "If an account with this email exists, a password reset link has been sent."
        }

    except Exception as e:
        # Generic error to prevent information disclosure
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset request failed"
        )


@router.put("/password-reset")
# @limiter.limit(f"{settings.SENSITIVE_RATE_LIMIT_ATTEMPTS}/{settings.SENSITIVE_RATE_LIMIT_WINDOW // 3600}hour")
async def confirm_password_reset(request: Request, reset_confirm: PasswordResetConfirmRequest, db: AsyncSession = Depends(get_db)):
    """Complete password reset with token"""
    try:
        # Validate password complexity
        is_valid, message = is_password_complex(reset_confirm.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        success = await PasswordResetService.reset_password(reset_confirm.token, reset_confirm.new_password, db)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )

        return {"message": "Password has been successfully reset"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )


@router.post("/google/login", response_model=GoogleOAuthResponse)
# @limiter.limit(f"{settings.AUTH_RATE_LIMIT_ATTEMPTS}/{settings.AUTH_RATE_LIMIT_WINDOW // 60}minute")
async def google_oauth_login(request: Request, oauth_request: GoogleOAuthRequest, db: AsyncSession = Depends(get_db)) -> GoogleOAuthResponse:
    """Authenticate user with Google OAuth"""
    try:
        # Exchange authorization code for access token
        access_token = await GoogleOAuthService.exchange_code_for_token(oauth_request.code)
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code"
            )

        # Get user information from Google
        google_user_info = await GoogleOAuthService.get_user_info(access_token)
        if not google_user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user information from Google"
            )

        # Create or get existing user
        is_new_user = await get_user_by_email(db, google_user_info.get("email")) is None
        user = await GoogleOAuthService.create_or_get_oauth_user(db, google_user_info)

        # Create JWT access and refresh tokens
        jwt_access_token = create_access_token(subject=user.email)
        jwt_refresh_token = create_refresh_token(subject=user.email)

        # Create session for token revocation tracking
        expires_at = datetime.now() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        await create_user_session(db, user.email, jwt_refresh_token, expires_at)

        return GoogleOAuthResponse(
            access_token=jwt_access_token,
            refresh_token=jwt_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
            is_new_user=is_new_user
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth authentication failed"
        )


@router.post("/google/link")
# @limiter.limit(f"{settings.SENSITIVE_RATE_LIMIT_ATTEMPTS}/{settings.SENSITIVE_RATE_LIMIT_WINDOW // 3600}hour")
async def link_google_account(request: Request, link_request: AccountLinkRequest, db: AsyncSession = Depends(get_db)):
    """Link Google account to existing email/password account"""
    try:
        # First authenticate the existing email/password user
        user = await authenticate_user(db, link_request.email, link_request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Exchange Google authorization code for access token
        access_token = await GoogleOAuthService.exchange_code_for_token(link_request.google_code)
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange Google authorization code"
            )

        # Get user information from Google
        google_user_info = await GoogleOAuthService.get_user_info(access_token)
        if not google_user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user information from Google"
            )

        # Verify the Google email matches the account being linked
        google_email = google_user_info.get("email")
        if google_email != link_request.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google account email must match your account email"
            )

        # Link the Google account
        success = await GoogleOAuthService.link_google_account(db, link_request.email, google_user_info)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to link Google account"
            )

        return {"message": "Google account linked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account linking failed"
        )