from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import os
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Initialize Fernet cipher for token encryption
# Use a dedicated encryption key, fallback to SECRET_KEY if not set
ENCRYPTION_KEY = getattr(settings, 'TOKEN_ENCRYPTION_KEY', None) or settings.SECRET_KEY
# Ensure the key is properly formatted for Fernet
if len(ENCRYPTION_KEY) < 32:
    # Pad or hash the key to make it 32 bytes
    ENCRYPTION_KEY = base64.urlsafe_b64encode(ENCRYPTION_KEY.encode().ljust(32)[:32]).decode()
else:
    ENCRYPTION_KEY = base64.urlsafe_b64encode(ENCRYPTION_KEY.encode()[:32]).decode()

fernet = Fernet(ENCRYPTION_KEY.encode())


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    subscription_tier: str = "free",
    is_admin: bool = False,
    user_id: Optional[int] = None
) -> str:
    """Create access token with user metadata"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "tier": subscription_tier,
        "admin": is_admin
    }
    if user_id is not None:
        to_encode["user_id"] = user_id

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create refresh token"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[str]:
    """Verify and decode token"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            return None

        # For refresh tokens, ensure it's actually a refresh token
        if token_type == "refresh":
            if payload.get("type") != "refresh":
                return None

        return username
    except JWTError:
        return None


def verify_refresh_token(token: str) -> Optional[str]:
    """Verify refresh token specifically"""
    return verify_token(token, "refresh")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def is_password_complex(password: str) -> tuple[bool, str]:
    """Check password complexity requirements"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        return False, "Password must contain at least one special character"

    return True, "Password meets complexity requirements"


def encrypt_value(value: str) -> str:
    """
    Encrypt sensitive data for storage

    @param value - Plain text value to encrypt
    @returns Base64 encoded encrypted value

    @since 1.0.0
    """
    if not value:
        return ""
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """
    Decrypt sensitive data from storage

    @param encrypted_value - Base64 encoded encrypted value
    @returns Decrypted plain text value

    @throws ValueError When decryption fails due to invalid token or corrupted data

    @since 1.0.0
    """
    if not encrypted_value:
        return ""
    try:
        return fernet.decrypt(encrypted_value.encode()).decode()
    except Exception as e:
        # Raise exception to surface decryption failures
        raise ValueError(f"Failed to decrypt value: {str(e)}")


def require_premium_tier(user: Any) -> None:
    """
    Verify user has premium tier subscription for accessing premium features

    @param user - User object with subscription tier information

    @throws HTTPException 403 Forbidden when user does not have premium access

    @since 4.4.0
    """
    from fastapi import HTTPException, status

    # Check if user has premium or pro subscription tier
    if not hasattr(user, 'subscription_tier'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required to access this feature"
        )

    allowed_tiers = ['premium', 'pro']
    if user.subscription_tier not in allowed_tiers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Premium subscription required. Your current tier: {user.subscription_tier}"
        )