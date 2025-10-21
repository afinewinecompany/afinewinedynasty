"""
Import 2020-2021 Fangraphs Grades
=================================

This script imports 2020-2021 Fangraphs prospect grades to expand training data.

Expected improvement:
- Current training: 338 samples (2022-2023)
- After import: ~700-900 samples (2020-2023)
- Regular class: 30 → 70-100 samples
- All-Star class: 0 → 5-10 samples

Database: Railway PostgreSQL
"""

import asyncio
import asyncpg
import csv
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"

# CSV file paths for 2020-2021
FILES = {
    2020: {
        'hitters': r"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-2020.csv",
        'pitchers': r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2020.csv",
        # No physical attributes file for 2020
    },
    2021: {
        'hitters': r"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-2021.csv",
        'pitchers': r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2021.csv",
        'physical': r"C:\Users\lilra\Downloads\fangraphs-the-board-all-2021-phys.csv",
    },
}


def parse_grade_range(value: str) -> tuple[Optional[int], Optional[int]]:
    """
    Parse Fangraphs grade range format: '45 / 55' or '50'.

    Returns:
        (current_grade, future_grade)
    """
    if not value or value == 'nan' or value == '':
        return None, None

    try:
        if '/' in value:
            parts = value.split('/')
            current = int(parts[0].strip())
            future = int(parts[1].strip())
            return current, future
        else:
            grade = int(value.strip())
            return grade, grade
    except (ValueError, IndexError, AttributeError):
        return None, None


async def import_hitters(conn, year: int, file_path: str) -> int:
    """Import hitters for a given year."""
    print(f"\nImporting {year} hitters from {file_path}...")

    count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                # Parse player info
                name = row['Name']
                position = row['Pos']
                organization = row['Org']
                age = float(row['Age']) if row['Age'] else None
                fv = int(row['FV']) if row['FV'] else None
                player_id = int(row['PlayerId']) if row['PlayerId'] else None

                if not player_id:
                    continue

                # Parse grades
                hit_current, hit_future = parse_grade_range(row.get('Hit', ''))
                game_pwr_current, game_pwr_future = parse_grade_range(row.get('Game Pwr', ''))
                raw_pwr_current, raw_pwr_future = parse_grade_range(row.get('Raw Pwr', ''))
                spd_current, spd_future = parse_grade_range(row.get('Spd', ''))
                fld_current, fld_future = parse_grade_range(row.get('Fld', ''))
                arm_current, arm_future = parse_grade_range(row.get('Arm', ''))

                # Insert into database
                await conn.execute("""
                    INSERT INTO fangraphs_hitter_grades (
                        fangraphs_player_id, name, position, organization,
                        age, hit_current, hit_future, game_power_current, game_power_future,
                        raw_power_current, raw_power_future, speed_current, speed_future,
                        fielding_current, fielding_future, arm_current, arm_future,
                        fangraphs_fv, data_year
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                    ON CONFLICT (fangraphs_player_id, data_year) DO UPDATE SET
                        name = EXCLUDED.name,
                        position = EXCLUDED.position,
                        organization = EXCLUDED.organization,
                        age = EXCLUDED.age,
                        hit_current = EXCLUDED.hit_current,
                        hit_future = EXCLUDED.hit_future,
                        game_power_current = EXCLUDED.game_power_current,
                        game_power_future = EXCLUDED.game_power_future,
                        raw_power_current = EXCLUDED.raw_power_current,
                        raw_power_future = EXCLUDED.raw_power_future,
                        speed_current = EXCLUDED.speed_current,
                        speed_future = EXCLUDED.speed_future,
                        fielding_current = EXCLUDED.fielding_current,
                        fielding_future = EXCLUDED.fielding_future,
                        arm_current = EXCLUDED.arm_current,
                        arm_future = EXCLUDED.arm_future,
                        fangraphs_fv = EXCLUDED.fangraphs_fv
                """, player_id, name, position, organization, age,
                    hit_current, hit_future, game_pwr_current, game_pwr_future,
                    raw_pwr_current, raw_pwr_future, spd_current, spd_future,
                    fld_current, fld_future, arm_current, arm_future,
                    fv, year)

                count += 1

            except Exception as e:
                print(f"  [ERROR] Failed to import hitter {row.get('Name', 'unknown')}: {e}")
                continue

    print(f"[OK] Imported {count} hitters for {year}")
    return count


async def import_pitchers(conn, year: int, file_path: str) -> int:
    """Import pitchers for a given year."""
    print(f"\nImporting {year} pitchers from {file_path}...")

    count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                # Parse player info
                name = row['Name']
                position = row.get('Pos', 'SP')
                organization = row['Org']
                age = float(row['Age']) if row['Age'] else None
                fv = int(row['FV']) if row['FV'] else None
                player_id = int(row['PlayerId']) if row['PlayerId'] else None

                if not player_id:
                    continue

                # Parse grades
                fb_current, fb_future = parse_grade_range(row.get('FB', ''))
                cb_current, cb_future = parse_grade_range(row.get('CB', ''))
                sl_current, sl_future = parse_grade_range(row.get('SL', ''))
                ch_current, ch_future = parse_grade_range(row.get('CH', ''))
                oth_current, oth_future = parse_grade_range(row.get('OTH', ''))
                cmd_current, cmd_future = parse_grade_range(row.get('CMD', ''))

                # Insert into database
                await conn.execute("""
                    INSERT INTO fangraphs_pitcher_grades (
                        fangraphs_player_id, name, position, organization,
                        age, fastball_current, fastball_future, curveball_current, curveball_future,
                        slider_current, slider_future, changeup_current, changeup_future,
                        other_current, other_future, command_current, command_future,
                        fangraphs_fv, data_year
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                    ON CONFLICT (fangraphs_player_id, data_year) DO UPDATE SET
                        name = EXCLUDED.name,
                        position = EXCLUDED.position,
                        organization = EXCLUDED.organization,
                        age = EXCLUDED.age,
                        fastball_current = EXCLUDED.fastball_current,
                        fastball_future = EXCLUDED.fastball_future,
                        curveball_current = EXCLUDED.curveball_current,
                        curveball_future = EXCLUDED.curveball_future,
                        slider_current = EXCLUDED.slider_current,
                        slider_future = EXCLUDED.slider_future,
                        changeup_current = EXCLUDED.changeup_current,
                        changeup_future = EXCLUDED.changeup_future,
                        other_current = EXCLUDED.other_current,
                        other_future = EXCLUDED.other_future,
                        command_current = EXCLUDED.command_current,
                        command_future = EXCLUDED.command_future,
                        fangraphs_fv = EXCLUDED.fangraphs_fv
                """, player_id, name, position, organization, age,
                    fb_current, fb_future, cb_current, cb_future,
                    sl_current, sl_future, ch_current, ch_future,
                    oth_current, oth_future, cmd_current, cmd_future,
                    fv, year)

                count += 1

            except Exception as e:
                print(f"  [ERROR] Failed to import pitcher {row.get('Name', 'unknown')}: {e}")
                continue

    print(f"[OK] Imported {count} pitchers for {year}")
    return count


async def import_physical_attributes(conn, year: int, file_path: str) -> int:
    """Import physical attributes for a given year."""
    print(f"\nImporting {year} physical attributes from {file_path}...")

    count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                player_id = int(row['PlayerId']) if row['PlayerId'] else None
                if not player_id:
                    continue

                # Parse physical grades
                frame_current, frame_future = parse_grade_range(row.get('Frame', ''))
                athleticism_current, athleticism_future = parse_grade_range(row.get('Ath', ''))

                await conn.execute("""
                    INSERT INTO fangraphs_physical_attributes (
                        fangraphs_player_id, frame_current, frame_future,
                        athleticism_current, athleticism_future, data_year
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (fangraphs_player_id, data_year) DO UPDATE SET
                        frame_current = EXCLUDED.frame_current,
                        frame_future = EXCLUDED.frame_future,
                        athleticism_current = EXCLUDED.athleticism_current,
                        athleticism_future = EXCLUDED.athleticism_future
                """, player_id, frame_current, frame_future,
                    athleticism_current, athleticism_future, year)

                count += 1

            except Exception as e:
                print(f"  [ERROR] Failed to import physical attributes: {e}")
                continue

    print(f"[OK] Imported {count} physical attributes for {year}")
    return count


async def verify_data_by_year(conn):
    """Verify imported data counts by year."""
    print("\n" + "="*80)
    print("DATA VERIFICATION")
    print("="*80)

    # Hitters by year
    print("\nHitters by Year:")
    hitter_counts = await conn.fetch("""
        SELECT data_year, COUNT(*) as count
        FROM fangraphs_hitter_grades
        GROUP BY data_year
        ORDER BY data_year
    """)
    for row in hitter_counts:
        print(f"  {row['data_year']}: {row['count']} hitters")

    # Pitchers by year
    print("\nPitchers by Year:")
    pitcher_counts = await conn.fetch("""
        SELECT data_year, COUNT(*) as count
        FROM fangraphs_pitcher_grades
        GROUP BY data_year
        ORDER BY data_year
    """)
    for row in pitcher_counts:
        print(f"  {row['data_year']}: {row['count']} pitchers")

    # Physical attributes by year
    print("\nPhysical Attributes by Year:")
    phys_counts = await conn.fetch("""
        SELECT data_year, COUNT(*) as count
        FROM fangraphs_physical_attributes
        GROUP BY data_year
        ORDER BY data_year
    """)
    for row in phys_counts:
        print(f"  {row['data_year']}: {row['count']} records")


async def main():
    print("="*80)
    print("IMPORT 2020-2021 FANGRAPHS GRADES")
    print("="*80)

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    print("\n[OK] Connected to database")

    try:
        # Import each year
        for year, files in sorted(FILES.items()):
            print("\n" + "="*80)
            print(f"IMPORTING {year} DATA")
            print("="*80)

            # Import hitters
            if 'hitters' in files:
                await import_hitters(conn, year, files['hitters'])

            # Import pitchers
            if 'pitchers' in files:
                await import_pitchers(conn, year, files['pitchers'])

            # Import physical attributes (if available)
            if 'physical' in files:
                await import_physical_attributes(conn, year, files['physical'])

        # Verify all data
        await verify_data_by_year(conn)

        print("\n" + "="*80)
        print("IMPORT COMPLETE")
        print("="*80)

        print("\nNext Steps:")
        print("  1. Run create_multi_year_mlb_expectation_labels.py to generate 2020-2021 labels")
        print("  2. Regenerate ML training datasets with 2020-2023 training data")
        print("  3. Retrain baseline model")
        print("  4. Expected improvement: +0.08-0.12 F1 (to 0.76-0.80)")

    finally:
        await conn.close()
        print("\n[OK] Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
