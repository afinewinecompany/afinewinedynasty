"""
Calculate league adjustment factors for MiLB levels INCLUDING AGE STATISTICS.

League adjustments normalize stats across different competitive environments:
- AAA typically has higher offensive environment than AA
- Each level has different average performance levels and AGE
- These factors allow translating stats between levels for ML modeling
- AGE is critical for prospect evaluation (young player at AAA >>> old player at AAA)
"""

import asyncio
import pandas as pd
from sqlalchemy import text
from app.db.database import engine
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def load_game_logs_with_age() -> pd.DataFrame:
    """Load all MiLB game logs with birth dates for age calculation."""
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                g.mlb_player_id,
                g.season,
                g.level,
                g.game_date,
                g.plate_appearances as pa,
                g.at_bats as ab,
                g.hits as h,
                g.doubles,
                g.triples,
                g.home_runs as hr,
                g.walks as bb,
                g.strikeouts as so,
                g.stolen_bases as sb,
                g.caught_stealing as cs,
                g.hit_by_pitch as hbp,
                g.sacrifice_flies as sf,
                p.birth_date,
                p.position as primary_position
            FROM milb_game_logs g
            LEFT JOIN prospects p ON g.mlb_player_id::text = p.mlb_player_id
            WHERE g.data_source = 'mlb_stats_api_gamelog'
            AND g.plate_appearances > 0
            ORDER BY g.season, g.level, g.mlb_player_id
        """))

        rows = result.fetchall()

    if not rows:
        logger.warning("No game logs found")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=[
        'mlb_player_id', 'season', 'level', 'game_date',
        'pa', 'ab', 'h', 'doubles', 'triples', 'hr', 'bb', 'so', 'sb', 'cs', 'hbp', 'sf', 'birth_date', 'primary_position'
    ])

    # Convert numeric columns
    numeric_cols = ['pa', 'ab', 'h', 'doubles', 'triples', 'hr', 'bb', 'so', 'sb', 'cs', 'hbp', 'sf']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calculate age at game date
    df['game_date'] = pd.to_datetime(df['game_date'])
    df['birth_date'] = pd.to_datetime(df['birth_date'])
    df['age_at_game'] = (df['game_date'] - df['birth_date']).dt.days / 365.25

    # Calculate derived stats
    df['singles'] = df['h'] - df['doubles'] - df['triples'] - df['hr']
    df['tb'] = df['singles'] + (df['doubles'] * 2) + (df['triples'] * 3) + (df['hr'] * 4)
    df['obp_numerator'] = df['h'] + df['bb'] + df['hbp']
    df['obp_denominator'] = df['ab'] + df['bb'] + df['hbp'] + df['sf']

    logger.info(f"Loaded {len(df):,} game logs")
    logger.info(f"Unique players: {df['mlb_player_id'].nunique()}")
    logger.info(f"Players with birth dates: {df['birth_date'].notna().sum():,} ({df['birth_date'].notna().sum()/len(df)*100:.1f}%)")
    logger.info(f"Seasons: {sorted(df['season'].unique())}")
    logger.info(f"Levels: {sorted(df['level'].unique())}")

    return df


def calculate_league_factors_with_age(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate league adjustment factors for each level/season INCLUDING AGE.

    League factors normalize stats across different competitive environments.
    Age is CRITICAL for prospect evaluation.
    """
    league_factors = []

    # Group by season and level
    for (season, level), level_games in df.groupby(['season', 'level']):

        total_pa = level_games['pa'].sum()
        total_ab = level_games['ab'].sum()
        total_h = level_games['h'].sum()
        total_hr = level_games['hr'].sum()
        total_bb = level_games['bb'].sum()
        total_so = level_games['so'].sum()
        total_sb = level_games['sb'].sum()
        total_cs = level_games['cs'].sum()
        total_tb = level_games['tb'].sum()
        total_obp_num = level_games['obp_numerator'].sum()
        total_obp_den = level_games['obp_denominator'].sum()

        # Calculate league average rates
        lg_avg = total_h / total_ab if total_ab > 0 else 0
        lg_obp = total_obp_num / total_obp_den if total_obp_den > 0 else 0
        lg_slg = total_tb / total_ab if total_ab > 0 else 0
        lg_hr_rate = (total_hr / total_pa * 100) if total_pa > 0 else 0
        lg_bb_rate = (total_bb / total_pa * 100) if total_pa > 0 else 0
        lg_so_rate = (total_so / total_pa * 100) if total_pa > 0 else 0
        lg_sb_rate = (total_sb / total_pa * 100) if total_pa > 0 else 0
        lg_sb_success = (total_sb / (total_sb + total_cs) * 100) if (total_sb + total_cs) > 0 else 0
        lg_ops = lg_obp + lg_slg

        # Calculate ISO (Isolated Power)
        lg_iso = lg_slg - lg_avg

        # Calculate AGE statistics (CRITICAL for ML)
        ages_with_data = level_games[level_games['age_at_game'].notna()]['age_at_game']

        if len(ages_with_data) > 0:
            lg_avg_age = ages_with_data.mean()
            lg_median_age = ages_with_data.median()
            lg_age_std = ages_with_data.std()
            lg_age_25th = ages_with_data.quantile(0.25)
            lg_age_75th = ages_with_data.quantile(0.75)
            players_with_age = level_games[level_games['age_at_game'].notna()]['mlb_player_id'].nunique()
        else:
            lg_avg_age = None
            lg_median_age = None
            lg_age_std = None
            lg_age_25th = None
            lg_age_75th = None
            players_with_age = 0

        league_factors.append({
            'season': int(season),
            'level': level,
            'total_pa': int(total_pa),
            'unique_players': int(level_games['mlb_player_id'].nunique()),
            'players_with_age': int(players_with_age),
            # Performance stats
            'lg_avg': round(lg_avg, 3),
            'lg_obp': round(lg_obp, 3),
            'lg_slg': round(lg_slg, 3),
            'lg_ops': round(lg_ops, 3),
            'lg_iso': round(lg_iso, 3),
            'lg_hr_rate': round(lg_hr_rate, 2),
            'lg_bb_rate': round(lg_bb_rate, 2),
            'lg_so_rate': round(lg_so_rate, 2),
            'lg_sb_rate': round(lg_sb_rate, 2),
            'lg_sb_success_pct': round(lg_sb_success, 1),
            # Age stats
            'lg_avg_age': round(lg_avg_age, 2) if lg_avg_age else None,
            'lg_median_age': round(lg_median_age, 2) if lg_median_age else None,
            'lg_age_std': round(lg_age_std, 2) if lg_age_std else None,
            'lg_age_25th_percentile': round(lg_age_25th, 2) if lg_age_25th else None,
            'lg_age_75th_percentile': round(lg_age_75th, 2) if lg_age_75th else None
        })

    lf_df = pd.DataFrame(league_factors)
    logger.info(f"Calculated league factors for {len(lf_df)} season-level combinations")

    return lf_df


def calculate_position_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate position-specific adjustment factors.

    Catchers typically hit worse than corner OFs at same level.
    These factors allow comparing players at different positions.

    Position groups:
    - C (Catcher) - Hardest defensive position, lowest offensive expectations
    - IF (Infield: SS, 2B, 3B, 1B)
    - OF (Outfield: LF, CF, RF)
    - DH (Designated Hitter) - Highest offensive expectations
    - P (Pitcher) - Not included (separate analysis)
    """
    position_factors = []

    # Map positions to groups
    position_map = {
        'C': 'C',
        'SS': 'IF',
        '2B': 'IF',
        '3B': 'IF',
        '1B': 'IF',
        'LF': 'OF',
        'CF': 'OF',
        'RF': 'OF',
        'OF': 'OF',
        'DH': 'DH',
        'P': 'P',
        'TWP': 'TWP'  # Two-way player
    }

    df['position_group'] = df['primary_position'].map(position_map)

    # Group by season, level, and position
    for (season, level, position_group), pos_games in df.groupby(['season', 'level', 'position_group']):

        # Skip if not enough data
        if len(pos_games) < 50:  # Minimum sample size
            continue

        # Skip pitchers (analyzed separately)
        if position_group == 'P':
            continue

        total_pa = pos_games['pa'].sum()
        total_ab = pos_games['ab'].sum()
        total_h = pos_games['h'].sum()
        total_hr = pos_games['hr'].sum()
        total_bb = pos_games['bb'].sum()
        total_so = pos_games['so'].sum()
        total_sb = pos_games['sb'].sum()
        total_cs = pos_games['cs'].sum()
        total_tb = pos_games['tb'].sum()
        total_obp_num = pos_games['obp_numerator'].sum()
        total_obp_den = pos_games['obp_denominator'].sum()

        # Calculate position average rates
        pos_avg = total_h / total_ab if total_ab > 0 else 0
        pos_obp = total_obp_num / total_obp_den if total_obp_den > 0 else 0
        pos_slg = total_tb / total_ab if total_ab > 0 else 0
        pos_hr_rate = (total_hr / total_pa * 100) if total_pa > 0 else 0
        pos_bb_rate = (total_bb / total_pa * 100) if total_pa > 0 else 0
        pos_so_rate = (total_so / total_pa * 100) if total_pa > 0 else 0
        pos_sb_rate = (total_sb / total_pa * 100) if total_pa > 0 else 0
        pos_ops = pos_obp + pos_slg
        pos_iso = pos_slg - pos_avg

        # Age statistics for position
        ages_with_data = pos_games[pos_games['age_at_game'].notna()]['age_at_game']
        pos_avg_age = ages_with_data.mean() if len(ages_with_data) > 0 else None

        position_factors.append({
            'season': int(season),
            'level': level,
            'position_group': position_group,
            'total_pa': int(total_pa),
            'unique_players': int(pos_games['mlb_player_id'].nunique()),
            'pos_avg': round(pos_avg, 3),
            'pos_obp': round(pos_obp, 3),
            'pos_slg': round(pos_slg, 3),
            'pos_ops': round(pos_ops, 3),
            'pos_iso': round(pos_iso, 3),
            'pos_hr_rate': round(pos_hr_rate, 2),
            'pos_bb_rate': round(pos_bb_rate, 2),
            'pos_so_rate': round(pos_so_rate, 2),
            'pos_sb_rate': round(pos_sb_rate, 2),
            'pos_avg_age': round(pos_avg_age, 2) if pos_avg_age else None
        })

    pf_df = pd.DataFrame(position_factors)
    logger.info(f"Calculated position factors for {len(pf_df)} season-level-position combinations")

    return pf_df


async def save_league_factors(df: pd.DataFrame):
    """Save league factors to database."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS milb_league_factors (
                id SERIAL PRIMARY KEY,
                season INTEGER NOT NULL,
                level VARCHAR(20) NOT NULL,
                total_pa INTEGER,
                unique_players INTEGER,
                players_with_age INTEGER,
                lg_avg FLOAT,
                lg_obp FLOAT,
                lg_slg FLOAT,
                lg_ops FLOAT,
                lg_iso FLOAT,
                lg_hr_rate FLOAT,
                lg_bb_rate FLOAT,
                lg_so_rate FLOAT,
                lg_sb_rate FLOAT,
                lg_sb_success_pct FLOAT,
                lg_avg_age FLOAT,
                lg_median_age FLOAT,
                lg_age_std FLOAT,
                lg_age_25th_percentile FLOAT,
                lg_age_75th_percentile FLOAT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(season, level)
            )
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_league_factors_season_level
            ON milb_league_factors(season, level)
        """))

        logger.info("League factors table created/verified")

    # Insert data
    inserted = 0
    updated = 0

    for _, row in df.iterrows():
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id FROM milb_league_factors
                    WHERE season = :season AND level = :level
                """),
                {'season': int(row['season']), 'level': row['level']}
            )

            existing = result.fetchone()

            if existing:
                await conn.execute(text("""
                    UPDATE milb_league_factors
                    SET total_pa = :total_pa,
                        unique_players = :unique_players,
                        players_with_age = :players_with_age,
                        lg_avg = :lg_avg, lg_obp = :lg_obp, lg_slg = :lg_slg,
                        lg_ops = :lg_ops, lg_iso = :lg_iso,
                        lg_hr_rate = :lg_hr_rate, lg_bb_rate = :lg_bb_rate, lg_so_rate = :lg_so_rate,
                        lg_sb_rate = :lg_sb_rate, lg_sb_success_pct = :lg_sb_success_pct,
                        lg_avg_age = :lg_avg_age, lg_median_age = :lg_median_age, lg_age_std = :lg_age_std,
                        lg_age_25th_percentile = :lg_age_25th_percentile, lg_age_75th_percentile = :lg_age_75th_percentile,
                        updated_at = NOW()
                    WHERE id = :id
                """), {
                    'id': existing[0],
                    'total_pa': int(row['total_pa']),
                    'unique_players': int(row['unique_players']),
                    'players_with_age': int(row['players_with_age']),
                    'lg_avg': float(row['lg_avg']),
                    'lg_obp': float(row['lg_obp']),
                    'lg_slg': float(row['lg_slg']),
                    'lg_ops': float(row['lg_ops']),
                    'lg_iso': float(row['lg_iso']),
                    'lg_hr_rate': float(row['lg_hr_rate']),
                    'lg_bb_rate': float(row['lg_bb_rate']),
                    'lg_so_rate': float(row['lg_so_rate']),
                    'lg_sb_rate': float(row['lg_sb_rate']),
                    'lg_sb_success_pct': float(row['lg_sb_success_pct']),
                    'lg_avg_age': float(row['lg_avg_age']) if row['lg_avg_age'] else None,
                    'lg_median_age': float(row['lg_median_age']) if row['lg_median_age'] else None,
                    'lg_age_std': float(row['lg_age_std']) if row['lg_age_std'] else None,
                    'lg_age_25th_percentile': float(row['lg_age_25th_percentile']) if row['lg_age_25th_percentile'] else None,
                    'lg_age_75th_percentile': float(row['lg_age_75th_percentile']) if row['lg_age_75th_percentile'] else None
                })
                updated += 1
            else:
                await conn.execute(text("""
                    INSERT INTO milb_league_factors
                    (season, level, total_pa, unique_players, players_with_age,
                     lg_avg, lg_obp, lg_slg, lg_ops, lg_iso,
                     lg_hr_rate, lg_bb_rate, lg_so_rate, lg_sb_rate, lg_sb_success_pct,
                     lg_avg_age, lg_median_age, lg_age_std,
                     lg_age_25th_percentile, lg_age_75th_percentile)
                    VALUES
                    (:season, :level, :total_pa, :unique_players, :players_with_age,
                     :lg_avg, :lg_obp, :lg_slg, :lg_ops, :lg_iso,
                     :lg_hr_rate, :lg_bb_rate, :lg_so_rate, :lg_sb_rate, :lg_sb_success_pct,
                     :lg_avg_age, :lg_median_age, :lg_age_std,
                     :lg_age_25th_percentile, :lg_age_75th_percentile)
                """), {
                    'season': int(row['season']),
                    'level': row['level'],
                    'total_pa': int(row['total_pa']),
                    'unique_players': int(row['unique_players']),
                    'players_with_age': int(row['players_with_age']),
                    'lg_avg': float(row['lg_avg']),
                    'lg_obp': float(row['lg_obp']),
                    'lg_slg': float(row['lg_slg']),
                    'lg_ops': float(row['lg_ops']),
                    'lg_iso': float(row['lg_iso']),
                    'lg_hr_rate': float(row['lg_hr_rate']),
                    'lg_bb_rate': float(row['lg_bb_rate']),
                    'lg_so_rate': float(row['lg_so_rate']),
                    'lg_sb_rate': float(row['lg_sb_rate']),
                    'lg_sb_success_pct': float(row['lg_sb_success_pct']),
                    'lg_avg_age': float(row['lg_avg_age']) if row['lg_avg_age'] else None,
                    'lg_median_age': float(row['lg_median_age']) if row['lg_median_age'] else None,
                    'lg_age_std': float(row['lg_age_std']) if row['lg_age_std'] else None,
                    'lg_age_25th_percentile': float(row['lg_age_25th_percentile']) if row['lg_age_25th_percentile'] else None,
                    'lg_age_75th_percentile': float(row['lg_age_75th_percentile']) if row['lg_age_75th_percentile'] else None
                })
                inserted += 1

    logger.info(f"League factors saved: {inserted} inserted, {updated} updated")


async def save_position_factors(df: pd.DataFrame):
    """Save position-specific factors to database."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS milb_position_factors (
                id SERIAL PRIMARY KEY,
                season INTEGER NOT NULL,
                level VARCHAR(20) NOT NULL,
                position_group VARCHAR(10) NOT NULL,
                total_pa INTEGER,
                unique_players INTEGER,
                pos_avg FLOAT,
                pos_obp FLOAT,
                pos_slg FLOAT,
                pos_ops FLOAT,
                pos_iso FLOAT,
                pos_hr_rate FLOAT,
                pos_bb_rate FLOAT,
                pos_so_rate FLOAT,
                pos_sb_rate FLOAT,
                pos_avg_age FLOAT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(season, level, position_group)
            )
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_position_factors_season_level_pos
            ON milb_position_factors(season, level, position_group)
        """))

        logger.info("Position factors table created/verified")

    # Insert data
    inserted = 0
    updated = 0

    for _, row in df.iterrows():
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id FROM milb_position_factors
                    WHERE season = :season AND level = :level AND position_group = :position_group
                """),
                {'season': int(row['season']), 'level': row['level'], 'position_group': row['position_group']}
            )

            existing = result.fetchone()

            if existing:
                await conn.execute(text("""
                    UPDATE milb_position_factors
                    SET total_pa = :total_pa,
                        unique_players = :unique_players,
                        pos_avg = :pos_avg, pos_obp = :pos_obp, pos_slg = :pos_slg,
                        pos_ops = :pos_ops, pos_iso = :pos_iso,
                        pos_hr_rate = :pos_hr_rate, pos_bb_rate = :pos_bb_rate, pos_so_rate = :pos_so_rate,
                        pos_sb_rate = :pos_sb_rate,
                        pos_avg_age = :pos_avg_age,
                        updated_at = NOW()
                    WHERE id = :id
                """), {
                    'id': existing[0],
                    'total_pa': int(row['total_pa']),
                    'unique_players': int(row['unique_players']),
                    'pos_avg': float(row['pos_avg']),
                    'pos_obp': float(row['pos_obp']),
                    'pos_slg': float(row['pos_slg']),
                    'pos_ops': float(row['pos_ops']),
                    'pos_iso': float(row['pos_iso']),
                    'pos_hr_rate': float(row['pos_hr_rate']),
                    'pos_bb_rate': float(row['pos_bb_rate']),
                    'pos_so_rate': float(row['pos_so_rate']),
                    'pos_sb_rate': float(row['pos_sb_rate']),
                    'pos_avg_age': float(row['pos_avg_age']) if row['pos_avg_age'] else None
                })
                updated += 1
            else:
                await conn.execute(text("""
                    INSERT INTO milb_position_factors
                    (season, level, position_group, total_pa, unique_players,
                     pos_avg, pos_obp, pos_slg, pos_ops, pos_iso,
                     pos_hr_rate, pos_bb_rate, pos_so_rate, pos_sb_rate,
                     pos_avg_age)
                    VALUES
                    (:season, :level, :position_group, :total_pa, :unique_players,
                     :pos_avg, :pos_obp, :pos_slg, :pos_ops, :pos_iso,
                     :pos_hr_rate, :pos_bb_rate, :pos_so_rate, :pos_sb_rate,
                     :pos_avg_age)
                """), {
                    'season': int(row['season']),
                    'level': row['level'],
                    'position_group': row['position_group'],
                    'total_pa': int(row['total_pa']),
                    'unique_players': int(row['unique_players']),
                    'pos_avg': float(row['pos_avg']),
                    'pos_obp': float(row['pos_obp']),
                    'pos_slg': float(row['pos_slg']),
                    'pos_ops': float(row['pos_ops']),
                    'pos_iso': float(row['pos_iso']),
                    'pos_hr_rate': float(row['pos_hr_rate']),
                    'pos_bb_rate': float(row['pos_bb_rate']),
                    'pos_so_rate': float(row['pos_so_rate']),
                    'pos_sb_rate': float(row['pos_sb_rate']),
                    'pos_avg_age': float(row['pos_avg_age']) if row['pos_avg_age'] else None
                })
                inserted += 1

    logger.info(f"Position factors saved: {inserted} inserted, {updated} updated")


async def show_league_factors():
    """Display league factors including age statistics."""
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT season, level, total_pa, unique_players, players_with_age,
                   lg_avg, lg_obp, lg_slg, lg_ops, lg_iso,
                   lg_hr_rate, lg_bb_rate, lg_so_rate, lg_sb_rate, lg_sb_success_pct,
                   lg_avg_age, lg_median_age
            FROM milb_league_factors
            ORDER BY season DESC,
                CASE level
                    WHEN 'AAA' THEN 1
                    WHEN 'AA' THEN 2
                    WHEN 'A+' THEN 3
                    WHEN 'A' THEN 4
                    WHEN 'ROK' THEN 5
                    WHEN 'ACL' THEN 6
                    WHEN 'DSL' THEN 7
                    ELSE 8
                END
        """))
        league_factors = result.fetchall()

    print("\n" + "="*160)
    print("LEAGUE AVERAGE STATS BY LEVEL AND SEASON (INCLUDING AGE & SB%)")
    print("="*160)
    print(f"{'Season':<8} {'Level':<6} {'PAs':>10} {'Players':>8} {'W/Age':>7} {'AVG':>6} {'OBP':>6} {'SLG':>6} {'OPS':>6} {'ISO':>6} {'HR%':>6} {'BB%':>6} {'K%':>6} {'SB%':>6} {'SB-Suc%':>8} {'Avg Age':>8} {'Med Age':>8}")
    print("-"*160)

    for row in league_factors:
        avg_age_str = f"{row[15]:.1f}" if row[15] else "N/A"
        med_age_str = f"{row[16]:.1f}" if row[16] else "N/A"
        print(f"{row[0]:<8} {row[1]:<6} {row[2]:>10,} {row[3]:>8,} {row[4]:>7,} {row[5]:>6.3f} {row[6]:>6.3f} {row[7]:>6.3f} {row[8]:>6.3f} {row[9]:>6.3f} {row[10]:>6.1f} {row[11]:>6.1f} {row[12]:>6.1f} {row[13]:>6.1f} {row[14]:>8.1f} {avg_age_str:>8} {med_age_str:>8}")

    print("="*160)
    print("\nKey Insights:")
    print("- Avg Age: Average age of players at this level")
    print("- Med Age: Median age (less affected by outliers)")
    print("- SB%: Stolen base attempts per 100 PAs")
    print("- SB-Suc%: Stolen base success rate (SB / (SB + CS))")
    print("- Younger players at higher levels = better prospects")
    print("- Use lg_avg_age to calculate age-adjusted metrics for ML")
    print("- Higher level leagues typically have lower SB% and higher success rates")


async def main():
    """Main entry point."""
    logger.info("=" * 80)
    logger.info("MiLB League & Position Factors Calculation (WITH AGE)")
    logger.info("=" * 80)

    # Load game logs with age
    df = await load_game_logs_with_age()

    if df.empty:
        logger.error("No data to process")
        return

    # Calculate league factors
    logger.info("Calculating league factors...")
    league_factors = calculate_league_factors_with_age(df)

    # Calculate position factors
    logger.info("Calculating position factors...")
    position_factors = calculate_position_factors(df)

    # Save to database
    logger.info("Saving league factors to database...")
    await save_league_factors(league_factors)

    logger.info("Saving position factors to database...")
    await save_position_factors(position_factors)

    # Display results
    await show_league_factors()

    logger.info("\n" + "=" * 80)
    logger.info("League & position factors calculation complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
