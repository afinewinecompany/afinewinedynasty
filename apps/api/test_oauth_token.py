"""
Test OAuth login and decode the JWT token to verify it contains tier and admin
"""
import asyncio
from jose import jwt
from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.services.oauth_service import GoogleOAuthService
from app.services.user_service import get_user_by_email
from app.core.security import create_access_token


async def test_token_generation():
    """Test that tokens are generated correctly with metadata"""

    async with AsyncSessionLocal() as db:
        # Get the user
        user = await get_user_by_email(db, "dylanmerlo@gmail.com")

        if not user:
            print("[ERROR] User not found!")
            return

        print("=" * 60)
        print("USER DATA FROM get_user_by_email:")
        print("=" * 60)
        print(f"Email: {user.email}")
        print(f"ID: {user.id}")
        print(f"Subscription Tier: {user.subscription_tier}")
        print(f"Is Admin: {user.is_admin}")
        print(f"Is Active: {user.is_active}")
        print()

        # Generate token like the auth endpoint does
        print("=" * 60)
        print("GENERATING JWT TOKEN:")
        print("=" * 60)

        token = create_access_token(
            subject=user.email,
            subscription_tier=user.subscription_tier or "free",
            is_admin=user.is_admin,
            user_id=user.id
        )

        print(f"Token: {token[:50]}...")
        print()

        # Decode the token to see what's inside
        print("=" * 60)
        print("DECODED JWT TOKEN PAYLOAD:")
        print("=" * 60)

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        for key, value in payload.items():
            print(f"{key}: {value}")

        print()
        print("=" * 60)
        print("VERIFICATION:")
        print("=" * 60)

        if "tier" in payload:
            print(f"[OK] Token contains 'tier': {payload['tier']}")
        else:
            print("[ERROR] Token does NOT contain 'tier'!")

        if "admin" in payload:
            print(f"[OK] Token contains 'admin': {payload['admin']}")
        else:
            print("[ERROR] Token does NOT contain 'admin'!")

        if "user_id" in payload:
            print(f"[OK] Token contains 'user_id': {payload['user_id']}")
        else:
            print("[ERROR] Token does NOT contain 'user_id'!")

        print()

        # Check what the token says
        if payload.get("tier") == "premium":
            print("[SUCCESS] Token correctly shows PREMIUM tier!")
        else:
            print(f"[ERROR] Token shows tier as: {payload.get('tier', 'MISSING')}")

        if payload.get("admin") == True:
            print("[SUCCESS] Token correctly shows ADMIN status!")
        else:
            print(f"[ERROR] Token shows admin as: {payload.get('admin', 'MISSING')}")


async def main():
    await test_token_generation()


if __name__ == "__main__":
    asyncio.run(main())
