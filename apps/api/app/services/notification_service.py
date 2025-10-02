"""
Notification service for handling push notifications

This service manages web push subscriptions and sends notifications to users
following the existing service pattern from the project.

@since 1.0.0
"""

from typing import Optional, List, Dict
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.services.base_service import BaseService
from app.db.models import UserPushSubscription, User
from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService(BaseService):
    """
    Service for managing push notifications and subscriptions

    Handles web push subscription storage and notification delivery
    to subscribed devices.
    """

    async def subscribe_to_push(
        self,
        db: AsyncSession,
        user_id: int,
        subscription_info: Dict
    ) -> UserPushSubscription:
        """
        Store web push subscription endpoint for a user

        Args:
            db: Database session
            user_id: User ID
            subscription_info: Push subscription data containing endpoint, keys, etc.

        Returns:
            UserPushSubscription: Created or updated subscription record

        Example:
            subscription = await notification_service.subscribe_to_push(
                db,
                user_id=123,
                subscription_info={
                    "endpoint": "https://fcm.googleapis.com/...",
                    "keys": {
                        "p256dh": "...",
                        "auth": "..."
                    },
                    "deviceInfo": {...}
                }
            )
        """
        try:
            # Check if subscription already exists
            existing = await db.execute(
                select(UserPushSubscription).where(
                    UserPushSubscription.endpoint == subscription_info["endpoint"]
                )
            )
            subscription = existing.scalar_one_or_none()

            if subscription:
                # Update existing subscription
                subscription.p256dh_key = subscription_info["keys"]["p256dh"]
                subscription.auth_key = subscription_info["keys"]["auth"]
                subscription.device_info = subscription_info.get("deviceInfo")
                subscription.is_active = True
                subscription.user_id = user_id
            else:
                # Create new subscription
                subscription = UserPushSubscription(
                    user_id=user_id,
                    endpoint=subscription_info["endpoint"],
                    p256dh_key=subscription_info["keys"]["p256dh"],
                    auth_key=subscription_info["keys"]["auth"],
                    device_info=subscription_info.get("deviceInfo"),
                    is_active=True
                )
                db.add(subscription)

            await db.commit()
            await db.refresh(subscription)

            logger.info(f"Push subscription saved for user {user_id}")
            return subscription

        except Exception as e:
            logger.error(f"Failed to save push subscription: {e}")
            await db.rollback()
            raise

    async def unsubscribe_from_push(
        self,
        db: AsyncSession,
        user_id: int,
        endpoint: str
    ) -> bool:
        """
        Remove push subscription for a user

        Args:
            db: Database session
            user_id: User ID
            endpoint: Push subscription endpoint to remove

        Returns:
            bool: True if subscription was removed, False if not found
        """
        try:
            result = await db.execute(
                select(UserPushSubscription).where(
                    and_(
                        UserPushSubscription.user_id == user_id,
                        UserPushSubscription.endpoint == endpoint
                    )
                )
            )
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription.is_active = False
                await db.commit()
                logger.info(f"Push subscription removed for user {user_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to remove push subscription: {e}")
            await db.rollback()
            raise

    async def get_user_subscriptions(
        self,
        db: AsyncSession,
        user_id: int
    ) -> List[UserPushSubscription]:
        """
        Get all active push subscriptions for a user

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List[UserPushSubscription]: List of active subscriptions
        """
        result = await db.execute(
            select(UserPushSubscription).where(
                and_(
                    UserPushSubscription.user_id == user_id,
                    UserPushSubscription.is_active == True
                )
            )
        )
        return result.scalars().all()

    async def send_notification(
        self,
        db: AsyncSession,
        user_id: int,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> bool:
        """
        Send push notification to user's subscribed devices

        Args:
            db: Database session
            user_id: User ID
            title: Notification title
            body: Notification body text
            data: Optional additional data for the notification

        Returns:
            bool: True if notification was sent to at least one device

        Note:
            This is a placeholder implementation. Actual web push sending
            would require integration with a service like web-push or FCM.
        """
        try:
            # Get user's active subscriptions
            subscriptions = await self.get_user_subscriptions(db, user_id)

            if not subscriptions:
                logger.info(f"No active subscriptions for user {user_id}")
                return False

            # TODO: Implement actual push notification sending
            # This would typically use a library like pywebpush
            # Example:
            # from pywebpush import webpush
            # for subscription in subscriptions:
            #     webpush(
            #         subscription_info={
            #             "endpoint": subscription.endpoint,
            #             "keys": {
            #                 "p256dh": subscription.p256dh_key,
            #                 "auth": subscription.auth_key
            #             }
            #         },
            #         data=json.dumps({
            #             "title": title,
            #             "body": body,
            #             "data": data
            #         }),
            #         vapid_private_key=settings.VAPID_PRIVATE_KEY,
            #         vapid_claims={
            #             "sub": f"mailto:{settings.VAPID_EMAIL}"
            #         }
            #     )

            logger.info(
                f"Would send notification to {len(subscriptions)} devices for user {user_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    async def send_bulk_notification(
        self,
        db: AsyncSession,
        user_ids: List[int],
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> Dict[int, bool]:
        """
        Send notification to multiple users

        Args:
            db: Database session
            user_ids: List of user IDs
            title: Notification title
            body: Notification body text
            data: Optional additional data

        Returns:
            Dict mapping user_id to success status
        """
        results = {}

        for user_id in user_ids:
            results[user_id] = await self.send_notification(
                db, user_id, title, body, data
            )

        return results

    async def cleanup_inactive_subscriptions(
        self,
        db: AsyncSession,
        days_inactive: int = 30
    ) -> int:
        """
        Clean up old inactive subscriptions

        Args:
            db: Database session
            days_inactive: Number of days of inactivity before cleanup

        Returns:
            int: Number of subscriptions cleaned up
        """
        # TODO: Implement cleanup of old inactive subscriptions
        # This would delete subscriptions that have been inactive for X days
        return 0