"""
Calculate league adjustment factors for MiLB levels.

League adjustments normalize stats across different competitive environments:
- AAA typically has higher offensive environment than AA
- Each level has different average performance levels
- These factors allow translating stats between levels for ML modeling
"""

import asyncio
import pandas as pd
from sqlalchemy import text
from app.db.database import engine
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def load_game_logs() -> pd.DataFrame:
    """Load all MiLB game logs."""
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                mlb_player_id,
                season,
                level,
                pa,
                ab,
                h,
                doubles,
                triples,
                hr,
                bb,
                so,
                sb,
                cs,
                hbp,
                sf
            FROM milb_game_logs
            WHERE data_source = '\''mlb_stats_api_gamelog'\''
            AND pa > 0
            ORDER BY season, level, mlb_player_id
        """))

        rows = result.fetchall()

    if not rows:
        logger.warning("No game logs found")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=[
        'mlb_player_id', 'season', 'level',
        'pa', 'ab', 'h', 'doubles', 'triples', 'hr', 'bb', 'so', 'sb', 'cs', 'hbp', 'sf'
    ])

    # Convert numeric columns
    numeric_cols = ['pa', 'ab', 'h', 'doubles', 'triples', 'hr', 'bb', 'so', 'sb', 'cs', 'hbp', 'sf']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calculate derived stats
    df['singles'] = df['h'] - df['doubles'] - df['triples'] - df['hr']
    df['tb'] = df['singles'] + (df['doubles'] * 2) + (df['triples'] * 3) + (df['hr'] * 4)
    df['obp_numerator'] = df['h'] + df['bb'] + df['hbp']
    df['obp_denominator'] = df['ab'] + df['bb'] + df['hbp'] + df['sf']

    logger.info(f"Loaded {len(df):,} game logs")
    logger.info(f"Unique players: {df['mlb_player_id'].nunique()}")
    logger.info(f"Seasons: {sorted(df['season'].unique())}")
    logger.info(f"Levels: {sorted(df['level'].unique())}")

    return df


def calculate_league_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate league adjustment factors for each level/season.

    League factors normalize stats across different competitive environments.
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
        lg_ops = lg_obp + lg_slg

        # Calculate ISO (Isolated Power)
        lg_iso = lg_slg - lg_avg

        league_factors.append({
            'season': int(season),
            'level': level,
            'total_pa': int(total_pa),
            'lg_avg': round(lg_avg, 3),
            'lg_obp': round(lg_obp, 3),
            'lg_slg': round(lg_slg, 3),
            'lg_ops': round(lg_ops, 3),
            'lg_iso': round(lg_iso, 3),
            'lg_hr_rate': round(lg_hr_rate, 2),
            'lg_bb_rate': round(lg_bb_rate, 2),
            'lg_so_rate': round(lg_so_rate, 2)
        })

    lf_df = pd.DataFrame(league_factors)
    logger.info(f"Calculated league factors for {len(lf_df)} season-level combinations")

    return lf_df


async def save_league_factors(df: pd.DataFrame):
    """Save league factors to database."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS milb_league_factors (
                id SERIAL PRIMARY KEY,
                season INTEGER NOT NULL,
                level VARCHAR(20) NOT NULL,
                total_pa INTEGER,
                lg_avg FLOAT,
                lg_obp FLOAT,
                lg_slg FLOAT,
                lg_ops FLOAT,
                lg_iso FLOAT,
                lg_hr_rate FLOAT,
                lg_bb_rate FLOAT,
                lg_so_rate FLOAT,
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
                        lg_avg = :lg_avg, lg_obp = :lg_obp, lg_slg = :lg_slg,
                        lg_ops = :lg_ops, lg_iso = :lg_iso,
                        lg_hr_rate = :lg_hr_rate, lg_bb_rate = :lg_bb_rate, lg_so_rate = :lg_so_rate,
                        updated_at = NOW()
                    WHERE id = :id
                """), {
                    'id': existing[0],
                    'total_pa': int(row['total_pa']),
                    'lg_avg': float(row['lg_avg']),
                    'lg_obp': float(row['lg_obp']),
                    'lg_slg': float(row['lg_slg']),
                    'lg_ops': float(row['lg_ops']),
                    'lg_iso': float(row['lg_iso']),
                    'lg_hr_rate': float(row['lg_hr_rate']),
                    'lg_bb_rate': float(row['lg_bb_rate']),
                    'lg_so_rate': float(row['lg_so_rate'])
                })
                updated += 1
            else:
                await conn.execute(text("""
                    INSERT INTO milb_league_factors
                    (season, level, total_pa, lg_avg, lg_obp, lg_slg, lg_ops, lg_iso,
                     lg_hr_rate, lg_bb_rate, lg_so_rate)
                    VALUES
                    (:season, :level, :total_pa, :lg_avg, :lg_obp, :lg_slg, :lg_ops, :lg_iso,
                     :lg_hr_rate, :lg_bb_rate, :lg_so_rate)
                """), {
                    'season': int(row['season']),
                    'level': row['level'],
                    'total_pa': int(row['total_pa']),
                    'lg_avg': float(row['lg_avg']),
                    'lg_obp': float(row['lg_obp']),
                    'lg_slg': float(row['lg_slg']),
                    'lg_ops': float(row['lg_ops']),
                    'lg_iso': float(row['lg_iso']),
                    'lg_hr_rate': float(row['lg_hr_rate']),
                    'lg_bb_rate': float(row['lg_bb_rate']),
                    'lg_so_rate': float(row['lg_so_rate'])
                })
                inserted += 1

    logger.info(f"League factors saved: {inserted} inserted, {updated} updated")


async def show_league_factors():
    """Display league factors."""
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT season, level, total_pa, lg_avg, lg_obp, lg_slg, lg_ops, lg_iso, lg_hr_rate, lg_bb_rate, lg_so_rate
            FROM milb_league_factors
            ORDER BY season DESC,
                CASE level
                    WHEN '\''AAA'\'' THEN 1
                    WHEN '\''AA'\'' THEN 2
                    WHEN '\''A+'\'1 THEN 3
                    WHEN '\''A'\'' THEN 4
                    WHEN '\''Rookie+'\'1 THEN 5
                    WHEN '\''Rookie'\'' THEN 6
                    ELSE 7
                END
        """))
        league_factors = result.fetchall()

    print("\n" + "="*120)
    print("LEAGUE AVERAGE STATS BY LEVEL AND SEASON")
    print("="*120)
    print(f"{'Season':<8} {'Level':<10} {'Total PA':<12} {'AVG':<8} {'OBP':<8} {'SLG':<8} {'OPS':<8} {'ISO':<8} {'HR%':<8} {'BB%':<8} {'K%':<8}")
    print("-"*120)

    for row in league_factors:
        print(f"{row[0]:<8} {row[1]:<10} {row[2]:<12,} {row[3]:<8.3f} {row[4]:<8.3f} {row[5]:<8.3f} {row[6]:<8.3f} {row[7]:<8.3f} {row[8]:<8.2f} {row[9]:<8.2f} {row[10]:<8.2f}")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("League Factor Calculation")
    logger.info("="*80)

    # Load game logs
    df = await load_game_logs()

    if len(df) == 0:
        logger.warning("No game logs found")
        return

    # Calculate league factors
    league_factors_df = calculate_league_factors(df)

    # Save to database
    await save_league_factors(league_factors_df)

    # Show results
    await show_league_factors()

    logger.info("\n" + "="*80)
    logger.info("Calculation Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
