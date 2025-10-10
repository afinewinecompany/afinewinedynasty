#!/usr/bin/env python3
"""
Quick import of only 2025 Fangraphs data into existing table.
"""

import pandas as pd
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def import_hitters_2025():
    """Import 2025 hitters data."""

    filepath = r"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-2025.csv"
    logger.info(f"Importing: {filepath}")

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
        'BB%': 'bb_rate',
        'K%': 'k_rate'
    })

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
                    'year': 2025,
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
                    'source_file': 'fangraphs-the-board-hitters-2025.csv'
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
                        fv = EXCLUDED.fv,
                        hit_future = EXCLUDED.hit_future,
                        game_power_future = EXCLUDED.game_power_future,
                        raw_power_future = EXCLUDED.raw_power_future,
                        speed_future = EXCLUDED.speed_future,
                        field_future = EXCLUDED.field_future
                """), values)
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting hitter {row.get('player_name')}: {str(e)}")
                continue

    logger.info(f"Imported {inserted} hitters from 2025")
    return inserted


async def import_pitchers_2025():
    """Import 2025 pitchers data."""

    filepath = r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2025.csv"
    logger.info(f"Importing: {filepath}")

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
                    'year': 2025,
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
                    'source_file': 'fangraphs-the-board-pitchers-2025.csv'
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
                        fv = EXCLUDED.fv,
                        fb_grade = EXCLUDED.fb_grade,
                        sl_grade = EXCLUDED.sl_grade,
                        cb_grade = EXCLUDED.cb_grade,
                        ch_grade = EXCLUDED.ch_grade,
                        cmd_grade = EXCLUDED.cmd_grade
                """), values)
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting pitcher {row.get('player_name')}: {str(e)}")
                continue

    logger.info(f"Imported {inserted} pitchers from 2025")
    return inserted


async def verify_import():
    """Verify the import results."""

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT year, data_type, COUNT(*) as count,
                   COUNT(DISTINCT fg_player_id) as unique_players,
                   COUNT(CASE WHEN top_100_rank IS NOT NULL THEN 1 END) as top_100
            FROM fangraphs_unified_grades
            WHERE year = 2025
            GROUP BY year, data_type
            ORDER BY data_type
        """))

        print("\n" + "="*70)
        print("2025 FANGRAPHS IMPORT RESULTS")
        print("="*70)

        total_records = 0
        for row in result.fetchall():
            print(f"{row[1]:8s}: {row[2]:4d} records, {row[3]:4d} unique players, {row[4]:3d} top 100")
            total_records += row[2]

        print(f"\nTotal 2025 records: {total_records:,}")

        # Show all years summary
        result = await conn.execute(text("""
            SELECT year, COUNT(*) as count
            FROM fangraphs_unified_grades
            GROUP BY year
            ORDER BY year
        """))

        print("\n=== ALL YEARS SUMMARY ===")
        grand_total = 0
        for row in result.fetchall():
            print(f"{row[0]}: {row[1]:,} records")
            grand_total += row[1]

        print(f"\nGrand Total: {grand_total:,} records")


async def main():
    """Import 2025 data only."""

    print("Starting 2025 FanGraphs import...")

    # Import hitters
    hitters_count = await import_hitters_2025()

    # Import pitchers
    pitchers_count = await import_pitchers_2025()

    # Verify results
    await verify_import()

    print(f"\nImport complete! Added {hitters_count + pitchers_count:,} total records for 2025")


if __name__ == "__main__":
    asyncio.run(main())
