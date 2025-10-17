from typing import Optional, Dict, Any
import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.config import settings
from app.db.models import User
from app.models.user import UserLogin
from app.core.security import get_password_hash
from datetime import datetime


class GoogleOAuthService:
    """Google OAuth 2.0 service for user authentication"""

    @staticmethod
    def get_google_token_url() -> str:
        """Get Google token URL from environment or default"""
        return getattr(settings, 'GOOGLE_TOKEN_URL', 'https://oauth2.googleapis.com/token')

    @staticmethod
    def get_google_userinfo_url() -> str:
        """Get Google userinfo URL from environment or default"""
        return getattr(settings, 'GOOGLE_USERINFO_URL', 'https://www.googleapis.com/oauth2/v2/userinfo')

    @classmethod
    async def exchange_code_for_token(cls, authorization_code: str) -> Optional[str]:
        """Exchange authorization code for access token"""
        import logging
        logger = logging.getLogger(__name__)

        token_data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": authorization_code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(cls.get_google_token_url(), data=token_data)
                response.raise_for_status()
                token_response = response.json()
                return token_response.get("access_token")
            except httpx.HTTPError as e:
                logger.error(f"Failed to exchange code for token: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error in exchange_code_for_token: {str(e)}", exc_info=True)
                return None

    @classmethod
    async def get_user_info(cls, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user information from Google using access token"""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(cls.get_google_userinfo_url(), headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError:
                return None

    @classmethod
    async def create_or_get_oauth_user(cls, db: AsyncSession, google_user_info: Dict[str, Any]) -> User:
        """Create or retrieve user from OAuth information"""
        email = google_user_info.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by Google"
            )

        # Check if user already exists
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # Update existing user with OAuth info if needed
            now = datetime.now()
            stmt = (
                update(User)
                .where(User.id == existing_user.id)
                .values(
                    google_id=google_user_info.get("id"),
                    profile_picture=google_user_info.get("picture"),
                    updated_at=now
                )
            )
            await db.execute(stmt)
            await db.commit()
            await db.refresh(existing_user)

            # Return the full User object with all fields including is_admin and subscription_tier
            return existing_user
        else:
            # Create new user from OAuth information
            now = datetime.now()
            user_db = User(
                email=email,
                hashed_password="",  # OAuth users don't need password
                full_name=google_user_info.get("name", ""),
                is_active=True,
                is_admin=False,  # New users are not admin by default
                subscription_tier="free",  # New users start with free tier
                google_id=google_user_info.get("id"),
                profile_picture=google_user_info.get("picture"),
                created_at=now,
                updated_at=now,
                preferences="{}",
                privacy_policy_accepted=True,  # Assumed for OAuth users
                privacy_policy_accepted_at=now,
                data_processing_accepted=True,  # Assumed for OAuth users
                data_processing_accepted_at=now,
                marketing_emails_accepted=False
            )

            db.add(user_db)
            await db.commit()
            await db.refresh(user_db)

            # Return the full User object with all fields including is_admin and subscription_tier
            return user_db

    @classmethod
    async def link_google_account(cls, db: AsyncSession, email: str, google_user_info: Dict[str, Any]) -> bool:
        """Link Google account to existing email/password user"""
        stmt = select(User).where(User.email == email, User.is_active == True)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if not existing_user:
            return False

        stmt = (
            update(User)
            .where(User.id == existing_user.id)
            .values(
                google_id=google_user_info.get("id"),
                profile_picture=google_user_info.get("picture"),
                updated_at=datetime.now()
            )
        )
        await db.execute(stmt)
        await db.commit()
        return True