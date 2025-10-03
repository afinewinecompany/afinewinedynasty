import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import User
from app.services.email_service import EmailService
from app.core.security import get_password_hash

# Temporary storage for reset tokens - TODO: Move to Redis or database table
reset_tokens_db: Dict[str, Dict] = {}

class PasswordResetService:
    """Service for handling password reset functionality"""

    @staticmethod
    def generate_reset_token() -> str:
        """Generate a secure reset token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    async def request_password_reset(email: str, db: AsyncSession) -> bool:
        """Request a password reset for the given email"""
        # Check if user exists
        stmt = select(User).where(User.email == email, User.is_active == True)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Don't reveal whether user exists or not for security
            return True

        # Don't allow password reset for OAuth users (those without password)
        if not user.hashed_password or user.google_id:
            # OAuth user - don't reveal this, just return success
            return True

        # Generate reset token
        reset_token = PasswordResetService.generate_reset_token()

        # Store token with expiry (1 hour)
        reset_tokens_db[reset_token] = {
            "email": email,
            "expires_at": datetime.now() + timedelta(hours=1),
            "used": False
        }

        # Send reset email
        email_service = EmailService()
        success = await email_service.send_password_reset_email(email, reset_token)

        if not success:
            # Clean up token if email failed
            if reset_token in reset_tokens_db:
                del reset_tokens_db[reset_token]
            return False

        return True

    @staticmethod
    def verify_reset_token(token: str) -> Optional[str]:
        """Verify reset token and return associated email"""
        token_data = reset_tokens_db.get(token)
        if not token_data:
            return None

        # Check if token has expired
        if datetime.now() > token_data["expires_at"]:
            # Clean up expired token
            del reset_tokens_db[token]
            return None

        # Check if token has been used
        if token_data["used"]:
            return None

        return token_data["email"]

    @staticmethod
    async def reset_password(token: str, new_password: str, db: AsyncSession) -> bool:
        """Reset password using the reset token"""
        email = PasswordResetService.verify_reset_token(token)
        if not email:
            return False

        # Get user from database
        stmt = select(User).where(User.email == email, User.is_active == True)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return False

        # Don't allow password reset for OAuth users
        if not user.hashed_password or user.google_id:
            return False

        # Update password in database
        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.now()

        await db.commit()

        # Mark token as used
        reset_tokens_db[token]["used"] = True

        return True

    @staticmethod
    def cleanup_expired_tokens():
        """Clean up expired tokens (should be called periodically)"""
        now = datetime.now()
        expired_tokens = [
            token for token, data in reset_tokens_db.items()
            if now > data["expires_at"]
        ]
        for token in expired_tokens:
            del reset_tokens_db[token]