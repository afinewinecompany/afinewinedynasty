import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import HTTPException, status
from app.services.auth_service import get_user_by_email
from app.services.email_service import EmailService
from app.core.security import get_password_hash

# Temporary storage for reset tokens - in production, use Redis or database
reset_tokens_db: Dict[str, Dict] = {}

class PasswordResetService:
    """Service for handling password reset functionality"""

    @staticmethod
    def generate_reset_token() -> str:
        """Generate a secure reset token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    async def request_password_reset(email: str) -> bool:
        """Request a password reset for the given email"""
        # Check if user exists
        user = get_user_by_email(email)
        if not user:
            # Don't reveal whether user exists or not for security
            return True

        # Don't allow password reset for OAuth users
        from app.services.auth_service import fake_users_db
        user_data = fake_users_db.get(email)
        if user_data and not user_data.get("hashed_password"):
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
    def reset_password(token: str, new_password: str) -> bool:
        """Reset password using the reset token"""
        email = PasswordResetService.verify_reset_token(token)
        if not email:
            return False

        # Get user
        user = get_user_by_email(email)
        if not user:
            return False

        # Update password in fake_users_db
        from app.services.auth_service import fake_users_db
        user_data = fake_users_db.get(email)
        if not user_data:
            return False

        # Don't allow password reset for OAuth users
        if not user_data.get("hashed_password"):
            return False

        # Update password
        user_data["hashed_password"] = get_password_hash(new_password)
        user_data["updated_at"] = datetime.now()

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