#!/usr/bin/env python3
"""
Manual test script for statline rankings endpoint.
Tests the API endpoint after fixing the SQL queries.
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.statline_ranking_service import StatlineRankingService

async def test_statline_rankings():
    """Test the statline rankings service directly."""

    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://afinewinedynasty:afwdpassword2024@localhost:5432/afwd_db")

    # Create async engine
    engine = create_async_engine(database_url, echo=True)

    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Initialize service
        service = StatlineRankingService(session)

        try:
            # Test with minimal parameters
            print("Testing statline rankings calculation...")
            rankings = await service.calculate_statline_rankings(
                level=None,
                min_plate_appearances=50,  # Lower threshold for testing
                season=2025,
                include_pitch_data=False  # Skip pitch data for now
            )

            print(f"\nFound {len(rankings)} qualified players")

            # Display top 5 if any
            if rankings:
                print("\nTop 5 players:")
                for i, player in enumerate(rankings[:5], 1):
                    print(f"{i}. {player.get('name', 'Unknown')} - Score: {player.get('overall_score', 0):.1f}")
            else:
                print("\nNo players found - checking database...")

                # Run a simple query to check if we have any data
                from sqlalchemy import text
                result = await session.execute(
                    text("SELECT COUNT(*) FROM prospect_stats")
                )
                count = result.scalar()
                print(f"Total prospect_stats records: {count}")

                result = await session.execute(
                    text("SELECT COUNT(*) FROM prospects")
                )
                count = result.scalar()
                print(f"Total prospects records: {count}")

        except Exception as e:
            print(f"Error during test: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_statline_rankings())