"""
Test Optimized Rankings with Batch Pitch Processing

This validates that:
1. Batch processing fetches pitch metrics efficiently
2. All prospects with pitch data are using it (not game log fallback)
3. Rankings load in reasonable time
"""
import asyncio
import time
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('app')

from app.services.prospect_ranking_service import ProspectRankingService

ASYNC_DB_URL = 'postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test():
    engine = create_async_engine(ASYNC_DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        service = ProspectRankingService(db)

        print("=" * 80)
        print("TESTING OPTIMIZED RANKINGS WITH BATCH PITCH PROCESSING")
        print("=" * 80)
        print()

        try:
            # Test with 25 prospects
            print("Generating top 25 rankings with batch processing...")
            start = time.time()

            rankings = await service.generate_prospect_rankings(limit=25)

            elapsed = time.time() - start

            print(f"\nSUCCESS! Generated {len(rankings)} rankings in {elapsed:.2f} seconds")
            print(f"Average time per prospect: {elapsed/len(rankings):.3f} seconds\n")

            # Count data sources
            pitch_data_count = 0
            game_log_count = 0
            no_data_count = 0

            for prospect in rankings:
                details = prospect.get('scores', {}).get('performance_details', {})
                source = details.get('source', 'unknown')

                if source == 'pitch_data':
                    pitch_data_count += 1
                elif source == 'game_logs':
                    game_log_count += 1
                else:
                    no_data_count += 1

            print("DATA SOURCE BREAKDOWN:")
            print(f"  Pitch Data:  {pitch_data_count}/{len(rankings)} ({pitch_data_count*100//len(rankings)}%)")
            print(f"  Game Logs:   {game_log_count}/{len(rankings)} ({game_log_count*100//len(rankings)}%)")
            print(f"  No Data:     {no_data_count}/{len(rankings)}")
            print()

            # Show top 10 with data sources
            print("TOP 10 PROSPECTS:")
            print("-" * 80)
            for i, prospect in enumerate(rankings[:10], 1):
                scores = prospect.get('scores', {})
                details = scores.get('performance_details', {})
                source = details.get('source', 'unknown')

                data_marker = ""
                if source == 'pitch_data':
                    sample_size = details.get('sample_size', 0)
                    data_marker = f" [PITCH DATA: {sample_size} pitches]"
                elif source == 'game_logs':
                    data_marker = " [GAME LOGS]"

                print(f"{i:2d}. {prospect['name']:25s} {scores.get('composite_score', 0):5.1f}{data_marker}")

            print("=" * 80)

            if pitch_data_count > len(rankings) * 0.7:  # 70% threshold
                print("SUCCESS - Most prospects using pitch data!")
            elif pitch_data_count > 0:
                print("PARTIAL - Some pitch data being used, but not majority")
            else:
                print("WARNING - NO pitch data being used!")

            print(f"\nPerformance: {elapsed:.2f}s for {len(rankings)} prospects")
            if elapsed < 30:
                print("EXCELLENT - Sub-30 second load time!")
            elif elapsed < 60:
                print("GOOD - Reasonable load time")
            else:
                print("SLOW - Optimization needed")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
