#!/usr/bin/env python3
"""
Import FanGraphs data with proper grade parsing including upside potential.
Handles:
- "present / future" format like "20 / 45" → present=20, future=45
- "+" suffix for upside like "45+" → future=45, has_upside=True
- Single values like "50" → future=50
"""

import pandas as pd
import asyncio
import logging
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def parse_grade_with_upside(grade_str):
    """
    Parse grade with upside potential.

    Returns: (present, future, has_upside)

    Examples:
    - "20 / 45" → (20, 45, False)
    - "45+" → (None, 45, True)
    - "30 / 55+" → (30, 55, True)
    - "50" → (None, 50, False)
    """
    if pd.isna(grade_str) or grade_str == '':
        return None, None, False

    grade_str = str(grade_str).strip()
    has_upside = grade_str.endswith('+')

    # Remove '+' for parsing
    if has_upside:
        grade_str = grade_str[:-1].strip()

    # Handle "present / future" format
    if '/' in grade_str:
        parts = grade_str.split('/')
        try:
            present = int(parts[0].strip()) if parts[0].strip() else None
            future = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else None
            return present, future, has_upside
        except ValueError:
            logger.debug(f"Failed to parse grade with slash: {grade_str}")
            return None, None, False

    # Handle single value (use as future)
    try:
        val = int(grade_str)
        return None, val, has_upside
    except ValueError:
        logger.debug(f"Failed to parse single grade: {grade_str}")
        return None, None, False


async def add_upside_columns():
    """Add has_upside boolean column to track '+' values."""

    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'fangraphs_unified_grades'
              AND column_name = 'has_upside'
        """))

        if not result.fetchone():
            logger.info("Adding has_upside column...")
            await conn.execute(text("""
                ALTER TABLE fangraphs_unified_grades
                ADD COLUMN has_upside BOOLEAN DEFAULT FALSE
            """))
        else:
            logger.info("has_upside column already exists")


async def import_hitters(year: int):
    """Import hitters data with grade parsing including upside."""

    filepath = rf"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-{year}.csv"
    logger.info(f"Importing hitters: {filepath}")

    df = pd.read_csv(filepath)
    logger.info(f"Found {len(df)} hitters for {year}")

    async with engine.begin() as conn:
        inserted = 0
        upside_count = 0

        for _, row in df.iterrows():
            try:
                # Parse grades with upside detection
                hit_present, hit_future, hit_upside = parse_grade_with_upside(row.get('Hit'))
                game_present, game_future, game_upside = parse_grade_with_upside(row.get('Game Pwr'))
                raw_present, raw_future, raw_upside = parse_grade_with_upside(row.get('Raw Pwr'))
                speed_present, speed_future, speed_upside = parse_grade_with_upside(row.get('Spd'))
                field_present, field_future, field_upside = parse_grade_with_upside(row.get('Fld'))

                # FV can also have upside
                fv_val = row.get('FV')
                has_fv_upside = False
                if pd.notna(fv_val):
                    fv_str = str(fv_val).strip()
                    has_fv_upside = fv_str.endswith('+')
                    if has_fv_upside:
                        fv_val = int(fv_str[:-1])
                    else:
                        fv_val = int(fv_val)
                else:
                    fv_val = None

                # Track if ANY grade has upside
                has_any_upside = any([hit_upside, game_upside, raw_upside, speed_upside, field_upside, has_fv_upside])
                if has_any_upside:
                    upside_count += 1

                values = {
                    'fg_player_id': str(row.get('PlayerId')) if pd.notna(row.get('PlayerId')) else None,
                    'player_name': row.get('Name'),
                    'position': row.get('Pos'),
                    'organization': row.get('Org'),
                    'year': year,
                    'data_type': 'hitter',
                    'age': float(row.get('Age')) if pd.notna(row.get('Age')) else None,
                    'top_100_rank': int(row.get('Top 100')) if pd.notna(row.get('Top 100')) else None,
                    'org_rank': int(row.get('Org Rk')) if pd.notna(row.get('Org Rk')) else None,
                    'fv': fv_val,
                    'hit_present': hit_present,
                    'hit_future': hit_future,
                    'game_power_present': game_present,
                    'game_power_future': game_future,
                    'raw_power_present': raw_present,
                    'raw_power_future': raw_future,
                    'speed_present': speed_present,
                    'speed_future': speed_future,
                    'field_present': field_present,
                    'field_future': field_future,
                    'has_upside': has_any_upside,
                    'source_file': f'fangraphs-the-board-hitters-{year}.csv'
                }

                await conn.execute(text("""
                    INSERT INTO fangraphs_unified_grades
                    (fg_player_id, player_name, position, organization, year, data_type,
                     age, top_100_rank, org_rank, fv,
                     hit_present, hit_future, game_power_present, game_power_future,
                     raw_power_present, raw_power_future, speed_present, speed_future,
                     field_present, field_future, has_upside, source_file)
                    VALUES
                    (:fg_player_id, :player_name, :position, :organization, :year, :data_type,
                     :age, :top_100_rank, :org_rank, :fv,
                     :hit_present, :hit_future, :game_power_present, :game_power_future,
                     :raw_power_present, :raw_power_future, :speed_present, :speed_future,
                     :field_present, :field_future, :has_upside, :source_file)
                    ON CONFLICT (fg_player_id, year, data_type)
                    DO UPDATE SET
                        player_name = EXCLUDED.player_name,
                        position = EXCLUDED.position,
                        organization = EXCLUDED.organization,
                        age = EXCLUDED.age,
                        top_100_rank = EXCLUDED.top_100_rank,
                        org_rank = EXCLUDED.org_rank,
                        fv = EXCLUDED.fv,
                        hit_present = EXCLUDED.hit_present,
                        hit_future = EXCLUDED.hit_future,
                        game_power_present = EXCLUDED.game_power_present,
                        game_power_future = EXCLUDED.game_power_future,
                        raw_power_present = EXCLUDED.raw_power_present,
                        raw_power_future = EXCLUDED.raw_power_future,
                        speed_present = EXCLUDED.speed_present,
                        speed_future = EXCLUDED.speed_future,
                        field_present = EXCLUDED.field_present,
                        field_future = EXCLUDED.field_future,
                        has_upside = EXCLUDED.has_upside
                """), values)
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting hitter {row.get('Name')}: {str(e)}")
                continue

    logger.info(f"Imported {inserted} hitters from {year} ({upside_count} with upside potential)")
    return inserted, upside_count


async def import_pitchers(year: int):
    """Import pitchers data with grade parsing including upside."""

    filepath = rf"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-{year}.csv"
    logger.info(f"Importing pitchers: {filepath}")

    df = pd.read_csv(filepath)
    logger.info(f"Found {len(df)} pitchers for {year}")

    async with engine.begin() as conn:
        inserted = 0
        upside_count = 0

        for _, row in df.iterrows():
            try:
                # Parse pitch grades with upside
                _, fb_grade, fb_upside = parse_grade_with_upside(row.get('FB'))
                _, sl_grade, sl_upside = parse_grade_with_upside(row.get('SL'))
                _, cb_grade, cb_upside = parse_grade_with_upside(row.get('CB'))
                _, ch_grade, ch_upside = parse_grade_with_upside(row.get('CH'))
                _, cmd_grade, cmd_upside = parse_grade_with_upside(row.get('CMD'))

                # FV with upside
                fv_val = row.get('FV')
                has_fv_upside = False
                if pd.notna(fv_val):
                    fv_str = str(fv_val).strip()
                    has_fv_upside = fv_str.endswith('+')
                    if has_fv_upside:
                        fv_val = int(fv_str[:-1])
                    else:
                        fv_val = int(fv_val)
                else:
                    fv_val = None

                # Track if ANY grade has upside
                has_any_upside = any([fb_upside, sl_upside, cb_upside, ch_upside, cmd_upside, has_fv_upside])
                if has_any_upside:
                    upside_count += 1

                values = {
                    'fg_player_id': str(row.get('PlayerId')) if pd.notna(row.get('PlayerId')) else None,
                    'player_name': row.get('Name'),
                    'position': row.get('Pos'),
                    'organization': row.get('Org'),
                    'year': year,
                    'data_type': 'pitcher',
                    'age': float(row.get('Age')) if pd.notna(row.get('Age')) else None,
                    'top_100_rank': int(row.get('Top 100')) if pd.notna(row.get('Top 100')) else None,
                    'org_rank': int(row.get('Org Rk')) if pd.notna(row.get('Org Rk')) else None,
                    'fv': fv_val,
                    'fb_grade': fb_grade,
                    'sl_grade': sl_grade,
                    'cb_grade': cb_grade,
                    'ch_grade': ch_grade,
                    'cmd_grade': cmd_grade,
                    'sits_velo': float(row.get('Sits')) if pd.notna(row.get('Sits')) else None,
                    'tops_velo': float(row.get('Tops')) if pd.notna(row.get('Tops')) else None,
                    'fb_type': row.get('FB Type') if pd.notna(row.get('FB Type')) else None,
                    'has_upside': has_any_upside,
                    'source_file': f'fangraphs-the-board-pitchers-{year}.csv'
                }

                await conn.execute(text("""
                    INSERT INTO fangraphs_unified_grades
                    (fg_player_id, player_name, position, organization, year, data_type,
                     age, top_100_rank, org_rank, fv,
                     fb_grade, sl_grade, cb_grade, ch_grade, cmd_grade,
                     sits_velo, tops_velo, fb_type, has_upside, source_file)
                    VALUES
                    (:fg_player_id, :player_name, :position, :organization, :year, :data_type,
                     :age, :top_100_rank, :org_rank, :fv,
                     :fb_grade, :sl_grade, :cb_grade, :ch_grade, :cmd_grade,
                     :sits_velo, :tops_velo, :fb_type, :has_upside, :source_file)
                    ON CONFLICT (fg_player_id, year, data_type)
                    DO UPDATE SET
                        player_name = EXCLUDED.player_name,
                        position = EXCLUDED.position,
                        organization = EXCLUDED.organization,
                        age = EXCLUDED.age,
                        top_100_rank = EXCLUDED.top_100_rank,
                        org_rank = EXCLUDED.org_rank,
                        fv = EXCLUDED.fv,
                        fb_grade = EXCLUDED.fb_grade,
                        sl_grade = EXCLUDED.sl_grade,
                        cb_grade = EXCLUDED.cb_grade,
                        ch_grade = EXCLUDED.ch_grade,
                        cmd_grade = EXCLUDED.cmd_grade,
                        sits_velo = EXCLUDED.sits_velo,
                        tops_velo = EXCLUDED.tops_velo,
                        fb_type = EXCLUDED.fb_type,
                        has_upside = EXCLUDED.has_upside
                """), values)
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting pitcher {row.get('Name')}: {str(e)}")
                continue

    logger.info(f"Imported {inserted} pitchers from {year} ({upside_count} with upside potential)")
    return inserted, upside_count


async def verify_import():
    """Verify the import results including upside tracking."""

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                year,
                COUNT(*) as total,
                COUNT(CASE WHEN hit_future IS NOT NULL THEN 1 END) as hit_grades,
                COUNT(CASE WHEN fb_grade IS NOT NULL THEN 1 END) as pitch_grades,
                COUNT(CASE WHEN fv IS NOT NULL THEN 1 END) as fv_grades,
                COUNT(CASE WHEN has_upside = TRUE THEN 1 END) as upside_players
            FROM fangraphs_unified_grades
            GROUP BY year
            ORDER BY year
        """))

        print("\n" + "="*90)
        print("FANGRAPHS IMPORT VERIFICATION (WITH UPSIDE TRACKING)")
        print("="*90)
        print("Year | Total | Hit Grades | Pitch Grades | FV Grades | Upside Players")
        print("-----|-------|------------|--------------|-----------|---------------")

        for row in result.fetchall():
            print(f"{row[0]} | {row[1]:>5,} | {row[2]:>10,} | {row[3]:>12,} | {row[4]:>9,} | {row[5]:>14,}")

        # Sample upside players
        result = await conn.execute(text("""
            SELECT player_name, year, data_type, fv, hit_future, game_power_future, fb_grade
            FROM fangraphs_unified_grades
            WHERE year = 2025 AND has_upside = TRUE
            LIMIT 15
        """))

        print("\n=== Sample 2025 Players with Upside Potential (+) ===")
        for row in result.fetchall():
            if row[2] == 'hitter':
                print(f"{row[0]:25s} {row[1]} {row[2]:7s} FV:{row[3]} Hit:{row[4]} Power:{row[5]}")
            else:
                print(f"{row[0]:25s} {row[1]} {row[2]:7s} FV:{row[3]} FB:{row[6]}")


async def main():
    """Import all years with upside tracking."""

    print("Importing FanGraphs data with upside potential tracking...")

    # Add upside column
    await add_upside_columns()

    total = 0
    total_upside = 0

    for year in [2022, 2023, 2024, 2025]:
        hitters, h_upside = await import_hitters(year)
        pitchers, p_upside = await import_pitchers(year)
        total += hitters + pitchers
        total_upside += h_upside + p_upside

    await verify_import()

    print(f"\nTotal records processed: {total:,}")
    print(f"Players with upside potential (+): {total_upside:,}")
    logger.info("Complete!")


if __name__ == "__main__":
    asyncio.run(main())
