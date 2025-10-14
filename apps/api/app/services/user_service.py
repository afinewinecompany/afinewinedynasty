from datetime import datetime, timedelta
from typing import Optional
import json
import stripe
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.db.models import User, UserSession
from app.models.user import UserInDB, UserLogin
from app.core.security import verify_password, get_password_hash, is_password_complex
from app.core.config import settings

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[UserLogin]:
    """Get user by email from database"""
    stmt = select(User).where(User.email == email, User.is_active == True)
    result = await db.execute(stmt)
    user_db = result.scalar_one_or_none()

    if user_db:
        return UserLogin(
            id=user_db.id,
            email=user_db.email,
            hashed_password=user_db.hashed_password,
            is_active=user_db.is_active,
            subscription_tier=user_db.subscription_tier or "free"
        )
    return None


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID from database"""
    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str, full_name: str) -> UserInDB:
    """Create new user"""
    # Check password complexity
    is_valid, message = is_password_complex(password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    # Check if user already exists
    existing_user = await get_user_by_email(db, email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )

    # Hash password and create user
    hashed_password = get_password_hash(password)
    now = datetime.now()

    # Create Stripe customer
    stripe_customer_id = None
    if settings.STRIPE_SECRET_KEY:  # Only create if Stripe is configured
        try:
            customer = stripe.Customer.create(
                email=email,
                name=full_name,
                metadata={
                    "platform": "afinewinedynasty",
                    "created_at": now.isoformat()
                }
            )
            stripe_customer_id = customer.id
        except stripe.error.StripeError as e:
            # Log error but don't fail user creation
            print(f"Failed to create Stripe customer: {e}")

    user_db = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        is_active=True,
        stripe_customer_id=stripe_customer_id,
        created_at=now,
        updated_at=now,
        preferences="{}",  # Default empty JSON
        privacy_policy_accepted=True,  # Required for registration
        privacy_policy_accepted_at=now,
        data_processing_accepted=True,  # Required for registration
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
        updated_at=user_db.updated_at
    )


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[UserLogin]:
    """Authenticate user credentials"""
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user_session(db: AsyncSession, user_email: str, refresh_token: str, expires_at: datetime) -> UserSession:
    """Create a new user session"""
    # Get user by email
    stmt = select(User).where(User.email == user_email, User.is_active == True)
    result = await db.execute(stmt)
    user_db = result.scalar_one_or_none()

    if not user_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    session = UserSession(
        user_id=user_db.id,
        refresh_token=refresh_token,
        is_revoked=False,
        expires_at=expires_at,
        created_at=datetime.now()
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def revoke_user_session(db: AsyncSession, refresh_token: str) -> bool:
    """Revoke a user session"""
    stmt = (
        update(UserSession)
        .where(UserSession.refresh_token == refresh_token)
        .values(is_revoked=True, revoked_at=datetime.now())
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


async def revoke_all_user_sessions(db: AsyncSession, user_email: str) -> int:
    """Revoke all sessions for a user"""
    # Get user by email
    stmt = select(User).where(User.email == user_email, User.is_active == True)
    result = await db.execute(stmt)
    user_db = result.scalar_one_or_none()

    if not user_db:
        return 0

    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_db.id, UserSession.is_revoked == False)
        .values(is_revoked=True, revoked_at=datetime.now())
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def is_session_valid(db: AsyncSession, refresh_token: str) -> bool:
    """Check if a session is valid (not revoked and not expired)"""
    stmt = select(UserSession).where(
        UserSession.refresh_token == refresh_token,
        UserSession.is_revoked == False,
        UserSession.expires_at > datetime.now()
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    return session is not None


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """Clean up expired sessions"""
    stmt = (
        update(UserSession)
        .where(
            UserSession.expires_at < datetime.now(),
            UserSession.is_revoked == False
        )
        .values(is_revoked=True, revoked_at=datetime.now())
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


def get_generic_error_message() -> str:
    """Return generic error message to prevent user enumeration"""
    return "Invalid email or password"