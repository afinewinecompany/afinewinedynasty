"""
Notification API endpoints

Handles web push notification subscription and preference management

@since 1.0.0
"""

from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api import deps
from app.db.database import get_db
from app.db.models import User
from app.services.notification_service import NotificationService

router = APIRouter()


class PushSubscriptionRequest(BaseModel):
    """Request model for push subscription"""
    endpoint: str = Field(..., description="Push notification endpoint URL")
    keys: Dict[str, str] = Field(..., description="Encryption keys (p256dh and auth)")
    deviceInfo: Optional[Dict] = Field(None, description="Optional device information")


class PushSubscriptionResponse(BaseModel):
    """Response model for push subscription"""
    id: int
    endpoint: str
    is_active: bool
    created_at: str


class NotificationPreferencesRequest(BaseModel):
    """Request model for notification preferences"""
    push_enabled: bool = Field(True, description="Enable push notifications")
    email_enabled: bool = Field(True, description="Enable email notifications")
    notification_types: Dict[str, bool] = Field(
        default_factory=lambda: {
            "prospect_updates": True,
            "ranking_changes": True,
            "watchlist_alerts": True,
            "comparison_ready": True,
            "system_updates": False
        },
        description="Notification type preferences"
    )


class NotificationPreferencesResponse(BaseModel):
    """Response model for notification preferences"""
    push_enabled: bool
    email_enabled: bool
    notification_types: Dict[str, bool]
    push_subscriptions_count: int


@router.post("/subscribe", response_model=PushSubscriptionResponse)
async def subscribe_to_push_notifications(
    subscription: PushSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> PushSubscriptionResponse:
    """
    Subscribe to push notifications

    Store web push subscription endpoint and keys for the current user.
    """
    notification_service = NotificationService()

    try:
        # Save subscription
        saved_subscription = await notification_service.subscribe_to_push(
            db,
            user_id=current_user.id,
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": subscription.keys,
                "deviceInfo": subscription.deviceInfo
            }
        )

        return PushSubscriptionResponse(
            id=saved_subscription.id,
            endpoint=saved_subscription.endpoint,
            is_active=saved_subscription.is_active,
            created_at=saved_subscription.created_at.isoformat()
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save push subscription: {str(e)}"
        )


@router.delete("/unsubscribe")
async def unsubscribe_from_push_notifications(
    endpoint: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, bool]:
    """
    Unsubscribe from push notifications

    Remove a specific push subscription endpoint for the current user.
    """
    notification_service = NotificationService()

    success = await notification_service.unsubscribe_from_push(
        db,
        user_id=current_user.id,
        endpoint=endpoint
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    return {"success": True}


@router.get("/subscriptions", response_model=list[PushSubscriptionResponse])
async def get_push_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> list[PushSubscriptionResponse]:
    """
    Get all push subscriptions

    Retrieve all active push subscription endpoints for the current user.
    """
    notification_service = NotificationService()

    subscriptions = await notification_service.get_user_subscriptions(
        db,
        user_id=current_user.id
    )

    return [
        PushSubscriptionResponse(
            id=sub.id,
            endpoint=sub.endpoint,
            is_active=sub.is_active,
            created_at=sub.created_at.isoformat()
        )
        for sub in subscriptions
    ]


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> NotificationPreferencesResponse:
    """
    Get notification preferences

    Retrieve the current user's notification preferences.
    """
    # Get preferences from user model (stored in JSONB)
    preferences = current_user.preferences or {}
    notification_prefs = preferences.get("notifications", {})

    # Get count of active push subscriptions
    notification_service = NotificationService()
    subscriptions = await notification_service.get_user_subscriptions(
        db,
        user_id=current_user.id
    )

    return NotificationPreferencesResponse(
        push_enabled=notification_prefs.get("push_enabled", True),
        email_enabled=notification_prefs.get("email_enabled", True),
        notification_types=notification_prefs.get("notification_types", {
            "prospect_updates": True,
            "ranking_changes": True,
            "watchlist_alerts": True,
            "comparison_ready": True,
            "system_updates": False
        }),
        push_subscriptions_count=len(subscriptions)
    )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    preferences: NotificationPreferencesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> NotificationPreferencesResponse:
    """
    Update notification preferences

    Update the current user's notification preferences.
    """
    # Update preferences in user model
    if not current_user.preferences:
        current_user.preferences = {}

    current_user.preferences["notifications"] = {
        "push_enabled": preferences.push_enabled,
        "email_enabled": preferences.email_enabled,
        "notification_types": preferences.notification_types
    }

    await db.commit()
    await db.refresh(current_user)

    # Get count of active push subscriptions
    notification_service = NotificationService()
    subscriptions = await notification_service.get_user_subscriptions(
        db,
        user_id=current_user.id
    )

    return NotificationPreferencesResponse(
        push_enabled=preferences.push_enabled,
        email_enabled=preferences.email_enabled,
        notification_types=preferences.notification_types,
        push_subscriptions_count=len(subscriptions)
    )


@router.post("/test")
async def send_test_notification(
    title: str = "Test Notification",
    body: str = "This is a test notification from A Fine Wine Dynasty",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, bool]:
    """
    Send test notification

    Send a test push notification to all active subscriptions for the current user.
    This endpoint is useful for testing push notification setup.
    """
    notification_service = NotificationService()

    success = await notification_service.send_notification(
        db,
        user_id=current_user.id,
        title=title,
        body=body,
        data={"test": True, "timestamp": "2025-09-30T00:00:00Z"}
    )

    return {"success": success}