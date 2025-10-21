"""
Test the updated RSS collector with new feeds
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.database import SyncSessionLocal
from app.services.rss_collector import collect_rss_feeds


async def test_rss_collection():
    """Test RSS feed collection with new feeds"""
    print("="*80)
    print("TESTING UPDATED RSS COLLECTOR")
    print("="*80)
    print()

    db = SyncSessionLocal()

    try:
        # Run collection
        results = await collect_rss_feeds(db)

        print("\n" + "="*80)
        print("COLLECTION RESULTS")
        print("="*80)
        print(f"Status: {results['status']}")
        print(f"Total articles: {results['total_articles']}")
        print(f"Articles with player mentions: {results.get('articles_with_players', 0)}")
        print(f"Total player-article associations: {results['processed_for_players']}")
        print(f"Unique players mentioned: {results.get('players_mentioned', 0)}")
        print()
        print("Feed Breakdown:")
        print("-"*80)
        for feed, count in sorted(results.get('feed_breakdown', {}).items(), key=lambda x: x[1], reverse=True):
            print(f"  {feed:45s}: {count:4d} articles")
        print("="*80)

    except Exception as e:
        print(f"Error during collection: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_rss_collection())
