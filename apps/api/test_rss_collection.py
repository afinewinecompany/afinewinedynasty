"""
Test RSS feed collection
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.services.rss_collector import collect_rss_feeds

async def test_rss():
    """Test RSS feed collection"""
    db = SessionLocal()

    try:
        print("Starting RSS feed collection...")
        result = await collect_rss_feeds(db)
        print(f"\nResult: {result}")

    except Exception as e:
        print(f"\n[EXCEPTION] Exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_rss())
