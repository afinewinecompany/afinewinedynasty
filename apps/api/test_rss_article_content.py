"""
Check actual RSS article content
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.services.rss_collector import RSSCollector

async def check_articles():
    """Check what RSS articles actually contain"""
    db = SessionLocal()

    try:
        collector = RSSCollector(db)

        # Collect from one feed
        print("Collecting from rotowire feed...")
        articles = await collector.collect_feed('rotowire')

        print(f"\nFound {len(articles)} articles\n")

        # Show first 3 articles
        for i, article in enumerate(articles[:3], 1):
            print(f"{'='*70}")
            print(f"Article {i}:")
            print(f"Title: {article['title']}")
            print(f"Summary: {article['summary'][:200]}...")
            print()

            # Check if any player names are mentioned
            full_text = f"{article['title']} {article['summary']}".lower()

            # Check for some common prospect names
            test_names = [
                'colt emerson', 'jj wetherholt', 'leo de vries',
                'paul skenes', 'jackson holliday', 'dylan crews',
                'wyatt langford', 'jackson merrill', 'james wood',
                'shota imanaga', 'yoshinobu yamamoto'
            ]

            found = []
            for name in test_names:
                if name in full_text:
                    found.append(name)

            if found:
                print(f"  MATCHES: {', '.join(found)}")
            else:
                print(f"  No matches from test list")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(check_articles())
