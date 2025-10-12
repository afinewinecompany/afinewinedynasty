#!/usr/bin/env python3
"""
Import FanGraphs data with proper grade parsing.
Handles "present / future" format like "20 / 45" → present=20, future=45
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


def parse_grade(grade_str):
    """Parse 'present / future' format like '20 / 45' or just '50'."""
    if pd.isna(grade_str) or grade_str == '':
        return None, None

    grade_str = str(grade_str).strip()

    # Handle "present / future" format
    if '/' in grade_str:
        parts = grade_str.split('/')
        try:
            present = int(parts[0].strip()) if parts[0].strip() else None
            future = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else None
            return present, future
        except:
            return None, None

    # Handle single value (use as future)
    try:
        val = int(grade_str)
        return None, val
    except:
        return None, None


async def import_hitters(year: int):
    """Import hitters data with grade parsing."""

    filepath = rf"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-{year}.csv"
    logger.info(f"Importing hitters: {filepath}")

    df = pd.read_csv(filepath)
    logger.info(f"Columns: {df.columns.tolist()}")

    async with engine.begin() as conn:
        inserted = 0
        for _, row in df.iterrows():
            try:
                # Parse grades
                hit_present, hit_future = parse_grade(row.get('Hit'))
                game_present, game_future = parse_grade(row.get('Game Pwr'))
                raw_present, raw_future = parse_grade(row.get('Raw Pwr'))
                speed_present, speed_future = parse_grade(row.get('Spd'))
                field_present, field_future = parse_grade(row.get('Fld'))

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
                    'fv': int(row.get('FV')) if pd.notna(row.get('FV')) else None,
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
                    'source_file': f'fangraphs-the-board-hitters-{year}.csv'
                }

                await conn.execute(text("""
                    INSERT INTO fangraphs_unified_grades
                    (fg_player_id, player_name, position, organization, year, data_type,
                     age, top_100_rank, org_rank, fv,
                     hit_present, hit_future, game_power_present, game_power_future,
                     raw_power_present, raw_power_future, speed_present, speed_future,
                     field_present, field_future, source_file)
                    VALUES
                    (:fg_player_id, :player_name, :position, :organization, :year, :data_type,
                     :age, :top_100_rank, :org_rank, :fv,
                     :hit_present, :hit_future, :game_power_present, :game_power_future,
                     :raw_power_present, :raw_power_future, :speed_present, :speed_future,
                     :field_present, :field_future, :source_file)
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
                        field_future = EXCLUDED.field_future
                """), values)
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting hitter {row.get('Name')}: {str(e)}")
                continue

    logger.info(f"Imported {inserted} hitters from {year}")
    return inserted


async def import_pitchers(year: int):
    """Import pitchers data with grade parsing."""

    filepath = rf"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-{year}.csv"
    logger.info(f"Importing pitchers: {filepath}")

    df = pd.read_csv(filepath)

    async with engine.begin() as conn:
        inserted = 0
        for _, row in df.iterrows():
            try:
                # Parse pitch grades (single values, not present/future)
                _, fb_grade = parse_grade(row.get('FB'))
                _, sl_grade = parse_grade(row.get('SL'))
                _, cb_grade = parse_grade(row.get('CB'))
                _, ch_grade = parse_grade(row.get('CH'))
                _, cmd_grade = parse_grade(row.get('CMD'))

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
                    'fv': int(row.get('FV')) if pd.notna(row.get('FV')) else None,
                    'fb_grade': fb_grade,
                    'sl_grade': sl_grade,
                    'cb_grade': cb_grade,
                    'ch_grade': ch_grade,
                    'cmd_grade': cmd_grade,
                    'sits_velo': float(row.get('Sits')) if pd.notna(row.get('Sits')) else None,
                    'tops_velo': float(row.get('Tops')) if pd.notna(row.get('Tops')) else None,
                    'fb_type': row.get('FB Type') if pd.notna(row.get('FB Type')) else None,
                    'source_file': f'fangraphs-the-board-pitchers-{year}.csv'
                }

                await conn.execute(text("""
                    INSERT INTO fangraphs_unified_grades
                    (fg_player_id, player_name, position, organization, year, data_type,
                     age, top_100_rank, org_rank, fv,
                     fb_grade, sl_grade, cb_grade, ch_grade, cmd_grade,
                     sits_velo, tops_velo, fb_type, source_file)
                    VALUES
                    (:fg_player_id, :player_name, :position, :organization, :year, :data_type,
                     :age, :top_100_rank, :org_rank, :fv,
                     :fb_grade, :sl_grade, :cb_grade, :ch_grade, :cmd_grade,
                     :sits_velo, :tops_velo, :fb_type, :source_file)
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
                        fb_type = EXCLUDED.fb_type
                """), values)
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting pitcher {row.get('Name')}: {str(e)}")
                continue

    logger.info(f"Imported {inserted} pitchers from {year}")
    return inserted


async def verify_import():
    """Verify the import results."""

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                year,
                COUNT(*) as total,
                COUNT(CASE WHEN hit_future IS NOT NULL THEN 1 END) as hit_grades,
                COUNT(CASE WHEN fb_grade IS NOT NULL THEN 1 END) as pitch_grades,
                COUNT(CASE WHEN fv IS NOT NULL THEN 1 END) as fv_grades
            FROM fangraphs_unified_grades
            GROUP BY year
            ORDER BY year
        """))

        print("\n" + "="*80)
        print("FANGRAPHS IMPORT VERIFICATION")
        print("="*80)
        print("Year | Total | Hit Grades | Pitch Grades | FV Grades")
        print("-----|-------|------------|--------------|----------")

        for row in result.fetchall():
            print(f"{row[0]} | {row[1]:>5,} | {row[2]:>10,} | {row[3]:>12,} | {row[4]:>9,}")

        # Sample data
        result = await conn.execute(text("""
            SELECT player_name, year, data_type, fv, hit_future, game_power_future, fb_grade, cmd_grade
            FROM fangraphs_unified_grades
            WHERE year = 2025 AND (hit_future IS NOT NULL OR fb_grade IS NOT NULL)
            LIMIT 10
        """))

        print("\n=== Sample 2025 Records with Grades ===")
        for row in result.fetchall():
            if row[2] == 'hitter':
                print(f"{row[0]:25s} {row[1]} {row[2]:7s} FV:{row[3]} Hit:{row[4]} Power:{row[5]}")
            else:
                print(f"{row[0]:25s} {row[1]} {row[2]:7s} FV:{row[3]} FB:{row[6]} CMD:{row[7]}")


async def main():
    """Import all years with proper grade parsing."""

    print("Importing FanGraphs data with grade parsing...")

    total = 0
    for year in [2022, 2023, 2024, 2025]:
        hitters = await import_hitters(year)
        pitchers = await import_pitchers(year)
        total += hitters + pitchers

    await verify_import()

    print(f"\nTotal records processed: {total:,}")
    logger.info("Complete!")


if __name__ == "__main__":
    asyncio.run(main())
