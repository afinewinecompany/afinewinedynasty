"""
Migrate Fangraphs Grades to Separate Hitter/Pitcher Tables
===========================================================

This script:
1. Drops the old fangraphs_unified_grades table
2. Creates new fangraphs_hitter_grades table
3. Creates new fangraphs_pitcher_grades table
4. Creates fangraphs_physical_attributes table
5. Imports data from the 2025 Fangraphs CSVs
6. Links to prospects via fangraphs_player_id

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

# CSV file paths
HITTERS_CSV = r"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-2025.csv"
PITCHERS_CSV = r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2025.csv"
PHYSICAL_CSV = r"C:\Users\lilra\Downloads\fangraphs-the-board-all-2025-phys.csv"


async def check_schema(conn):
    """Check current database schema"""
    print("\n" + "="*80)
    print("STEP 1: Checking Current Schema")
    print("="*80)

    # Check if old table exists
    old_table_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'fangraphs_unified_grades'
        )
    """)

    if old_table_exists:
        row_count = await conn.fetchval("SELECT COUNT(*) FROM fangraphs_unified_grades")
        print(f"[OK] Found old table: fangraphs_unified_grades ({row_count:,} rows)")
    else:
        print("[SKIP] Old table fangraphs_unified_grades does not exist")

    # Check prospects table for fg_player_id
    fangraphs_id_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'prospects'
            AND column_name = 'fg_player_id'
        )
    """)

    if fangraphs_id_exists:
        count_with_fg = await conn.fetchval("""
            SELECT COUNT(*) FROM prospects
            WHERE fg_player_id IS NOT NULL
        """)
        print(f"[OK] prospects.fg_player_id column exists ({count_with_fg:,} non-null)")
    else:
        print("[WARN] WARNING: prospects.fg_player_id column does NOT exist!")
        print("  This column is needed to link Fangraphs grades to prospects")

    return old_table_exists, fangraphs_id_exists


async def drop_old_table(conn):
    """Drop the old unified grades table"""
    print("\n" + "="*80)
    print("STEP 2: Dropping Old Table")
    print("="*80)

    await conn.execute("DROP TABLE IF EXISTS fangraphs_unified_grades CASCADE")
    print("[OK] Dropped fangraphs_unified_grades table")


async def create_new_tables(conn):
    """Create new separate tables for hitters, pitchers, and physical attributes"""
    print("\n" + "="*80)
    print("STEP 3: Creating New Tables")
    print("="*80)

    # Hitter Grades Table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS fangraphs_hitter_grades (
            id SERIAL PRIMARY KEY,
            fangraphs_player_id VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            position VARCHAR(10),
            organization VARCHAR(10),
            top_100_rank INTEGER,
            org_rank INTEGER,
            age NUMERIC(5,2),

            -- Hitting Tool Grades (current / future)
            hit_current INTEGER,
            hit_future INTEGER,
            pitch_sel_current INTEGER,
            pitch_sel_future INTEGER,
            bat_ctrl_current INTEGER,
            bat_ctrl_future INTEGER,

            -- Contact Style
            contact_style VARCHAR(50),

            -- Power Grades
            game_power_current INTEGER,
            game_power_future INTEGER,
            raw_power_current INTEGER,
            raw_power_future INTEGER,

            -- Athleticism Grades
            speed_current INTEGER,
            speed_future INTEGER,
            fielding_current INTEGER,
            fielding_future INTEGER,
            versatility_current INTEGER,
            versatility_future INTEGER,

            -- Performance Metrics
            hard_hit_pct NUMERIC(5,2),

            -- Overall Grade
            fv INTEGER,  -- Future Value (40/45/50/55/60/etc)

            -- Metadata
            data_year INTEGER NOT NULL DEFAULT 2025,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            -- Note: Foreign key removed because fg_player_id doesn't have UNIQUE constraint
            -- Link manually via JOIN on fangraphs_player_id = prospects.fg_player_id
        );
    """)
    print("[OK] Created fangraphs_hitter_grades table")

    # Pitcher Grades Table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS fangraphs_pitcher_grades (
            id SERIAL PRIMARY KEY,
            fangraphs_player_id VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            position VARCHAR(10),
            organization VARCHAR(10),
            top_100_rank INTEGER,
            org_rank INTEGER,
            age NUMERIC(5,2),

            -- Tommy John Surgery
            tj_date DATE,

            -- Fastball Type and Grade
            fb_type VARCHAR(50),
            fb_current INTEGER,
            fb_future INTEGER,

            -- Secondary Pitch Grades
            sl_current INTEGER,
            sl_future INTEGER,
            cb_current INTEGER,
            cb_future INTEGER,
            ch_current INTEGER,
            ch_future INTEGER,

            -- Command
            cmd_current INTEGER,
            cmd_future INTEGER,

            -- Velocity
            velocity_sits_low INTEGER,
            velocity_sits_high INTEGER,
            velocity_tops INTEGER,

            -- Overall Grade
            fv INTEGER,  -- Future Value

            -- Metadata
            data_year INTEGER NOT NULL DEFAULT 2025,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            -- Note: Foreign key removed because fg_player_id doesn't have UNIQUE constraint
        );
    """)
    print("[OK] Created fangraphs_pitcher_grades table")

    # Physical Attributes Table (for both hitters and pitchers)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS fangraphs_physical_attributes (
            id SERIAL PRIMARY KEY,
            fangraphs_player_id VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            position VARCHAR(10),
            age NUMERIC(5,2),

            -- Physical Attributes
            frame_grade INTEGER,      -- -2 to +2 scale
            athleticism_grade INTEGER, -- -2 to +2 scale
            levers VARCHAR(20),        -- Short/Med/Long
            arm_grade INTEGER,         -- 20-80 scale
            performance_grade INTEGER, -- -2 to +2 scale
            delivery_grade INTEGER,    -- -2 to +2 scale (pitchers only)

            -- Metadata
            data_year INTEGER NOT NULL DEFAULT 2025,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            -- Note: Foreign key removed because fg_player_id doesn't have UNIQUE constraint
        );
    """)
    print("[OK] Created fangraphs_physical_attributes table")

    # Create indexes
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_hitter_grades_fg_id ON fangraphs_hitter_grades(fangraphs_player_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_hitter_grades_fv ON fangraphs_hitter_grades(fv)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_hitter_grades_top100 ON fangraphs_hitter_grades(top_100_rank)")

    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pitcher_grades_fg_id ON fangraphs_pitcher_grades(fangraphs_player_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pitcher_grades_fv ON fangraphs_pitcher_grades(fv)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pitcher_grades_top100 ON fangraphs_pitcher_grades(top_100_rank)")

    await conn.execute("CREATE INDEX IF NOT EXISTS idx_physical_fg_id ON fangraphs_physical_attributes(fangraphs_player_id)")

    print("[OK] Created indexes")


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

    # Remove '+' or other characters
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
        # Parse M/D/YYYY format and return date object
        dt = datetime.strptime(date_str, '%m/%d/%Y')
        return dt.date()  # Return date object, not string
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


async def import_hitters(conn):
    """Import hitter grades from CSV"""
    print("\n" + "="*80)
    print("STEP 4: Importing Hitter Grades")
    print("="*80)

    imported = 0
    skipped = 0

    with open(HITTERS_CSV, 'r', encoding='utf-8') as f:
        # Skip the header row with thousands of empty columns
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
                        hard_hit_pct, fv
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, $11, $12, $13, $14,
                        $15, $16, $17, $18, $19, $20,
                        $21, $22, $23, $24, $25, $26
                    )
                    ON CONFLICT (fangraphs_player_id) DO UPDATE SET
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
                    hard_hit, fv
                )
                imported += 1
            except Exception as e:
                print(f"[SKIP] Skipped {row['Name']}: {str(e)}")
                skipped += 1

    print(f"[OK] Imported {imported:,} hitters")
    if skipped > 0:
        print(f"[WARN] Skipped {skipped} hitters (likely missing from prospects table)")


async def import_pitchers(conn):
    """Import pitcher grades from CSV"""
    print("\n" + "="*80)
    print("STEP 5: Importing Pitcher Grades")
    print("="*80)

    imported = 0
    skipped = 0

    with open(PITCHERS_CSV, 'r', encoding='utf-8') as f:
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
                        fv
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8,
                        $9, $10, $11, $12, $13, $14, $15,
                        $16, $17, $18, $19, $20, $21, $22, $23
                    )
                    ON CONFLICT (fangraphs_player_id) DO UPDATE SET
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
                    fv
                )
                imported += 1
            except Exception as e:
                print(f"[SKIP] Skipped {row['Name']}: {str(e)}")
                skipped += 1

    print(f"[OK] Imported {imported:,} pitchers")
    if skipped > 0:
        print(f"[WARN] Skipped {skipped} pitchers (likely missing from prospects table)")


async def import_physical(conn):
    """Import physical attributes from CSV"""
    print("\n" + "="*80)
    print("STEP 6: Importing Physical Attributes")
    print("="*80)

    imported = 0
    skipped = 0

    with open(PHYSICAL_CSV, 'r', encoding='utf-8') as f:
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
                        arm_grade, performance_grade, delivery_grade
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
                    )
                    ON CONFLICT (fangraphs_player_id) DO UPDATE SET
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
                    arm, performance, delivery
                )
                imported += 1
            except Exception as e:
                print(f"[SKIP] Skipped {row['Name']}: {str(e)}")
                skipped += 1

    print(f"[OK] Imported {imported:,} physical attribute records")
    if skipped > 0:
        print(f"[WARN] Skipped {skipped} records (likely missing from prospects table)")


async def generate_report(conn):
    """Generate final ML readiness report"""
    print("\n" + "="*80)
    print("STEP 7: ML Readiness Report")
    print("="*80)

    # Count records
    hitter_count = await conn.fetchval("SELECT COUNT(*) FROM fangraphs_hitter_grades")
    pitcher_count = await conn.fetchval("SELECT COUNT(*) FROM fangraphs_pitcher_grades")
    physical_count = await conn.fetchval("SELECT COUNT(*) FROM fangraphs_physical_attributes")

    # Check linkage to prospects
    hitters_linked = await conn.fetchval("""
        SELECT COUNT(*)
        FROM fangraphs_hitter_grades h
        JOIN prospects p ON h.fangraphs_player_id = p.fg_player_id
    """)

    pitchers_linked = await conn.fetchval("""
        SELECT COUNT(*)
        FROM fangraphs_pitcher_grades pg
        JOIN prospects p ON pg.fangraphs_player_id = p.fg_player_id
    """)

    # Check FV distribution
    hitter_fv_dist = await conn.fetch("""
        SELECT fv, COUNT(*) as count
        FROM fangraphs_hitter_grades
        WHERE fv IS NOT NULL
        GROUP BY fv
        ORDER BY fv DESC
    """)

    pitcher_fv_dist = await conn.fetch("""
        SELECT fv, COUNT(*) as count
        FROM fangraphs_pitcher_grades
        WHERE fv IS NOT NULL
        GROUP BY fv
        ORDER BY fv DESC
    """)

    print(f"\n📊 Data Summary:")
    print(f"  Hitters: {hitter_count:,} total, {hitters_linked:,} linked to prospects ({hitters_linked/hitter_count*100:.1f}%)")
    print(f"  Pitchers: {pitcher_count:,} total, {pitchers_linked:,} linked to prospects ({pitchers_linked/pitcher_count*100:.1f}%)")
    print(f"  Physical: {physical_count:,} records")

    print(f"\n🎯 Hitter FV Distribution:")
    for row in hitter_fv_dist[:10]:
        print(f"  FV {row['fv']}: {row['count']:,} players")

    print(f"\n🎯 Pitcher FV Distribution:")
    for row in pitcher_fv_dist[:10]:
        print(f"  FV {row['fv']}: {row['count']:,} players")

    print(f"\n[SUCCESS] MIGRATION COMPLETE!")
    print(f"\n[INFO] Next Steps for Machine Learning:")
    print(f"  1. Join Fangraphs grades with MiLB performance data")
    print(f"  2. Create feature engineering pipeline combining:")
    print(f"     - Fangraphs tool grades (Hit, Power, Speed, FB, SL, CMD, etc.)")
    print(f"     - MiLB stats (AVG, OPS, ERA, K/9, BB/9, etc.)")
    print(f"     - Physical attributes (Frame, Athleticism, Arm)")
    print(f"     - Age-relative-to-level adjustments")
    print(f"  3. Use FV (Future Value) as target variable for validation")
    print(f"  4. Build separate models for hitters and pitchers")
    print(f"  5. Train models to predict MLB success, ETA, and breakouts")


async def main():
    """Main execution"""
    # Set UTF-8 encoding for Windows console
    import sys
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

    print("="*80)
    print("FANGRAPHS GRADES MIGRATION - ML PIPELINE PREPARATION")
    print("="*80)

    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        print(f"[OK] Connected to database")

        # Execute migration steps
        old_exists, fg_id_exists = await check_schema(conn)

        if not fg_id_exists:
            print("\n[ERROR] prospects.fg_player_id column does not exist!")
            print("Cannot proceed with migration. Please run migration to add this column first.")
            await conn.close()
            return

        # Drop old table
        if old_exists:
            confirm = input("\nDrop old fangraphs_unified_grades table? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Aborting migration.")
                await conn.close()
                return

        await drop_old_table(conn)

        # Create new tables
        await create_new_tables(conn)

        # Import data
        await import_hitters(conn)
        await import_pitchers(conn)
        await import_physical(conn)

        # Generate report
        await generate_report(conn)

        await conn.close()
        print("\n[OK] Database connection closed")

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
