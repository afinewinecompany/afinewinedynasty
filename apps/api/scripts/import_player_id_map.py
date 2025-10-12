"""
Import SFBB Player ID Map to link MLB IDs to FanGraphs IDs.
"""

import asyncio
import pandas as pd
from sqlalchemy import text
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def create_id_mapping_table():
    """Create table to store player ID mappings."""

    create_table_query = """
    CREATE TABLE IF NOT EXISTS player_id_mapping (
        id SERIAL PRIMARY KEY,
        player_name VARCHAR(255),
        mlb_id INTEGER,
        fg_id VARCHAR(50),
        mlbam_id INTEGER,
        retrosheet_id VARCHAR(50),
        bbref_id VARCHAR(50),
        bbref_minors_id VARCHAR(50),
        espn_id INTEGER,
        yahoo_id INTEGER,
        ottoneu_id INTEGER,
        rotowire_id INTEGER,
        ftrax_id VARCHAR(50),
        cbs_id INTEGER,
        nfbc_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(mlb_id, fg_id)
    )
    """

    async with engine.begin() as conn:
        await conn.execute(text(create_table_query))
        logger.info("ID mapping table created/verified")


async def import_player_id_map():
    """Import the SFBB Player ID Map Excel file."""

    filepath = r"C:\Users\lilra\Downloads\SFBB-Player-ID-Map.xlsx"

    try:
        # Read the Excel file
        logger.info(f"Reading {filepath}...")
        df = pd.read_excel(filepath)

        logger.info(f"Loaded {len(df)} player records")

        # Check columns
        logger.info(f"Available columns: {df.columns.tolist()}")

        # Common column name mappings - based on actual columns
        column_mappings = {
            'PLAYERNAME': 'player_name',
            'MLBID': 'mlb_id',
            'IDFANGRAPHS': 'fg_id',  # This is the FanGraphs ID column
            'MLBAMID': 'mlbam_id',
            'BREFID': 'bbref_id',
            'RETROID': 'retrosheet_id'
        }

        # Rename columns based on mapping
        for old_col, new_col in column_mappings.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})

        # Ensure we have at least mlb_id and fg_id
        required_cols = ['mlb_id', 'fg_id']
        missing = [col for col in required_cols if col not in df.columns]

        if missing:
            logger.error(f"Missing required columns: {missing}")
            logger.info(f"Available columns after mapping: {df.columns.tolist()}")
            return

        # Clean data
        df = df.dropna(subset=['mlb_id', 'fg_id'], how='all')

        # Convert IDs to appropriate types
        if 'mlb_id' in df.columns:
            df['mlb_id'] = pd.to_numeric(df['mlb_id'], errors='coerce')

        if 'fg_id' in df.columns:
            df['fg_id'] = df['fg_id'].astype(str)

        # Filter out invalid rows
        df = df[df['mlb_id'].notna() | df['fg_id'].notna()]

        logger.info(f"Cleaned data: {len(df)} valid records")

        # Insert into database
        insert_query = """
        INSERT INTO player_id_mapping (
            player_name, mlb_id, fg_id, mlbam_id,
            retrosheet_id, bbref_id
        ) VALUES (
            :player_name, :mlb_id, :fg_id, :mlbam_id,
            :retrosheet_id, :bbref_id
        )
        ON CONFLICT (mlb_id, fg_id) DO UPDATE SET
            player_name = EXCLUDED.player_name
        """

        # Prepare data for insertion
        records_to_insert = []
        for _, row in df.iterrows():
            record = {
                'player_name': row.get('player_name'),
                'mlb_id': int(row['mlb_id']) if pd.notna(row.get('mlb_id')) else None,
                'fg_id': str(row.get('fg_id')) if pd.notna(row.get('fg_id')) else None,
                'mlbam_id': int(row['mlbam_id']) if pd.notna(row.get('mlbam_id')) else None,
                'retrosheet_id': str(row.get('retrosheet_id')) if pd.notna(row.get('retrosheet_id')) else None,
                'bbref_id': str(row.get('bbref_id')) if pd.notna(row.get('bbref_id')) else None
            }

            # Skip if both mlb_id and fg_id are None
            if record['mlb_id'] is None and record['fg_id'] is None:
                continue

            records_to_insert.append(record)

        # Bulk insert for better performance
        async with engine.begin() as conn:
            # First, clear existing data to avoid conflicts
            await conn.execute(text("TRUNCATE TABLE player_id_mapping"))

            # Then bulk insert all records
            if records_to_insert:
                await conn.execute(text(insert_query), records_to_insert)
                logger.info(f"Bulk inserted {len(records_to_insert)} records")

        logger.info(f"Inserted {len(records_to_insert)} player ID mappings")

        # Show statistics
        await show_mapping_statistics()

    except Exception as e:
        logger.error(f"Error importing file: {e}")
        import traceback
        traceback.print_exc()


async def show_mapping_statistics():
    """Show statistics about the imported mappings."""

    stats_query = """
    SELECT
        COUNT(*) as total_mappings,
        COUNT(DISTINCT mlb_id) as unique_mlb,
        COUNT(DISTINCT fg_id) as unique_fg,
        COUNT(CASE WHEN mlb_id IS NOT NULL AND fg_id IS NOT NULL THEN 1 END) as both_ids,
        COUNT(CASE WHEN mlb_id IS NOT NULL AND fg_id IS NULL THEN 1 END) as mlb_only,
        COUNT(CASE WHEN mlb_id IS NULL AND fg_id IS NOT NULL THEN 1 END) as fg_only
    FROM player_id_mapping
    """

    async with engine.begin() as conn:
        result = await conn.execute(text(stats_query))
        stats = result.fetchone()

    print("\n" + "="*80)
    print("PLAYER ID MAPPING STATISTICS")
    print("="*80)
    print(f"Total Mappings:     {stats[0]:,}")
    print(f"Unique MLB IDs:     {stats[1]:,}")
    print(f"Unique FG IDs:      {stats[2]:,}")
    print(f"Both MLB & FG:      {stats[3]:,}")
    print(f"MLB Only:           {stats[4]:,}")
    print(f"FG Only:            {stats[5]:,}")

    # Now check how many FanGraphs prospects we can match
    match_query = """
    WITH fg_players AS (
        SELECT DISTINCT fg_player_id, player_name
        FROM fangraphs_prospect_grades
        WHERE fg_player_id IS NOT NULL
    ),
    matched AS (
        SELECT
            fg.fg_player_id,
            fg.player_name as fg_name,
            pm.mlb_id,
            pm.player_name as mapped_name
        FROM fg_players fg
        INNER JOIN player_id_mapping pm ON fg.fg_player_id = pm.fg_id
    )
    SELECT
        COUNT(DISTINCT fg_player_id) as matched_fg_players,
        COUNT(DISTINCT mlb_id) as unique_mlb_matches
    FROM matched
    """

    result = await conn.execute(text(match_query))
    matches = result.fetchone()

    print("\n" + "="*80)
    print("FANGRAPHS PROSPECT MATCHING")
    print("="*80)
    print(f"FanGraphs prospects with MLB IDs: {matches[0]:,}")
    print(f"Unique MLB players matched:       {matches[1]:,}")

    # Show sample matches
    sample_query = """
    SELECT
        fg.player_name as fg_name,
        fg.organization,
        fg.position,
        fg.fv,
        pm.mlb_id
    FROM fangraphs_prospect_grades fg
    INNER JOIN player_id_mapping pm ON fg.fg_player_id = pm.fg_id
    WHERE fg.fv >= 50
    ORDER BY fg.fv DESC
    LIMIT 20
    """

    result = await conn.execute(text(sample_query))
    samples = pd.DataFrame(result.fetchall(), columns=result.keys())

    if not samples.empty:
        print("\n" + "="*80)
        print("SAMPLE HIGH-FV PROSPECTS WITH MLB IDS")
        print("="*80)
        print(samples.to_string(index=False))


async def main():
    await create_id_mapping_table()
    await import_player_id_map()


if __name__ == "__main__":
    asyncio.run(main())