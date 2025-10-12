"""
Manually trigger Bluesky collection for Trey Yesavage
This will collect and save posts immediately
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set Bluesky credentials if not already set
if not os.getenv('BLUESKY_HANDLE'):
    print("WARNING: Bluesky credentials not configured")
    print("Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD environment variables")
    print("Example: export BLUESKY_HANDLE='username.bsky.social'")
    print("         export BLUESKY_APP_PASSWORD='your-app-password'")

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype
from app.services.social_collector import SocialMediaCollector
from app.services.hype_calculator import HypeCalculator

async def manual_collect():
    """Manually collect data for Trey Yesavage"""
    db = SessionLocal()

    try:
        # Find Trey Yesavage
        trey = db.query(PlayerHype).filter(
            PlayerHype.player_name.ilike('%yesavage%')
        ).first()

        if not trey:
            print("ERROR: Trey Yesavage not found in database")
            return

        print(f"Found: {trey.player_name} (ID: {trey.player_id})")
        print(f"Current HYPE Score: {trey.hype_score}")
        print(f"Last calculated: {trey.last_calculated}")
        print()

        # Collect data from all platforms
        collector = SocialMediaCollector(db)

        print("="*70)
        print("COLLECTING SOCIAL DATA...")
        print("="*70)

        result = await collector.collect_all_platforms(
            trey.player_name,
            trey.player_id
        )

        for platform, data in result.items():
            print(f"\n{platform.upper()}:")
            print(f"  Status: {data.get('status', 'unknown')}")
            if data.get('status') == 'success':
                print(f"  Count: {data.get('count', 0)}")
            elif data.get('status') == 'error':
                print(f"  Error: {data.get('message', 'Unknown error')}")
            elif data.get('status') == 'skipped':
                print(f"  Reason: {data.get('reason', 'Unknown')}")

        # Recalculate HYPE score
        print("\n" + "="*70)
        print("RECALCULATING HYPE SCORE...")
        print("="*70)

        calculator = HypeCalculator(db)
        calc_result = calculator.calculate_hype_score(trey.player_id)

        print(f"\nNew HYPE Score: {calc_result['hype_score']:.2f}")
        print(f"Trend: {calc_result['trend']:.2f}%")
        print(f"24h Mentions: {calc_result['metrics']['social'].get('total_mentions_24h', 0)}")
        print(f"7d Mentions: {calc_result['metrics']['social'].get('total_mentions_7d', 0)}")
        print(f"14d Mentions: {calc_result['metrics']['social'].get('total_mentions_14d', 0)}")

        # Show breakdown
        print("\nComponent Scores:")
        for component, score in calc_result['components'].items():
            print(f"  {component.capitalize()}: {score:.2f}")

        print("\n" + "="*70)
        print("Collection complete! Data has been saved to database.")
        print("The HYPE detail page should now show the updated information.")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("Manual HYPE Data Collection for Trey Yesavage")
    print("="*70)
    asyncio.run(manual_collect())