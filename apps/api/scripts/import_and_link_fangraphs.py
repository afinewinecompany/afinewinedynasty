#!/usr/bin/env python3
"""
Import Fangraphs CSV and Create Player Linkage Table

This script:
1. Imports the latest Fangraphs CSV data
2. Creates a linkage table between fg_player_id and mlb_player_id
3. Tests the linkage accuracy
"""

import pandas as pd
import asyncio
import logging
from typing import Dict, List, Optional
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def drop_and_recreate_fangraphs_table():
    """Drop existing Fangraphs table and recreate with proper schema."""

    async with engine.begin() as conn:
        # Drop existing table
        await conn.execute(text("DROP TABLE IF EXISTS fangraphs_prospect_grades CASCADE"))

        # Create new table with proper schema
        await conn.execute(text("""
            CREATE TABLE fangraphs_prospect_grades (
                id SERIAL PRIMARY KEY,
                fg_player_id VARCHAR(50),
                player_name VARCHAR(255),
                position VARCHAR(10),
                organization VARCHAR(10),
                top_100_rank INTEGER,
                org_rank INTEGER,
                age FLOAT,
                tj_date VARCHAR(50),
                fb_type VARCHAR(20),
                fb_grade INTEGER,
                sl_grade INTEGER,
                cb_grade INTEGER,
                ch_grade INTEGER,
                cmd_grade INTEGER,
                sits_velo FLOAT,
                tops_velo FLOAT,
                fv INTEGER,
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        logger.info("Created new fangraphs_prospect_grades table")


async def import_fangraphs_csv(csv_path: str):
    """Import Fangraphs CSV data into database."""

    # Read CSV
    df = pd.read_csv(csv_path)
    logger.info(f"Read {len(df)} rows from {csv_path}")

    # Rename columns to match database
    column_mapping = {
        'Name': 'player_name',
        'Pos': 'position',
        'Org': 'organization',
        'Top 100': 'top_100_rank',
        'Org Rk': 'org_rank',
        'Age': 'age',
        'TJ Date': 'tj_date',
        'FB Type': 'fb_type',
        'FB': 'fb_grade',
        'SL': 'sl_grade',
        'CB': 'cb_grade',
        'CH': 'ch_grade',
        'CMD': 'cmd_grade',
        'Sits': 'sits_velo',
        'Tops': 'tops_velo',
        'FV': 'fv',
        'PlayerId': 'fg_player_id'
    }

    df = df.rename(columns=column_mapping)

    # Convert grades to integers where possible
    grade_columns = ['fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'cmd_grade', 'fv']
    for col in grade_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Convert numeric columns
    numeric_columns = ['top_100_rank', 'org_rank', 'age', 'sits_velo', 'tops_velo']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Insert data
    async with engine.begin() as conn:
        for _, row in df.iterrows():
            values = {
                'fg_player_id': row.get('fg_player_id') if pd.notna(row.get('fg_player_id')) else None,
                'player_name': row.get('player_name') if pd.notna(row.get('player_name')) else None,
                'position': row.get('position') if pd.notna(row.get('position')) else None,
                'organization': row.get('organization') if pd.notna(row.get('organization')) else None,
                'top_100_rank': row.get('top_100_rank') if pd.notna(row.get('top_100_rank')) else None,
                'org_rank': row.get('org_rank') if pd.notna(row.get('org_rank')) else None,
                'age': row.get('age') if pd.notna(row.get('age')) else None,
                'tj_date': row.get('tj_date') if pd.notna(row.get('tj_date')) else None,
                'fb_type': row.get('fb_type') if pd.notna(row.get('fb_type')) else None,
                'fb_grade': row.get('fb_grade') if pd.notna(row.get('fb_grade')) else None,
                'sl_grade': row.get('sl_grade') if pd.notna(row.get('sl_grade')) else None,
                'cb_grade': row.get('cb_grade') if pd.notna(row.get('cb_grade')) else None,
                'ch_grade': row.get('ch_grade') if pd.notna(row.get('ch_grade')) else None,
                'cmd_grade': row.get('cmd_grade') if pd.notna(row.get('cmd_grade')) else None,
                'sits_velo': row.get('sits_velo') if pd.notna(row.get('sits_velo')) else None,
                'tops_velo': row.get('tops_velo') if pd.notna(row.get('tops_velo')) else None,
                'fv': row.get('fv') if pd.notna(row.get('fv')) else None
            }

            await conn.execute(text("""
                INSERT INTO fangraphs_prospect_grades
                (fg_player_id, player_name, position, organization, top_100_rank,
                 org_rank, age, tj_date, fb_type, fb_grade, sl_grade, cb_grade,
                 ch_grade, cmd_grade, sits_velo, tops_velo, fv)
                VALUES
                (:fg_player_id, :player_name, :position, :organization, :top_100_rank,
                 :org_rank, :age, :tj_date, :fb_type, :fb_grade, :sl_grade, :cb_grade,
                 :ch_grade, :cmd_grade, :sits_velo, :tops_velo, :fv)
            """), values)

    logger.info(f"Imported {len(df)} records into fangraphs_prospect_grades")


async def create_player_linkage_table():
    """Create linkage table between Fangraphs and MLB player IDs."""

    async with engine.begin() as conn:
        # Drop existing table
        await conn.execute(text("DROP TABLE IF EXISTS fangraphs_mlb_linkage"))

        # Create linkage table
        await conn.execute(text("""
            CREATE TABLE fangraphs_mlb_linkage (
                id SERIAL PRIMARY KEY,
                fg_player_id VARCHAR(50),
                mlb_player_id INTEGER,
                player_name VARCHAR(255),
                confidence_score FLOAT,
                linkage_method VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(fg_player_id, mlb_player_id)
            )
        """))

        logger.info("Created fangraphs_mlb_linkage table")


async def test_direct_id_matches():
    """Test if fg_player_id directly matches mlb_player_id."""

    async with engine.begin() as conn:
        # Get unique Fangraphs IDs
        result = await conn.execute(text("""
            SELECT DISTINCT fg_player_id, player_name
            FROM fangraphs_prospect_grades
            WHERE fg_player_id IS NOT NULL
        """))

        fg_players = result.fetchall()
        logger.info(f"Testing {len(fg_players)} Fangraphs player IDs")

        direct_matches = 0
        numeric_ids = 0

        for fg_id, name in fg_players:
            # Check if ID is numeric
            if fg_id and fg_id.isdigit():
                numeric_ids += 1

                # Try direct match
                result = await conn.execute(text("""
                    SELECT COUNT(*)
                    FROM milb_game_logs
                    WHERE mlb_player_id = :id
                """), {'id': int(fg_id)})

                if result.scalar() > 0:
                    direct_matches += 1

                    # Insert linkage
                    await conn.execute(text("""
                        INSERT INTO fangraphs_mlb_linkage
                        (fg_player_id, mlb_player_id, player_name, confidence_score, linkage_method)
                        VALUES (:fg_id, :mlb_id, :name, 1.0, 'direct_id_match')
                        ON CONFLICT (fg_player_id, mlb_player_id) DO NOTHING
                    """), {'fg_id': fg_id, 'mlb_id': int(fg_id), 'name': name})

        logger.info(f"Numeric IDs: {numeric_ids}/{len(fg_players)}")
        logger.info(f"Direct ID matches: {direct_matches}/{numeric_ids} ({direct_matches/numeric_ids*100:.1f}%)")

        return direct_matches


async def test_linkage_coverage():
    """Test overall linkage coverage and quality."""

    async with engine.begin() as conn:
        # Check linkage stats
        result = await conn.execute(text("""
            SELECT
                COUNT(DISTINCT fg_player_id) as linked_fg_players,
                COUNT(DISTINCT mlb_player_id) as linked_mlb_players,
                AVG(confidence_score) as avg_confidence,
                COUNT(*) as total_links
            FROM fangraphs_mlb_linkage
        """))

        stats = result.fetchone()

        # Check total Fangraphs players
        result = await conn.execute(text("""
            SELECT COUNT(DISTINCT fg_player_id)
            FROM fangraphs_prospect_grades
            WHERE fg_player_id IS NOT NULL
        """))

        total_fg = result.scalar()

        print("\n" + "="*80)
        print("FANGRAPHS LINKAGE ANALYSIS")
        print("="*80)
        print(f"Total Fangraphs players: {total_fg}")
        print(f"Linked Fangraphs players: {stats[0]} ({stats[0]/total_fg*100:.1f}%)")
        print(f"Linked MLB players: {stats[1]}")
        print(f"Average confidence: {stats[2]:.2f}")
        print(f"Total linkage records: {stats[3]}")

        # Check top prospects linkage
        result = await conn.execute(text("""
            SELECT
                fg.player_name,
                fg.organization,
                fg.fv,
                fg.top_100_rank,
                CASE WHEN l.mlb_player_id IS NOT NULL THEN 'Linked' ELSE 'Not Linked' END as status
            FROM fangraphs_prospect_grades fg
            LEFT JOIN fangraphs_mlb_linkage l ON fg.fg_player_id = l.fg_player_id
            WHERE fg.top_100_rank IS NOT NULL
            ORDER BY fg.top_100_rank
            LIMIT 20
        """))

        print("\n=== Top 20 Prospects Linkage Status ===")
        for row in result.fetchall():
            print(f"#{row[3]:3d} {row[0]:25s} ({row[1]}) FV={row[2]:2d} - {row[4]}")


async def main():
    """Main execution function."""

    csv_path = r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2025.csv"

    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return

    logger.info("Starting Fangraphs import and linkage process...")

    # Step 1: Drop and recreate table
    await drop_and_recreate_fangraphs_table()

    # Step 2: Import CSV
    await import_fangraphs_csv(csv_path)

    # Step 3: Create linkage table
    await create_player_linkage_table()

    # Step 4: Test direct ID matches
    matches = await test_direct_id_matches()

    # Step 5: Analyze linkage coverage
    await test_linkage_coverage()

    logger.info("Import and linkage process complete!")


if __name__ == "__main__":
    asyncio.run(main())