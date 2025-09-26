#!/usr/bin/env python3
"""
Development data seeding script for A Fine Wine Dynasty.
Creates sample prospects, statistics, and scouting grades for testing.
"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.db.database import get_async_session, DATABASE_URL
from app.db.models import Prospect, ProspectStats, ScoutingGrades


# Sample prospect data
SAMPLE_PROSPECTS = [
    {
        "mlb_id": "SA2024001",
        "name": "Jackson Rodriguez",
        "position": "SS",
        "organization": "Los Angeles Dodgers",
        "level": "AA",
        "age": 21,
        "eta_year": 2026
    },
    {
        "mlb_id": "SA2024002",
        "name": "Connor Williams",
        "position": "SP",
        "organization": "New York Yankees",
        "level": "AAA",
        "age": 23,
        "eta_year": 2025
    },
    {
        "mlb_id": "SA2024003",
        "name": "Miguel Gonzalez",
        "position": "CF",
        "organization": "Houston Astros",
        "level": "A+",
        "age": 19,
        "eta_year": 2027
    },
    {
        "mlb_id": "SA2024004",
        "name": "Dylan Thompson",
        "position": "3B",
        "organization": "Atlanta Braves",
        "level": "AA",
        "age": 22,
        "eta_year": 2026
    },
    {
        "mlb_id": "SA2024005",
        "name": "Alex Chen",
        "position": "RP",
        "organization": "San Francisco Giants",
        "level": "AAA",
        "age": 24,
        "eta_year": 2025
    }
]


async def create_sample_prospects(session: AsyncSession) -> list[Prospect]:
    """Create sample prospect records."""
    print("📝 Creating sample prospects...")

    prospects = []
    for prospect_data in SAMPLE_PROSPECTS:
        # Check if prospect already exists
        result = await session.execute(
            select(Prospect).where(Prospect.mlb_id == prospect_data["mlb_id"])
        )
        existing_prospect = result.scalar_one_or_none()

        if existing_prospect:
            print(f"  ↳ Prospect {prospect_data['name']} already exists, skipping")
            prospects.append(existing_prospect)
            continue

        prospect = Prospect(**prospect_data)
        session.add(prospect)
        prospects.append(prospect)
        print(f"  ✅ Created prospect: {prospect_data['name']} ({prospect_data['position']})")

    await session.commit()
    return prospects


async def create_sample_stats(session: AsyncSession, prospects: list[Prospect]):
    """Create sample prospect statistics."""
    print("📊 Creating sample prospect statistics...")

    base_date = date(2024, 4, 1)

    for prospect in prospects:
        # Create stats for the current season
        for i in range(5):  # 5 stat entries per prospect
            stat_date = base_date + timedelta(days=30 * i)

            if prospect.position in ['SP', 'RP']:
                # Pitching stats
                stats = ProspectStats(
                    prospect_id=prospect.id,
                    date_recorded=stat_date,
                    season=2024,
                    games_played=i * 3 + 5,
                    innings_pitched=float(i * 15 + 25),
                    earned_runs=i * 2 + 8,
                    era=2.50 + (i * 0.3),
                    whip=1.10 + (i * 0.05),
                    strikeouts_per_nine=9.5 + (i * 0.2),
                    walks_per_nine=2.8 - (i * 0.1)
                )
            else:
                # Hitting stats
                stats = ProspectStats(
                    prospect_id=prospect.id,
                    date_recorded=stat_date,
                    season=2024,
                    games_played=i * 20 + 50,
                    at_bats=i * 75 + 180,
                    hits=i * 22 + 52,
                    home_runs=i * 3 + 8,
                    rbi=i * 12 + 25,
                    stolen_bases=i * 2 + 6,
                    walks=i * 15 + 32,
                    strikeouts=i * 28 + 45,
                    batting_avg=0.275 + (i * 0.005),
                    on_base_pct=0.340 + (i * 0.008),
                    slugging_pct=0.425 + (i * 0.012),
                    woba=0.325 + (i * 0.008),
                    wrc_plus=110 + (i * 5)
                )

            session.add(stats)

        print(f"  ✅ Created 5 stat entries for {prospect.name}")

    await session.commit()


async def create_sample_scouting_grades(session: AsyncSession, prospects: list[Prospect]):
    """Create sample scouting grades from multiple sources."""
    print("🔍 Creating sample scouting grades...")

    sources = ["Fangraphs", "MLB Pipeline", "Baseball America"]

    for prospect in prospects:
        for source in sources:
            if prospect.position in ['SP', 'RP']:
                # Pitching grades
                grades = ScoutingGrades(
                    prospect_id=prospect.id,
                    source=source,
                    overall=55 + (prospects.index(prospect) * 2),
                    fastball=60 if source == "Fangraphs" else 55,
                    curveball=45 + (prospects.index(prospect) * 2),
                    slider=50 if prospect.position == 'SP' else 60,
                    changeup=55 if prospect.position == 'SP' else 40,
                    control=50 + (prospects.index(prospect) * 2),
                    future_value=50 + (prospects.index(prospect) * 3),
                    risk="Moderate"
                )
            else:
                # Position player grades
                grades = ScoutingGrades(
                    prospect_id=prospect.id,
                    source=source,
                    overall=52 + (prospects.index(prospect) * 3),
                    hit=55 + (prospects.index(prospect) * 2),
                    power=50 if prospect.position in ['SS', 'CF'] else 60,
                    run=60 if prospect.position in ['CF', 'SS'] else 45,
                    field=55 + (2 if prospect.position == 'SS' else 0),
                    throw=60 if prospect.position in ['SS', '3B'] else 50,
                    future_value=52 + (prospects.index(prospect) * 3),
                    risk="Moderate" if prospects.index(prospect) % 2 == 0 else "High"
                )

            session.add(grades)

        print(f"  ✅ Created scouting grades from 3 sources for {prospect.name}")

    await session.commit()


async def seed_development_data():
    """Main seeding function."""
    print("🌱 Starting development data seeding...")

    engine = create_async_engine(DATABASE_URL)

    try:
        async with AsyncSession(engine) as session:
            # Create sample data
            prospects = await create_sample_prospects(session)
            await create_sample_stats(session, prospects)
            await create_sample_scouting_grades(session, prospects)

            print("✅ Development data seeding completed successfully!")
            print(f"   Created {len(prospects)} prospects with stats and scouting grades")

    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        return False
    finally:
        await engine.dispose()

    return True


if __name__ == "__main__":
    success = asyncio.run(seed_development_data())
    sys.exit(0 if success else 1)