"""
Test rookie ball collection on a single season (2024) to verify it works
"""
import asyncio
from collect_rookie_ball import RookieBallCollector

async def test_single_season():
    """Test collection for 2024 season only."""
    print("=" * 80)
    print("TESTING ROOKIE BALL COLLECTION - 2024 SEASON")
    print("=" * 80)
    print("This will collect rookie ball data for 2024 only as a test.")
    print("=" * 80)

    collector = RookieBallCollector()
    collector.seasons = [2024]  # Override to only collect 2024

    try:
        await collector.init_db()
        await collector.collect_season(2024)

        print("\n" + "=" * 80)
        print("TEST COLLECTION COMPLETE")
        print("=" * 80)
        print(f"Players processed: {collector.stats['total_players']}")
        print(f"Game logs stored: {collector.stats['total_game_logs']}")
        print("=" * 80)

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await collector.close_db()

if __name__ == "__main__":
    asyncio.run(test_single_season())