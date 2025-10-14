from typing import Optional
from functools import wraps
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import verify_token
from app.services.auth_service import get_user_by_email
from app.models.user import UserLogin
from app.db.database import get_db
from app.db.models import User, Subscription
from app.services.subscription_service import SubscriptionService

security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[UserLogin]:
    """Get current user from JWT token"""
    token = credentials.credentials
    username = verify_token(token)

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_email(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_active_user(current_user: UserLogin = Depends(get_current_user)) -> UserLogin:
    """Get current active user (alias for compatibility)"""
    return current_user


def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional)) -> Optional[UserLogin]:
    """Get current user from JWT token, or None if not authenticated"""
    if not credentials:
        return None

    token = credentials.credentials
    username = verify_token(token)

    if not username:
        return None

    user = get_user_by_email(username)
    if not user or not user.is_active:
        return None

    return user


async def get_subscription_status(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Optional[Subscription]:
    """
    Get current user's subscription status.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Subscription record or None if no subscription
    """
    service = SubscriptionService()
    # Get user by email to get the user ID
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return None

    return await service.get_subscription_status(db, user.id)


async def require_admin_access(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Verify user has admin access.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        User object if admin access verified

    Raises:
        HTTPException: If user is not admin
    """
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check for admin flag (should be added to User model)
    # For now, using subscription_tier == "admin" as temporary check
    if not hasattr(user, 'is_admin') or not user.is_admin:
        # Fallback to subscription_tier check
        if user.subscription_tier != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

    return user


def subscription_tier_required(tier: str):
    """
    Decorator to require specific subscription tier for endpoint access.

    Args:
        tier: Required subscription tier ('premium' or 'free')

    Returns:
        FastAPI dependency decorator

    Example:
        @router.get("/premium-feature")
        @subscription_tier_required("premium")
        async def premium_only_endpoint():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(
            *args,
            current_user: UserLogin = Depends(get_current_user),
            db: AsyncSession = Depends(get_db),
            **kwargs
        ):
            # Get user subscription status
            from sqlalchemy import select
            stmt = select(User).where(User.email == current_user.email)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User not found"
                )

            # Check subscription tier
            if tier == "premium" and user.subscription_tier != "premium":
                # Check if user has active subscription
                service = SubscriptionService()
                subscription = await service.get_subscription_status(db, user.id)

                if not subscription or subscription.status not in ["active", "trialing"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Premium subscription required for this feature"
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def check_subscription_feature(
    feature: str,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> bool:
    """
    Check if user has access to a specific feature based on subscription.

    Args:
        feature: Feature to check (e.g., 'prospects_limit', 'export_enabled', 'advanced_filters_enabled', 'comparison_enabled')
        current_user: Current authenticated user
        db: Database session

    Returns:
        True if user has access to feature, False otherwise
    """
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return False

    # Feature access rules
    feature_rules = {
        "prospects_limit": {
            "free": 100,
            "premium": 500
        },
        "export_enabled": {
            "free": False,
            "premium": True
        },
        "advanced_filters_enabled": {
            "free": False,
            "premium": True
        },
        "comparison_enabled": {
            "free": False,
            "premium": True
        }
    }

    if feature not in feature_rules:
        return False

    rule = feature_rules[feature]
    tier = user.subscription_tier or "free"

    if isinstance(rule[tier], bool):
        return rule[tier]
    else:
        # For numeric limits, return the value
        return rule[tier]