#!/usr/bin/env python
"""Test script to verify all imports are working correctly"""

import sys
import traceback

def test_imports():
    """Test all critical imports"""

    errors = []

    # Test database imports
    try:
        from app.db.database import get_db, SessionLocal, Base
        print("✓ Database imports successful")
    except Exception as e:
        errors.append(f"Database import error: {e}")
        traceback.print_exc()

    # Test auth imports
    try:
        from app.core.auth import get_current_user
        print("✓ Auth imports successful")
    except Exception as e:
        errors.append(f"Auth import error: {e}")
        traceback.print_exc()

    # Test hype model imports
    try:
        from app.models.hype import (
            PlayerHype, SocialMention, MediaArticle,
            HypeHistory, HypeAlert, TrendingTopic
        )
        print("✓ Hype model imports successful")
    except Exception as e:
        errors.append(f"Hype model import error: {e}")
        traceback.print_exc()

    # Test hype router imports
    try:
        from app.routers.hype import router
        print("✓ Hype router imports successful")
    except Exception as e:
        errors.append(f"Hype router import error: {e}")
        traceback.print_exc()

    # Test API router imports
    try:
        from app.api.api_v1.api import api_router
        print("✓ API router imports successful")
    except Exception as e:
        errors.append(f"API router import error: {e}")
        traceback.print_exc()

    # Test main app imports (without scheduler)
    try:
        from app.main import app
        print("✓ Main app imports successful")
    except Exception as e:
        errors.append(f"Main app import error: {e}")
        traceback.print_exc()

    return errors

if __name__ == "__main__":
    print("Testing imports...")
    print("-" * 50)

    errors = test_imports()

    print("-" * 50)
    if errors:
        print(f"\n❌ Found {len(errors)} import errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("\n✅ All imports successful!")
        sys.exit(0)