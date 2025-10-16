"""
Create or update maulikramani93@gmail.com as admin with premium tier
Usage: python create_admin_maulik.py
"""
import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User
# No password hashing needed for OAuth-only user
from datetime import datetime


async def create_or_update_admin(email: str):
    """Create or update user with admin access and premium subscription"""

    async with AsyncSessionLocal() as db:
        # Check if user exists
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            print(f"[OK] Found existing user: {user.email} (ID: {user.id})")
            print(f"   Current status:")
            print(f"   - is_admin: {user.is_admin}")
            print(f"   - subscription_tier: {user.subscription_tier}")
            print(f"   - is_active: {user.is_active}")
            print()

            # Update existing user to admin with premium tier
            user.is_admin = True
            user.subscription_tier = "premium"
            user.is_active = True
            user.updated_at = datetime.now()

            await db.commit()
            await db.refresh(user)

            print(f"[OK] Admin access granted!")
        else:
            print(f"[INFO] User not found, creating new user: {email}")
            print()

            # Create new user with admin privileges
            # Use a secure random password (user should use OAuth)
            import secrets
            import hashlib
            random_password = secrets.token_urlsafe(32)
            hashed = hashlib.sha256(random_password.encode()).hexdigest()

            user = User(
                email=email,
                full_name="Maulik Ramani",  # Can be updated on first OAuth login
                hashed_password=hashed,  # Placeholder - user should use OAuth
                is_active=True,
                is_admin=True,
                subscription_tier="premium",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            db.add(user)
            await db.commit()
            await db.refresh(user)

            print(f"[OK] User created successfully!")
            print(f"   User should log in using Google OAuth")

        print()
        print(f"   Final status:")
        print(f"   - ID: {user.id}")
        print(f"   - Email: {user.email}")
        print(f"   - is_admin: {user.is_admin}")
        print(f"   - subscription_tier: {user.subscription_tier}")
        print(f"   - is_active: {user.is_active}")
        print()
        print(f"[SUCCESS] User {email} now has admin access and premium features!")

        return True


async def main():
    """Main function"""
    email = "maulikramani93@gmail.com"

    print("=" * 60)
    print("[ADMIN] A Fine Wine Dynasty - Create/Update Admin User")
    print("=" * 60)
    print(f"Target user: {email}")
    print()

    try:
        success = await create_or_update_admin(email)

        if success:
            print()
            print("=" * 60)
            print("[SUCCESS] Admin access configured successfully!")
            print("=" * 60)
            print()
            print("Next steps:")
            print("1. User can log in with email: maulikramani93@gmail.com")
            print("2. If newly created, use temporary password or OAuth")
            print("3. All premium features are now accessible")
            print("4. Admin-only endpoints are now available")
    except Exception as e:
        print()
        print("=" * 60)
        print("[ERROR] Failed to configure admin access")
        print("=" * 60)
        print(f"Error: {str(e)}")
        print()
        print("Troubleshooting:")
        print("1. Check that the database connection is working")
        print("2. Verify the database schema is up to date")
        print("3. Check application logs for detailed errors")


if __name__ == "__main__":
    asyncio.run(main())
