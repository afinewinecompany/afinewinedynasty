from typing import Optional, Dict, Any
import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.config import settings
from app.db.models import User
from app.models.user import UserInDB, UserLogin
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
            except httpx.HTTPError:
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
    async def create_or_get_oauth_user(cls, db: AsyncSession, google_user_info: Dict[str, Any]) -> UserInDB:
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

            return UserInDB(
                id=existing_user.id,
                email=existing_user.email,
                full_name=existing_user.full_name,
                hashed_password=existing_user.hashed_password,
                is_active=existing_user.is_active,
                created_at=existing_user.created_at,
                updated_at=existing_user.updated_at,
                google_id=existing_user.google_id,
                profile_picture=existing_user.profile_picture
            )
        else:
            # Create new user from OAuth information
            now = datetime.now()
            user_db = User(
                email=email,
                hashed_password="",  # OAuth users don't need password
                full_name=google_user_info.get("name", ""),
                is_active=True,
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

            return UserInDB(
                id=user_db.id,
                email=user_db.email,
                full_name=user_db.full_name,
                hashed_password=user_db.hashed_password,
                is_active=user_db.is_active,
                created_at=user_db.created_at,
                updated_at=user_db.updated_at,
                google_id=user_db.google_id,
                profile_picture=user_db.profile_picture
            )

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