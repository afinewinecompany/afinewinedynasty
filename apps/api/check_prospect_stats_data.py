#!/usr/bin/env python3
"""
Quick check to see what data exists in prospect_stats table
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

async def check_data():
    """Check what years and data we have in prospect_stats."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Use Railway production database
        database_url = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check years available
        result = await session.execute(text("""
            SELECT
                EXTRACT(YEAR FROM date_recorded) as year,
                COUNT(*) as count
            FROM prospect_stats
            GROUP BY EXTRACT(YEAR FROM date_recorded)
            ORDER BY year DESC
        """))

        print("Years available in prospect_stats:")
        for row in result:
            print(f"  Year {int(row.year)}: {row.count} records")

        # Check sample of data with high at_bats
        result = await session.execute(text("""
            SELECT
                p.name,
                ps.at_bats,
                ps.games_played,
                ps.batting_avg,
                ps.date_recorded,
                p.level
            FROM prospect_stats ps
            JOIN prospects p ON p.id = ps.prospect_id
            WHERE ps.at_bats IS NOT NULL
            ORDER BY ps.at_bats DESC
            LIMIT 10
        """))

        print("\nTop 10 players by at_bats:")
        for row in result:
            print(f"  {row.name}: {row.at_bats} ABs in {row.games_played} games ({row.batting_avg:.3f} AVG) - {row.level} - {row.date_recorded}")

        # Count players with 100+ at_bats
        result = await session.execute(text("""
            SELECT COUNT(DISTINCT ps.prospect_id) as count
            FROM prospect_stats ps
            WHERE ps.at_bats >= 100
        """))
        count = result.scalar()
        print(f"\nPlayers with 100+ at_bats: {count}")

        # Count players with 50+ at_bats (lower threshold)
        result = await session.execute(text("""
            SELECT COUNT(DISTINCT ps.prospect_id) as count
            FROM prospect_stats ps
            WHERE ps.at_bats >= 50
        """))
        count = result.scalar()
        print(f"Players with 50+ at_bats: {count}")

        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_data())