"""
Calculate park and league adjustment factors for MiLB levels.

Park factors measure how much a ballpark inflates or deflates offense:
- Park Factor > 100: Hitter-friendly (more runs/hits than average)
- Park Factor = 100: Neutral
- Park Factor < 100: Pitcher-friendly (fewer runs/hits than average)

League adjustments normalize stats across different competitive levels:
- AAA typically has higher offensive environment than AA
- Different leagues within same level can have different scoring environments
"""

import asyncio
import pandas as pd
from sqlalchemy import text
from app.db.database import engine
import logging
from typing import Dict, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def load_game_logs() -> pd.DataFrame:
    """Load all MiLB game logs with venue and league information."""
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                mlb_player_id,
                game_pk,
                game_date,
                season,
                level,
                home_away,
                venue_id,
                venue_name,
                opponent_team_id,
                opponent_name,
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
            WHERE data_source = 'mlb_stats_api_gamelog'
            AND pa > 0
            ORDER BY season, game_pk, mlb_player_id
        """))

        rows = result.fetchall()

    df = pd.DataFrame(rows, columns=[
        'mlb_player_id', 'game_pk', 'game_date', 'season', 'level', 'home_away',
        'venue_id', 'venue_name', 'opponent_team_id', 'opponent_name',
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
    df['slg_denominator'] = df['ab']

    logger.info(f"Loaded {len(df):,} game logs")
    logger.info(f"Unique players: {df['mlb_player_id'].nunique()}")
    logger.info(f"Unique venues: {df['venue_id'].nunique()}")
    logger.info(f"Seasons: {sorted(df['season'].unique())}")

    return df


def calculate_park_factors(df: pd.DataFrame, min_games: int = 50) -> pd.DataFrame:
    """
    Calculate park factors for each venue.

    Method:
    1. Compare offensive stats in home games vs road games at each park
    2. Park Factor = (Home Stats / Road Stats) * 100
    3. Requires minimum number of games for reliability
    """
    park_factors = []

    # Group by venue, season, level
    for (venue_id, venue_name, season, level), venue_games in df.groupby(['venue_id', 'venue_name', 'season', 'level']):

        if pd.isna(venue_id) or venue_id == 0:
            continue

        # Split into home and away games
        home_games = venue_games[venue_games['home_away'] == 'home']
        away_games = venue_games[venue_games['home_away'] == 'away']

        total_games = len(venue_games)

        if total_games < min_games:
            continue

        # Calculate aggregate stats for home games
        home_pa = home_games['pa'].sum()
        home_ab = home_games['ab'].sum()
        home_h = home_games['h'].sum()
        home_hr = home_games['hr'].sum()
        home_bb = home_games['bb'].sum()
        home_tb = home_games['tb'].sum()
        home_obp_num = home_games['obp_numerator'].sum()
        home_obp_den = home_games['obp_denominator'].sum()

        # Calculate aggregate stats for away games
        away_pa = away_games['pa'].sum()
        away_ab = away_games['ab'].sum()
        away_h = away_games['h'].sum()
        away_hr = away_games['hr'].sum()
        away_bb = away_games['bb'].sum()
        away_tb = away_games['tb'].sum()
        away_obp_num = away_games['obp_numerator'].sum()
        away_obp_den = away_games['obp_denominator'].sum()

        # Calculate rates
        home_avg = home_h / home_ab if home_ab > 0 else 0
        away_avg = away_h / away_ab if away_ab > 0 else 0

        home_obp = home_obp_num / home_obp_den if home_obp_den > 0 else 0
        away_obp = away_obp_num / away_obp_den if away_obp_den > 0 else 0

        home_slg = home_tb / home_ab if home_ab > 0 else 0
        away_slg = away_tb / away_ab if away_ab > 0 else 0

        home_hr_rate = (home_hr / home_pa * 100) if home_pa > 0 else 0
        away_hr_rate = (away_hr / away_pa * 100) if away_pa > 0 else 0

        # Calculate park factors (home vs away, normalized to 100)
        pf_avg = (home_avg / away_avg * 100) if away_avg > 0 else 100
        pf_obp = (home_obp / away_obp * 100) if away_obp > 0 else 100
        pf_slg = (home_slg / away_slg * 100) if away_slg > 0 else 100
        pf_hr = (home_hr_rate / away_hr_rate * 100) if away_hr_rate > 0 else 100

        # Overall park factor (weighted average)
        pf_overall = (pf_avg * 0.25 + pf_obp * 0.35 + pf_slg * 0.40)

        park_factors.append({
            'venue_id': int(venue_id),
            'venue_name': venue_name,
            'season': int(season),
            'level': level,
            'games': total_games,
            'home_games': len(home_games),
            'away_games': len(away_games),
            'pf_overall': round(pf_overall, 1),
            'pf_avg': round(pf_avg, 1),
            'pf_obp': round(pf_obp, 1),
            'pf_slg': round(pf_slg, 1),
            'pf_hr': round(pf_hr, 1),
            'home_avg': round(home_avg, 3),
            'away_avg': round(away_avg, 3),
            'home_hr_rate': round(home_hr_rate, 2),
            'away_hr_rate': round(away_hr_rate, 2)
        })

    pf_df = pd.DataFrame(park_factors)
    logger.info(f"Calculated park factors for {len(pf_df)} venue-season-level combinations")

    return pf_df


def calculate_league_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate league adjustment factors for each level/season.

    League factors normalize stats across different competitive environments:
    - Compare average stats at each level
    - Used to translate stats between levels (e.g., AA to AAA)
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

        league_factors.append({
            'season': int(season),
            'level': level,
            'total_pa': int(total_pa),
            'lg_avg': round(lg_avg, 3),
            'lg_obp': round(lg_obp, 3),
            'lg_slg': round(lg_slg, 3),
            'lg_hr_rate': round(lg_hr_rate, 2),
            'lg_bb_rate': round(lg_bb_rate, 2),
            'lg_so_rate': round(lg_so_rate, 2),
            'lg_ops': round(lg_obp + lg_slg, 3)
        })

    lf_df = pd.DataFrame(league_factors)
    logger.info(f"Calculated league factors for {len(lf_df)} season-level combinations")

    return lf_df


async def save_park_factors(df: pd.DataFrame):
    """Save park factors to database."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS milb_park_factors (
                id SERIAL PRIMARY KEY,
                venue_id INTEGER NOT NULL,
                venue_name VARCHAR(255),
                season INTEGER NOT NULL,
                level VARCHAR(20) NOT NULL,
                games INTEGER,
                home_games INTEGER,
                away_games INTEGER,
                pf_overall FLOAT,
                pf_avg FLOAT,
                pf_obp FLOAT,
                pf_slg FLOAT,
                pf_hr FLOAT,
                home_avg FLOAT,
                away_avg FLOAT,
                home_hr_rate FLOAT,
                away_hr_rate FLOAT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(venue_id, season, level)
            )
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_park_factors_venue
            ON milb_park_factors(venue_id)
        """))

        logger.info("Park factors table created/verified")

    # Insert data
    inserted = 0
    updated = 0

    for _, row in df.iterrows():
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id FROM milb_park_factors
                    WHERE venue_id = :venue_id AND season = :season AND level = :level
                """),
                {'venue_id': int(row['venue_id']), 'season': int(row['season']), 'level': row['level']}
            )

            existing = result.fetchone()

            if existing:
                await conn.execute(text("""
                    UPDATE milb_park_factors
                    SET venue_name = :venue_name, games = :games,
                        home_games = :home_games, away_games = :away_games,
                        pf_overall = :pf_overall, pf_avg = :pf_avg, pf_obp = :pf_obp,
                        pf_slg = :pf_slg, pf_hr = :pf_hr,
                        home_avg = :home_avg, away_avg = :away_avg,
                        home_hr_rate = :home_hr_rate, away_hr_rate = :away_hr_rate,
                        updated_at = NOW()
                    WHERE id = :id
                """), {
                    'id': existing[0],
                    'venue_name': row['venue_name'],
                    'games': int(row['games']),
                    'home_games': int(row['home_games']),
                    'away_games': int(row['away_games']),
                    'pf_overall': float(row['pf_overall']),
                    'pf_avg': float(row['pf_avg']),
                    'pf_obp': float(row['pf_obp']),
                    'pf_slg': float(row['pf_slg']),
                    'pf_hr': float(row['pf_hr']),
                    'home_avg': float(row['home_avg']),
                    'away_avg': float(row['away_avg']),
                    'home_hr_rate': float(row['home_hr_rate']),
                    'away_hr_rate': float(row['away_hr_rate'])
                })
                updated += 1
            else:
                await conn.execute(text("""
                    INSERT INTO milb_park_factors
                    (venue_id, venue_name, season, level, games, home_games, away_games,
                     pf_overall, pf_avg, pf_obp, pf_slg, pf_hr,
                     home_avg, away_avg, home_hr_rate, away_hr_rate)
                    VALUES
                    (:venue_id, :venue_name, :season, :level, :games, :home_games, :away_games,
                     :pf_overall, :pf_avg, :pf_obp, :pf_slg, :pf_hr,
                     :home_avg, :away_avg, :home_hr_rate, :away_hr_rate)
                """), {
                    'venue_id': int(row['venue_id']),
                    'venue_name': row['venue_name'],
                    'season': int(row['season']),
                    'level': row['level'],
                    'games': int(row['games']),
                    'home_games': int(row['home_games']),
                    'away_games': int(row['away_games']),
                    'pf_overall': float(row['pf_overall']),
                    'pf_avg': float(row['pf_avg']),
                    'pf_obp': float(row['pf_obp']),
                    'pf_slg': float(row['pf_slg']),
                    'pf_hr': float(row['pf_hr']),
                    'home_avg': float(row['home_avg']),
                    'away_avg': float(row['away_avg']),
                    'home_hr_rate': float(row['home_hr_rate']),
                    'away_hr_rate': float(row['away_hr_rate'])
                })
                inserted += 1

        if (inserted + updated) % 50 == 0:
            logger.info(f"Progress: {inserted} inserted, {updated} updated")

    logger.info(f"Park factors saved: {inserted} inserted, {updated} updated")


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
                        lg_avg = :lg_avg, lg_obp = :lg_obp, lg_slg = :lg_slg, lg_ops = :lg_ops,
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
                    'lg_hr_rate': float(row['lg_hr_rate']),
                    'lg_bb_rate': float(row['lg_bb_rate']),
                    'lg_so_rate': float(row['lg_so_rate'])
                })
                updated += 1
            else:
                await conn.execute(text("""
                    INSERT INTO milb_league_factors
                    (season, level, total_pa, lg_avg, lg_obp, lg_slg, lg_ops,
                     lg_hr_rate, lg_bb_rate, lg_so_rate)
                    VALUES
                    (:season, :level, :total_pa, :lg_avg, :lg_obp, :lg_slg, :lg_ops,
                     :lg_hr_rate, :lg_bb_rate, :lg_so_rate)
                """), {
                    'season': int(row['season']),
                    'level': row['level'],
                    'total_pa': int(row['total_pa']),
                    'lg_avg': float(row['lg_avg']),
                    'lg_obp': float(row['lg_obp']),
                    'lg_slg': float(row['lg_slg']),
                    'lg_ops': float(row['lg_ops']),
                    'lg_hr_rate': float(row['lg_hr_rate']),
                    'lg_bb_rate': float(row['lg_bb_rate']),
                    'lg_so_rate': float(row['lg_so_rate'])
                })
                inserted += 1

    logger.info(f"League factors saved: {inserted} inserted, {updated} updated")


async def show_sample_factors():
    """Display sample park and league factors."""

    # Show most extreme park factors
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT venue_name, season, level, games, pf_overall, pf_hr, home_avg, away_avg
            FROM milb_park_factors
            WHERE games >= 100
            ORDER BY pf_overall DESC
            LIMIT 10
        """))
        extreme_parks = result.fetchall()

    print("\n" + "="*100)
    print("MOST HITTER-FRIENDLY PARKS (min 100 games)")
    print("="*100)
    print(f"{'Venue':<35} {'Season':<8} {'Level':<8} {'Games':<8} {'PF':<8} {'HR PF':<8} {'Home BA':<10} {'Away BA':<10}")
    print("-"*100)
    for row in extreme_parks:
        print(f"{row[0][:34]:<35} {row[1]:<8} {row[2]:<8} {row[3]:<8} {row[4]:<8.1f} {row[5]:<8.1f} {row[6]:<10.3f} {row[7]:<10.3f}")

    # Show league factors
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT season, level, total_pa, lg_avg, lg_obp, lg_slg, lg_ops, lg_hr_rate
            FROM milb_league_factors
            ORDER BY season DESC,
                CASE level
                    WHEN 'AAA' THEN 1
                    WHEN 'AA' THEN 2
                    WHEN 'A+' THEN 3
                    WHEN 'A' THEN 4
                    ELSE 5
                END
        """))
        league_factors = result.fetchall()

    print("\n" + "="*100)
    print("LEAGUE AVERAGE STATS BY LEVEL")
    print("="*100)
    print(f"{'Season':<8} {'Level':<8} {'Total PA':<12} {'AVG':<8} {'OBP':<8} {'SLG':<8} {'OPS':<8} {'HR%':<8}")
    print("-"*100)
    for row in league_factors:
        print(f"{row[0]:<8} {row[1]:<8} {row[2]:<12,} {row[3]:<8.3f} {row[4]:<8.3f} {row[5]:<8.3f} {row[6]:<8.3f} {row[7]:<8.2f}")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("Park and League Factor Calculation")
    logger.info("="*80)

    # Load game logs
    df = await load_game_logs()

    if len(df) == 0:
        logger.warning("No game logs found")
        return

    # Calculate park factors
    park_factors_df = calculate_park_factors(df, min_games=50)
    await save_park_factors(park_factors_df)

    # Calculate league factors
    league_factors_df = calculate_league_factors(df)
    await save_league_factors(league_factors_df)

    # Show samples
    await show_sample_factors()

    logger.info("\n" + "="*80)
    logger.info("Calculation Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
