"""
Grant admin access and premium tier to a specific user
Usage: python grant_admin_access.py
"""
import asyncio
from sqlalchemy import select, update
from app.db.database import AsyncSessionLocal
from app.db.models import User
from datetime import datetime


async def grant_admin_access(email: str):
    """Grant admin access and premium subscription to user"""

    async with AsyncSessionLocal() as db:
        # Find user by email
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            print(f"[ERROR] User not found: {email}")
            return False

        print(f"[OK] Found user: {user.email} (ID: {user.id})")
        print(f"   Current status:")
        print(f"   - is_admin: {user.is_admin}")
        print(f"   - subscription_tier: {user.subscription_tier}")
        print(f"   - is_active: {user.is_active}")
        print()

        # Update user to admin with premium tier
        user.is_admin = True
        user.subscription_tier = "premium"
        user.is_active = True
        user.updated_at = datetime.now()

        await db.commit()
        await db.refresh(user)

        print(f"[OK] Admin access granted!")
        print(f"   Updated status:")
        print(f"   - is_admin: {user.is_admin}")
        print(f"   - subscription_tier: {user.subscription_tier}")
        print(f"   - is_active: {user.is_active}")
        print()
        print(f"[SUCCESS] User {email} now has admin access and premium features!")

        return True


async def main():
    """Main function"""
    email = "dylanmerlo@gmail.com"

    print("=" * 60)
    print("[ADMIN] A Fine Wine Dynasty - Grant Admin Access")
    print("=" * 60)
    print(f"Target user: {email}")
    print()

    success = await grant_admin_access(email)

    if success:
        print()
        print("=" * 60)
        print("[SUCCESS] Admin access granted successfully!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Log out and log back in to refresh your session")
        print("2. All premium features should now be accessible")
        print("3. Admin-only endpoints are now available")
    else:
        print()
        print("=" * 60)
        print("[ERROR] Failed to grant admin access")
        print("=" * 60)
        print()
        print("Troubleshooting:")
        print("1. Make sure you've logged in at least once")
        print("2. Check that the email address is correct")
        print("3. Verify database connection is working")


if __name__ == "__main__":
    asyncio.run(main())
