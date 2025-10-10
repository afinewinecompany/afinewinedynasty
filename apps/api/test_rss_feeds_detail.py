"""
Check RSS feed collection in detail
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.services.rss_collector import RSSCollector

async def check_feeds():
    """Check each RSS feed in detail"""
    db = SessionLocal()

    try:
        collector = RSSCollector(db)

        print(f"Total RSS feeds configured: {len(collector.feeds)}\n")

        total_articles = 0
        successful_feeds = 0
        failed_feeds = 0

        for source, url in collector.feeds.items():
            print(f"Fetching {source}...")
            print(f"  URL: {url[:80]}...")

            articles = await collector.fetch_feed(source, url)

            if articles:
                print(f"  [OK] Got {len(articles)} articles")
                successful_feeds += 1
                total_articles += len(articles)

                # Show date range
                if articles:
                    dates = [a['published'] for a in articles if a['published']]
                    if dates:
                        print(f"    Date range: {min(dates).date()} to {max(dates).date()}")
            else:
                print(f"  [FAIL] No articles")
                failed_feeds += 1

            print()

        print("="*70)
        print(f"SUMMARY:")
        print(f"  Total feeds configured: {len(collector.feeds)}")
        print(f"  Successful feeds: {successful_feeds}")
        print(f"  Failed feeds: {failed_feeds}")
        print(f"  Total articles fetched: {total_articles}")
        print(f"  Average per feed: {total_articles / successful_feeds if successful_feeds > 0 else 0:.1f}")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(check_feeds())
