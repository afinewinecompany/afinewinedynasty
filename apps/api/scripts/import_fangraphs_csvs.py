"""
Import FanGraphs prospect grades from manually exported CSVs
"""
import pandas as pd
import asyncio
from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine


def parse_grade(grade_str):
    """Parse '20 / 45' into present (20) and future (45)."""
    if pd.isna(grade_str) or grade_str == '' or grade_str == '""':
        return None, None

    # Handle string format
    grade_str = str(grade_str).strip().strip('"')

    if ' / ' in grade_str:
        parts = grade_str.split(' / ')
        try:
            present = int(parts[0].strip().rstrip('+'))
            future = int(parts[1].strip().rstrip('+'))
            return present, future
        except:
            return None, None

    # Single value - use as future grade
    try:
        val = int(grade_str.rstrip('+'))
        return None, val
    except:
        return None, None


def parse_fv(fv_str):
    """Parse FV which can be like '45', '45+', '50'."""
    if pd.isna(fv_str) or fv_str == '':
        return None

    try:
        return int(str(fv_str).strip().rstrip('+'))
    except:
        return None


async def create_table():
    """Create FanGraphs prospect grades table."""
    async with engine.begin() as conn:
        await conn.execute(text('''
            DROP TABLE IF EXISTS fangraphs_prospect_grades CASCADE
        '''))

        await conn.execute(text('''
            CREATE TABLE fangraphs_prospect_grades (
                id SERIAL PRIMARY KEY,
                fg_player_id VARCHAR(50) NOT NULL,
                player_name VARCHAR(255),
                position VARCHAR(20),
                organization VARCHAR(100),

                -- Rankings
                top_100_rank INTEGER,
                org_rank INTEGER,
                age FLOAT,

                -- Future Value (20-80 scale)
                fv INTEGER,

                -- Hitter Tool Grades (present / future on 20-80 scale)
                hit_present INTEGER,
                hit_future INTEGER,
                pitch_sel INTEGER,
                bat_ctrl INTEGER,
                contact_style VARCHAR(50),
                game_pwr_present INTEGER,
                game_pwr_future INTEGER,
                raw_pwr_present INTEGER,
                raw_pwr_future INTEGER,
                spd_present INTEGER,
                spd_future INTEGER,
                fld_present INTEGER,
                fld_future INTEGER,
                versatility VARCHAR(100),
                hard_hit_pct FLOAT,

                -- Pitcher Grades
                tj_date VARCHAR(50),
                fb_type VARCHAR(50),
                fb_present INTEGER,
                fb_future INTEGER,
                sl_present INTEGER,
                sl_future INTEGER,
                cb_present INTEGER,
                cb_future INTEGER,
                ch_present INTEGER,
                ch_future INTEGER,
                cmd_present INTEGER,
                cmd_future INTEGER,
                sits_velo VARCHAR(20),
                tops_velo VARCHAR(20),

                -- Physical Attributes
                frame INTEGER,
                athleticism INTEGER,
                levers VARCHAR(50),
                arm INTEGER,
                performance INTEGER,
                delivery INTEGER,

                -- Metadata
                report_year INTEGER NOT NULL,
                report_date DATE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        '''))

        await conn.execute(text('''
            CREATE UNIQUE INDEX idx_fg_grades_player_year ON fangraphs_prospect_grades(fg_player_id, report_year)
        '''))

        await conn.execute(text('''
            CREATE INDEX idx_fg_grades_name ON fangraphs_prospect_grades(player_name)
        '''))

        await conn.execute(text('''
            CREATE INDEX idx_fg_grades_year ON fangraphs_prospect_grades(report_year)
        '''))

        print('Created fangraphs_prospect_grades table')


async def import_hitters(hitters_path, report_year):
    """Import hitter grades."""
    print(f'\nImporting hitters from {hitters_path}')

    df = pd.read_csv(hitters_path)
    print(f'Loaded {len(df)} hitters')

    # Parse tool grades
    df['hit_present'], df['hit_future'] = zip(*df['Hit'].apply(parse_grade))
    df['game_pwr_present'], df['game_pwr_future'] = zip(*df['Game Pwr'].apply(parse_grade))
    df['raw_pwr_present'], df['raw_pwr_future'] = zip(*df['Raw Pwr'].apply(parse_grade))
    df['spd_present'], df['spd_future'] = zip(*df['Spd'].apply(parse_grade))
    df['fld_present'], df['fld_future'] = zip(*df['Fld'].apply(parse_grade))

    async with engine.begin() as conn:
        for _, row in df.iterrows():
            await conn.execute(text('''
                INSERT INTO fangraphs_prospect_grades
                (fg_player_id, player_name, position, organization,
                 top_100_rank, org_rank, age, fv,
                 hit_present, hit_future, pitch_sel, bat_ctrl, contact_style,
                 game_pwr_present, game_pwr_future,
                 raw_pwr_present, raw_pwr_future,
                 spd_present, spd_future,
                 fld_present, fld_future,
                 versatility, hard_hit_pct,
                 report_year)
                VALUES
                (:fg_player_id, :player_name, :position, :organization,
                 :top_100_rank, :org_rank, :age, :fv,
                 :hit_present, :hit_future, :pitch_sel, :bat_ctrl, :contact_style,
                 :game_pwr_present, :game_pwr_future,
                 :raw_pwr_present, :raw_pwr_future,
                 :spd_present, :spd_future,
                 :fld_present, :fld_future,
                 :versatility, :hard_hit_pct,
                 :report_year)
                ON CONFLICT (fg_player_id, report_year) DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    position = EXCLUDED.position,
                    organization = EXCLUDED.organization,
                    top_100_rank = EXCLUDED.top_100_rank,
                    org_rank = EXCLUDED.org_rank,
                    age = EXCLUDED.age,
                    fv = EXCLUDED.fv,
                    hit_present = EXCLUDED.hit_present,
                    hit_future = EXCLUDED.hit_future,
                    pitch_sel = EXCLUDED.pitch_sel,
                    bat_ctrl = EXCLUDED.bat_ctrl,
                    contact_style = EXCLUDED.contact_style,
                    game_pwr_present = EXCLUDED.game_pwr_present,
                    game_pwr_future = EXCLUDED.game_pwr_future,
                    raw_pwr_present = EXCLUDED.raw_pwr_present,
                    raw_pwr_future = EXCLUDED.raw_pwr_future,
                    spd_present = EXCLUDED.spd_present,
                    spd_future = EXCLUDED.spd_future,
                    fld_present = EXCLUDED.fld_present,
                    fld_future = EXCLUDED.fld_future,
                    versatility = EXCLUDED.versatility,
                    hard_hit_pct = EXCLUDED.hard_hit_pct,
                    updated_at = NOW()
            '''), {
                'fg_player_id': str(row['PlayerId']),
                'player_name': str(row['Name']),
                'position': str(row['Pos']) if pd.notna(row['Pos']) else None,
                'organization': str(row['Org']) if pd.notna(row['Org']) else None,
                'top_100_rank': int(row['Top 100']) if pd.notna(row['Top 100']) else None,
                'org_rank': int(row['Org Rk']) if pd.notna(row['Org Rk']) else None,
                'age': float(row['Age']) if pd.notna(row['Age']) else None,
                'fv': parse_fv(row['FV']),
                'hit_present': int(row['hit_present']) if pd.notna(row['hit_present']) else None,
                'hit_future': int(row['hit_future']) if pd.notna(row['hit_future']) else None,
                'pitch_sel': int(row['Pitch Sel']) if pd.notna(row['Pitch Sel']) and 'Pitch Sel' in row else None,
                'bat_ctrl': int(row['Bat Ctrl']) if pd.notna(row['Bat Ctrl']) and 'Bat Ctrl' in row else None,
                'contact_style': str(row['Con Style']) if 'Con Style' in row and pd.notna(row['Con Style']) else None,
                'game_pwr_present': int(row['game_pwr_present']) if pd.notna(row['game_pwr_present']) else None,
                'game_pwr_future': int(row['game_pwr_future']) if pd.notna(row['game_pwr_future']) else None,
                'raw_pwr_present': int(row['raw_pwr_present']) if pd.notna(row['raw_pwr_present']) else None,
                'raw_pwr_future': int(row['raw_pwr_future']) if pd.notna(row['raw_pwr_future']) else None,
                'spd_present': int(row['spd_present']) if pd.notna(row['spd_present']) else None,
                'spd_future': int(row['spd_future']) if pd.notna(row['spd_future']) else None,
                'fld_present': int(row['fld_present']) if pd.notna(row['fld_present']) else None,
                'fld_future': int(row['fld_future']) if pd.notna(row['fld_future']) else None,
                'versatility': str(row['Versa']) if 'Versa' in row and pd.notna(row['Versa']) else None,
                'hard_hit_pct': float(row['Hard Hit%']) if 'Hard Hit%' in row and pd.notna(row['Hard Hit%']) else None,
                'report_year': report_year,
            })

    print(f'Imported {len(df)} hitters')


async def import_pitchers(pitchers_path, report_year):
    """Import pitcher grades."""
    print(f'\nImporting pitchers from {pitchers_path}')

    df = pd.read_csv(pitchers_path)
    print(f'Loaded {len(df)} rows from pitchers file')

    # Filter to only actual pitchers (those with pitch grades)
    pitcher_df = df[df['FB'].notna() | df['SL'].notna() | df['CB'].notna() | df['CH'].notna()].copy()
    print(f'Found {len(pitcher_df)} actual pitchers with grades')

    # Parse pitch grades (these can be "70" or "70 / 70")
    pitcher_df['fb_present'], pitcher_df['fb_future'] = zip(*pitcher_df['FB'].apply(parse_grade))
    pitcher_df['sl_present'], pitcher_df['sl_future'] = zip(*pitcher_df['SL'].apply(parse_grade))
    pitcher_df['cb_present'], pitcher_df['cb_future'] = zip(*pitcher_df['CB'].apply(parse_grade))
    pitcher_df['ch_present'], pitcher_df['ch_future'] = zip(*pitcher_df['CH'].apply(parse_grade))
    pitcher_df['cmd_present'], pitcher_df['cmd_future'] = zip(*pitcher_df['CMD'].apply(parse_grade))

    async with engine.begin() as conn:
        for _, row in pitcher_df.iterrows():
            await conn.execute(text('''
                INSERT INTO fangraphs_prospect_grades
                (fg_player_id, player_name, position, organization,
                 top_100_rank, org_rank, age, fv,
                 tj_date, fb_type,
                 fb_present, fb_future, sl_present, sl_future,
                 cb_present, cb_future, ch_present, ch_future,
                 cmd_present, cmd_future,
                 sits_velo, tops_velo,
                 report_year)
                VALUES
                (:fg_player_id, :player_name, :position, :organization,
                 :top_100_rank, :org_rank, :age, :fv,
                 :tj_date, :fb_type,
                 :fb_present, :fb_future, :sl_present, :sl_future,
                 :cb_present, :cb_future, :ch_present, :ch_future,
                 :cmd_present, :cmd_future,
                 :sits_velo, :tops_velo,
                 :report_year)
                ON CONFLICT (fg_player_id, report_year) DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    position = EXCLUDED.position,
                    organization = EXCLUDED.organization,
                    top_100_rank = EXCLUDED.top_100_rank,
                    org_rank = EXCLUDED.org_rank,
                    age = EXCLUDED.age,
                    fv = EXCLUDED.fv,
                    tj_date = EXCLUDED.tj_date,
                    fb_type = EXCLUDED.fb_type,
                    fb_present = EXCLUDED.fb_present,
                    fb_future = EXCLUDED.fb_future,
                    sl_present = EXCLUDED.sl_present,
                    sl_future = EXCLUDED.sl_future,
                    cb_present = EXCLUDED.cb_present,
                    cb_future = EXCLUDED.cb_future,
                    ch_present = EXCLUDED.ch_present,
                    ch_future = EXCLUDED.ch_future,
                    cmd_present = EXCLUDED.cmd_present,
                    cmd_future = EXCLUDED.cmd_future,
                    sits_velo = EXCLUDED.sits_velo,
                    tops_velo = EXCLUDED.tops_velo,
                    updated_at = NOW()
            '''), {
                'fg_player_id': str(row['PlayerId']),
                'player_name': str(row['Name']),
                'position': str(row['Pos']) if pd.notna(row['Pos']) else None,
                'organization': str(row['Org']) if pd.notna(row['Org']) else None,
                'top_100_rank': int(row['Top 100']) if pd.notna(row['Top 100']) else None,
                'org_rank': int(row['Org Rk']) if pd.notna(row['Org Rk']) else None,
                'age': float(row['Age']) if pd.notna(row['Age']) else None,
                'fv': parse_fv(row['FV']),
                'tj_date': str(row['TJ Date']) if pd.notna(row['TJ Date']) else None,
                'fb_type': str(row['FB Type']) if pd.notna(row['FB Type']) else None,
                'fb_present': int(row['fb_present']) if pd.notna(row['fb_present']) else None,
                'fb_future': int(row['fb_future']) if pd.notna(row['fb_future']) else None,
                'sl_present': int(row['sl_present']) if pd.notna(row['sl_present']) else None,
                'sl_future': int(row['sl_future']) if pd.notna(row['sl_future']) else None,
                'cb_present': int(row['cb_present']) if pd.notna(row['cb_present']) else None,
                'cb_future': int(row['cb_future']) if pd.notna(row['cb_future']) else None,
                'ch_present': int(row['ch_present']) if pd.notna(row['ch_present']) else None,
                'ch_future': int(row['ch_future']) if pd.notna(row['ch_future']) else None,
                'cmd_present': int(row['cmd_present']) if pd.notna(row['cmd_present']) else None,
                'cmd_future': int(row['cmd_future']) if pd.notna(row['cmd_future']) else None,
                'sits_velo': str(row['Sits']) if pd.notna(row['Sits']) else None,
                'tops_velo': str(row['Tops']) if pd.notna(row['Tops']) else None,
                'report_year': report_year,
            })

    print(f'Imported {len(pitcher_df)} pitchers')


async def import_physical(phys_path):
    """Import physical attributes."""
    print(f'\nImporting physical attributes from {phys_path}')

    df = pd.read_csv(phys_path)
    print(f'Loaded {len(df)} prospects')

    async with engine.begin() as conn:
        for _, row in df.iterrows():
            await conn.execute(text('''
                UPDATE fangraphs_prospect_grades
                SET
                    frame = :frame,
                    athleticism = :athleticism,
                    levers = :levers,
                    arm = :arm,
                    performance = :performance,
                    delivery = :delivery,
                    updated_at = NOW()
                WHERE fg_player_id = :fg_player_id
            '''), {
                'fg_player_id': str(row['PlayerId']),
                'frame': int(row['Frame']) if pd.notna(row['Frame']) else None,
                'athleticism': int(row['Athl']) if pd.notna(row['Athl']) else None,
                'levers': str(row['Levers']) if pd.notna(row['Levers']) else None,
                'arm': int(row['Arm']) if pd.notna(row['Arm']) else None,
                'performance': int(row['Perf']) if pd.notna(row['Perf']) else None,
                'delivery': int(row['Delivery']) if pd.notna(row['Delivery']) else None,
            })

    print(f'Updated physical attributes for {len(df)} prospects')


async def print_summary():
    """Print summary statistics."""
    async with engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN hit_future IS NOT NULL THEN 1 END) as hitters,
                   COUNT(CASE WHEN fb_future IS NOT NULL THEN 1 END) as pitchers,
                   AVG(fv) as avg_fv,
                   MIN(top_100_rank) as best_rank,
                   MAX(top_100_rank) as worst_rank
            FROM fangraphs_prospect_grades
        '''))
        row = result.fetchone()

        print('\n' + '=' * 80)
        print('IMPORT SUMMARY')
        print('=' * 80)
        print(f'Total prospects: {row[0]}')
        print(f'Hitters: {row[1]}')
        print(f'Pitchers: {row[2]}')
        print(f'Average FV: {row[3]:.1f}')
        print(f'Rank range: {row[4]} - {row[5]}')

        # Top 10 prospects
        result = await conn.execute(text('''
            SELECT player_name, position, organization, top_100_rank, fv
            FROM fangraphs_prospect_grades
            ORDER BY top_100_rank
            LIMIT 10
        '''))

        print('\nTop 10 Prospects:')
        for row in result:
            print(f'  {row[3]:3d}. {row[0]:25s} {row[1]:3s} {row[2]:4s} FV:{row[4]}')

        print('=' * 80)


async def import_year(year):
    """Import FanGraphs data for a specific year."""
    print(f'\n{"=" * 80}')
    print(f'IMPORTING {year} FANGRAPHS DATA')
    print(f'{"=" * 80}')

    hitters_path = rf'C:\Users\lilra\Downloads\fangraphs-the-board-hitters-{year}.csv'
    pitchers_path = rf'C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-{year}.csv'
    phys_path = rf'C:\Users\lilra\Downloads\fangraphs-the-board-all-{year}-phys.csv'

    # Check if files exist
    import os
    if not os.path.exists(hitters_path):
        print(f'WARNING: {hitters_path} not found, skipping hitters')
    else:
        await import_hitters(hitters_path, year)

    if not os.path.exists(pitchers_path):
        print(f'WARNING: {pitchers_path} not found, skipping pitchers')
    else:
        await import_pitchers(pitchers_path, year)

    if not os.path.exists(phys_path):
        print(f'WARNING: {phys_path} not found, skipping physical')
    else:
        await import_physical(phys_path)


async def main():
    print('=' * 80)
    print('FANGRAPHS PROSPECT GRADES IMPORT (2022-2025)')
    print('=' * 80)

    # Create table
    await create_table()

    # Import all years
    for year in [2022, 2023, 2024, 2025]:
        await import_year(year)

    # Print summary
    await print_summary()


if __name__ == '__main__':
    asyncio.run(main())
