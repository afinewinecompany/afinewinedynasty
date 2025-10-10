"""
Test Bluesky collection for Tink Hence
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.services.social_collector import SocialMediaCollector

async def test_tink_hence():
    """Test collecting Bluesky data for Tink Hence"""
    db = SessionLocal()

    try:
        collector = SocialMediaCollector(db)

        print("Testing Bluesky collection for 'Tink Hence'...")
        result = await collector.collect_bluesky_data("Tink Hence", "tink-hence")

        print(f"\nResult: {result}")

        if result['status'] == 'success':
            print(f"\n[SUCCESS] Successfully collected {result['count']} posts")

            # Show the posts
            if 'posts' in result:
                print("\nPosts collected:")
                for i, post in enumerate(result['posts'], 1):
                    print(f"\n{i}. ID: {post['id']}")
                    print(f"   Author: {post['author']}")
                    print(f"   Text: {post['text'][:100]}...")
                    print(f"   Sentiment: {post['sentiment']}")
        else:
            print(f"\n[ERROR] Error: {result.get('message', 'Unknown error')}")

    except Exception as e:
        print(f"\n[EXCEPTION] Exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_tink_hence())
