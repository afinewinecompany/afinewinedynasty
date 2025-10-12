#!/usr/bin/env python3
"""
Import all Fangraphs data from 2022-2025, including both hitters and pitchers grades.

Creates a unified table with all prospect grades.
"""

import pandas as pd
import asyncio
import logging
from typing import Dict, List, Optional
import sys
import os
from datetime import datetime
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def create_unified_fangraphs_table():
    """Create a comprehensive table with all hitting and pitching grades."""

    async with engine.begin() as conn:
        # Drop existing table
        await conn.execute(text("DROP TABLE IF EXISTS fangraphs_unified_grades CASCADE"))

        # Create new unified table
        await conn.execute(text("""
            CREATE TABLE fangraphs_unified_grades (
                id SERIAL PRIMARY KEY,
                fg_player_id VARCHAR(50),
                player_name VARCHAR(255),
                position VARCHAR(10),
                organization VARCHAR(10),
                year INTEGER,
                data_type VARCHAR(20),  -- 'hitter', 'pitcher', or 'phys'

                -- Basic info
                age FLOAT,
                top_100_rank INTEGER,
                org_rank INTEGER,
                fv INTEGER,  -- Future Value

                -- Hitting grades (from hitters files)
                hit_present INTEGER,
                hit_future INTEGER,
                game_power_present INTEGER,
                game_power_future INTEGER,
                raw_power_present INTEGER,
                raw_power_future INTEGER,
                speed_present INTEGER,
                speed_future INTEGER,
                field_present INTEGER,
                field_future INTEGER,

                -- Hitting metrics
                bb_rate FLOAT,
                k_rate FLOAT,

                -- Pitching grades (from pitchers files)
                fb_grade INTEGER,
                sl_grade INTEGER,
                cb_grade INTEGER,
                ch_grade INTEGER,
                ct_grade INTEGER,  -- Cutter
                cmd_grade INTEGER,
                sits_velo FLOAT,
                tops_velo FLOAT,
                fb_type VARCHAR(20),

                -- Physical attributes (from phys files)
                height VARCHAR(10),
                weight INTEGER,

                -- Metadata
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_file VARCHAR(255),

                -- Create unique constraint on player, year, and data type
                UNIQUE(fg_player_id, year, data_type)
            )
        """))

        logger.info("Created unified fangraphs_unified_grades table")


async def import_hitters_file(filepath: str, year: int):
    """Import a hitters CSV file."""

    logger.info(f"Importing hitters file: {filepath}")
    df = pd.read_csv(filepath)

    # Standardize column names
    df = df.rename(columns={
        'Name': 'player_name',
        'PlayerId': 'fg_player_id',
        'Pos': 'position',
        'Org': 'organization',
        'Top 100': 'top_100_rank',
        'Org Rk': 'org_rank',
        'Age': 'age',
        'FV': 'fv',
        # Hitting tool grades
        'Hit': 'hit_present',
        'Hit FV': 'hit_future',
        'Game': 'game_power_present',
        'Game FV': 'game_power_future',
        'Raw': 'raw_power_present',
        'Raw FV': 'raw_power_future',
        'Spd': 'speed_present',
        'Spd FV': 'speed_future',
        'Fld': 'field_present',
        'Fld FV': 'field_future',
        # Metrics
        'BB%': 'bb_rate',
        'K%': 'k_rate'
    })

    # Add metadata
    df['year'] = year
    df['data_type'] = 'hitter'
    df['source_file'] = os.path.basename(filepath)

    # Convert numeric columns
    numeric_cols = ['top_100_rank', 'org_rank', 'age', 'fv',
                   'hit_present', 'hit_future', 'game_power_present', 'game_power_future',
                   'raw_power_present', 'raw_power_future', 'speed_present', 'speed_future',
                   'field_present', 'field_future', 'bb_rate', 'k_rate']

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Insert data
    async with engine.begin() as conn:
        inserted = 0
        for _, row in df.iterrows():
            try:
                values = {
                    'fg_player_id': row.get('fg_player_id') if pd.notna(row.get('fg_player_id')) else None,
                    'player_name': row.get('player_name'),
                    'position': row.get('position'),
                    'organization': row.get('organization'),
                    'year': year,
                    'data_type': 'hitter',
                    'age': row.get('age') if pd.notna(row.get('age')) else None,
                    'top_100_rank': int(row.get('top_100_rank')) if pd.notna(row.get('top_100_rank')) else None,
                    'org_rank': int(row.get('org_rank')) if pd.notna(row.get('org_rank')) else None,
                    'fv': int(row.get('fv')) if pd.notna(row.get('fv')) else None,
                    'hit_present': int(row.get('hit_present')) if pd.notna(row.get('hit_present')) else None,
                    'hit_future': int(row.get('hit_future')) if pd.notna(row.get('hit_future')) else None,
                    'game_power_present': int(row.get('game_power_present')) if pd.notna(row.get('game_power_present')) else None,
                    'game_power_future': int(row.get('game_power_future')) if pd.notna(row.get('game_power_future')) else None,
                    'raw_power_present': int(row.get('raw_power_present')) if pd.notna(row.get('raw_power_present')) else None,
                    'raw_power_future': int(row.get('raw_power_future')) if pd.notna(row.get('raw_power_future')) else None,
                    'speed_present': int(row.get('speed_present')) if pd.notna(row.get('speed_present')) else None,
                    'speed_future': int(row.get('speed_future')) if pd.notna(row.get('speed_future')) else None,
                    'field_present': int(row.get('field_present')) if pd.notna(row.get('field_present')) else None,
                    'field_future': int(row.get('field_future')) if pd.notna(row.get('field_future')) else None,
                    'bb_rate': row.get('bb_rate') if pd.notna(row.get('bb_rate')) else None,
                    'k_rate': row.get('k_rate') if pd.notna(row.get('k_rate')) else None,
                    'source_file': os.path.basename(filepath)
                }

                await conn.execute(text("""
                    INSERT INTO fangraphs_unified_grades
                    (fg_player_id, player_name, position, organization, year, data_type,
                     age, top_100_rank, org_rank, fv,
                     hit_present, hit_future, game_power_present, game_power_future,
                     raw_power_present, raw_power_future, speed_present, speed_future,
                     field_present, field_future, bb_rate, k_rate, source_file)
                    VALUES
                    (:fg_player_id, :player_name, :position, :organization, :year, :data_type,
                     :age, :top_100_rank, :org_rank, :fv,
                     :hit_present, :hit_future, :game_power_present, :game_power_future,
                     :raw_power_present, :raw_power_future, :speed_present, :speed_future,
                     :field_present, :field_future, :bb_rate, :k_rate, :source_file)
                    ON CONFLICT (fg_player_id, year, data_type)
                    DO UPDATE SET
                        player_name = EXCLUDED.player_name,
                        position = EXCLUDED.position,
                        organization = EXCLUDED.organization,
                        age = EXCLUDED.age,
                        top_100_rank = EXCLUDED.top_100_rank,
                        org_rank = EXCLUDED.org_rank,
                        fv = EXCLUDED.fv
                """), values)
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting hitter {row.get('player_name')}: {str(e)}")
                continue

    logger.info(f"Imported {inserted} hitters from {year}")
    return inserted


async def import_pitchers_file(filepath: str, year: int):
    """Import a pitchers CSV file."""

    logger.info(f"Importing pitchers file: {filepath}")
    df = pd.read_csv(filepath)

    # Standardize column names
    df = df.rename(columns={
        'Name': 'player_name',
        'PlayerId': 'fg_player_id',
        'Pos': 'position',
        'Org': 'organization',
        'Top 100': 'top_100_rank',
        'Org Rk': 'org_rank',
        'Age': 'age',
        'FV': 'fv',
        # Pitching grades
        'FB': 'fb_grade',
        'SL': 'sl_grade',
        'CB': 'cb_grade',
        'CH': 'ch_grade',
        'CT': 'ct_grade',
        'CMD': 'cmd_grade',
        'Sits': 'sits_velo',
        'Tops': 'tops_velo',
        'FB Type': 'fb_type'
    })

    # Add metadata
    df['year'] = year
    df['data_type'] = 'pitcher'
    df['source_file'] = os.path.basename(filepath)

    # Convert numeric columns
    numeric_cols = ['top_100_rank', 'org_rank', 'age', 'fv',
                   'fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'ct_grade', 'cmd_grade',
                   'sits_velo', 'tops_velo']

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Insert data
    async with engine.begin() as conn:
        inserted = 0
        for _, row in df.iterrows():
            try:
                values = {
                    'fg_player_id': row.get('fg_player_id') if pd.notna(row.get('fg_player_id')) else None,
                    'player_name': row.get('player_name'),
                    'position': row.get('position'),
                    'organization': row.get('organization'),
                    'year': year,
                    'data_type': 'pitcher',
                    'age': row.get('age') if pd.notna(row.get('age')) else None,
                    'top_100_rank': int(row.get('top_100_rank')) if pd.notna(row.get('top_100_rank')) else None,
                    'org_rank': int(row.get('org_rank')) if pd.notna(row.get('org_rank')) else None,
                    'fv': int(row.get('fv')) if pd.notna(row.get('fv')) else None,
                    'fb_grade': int(row.get('fb_grade')) if pd.notna(row.get('fb_grade')) else None,
                    'sl_grade': int(row.get('sl_grade')) if pd.notna(row.get('sl_grade')) else None,
                    'cb_grade': int(row.get('cb_grade')) if pd.notna(row.get('cb_grade')) else None,
                    'ch_grade': int(row.get('ch_grade')) if pd.notna(row.get('ch_grade')) else None,
                    'ct_grade': int(row.get('ct_grade')) if pd.notna(row.get('ct_grade')) else None,
                    'cmd_grade': int(row.get('cmd_grade')) if pd.notna(row.get('cmd_grade')) else None,
                    'sits_velo': row.get('sits_velo') if pd.notna(row.get('sits_velo')) else None,
                    'tops_velo': row.get('tops_velo') if pd.notna(row.get('tops_velo')) else None,
                    'fb_type': row.get('fb_type') if pd.notna(row.get('fb_type')) else None,
                    'source_file': os.path.basename(filepath)
                }

                await conn.execute(text("""
                    INSERT INTO fangraphs_unified_grades
                    (fg_player_id, player_name, position, organization, year, data_type,
                     age, top_100_rank, org_rank, fv,
                     fb_grade, sl_grade, cb_grade, ch_grade, ct_grade, cmd_grade,
                     sits_velo, tops_velo, fb_type, source_file)
                    VALUES
                    (:fg_player_id, :player_name, :position, :organization, :year, :data_type,
                     :age, :top_100_rank, :org_rank, :fv,
                     :fb_grade, :sl_grade, :cb_grade, :ch_grade, :ct_grade, :cmd_grade,
                     :sits_velo, :tops_velo, :fb_type, :source_file)
                    ON CONFLICT (fg_player_id, year, data_type)
                    DO UPDATE SET
                        player_name = EXCLUDED.player_name,
                        position = EXCLUDED.position,
                        organization = EXCLUDED.organization,
                        age = EXCLUDED.age,
                        top_100_rank = EXCLUDED.top_100_rank,
                        org_rank = EXCLUDED.org_rank,
                        fv = EXCLUDED.fv
                """), values)
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting pitcher {row.get('player_name')}: {str(e)}")
                continue

    logger.info(f"Imported {inserted} pitchers from {year}")
    return inserted


async def analyze_import_results():
    """Analyze the imported data."""

    async with engine.begin() as conn:
        # Overall stats
        result = await conn.execute(text("""
            SELECT
                year,
                data_type,
                COUNT(*) as count,
                COUNT(DISTINCT fg_player_id) as unique_players,
                COUNT(CASE WHEN top_100_rank IS NOT NULL THEN 1 END) as top_100
            FROM fangraphs_unified_grades
            GROUP BY year, data_type
            ORDER BY year, data_type
        """))

        print("\n" + "="*80)
        print("FANGRAPHS DATA IMPORT SUMMARY")
        print("="*80)

        stats = result.fetchall()
        for row in stats:
            print(f"{row[0]} {row[1]:8s}: {row[2]:4d} records, {row[3]:4d} unique players, {row[4]:3d} top 100")

        # Check grade coverage
        result = await conn.execute(text("""
            SELECT
                COUNT(DISTINCT CASE WHEN hit_future IS NOT NULL THEN fg_player_id END) as has_hit_grade,
                COUNT(DISTINCT CASE WHEN game_power_future IS NOT NULL THEN fg_player_id END) as has_power_grade,
                COUNT(DISTINCT CASE WHEN speed_future IS NOT NULL THEN fg_player_id END) as has_speed_grade,
                COUNT(DISTINCT CASE WHEN field_future IS NOT NULL THEN fg_player_id END) as has_field_grade,
                COUNT(DISTINCT CASE WHEN fb_grade IS NOT NULL THEN fg_player_id END) as has_fb_grade,
                COUNT(DISTINCT CASE WHEN cmd_grade IS NOT NULL THEN fg_player_id END) as has_cmd_grade
            FROM fangraphs_unified_grades
        """))

        coverage = result.fetchone()
        print("\n=== Grade Coverage ===")
        print(f"Players with hit grades: {coverage[0]:,}")
        print(f"Players with power grades: {coverage[1]:,}")
        print(f"Players with speed grades: {coverage[2]:,}")
        print(f"Players with field grades: {coverage[3]:,}")
        print(f"Players with FB grades: {coverage[4]:,}")
        print(f"Players with CMD grades: {coverage[5]:,}")

        # Sample top prospects
        result = await conn.execute(text("""
            SELECT DISTINCT ON (fg_player_id)
                player_name,
                position,
                organization,
                year,
                fv,
                top_100_rank
            FROM fangraphs_unified_grades
            WHERE top_100_rank <= 10
            ORDER BY fg_player_id, year DESC, top_100_rank
            LIMIT 10
        """))

        print("\n=== Sample Top 10 Prospects (Most Recent) ===")
        for row in result.fetchall():
            print(f"#{row[5]:3d} {row[0]:25s} {row[1]:3s} ({row[2]}) {row[3]} FV={row[4]}")


async def main():
    """Import all Fangraphs data files."""

    downloads_dir = r"C:\Users\lilra\Downloads"

    # Create unified table
    await create_unified_fangraphs_table()

    # Process each year
    for year in [2022, 2023, 2024, 2025]:
        # Import hitters
        hitters_file = os.path.join(downloads_dir, f"fangraphs-the-board-hitters-{year}.csv")
        if os.path.exists(hitters_file):
            await import_hitters_file(hitters_file, year)
        else:
            logger.warning(f"Hitters file not found: {hitters_file}")

        # Import pitchers
        pitchers_file = os.path.join(downloads_dir, f"fangraphs-the-board-pitchers-{year}.csv")
        if os.path.exists(pitchers_file):
            await import_pitchers_file(pitchers_file, year)
        else:
            logger.warning(f"Pitchers file not found: {pitchers_file}")

    # Analyze results
    await analyze_import_results()

    logger.info("All Fangraphs data import complete!")


if __name__ == "__main__":
    asyncio.run(main())