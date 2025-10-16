"""
Verify admin status for a user
"""
import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User


async def verify_user_status(email: str):
    """Verify current user status in database"""

    async with AsyncSessionLocal() as db:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            print(f"[ERROR] User not found: {email}")
            return

        print("=" * 60)
        print(f"USER STATUS REPORT: {email}")
        print("=" * 60)
        print(f"User ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Full Name: {user.full_name}")
        print(f"Is Active: {user.is_active}")
        print(f"Is Admin: {user.is_admin}")
        print(f"Subscription Tier: {user.subscription_tier}")
        print(f"Google ID: {user.google_id}")
        print(f"Stripe Customer ID: {user.stripe_customer_id}")
        print(f"Created At: {user.created_at}")
        print(f"Updated At: {user.updated_at}")
        print("=" * 60)


async def main():
    await verify_user_status("dylanmerlo@gmail.com")


if __name__ == "__main__":
    asyncio.run(main())
