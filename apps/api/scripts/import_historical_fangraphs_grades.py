"""
Import Historical Fangraphs Grades (2022-2024)
==============================================

This script imports Fangraphs prospect grades from multiple years,
enabling TRUE TEMPORAL VALIDATION for machine learning models.

Key Changes:
- Tables now support multiple years per prospect (remove UNIQUE constraint)
- Add data_year column to track which year's grades
- Same prospect can have different grades in different years

Database: Railway PostgreSQL
Author: BMad Party Mode Team
Date: 2025-10-19
"""

import asyncio
import asyncpg
import csv
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"

# CSV file paths by year
FILES = {
    2022: {
        'hitters': r"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-2022.csv",
        'pitchers': r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2022.csv",
        'physical': r"C:\Users\lilra\Downloads\fangraphs-the-board-all-2022-phys.csv",
    },
    2023: {
        'hitters': r"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-2023.csv",
        'pitchers': r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2023.csv",
        'physical': r"C:\Users\lilra\Downloads\fangraphs-the-board-all-2023-phys.csv",
    },
    2024: {
        'hitters': r"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-2024.csv",
        'pitchers': r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2024.csv",
        'physical': r"C:\Users\lilra\Downloads\fangraphs-the-board-all-2024-phys.csv",
    },
}


async def update_table_schemas(conn):
    """
    Update tables to support multi-year grades
    - Remove UNIQUE constraint on fangraphs_player_id
    - Add composite UNIQUE (fangraphs_player_id, data_year)
    """
    print("\n" + "="*80)
    print("STEP 1: Updating Table Schemas for Multi-Year Support")
    print("="*80 + "\n")

    # Drop existing unique constraints and recreate with data_year
    print("Updating fangraphs_hitter_grades...")
    await conn.execute("""
        ALTER TABLE fangraphs_hitter_grades
        DROP CONSTRAINT IF EXISTS fangraphs_hitter_grades_fangraphs_player_id_key;
    """)

    await conn.execute("""
        ALTER TABLE fangraphs_hitter_grades
        DROP CONSTRAINT IF EXISTS fangraphs_hitter_grades_player_year_key;
    """)

    await conn.execute("""
        ALTER TABLE fangraphs_hitter_grades
        ADD CONSTRAINT fangraphs_hitter_grades_player_year_key
        UNIQUE (fangraphs_player_id, data_year);
    """)

    print("Updating fangraphs_pitcher_grades...")
    await conn.execute("""
        ALTER TABLE fangraphs_pitcher_grades
        DROP CONSTRAINT IF EXISTS fangraphs_pitcher_grades_fangraphs_player_id_key;
    """)

    await conn.execute("""
        ALTER TABLE fangraphs_pitcher_grades
        DROP CONSTRAINT IF EXISTS fangraphs_pitcher_grades_player_year_key;
    """)

    await conn.execute("""
        ALTER TABLE fangraphs_pitcher_grades
        ADD CONSTRAINT fangraphs_pitcher_grades_player_year_key
        UNIQUE (fangraphs_player_id, data_year);
    """)

    print("Updating fangraphs_physical_attributes...")
    await conn.execute("""
        ALTER TABLE fangraphs_physical_attributes
        DROP CONSTRAINT IF EXISTS fangraphs_physical_attributes_fangraphs_player_id_key;
    """)

    await conn.execute("""
        ALTER TABLE fangraphs_physical_attributes
        DROP CONSTRAINT IF EXISTS fangraphs_physical_attributes_player_year_key;
    """)

    await conn.execute("""
        ALTER TABLE fangraphs_physical_attributes
        ADD CONSTRAINT fangraphs_physical_attributes_player_year_key
        UNIQUE (fangraphs_player_id, data_year);
    """)

    print("[OK] Table schemas updated for multi-year support")


# Reuse parsing functions from migration script
def parse_grade_pair(grade_str: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """Parse Fangraphs grade format '40 / 50' into (current, future)"""
    if not grade_str or grade_str == '':
        return None, None
    parts = grade_str.split('/')
    if len(parts) == 2:
        try:
            current = int(parts[0].strip()) if parts[0].strip() else None
            future = int(parts[1].strip()) if parts[1].strip() else None
            return current, future
        except ValueError:
            return None, None
    return None, None


def parse_velocity_range(vel_str: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """Parse velocity format '93-96' into (low, high)"""
    if not vel_str or vel_str == '':
        return None, None
    parts = vel_str.split('-')
    if len(parts) == 2:
        try:
            low = int(parts[0].strip())
            high = int(parts[1].strip())
            return low, high
        except ValueError:
            return None, None
    return None, None


def parse_fv(fv_str: Optional[str]) -> Optional[int]:
    """Parse FV which can be '50', '45+', etc."""
    if not fv_str or fv_str == '':
        return None
    fv_clean = fv_str.replace('+', '').strip()
    try:
        return int(fv_clean)
    except ValueError:
        return None


def parse_tj_date(date_str: Optional[str]):
    """Parse Tommy John date format 'M/D/YYYY' and return datetime.date"""
    if not date_str or date_str == '':
        return None
    try:
        dt = datetime.strptime(date_str, '%m/%d/%Y')
        return dt.date()
    except:
        return None


def parse_numeric_grade(grade_str: Optional[str]) -> Optional[int]:
    """Parse simple numeric grade, handling empty strings"""
    if not grade_str or grade_str == '':
        return None
    try:
        return int(grade_str)
    except ValueError:
        return None


async def import_hitters_for_year(conn, year: int, csv_path: str):
    """Import hitter grades for a specific year"""
    print(f"\nImporting {year} hitters from {csv_path}...")

    imported = 0
    skipped = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Parse grades
            hit_curr, hit_fut = parse_grade_pair(row.get('Hit'))
            pitch_sel_curr, pitch_sel_fut = parse_grade_pair(row.get('Pitch Sel'))
            bat_ctrl_curr, bat_ctrl_fut = parse_grade_pair(row.get('Bat Ctrl'))
            game_pwr_curr, game_pwr_fut = parse_grade_pair(row.get('Game Pwr'))
            raw_pwr_curr, raw_pwr_fut = parse_grade_pair(row.get('Raw Pwr'))
            spd_curr, spd_fut = parse_grade_pair(row.get('Spd'))
            fld_curr, fld_fut = parse_grade_pair(row.get('Fld'))
            versa_curr, versa_fut = parse_grade_pair(row.get('Versa'))

            fv = parse_fv(row.get('FV'))
            hard_hit = float(row['Hard Hit%']) if row.get('Hard Hit%') and row['Hard Hit%'] != '' else None
            top_100 = int(row['Top 100']) if row.get('Top 100') and row['Top 100'] != '' else None
            org_rank = int(row['Org Rk']) if row.get('Org Rk') and row['Org Rk'] != '' else None
            age = float(row['Age']) if row.get('Age') and row['Age'] != '' else None

            try:
                await conn.execute("""
                    INSERT INTO fangraphs_hitter_grades (
                        fangraphs_player_id, name, position, organization,
                        top_100_rank, org_rank, age,
                        hit_current, hit_future,
                        pitch_sel_current, pitch_sel_future,
                        bat_ctrl_current, bat_ctrl_future,
                        contact_style,
                        game_power_current, game_power_future,
                        raw_power_current, raw_power_future,
                        speed_current, speed_future,
                        fielding_current, fielding_future,
                        versatility_current, versatility_future,
                        hard_hit_pct, fv, data_year
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, $11, $12, $13, $14,
                        $15, $16, $17, $18, $19, $20,
                        $21, $22, $23, $24, $25, $26, $27
                    )
                    ON CONFLICT (fangraphs_player_id, data_year) DO UPDATE SET
                        name = EXCLUDED.name,
                        position = EXCLUDED.position,
                        organization = EXCLUDED.organization,
                        top_100_rank = EXCLUDED.top_100_rank,
                        org_rank = EXCLUDED.org_rank,
                        age = EXCLUDED.age,
                        hit_current = EXCLUDED.hit_current,
                        hit_future = EXCLUDED.hit_future,
                        pitch_sel_current = EXCLUDED.pitch_sel_current,
                        pitch_sel_future = EXCLUDED.pitch_sel_future,
                        bat_ctrl_current = EXCLUDED.bat_ctrl_current,
                        bat_ctrl_future = EXCLUDED.bat_ctrl_future,
                        contact_style = EXCLUDED.contact_style,
                        game_power_current = EXCLUDED.game_power_current,
                        game_power_future = EXCLUDED.game_power_future,
                        raw_power_current = EXCLUDED.raw_power_current,
                        raw_power_future = EXCLUDED.raw_power_future,
                        speed_current = EXCLUDED.speed_current,
                        speed_future = EXCLUDED.speed_future,
                        fielding_current = EXCLUDED.fielding_current,
                        fielding_future = EXCLUDED.fielding_future,
                        versatility_current = EXCLUDED.versatility_current,
                        versatility_future = EXCLUDED.versatility_future,
                        hard_hit_pct = EXCLUDED.hard_hit_pct,
                        fv = EXCLUDED.fv,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    row['PlayerId'], row['Name'], row.get('Pos'), row.get('Org'),
                    top_100, org_rank, age,
                    hit_curr, hit_fut,
                    pitch_sel_curr, pitch_sel_fut,
                    bat_ctrl_curr, bat_ctrl_fut,
                    row.get('Con Style'),
                    game_pwr_curr, game_pwr_fut,
                    raw_pwr_curr, raw_pwr_fut,
                    spd_curr, spd_fut,
                    fld_curr, fld_fut,
                    versa_curr, versa_fut,
                    hard_hit, fv, year
                )
                imported += 1
            except Exception as e:
                print(f"[SKIP] {row['Name']}: {str(e)}")
                skipped += 1

    print(f"[OK] Imported {imported:,} hitters for {year}")
    if skipped > 0:
        print(f"[WARN] Skipped {skipped}")

    return imported, skipped


async def import_pitchers_for_year(conn, year: int, csv_path: str):
    """Import pitcher grades for a specific year"""
    print(f"\nImporting {year} pitchers from {csv_path}...")

    imported = 0
    skipped = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Parse grades
            fb_curr, fb_fut = parse_grade_pair(row.get('FB'))
            sl_curr, sl_fut = parse_grade_pair(row.get('SL'))
            cb_curr, cb_fut = parse_grade_pair(row.get('CB'))
            ch_curr, ch_fut = parse_grade_pair(row.get('CH'))
            cmd_curr, cmd_fut = parse_grade_pair(row.get('CMD'))

            # Parse velocity
            sits_low, sits_high = parse_velocity_range(row.get('Sits'))
            tops = int(row['Tops']) if row.get('Tops') and row['Tops'] != '' else None

            fv = parse_fv(row.get('FV'))
            tj_date = parse_tj_date(row.get('TJ Date'))
            top_100 = int(row['Top 100']) if row.get('Top 100') and row['Top 100'] != '' else None
            org_rank = int(row['Org Rk']) if row.get('Org Rk') and row['Org Rk'] != '' else None
            age = float(row['Age']) if row.get('Age') and row['Age'] != '' else None

            try:
                await conn.execute("""
                    INSERT INTO fangraphs_pitcher_grades (
                        fangraphs_player_id, name, position, organization,
                        top_100_rank, org_rank, age, tj_date,
                        fb_type, fb_current, fb_future,
                        sl_current, sl_future,
                        cb_current, cb_future,
                        ch_current, ch_future,
                        cmd_current, cmd_future,
                        velocity_sits_low, velocity_sits_high, velocity_tops,
                        fv, data_year
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8,
                        $9, $10, $11, $12, $13, $14, $15,
                        $16, $17, $18, $19, $20, $21, $22, $23, $24
                    )
                    ON CONFLICT (fangraphs_player_id, data_year) DO UPDATE SET
                        name = EXCLUDED.name,
                        position = EXCLUDED.position,
                        organization = EXCLUDED.organization,
                        top_100_rank = EXCLUDED.top_100_rank,
                        org_rank = EXCLUDED.org_rank,
                        age = EXCLUDED.age,
                        tj_date = EXCLUDED.tj_date,
                        fb_type = EXCLUDED.fb_type,
                        fb_current = EXCLUDED.fb_current,
                        fb_future = EXCLUDED.fb_future,
                        sl_current = EXCLUDED.sl_current,
                        sl_future = EXCLUDED.sl_future,
                        cb_current = EXCLUDED.cb_current,
                        cb_future = EXCLUDED.cb_future,
                        ch_current = EXCLUDED.ch_current,
                        ch_future = EXCLUDED.ch_future,
                        cmd_current = EXCLUDED.cmd_current,
                        cmd_future = EXCLUDED.cmd_future,
                        velocity_sits_low = EXCLUDED.velocity_sits_low,
                        velocity_sits_high = EXCLUDED.velocity_sits_high,
                        velocity_tops = EXCLUDED.velocity_tops,
                        fv = EXCLUDED.fv,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    row['PlayerId'], row['Name'], row.get('Pos'), row.get('Org'),
                    top_100, org_rank, age, tj_date,
                    row.get('FB Type'), fb_curr, fb_fut,
                    sl_curr, sl_fut,
                    cb_curr, cb_fut,
                    ch_curr, ch_fut,
                    cmd_curr, cmd_fut,
                    sits_low, sits_high, tops,
                    fv, year
                )
                imported += 1
            except Exception as e:
                print(f"[SKIP] {row['Name']}: {str(e)}")
                skipped += 1

    print(f"[OK] Imported {imported:,} pitchers for {year}")
    if skipped > 0:
        print(f"[WARN] Skipped {skipped}")

    return imported, skipped


async def import_physical_for_year(conn, year: int, csv_path: str):
    """Import physical attributes for a specific year"""
    print(f"\nImporting {year} physical attributes from {csv_path}...")

    imported = 0
    skipped = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            frame = parse_numeric_grade(row.get('Frame'))
            athleticism = parse_numeric_grade(row.get('Athl'))
            arm = parse_numeric_grade(row.get('Arm'))
            performance = parse_numeric_grade(row.get('Perf'))
            delivery = parse_numeric_grade(row.get('Delivery'))
            age = float(row['Age']) if row.get('Age') and row['Age'] != '' else None

            try:
                await conn.execute("""
                    INSERT INTO fangraphs_physical_attributes (
                        fangraphs_player_id, name, position, age,
                        frame_grade, athleticism_grade, levers,
                        arm_grade, performance_grade, delivery_grade, data_year
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
                    )
                    ON CONFLICT (fangraphs_player_id, data_year) DO UPDATE SET
                        name = EXCLUDED.name,
                        position = EXCLUDED.position,
                        age = EXCLUDED.age,
                        frame_grade = EXCLUDED.frame_grade,
                        athleticism_grade = EXCLUDED.athleticism_grade,
                        levers = EXCLUDED.levers,
                        arm_grade = EXCLUDED.arm_grade,
                        performance_grade = EXCLUDED.performance_grade,
                        delivery_grade = EXCLUDED.delivery_grade,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    row['PlayerId'], row['Name'], row.get('Pos'), age,
                    frame, athleticism, row.get('Levers'),
                    arm, performance, delivery, year
                )
                imported += 1
            except Exception as e:
                print(f"[SKIP] {row['Name']}: {str(e)}")
                skipped += 1

    print(f"[OK] Imported {imported:,} physical attributes for {year}")
    if skipped > 0:
        print(f"[WARN] Skipped {skipped}")

    return imported, skipped


async def generate_summary(conn):
    """Generate summary of all years"""
    print("\n" + "="*80)
    print("MULTI-YEAR IMPORT SUMMARY")
    print("="*80 + "\n")

    # Hitters by year
    print("Hitters by Year:")
    hitter_result = await conn.fetch("""
        SELECT data_year, COUNT(*) as count
        FROM fangraphs_hitter_grades
        GROUP BY data_year
        ORDER BY data_year
    """)
    for row in hitter_result:
        print(f"  {row['data_year']}: {row['count']:,} hitters")

    # Pitchers by year
    print("\nPitchers by Year:")
    pitcher_result = await conn.fetch("""
        SELECT data_year, COUNT(*) as count
        FROM fangraphs_pitcher_grades
        GROUP BY data_year
        ORDER BY data_year
    """)
    for row in pitcher_result:
        print(f"  {row['data_year']}: {row['count']:,} pitchers")

    # Physical by year
    print("\nPhysical Attributes by Year:")
    physical_result = await conn.fetch("""
        SELECT data_year, COUNT(*) as count
        FROM fangraphs_physical_attributes
        GROUP BY data_year
        ORDER BY data_year
    """)
    for row in physical_result:
        print(f"  {row['data_year']}: {row['count']:,} records")

    # Prospects with multi-year grades
    print("\nProspects with Multi-Year Grades:")
    multi_year = await conn.fetch("""
        WITH prospect_years AS (
            SELECT fangraphs_player_id, COUNT(DISTINCT data_year) as years
            FROM fangraphs_hitter_grades
            GROUP BY fangraphs_player_id
            UNION ALL
            SELECT fangraphs_player_id, COUNT(DISTINCT data_year) as years
            FROM fangraphs_pitcher_grades
            GROUP BY fangraphs_player_id
        )
        SELECT
            COUNT(CASE WHEN years >= 4 THEN 1 END) as four_years,
            COUNT(CASE WHEN years >= 3 THEN 1 END) as three_years,
            COUNT(CASE WHEN years >= 2 THEN 1 END) as two_years
        FROM prospect_years
    """)
    r = multi_year[0]
    print(f"  4 years of grades: {r['four_years']:,} prospects")
    print(f"  3 years of grades: {r['three_years']:,} prospects")
    print(f"  2 years of grades: {r['two_years']:,} prospects")

    print("\n" + "="*80)
    print("TEMPORAL VALIDATION NOW POSSIBLE!")
    print("="*80)
    print("\nYou can now do:")
    print("  - Train on 2022-2023 data")
    print("  - Validate on 2024 data")
    print("  - Test on 2025 data (true holdout)")
    print("\nSee updated CORRECTED_VALIDATION_STRATEGY.md for details")


async def main():
    """Main execution"""
    import sys
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

    print("="*80)
    print("HISTORICAL FANGRAPHS GRADES IMPORT (2022-2024)")
    print("="*80)

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("\n[OK] Connected to database")

        # Update table schemas
        await update_table_schemas(conn)

        # Import each year
        total_hitters = 0
        total_pitchers = 0
        total_physical = 0

        for year in [2022, 2023, 2024]:
            print(f"\n{'='*80}")
            print(f"IMPORTING {year} DATA")
            print(f"{'='*80}")

            # Import hitters
            h_imported, h_skipped = await import_hitters_for_year(
                conn, year, FILES[year]['hitters']
            )
            total_hitters += h_imported

            # Import pitchers
            p_imported, p_skipped = await import_pitchers_for_year(
                conn, year, FILES[year]['pitchers']
            )
            total_pitchers += p_imported

            # Import physical
            ph_imported, ph_skipped = await import_physical_for_year(
                conn, year, FILES[year]['physical']
            )
            total_physical += ph_imported

        # Generate summary
        await generate_summary(conn)

        print(f"\n[OK] Total imported:")
        print(f"  Hitters: {total_hitters:,}")
        print(f"  Pitchers: {total_pitchers:,}")
        print(f"  Physical: {total_physical:,}")

        await conn.close()
        print("\n[OK] Database connection closed")

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
