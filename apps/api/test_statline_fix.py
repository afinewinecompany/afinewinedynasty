"""Test the fixed statline rankings."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.statline_ranking_service import StatlineRankingService
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"


async def test_statline_rankings():
    """Test the statline ranking service."""

    # Create engine and session
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        service = StatlineRankingService(db)

        print("\n" + "="*60)
        print("Testing Statline Rankings with Fixed Query")
        print("="*60)

        # Test 1: Get all players (no level filter, low min PA)
        print("\n--- Test 1: All levels, min PA = 25 ---")
        rankings = await service.calculate_statline_rankings(
            level=None,
            min_plate_appearances=25,
            season=2025,
            include_pitch_data=True
        )

        print(f"Found {len(rankings)} total players")

        if rankings:
            print("\nTop 10 Players:")
            print(f"{'Rank':<5} {'Name':<25} {'Level':<6} {'PA':<5} {'Disc':<6} {'Pwr':<6} {'Cont':<6} {'Overall':<8}")
            print("-" * 85)

            for player in rankings[:10]:
                print(f"{player['rank']:<5} "
                      f"{player.get('name', 'Unknown')[:24]:<25} "
                      f"{player.get('level', 'N/A'):<6} "
                      f"{player.get('total_pa', 0):<5} "
                      f"{player.get('discipline_grade', 'N/A'):<6} "
                      f"{player.get('power_grade', 'N/A'):<6} "
                      f"{player.get('contact_grade', 'N/A'):<6} "
                      f"{player.get('overall_score', 0):<8.2f}")

        # Test 2: By level
        for level in ['AAA', 'AA', 'A+']:
            print(f"\n--- Test 2: Level = {level}, min PA = 50 ---")
            rankings = await service.calculate_statline_rankings(
                level=level,
                min_plate_appearances=50,
                season=2025,
                include_pitch_data=True
            )

            print(f"Found {len(rankings)} players at {level}")

            if rankings and len(rankings) > 0:
                print(f"\nTop 5 at {level}:")
                for i, player in enumerate(rankings[:5], 1):
                    print(f"  {i}. {player.get('name', 'Unknown'):<25} "
                          f"PA: {player.get('total_pa', 0):<4} "
                          f"Disc: {player.get('discipline_score', 0):.1f} "
                          f"Pwr: {player.get('power_score', 0):.1f} "
                          f"Cont: {player.get('contact_score', 0):.1f}")

        # Test 3: Check score distribution
        print("\n--- Test 3: Score Distribution (All Players) ---")
        all_rankings = await service.calculate_statline_rankings(
            level=None,
            min_plate_appearances=10,
            season=2025,
            include_pitch_data=True
        )

        if all_rankings:
            disc_scores = [p.get('discipline_score', 0) for p in all_rankings]
            power_scores = [p.get('power_score', 0) for p in all_rankings]
            contact_scores = [p.get('contact_score', 0) for p in all_rankings]
            overall_scores = [p.get('overall_score', 0) for p in all_rankings]

            print(f"\nScore Statistics ({len(all_rankings)} players):")
            print(f"  Discipline: Min={min(disc_scores):.1f}, Max={max(disc_scores):.1f}, "
                  f"Avg={sum(disc_scores)/len(disc_scores):.1f}")
            print(f"  Power:      Min={min(power_scores):.1f}, Max={max(power_scores):.1f}, "
                  f"Avg={sum(power_scores)/len(power_scores):.1f}")
            print(f"  Contact:    Min={min(contact_scores):.1f}, Max={max(contact_scores):.1f}, "
                  f"Avg={sum(contact_scores)/len(contact_scores):.1f}")
            print(f"  Overall:    Min={min(overall_scores):.1f}, Max={max(overall_scores):.1f}, "
                  f"Avg={sum(overall_scores)/len(overall_scores):.1f}")

            # Check data completeness
            print("\nData Completeness:")
            has_name = sum(1 for p in all_rankings if p.get('name') and p['name'] != 'Unknown')
            has_pa = sum(1 for p in all_rankings if p.get('total_pa', 0) > 0)
            has_level = sum(1 for p in all_rankings if p.get('level'))
            has_age = sum(1 for p in all_rankings if p.get('age', 0) > 0)

            print(f"  Has name: {has_name}/{len(all_rankings)} ({has_name/len(all_rankings)*100:.1f}%)")
            print(f"  Has PA: {has_pa}/{len(all_rankings)} ({has_pa/len(all_rankings)*100:.1f}%)")
            print(f"  Has level: {has_level}/{len(all_rankings)} ({has_level/len(all_rankings)*100:.1f}%)")
            print(f"  Has age: {has_age}/{len(all_rankings)} ({has_age/len(all_rankings)*100:.1f}%)")

    await engine.dispose()
    print("\n" + "="*60)
    print("Test Complete")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_statline_rankings())