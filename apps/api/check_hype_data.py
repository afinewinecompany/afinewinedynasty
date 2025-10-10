"""
Check HYPE data setup
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, MediaArticle
from app.db.models import Prospect

def check_data():
    """Check HYPE data setup"""
    db = SessionLocal()

    try:
        # Check prospects
        prospects = db.query(Prospect).limit(5).all()
        print(f"Found {db.query(Prospect).count()} prospects in Prospect table")
        print("\nFirst 5 prospects:")
        for p in prospects:
            print(f"  - {p.name} (mlb_id: {p.mlb_id})")

        # Check PlayerHype
        players = db.query(PlayerHype).limit(5).all()
        print(f"\nFound {db.query(PlayerHype).count()} players in PlayerHype table")
        print("\nFirst 5 PlayerHype records:")
        for p in players:
            print(f"  - {p.player_name} (player_id: {p.player_id})")

        # Check media articles
        articles = db.query(MediaArticle).all()
        print(f"\nFound {len(articles)} media articles")
        if articles:
            print("\nFirst 5 articles:")
            for article in articles[:5]:
                print(f"  - {article.title}")
                print(f"    Source: {article.source}")
                print(f"    Player HYPE ID: {article.player_hype_id}")

    finally:
        db.close()

if __name__ == "__main__":
    check_data()
