"""
Check MiLB related tables in Railway database
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file
load_dotenv()

# Get database URL
db_url = os.getenv('SQLALCHEMY_DATABASE_URI')
if 'postgresql+asyncpg://' in db_url:
    db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')

engine = create_engine(db_url)

print("=" * 70)
print("MiLB DATA TABLES CHECK")
print("=" * 70)
print()

with engine.connect() as conn:
    # Find all MiLB related tables
    result = conn.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND (
            table_name LIKE '%milb%'
            OR table_name LIKE '%play%'
            OR table_name LIKE '%pbp%'
            OR table_name LIKE '%game%'
            OR table_name LIKE '%plate%'
            OR table_name LIKE '%appearance%'
        )
        ORDER BY table_name
    """))

    print("MiLB/Play-by-play related tables:")
    tables = []
    for row in result:
        tables.append(row[0])
        print(f"  - {row[0]}")

    print()

    # Check each table for record counts
    for table in tables:
        try:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.fetchone()[0]
            print(f"{table}: {count:,} records")
        except Exception as e:
            print(f"{table}: Error - {e}")

    print()
    print("=" * 70)

    # Check specifically for plate appearances data for 2021-2025
    if 'milb_plate_appearances' in tables:
        print("MiLB Plate Appearances by Season:")
        result = conn.execute(text("""
            SELECT
                season,
                COUNT(*) as records,
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(DISTINCT game_pk) as games
            FROM milb_plate_appearances
            WHERE season IN (2021, 2022, 2023, 2024, 2025)
            GROUP BY season
            ORDER BY season DESC
        """))

        for row in result:
            print(f"  {row[0]}: {row[1]:,} records, {row[2]} players, {row[3]} games")

    # Check for game logs
    if 'milb_game_logs' in tables:
        print()
        print("MiLB Game Logs by Season:")
        result = conn.execute(text("""
            SELECT
                season,
                COUNT(*) as records,
                COUNT(DISTINCT mlb_player_id) as players
            FROM milb_game_logs
            WHERE season IN (2021, 2022, 2023, 2024, 2025)
            GROUP BY season
            ORDER BY season DESC
        """))

        for row in result:
            print(f"  {row[0]}: {row[1]:,} records, {row[2]} players")

    # Check prospects table
    result = conn.execute(text("""
        SELECT COUNT(*) as total_prospects,
               COUNT(DISTINCT organization) as orgs
        FROM prospects
    """))
    row = result.fetchone()
    print()
    print(f"Prospects: {row[0]:,} players from {row[1]} organizations")