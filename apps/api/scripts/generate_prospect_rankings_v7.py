"""
Generate V7 Prospect Rankings: Integrated FanGraphs Expert Grades

V7 Formula:
- 50% FanGraphs Expert Grades (scouting-driven)
- 40% V4 Performance-Based Rankings (MiLB stats)
- 10% V5 ML Projection Rankings (ensemble predictions)

This makes expert grades "a large portion" of the ranking as requested.
"""

import pandas as pd
import numpy as np
import asyncio
from sqlalchemy import text
import sys
import os
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine


def load_v6_rankings():
    """Load V6 rankings which contain both V4 and V5 scores."""
    df = pd.read_csv('prospect_rankings_v6_blended.csv')
    # Keep only what we need
    df = df[['mlb_player_id', 'full_name', 'v4_score', 'v5_score']].copy()
    df = df.rename(columns={'full_name': 'name'})
    return df


async def load_fangraphs_grades():
    """
    Load latest FanGraphs grades for each prospect.
    Filters out players with 130+ MLB at-bats.
    """
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            WITH latest_grades AS (
                SELECT
                    fg.fg_player_id,
                    fg.player_name,
                    fg.report_year,
                    fg.fv,
                    fg.hit_future,
                    fg.game_pwr_future,
                    fg.raw_pwr_future,
                    fg.spd_future,
                    fg.fld_future,
                    fg.arm,
                    fg.pitch_sel,
                    fg.bat_ctrl,
                    fg.frame,
                    fg.athleticism,
                    fg.performance,
                    fg.hard_hit_pct,
                    fg.top_100_rank,
                    fg.age,
                    ROW_NUMBER() OVER (PARTITION BY fg.fg_player_id ORDER BY fg.report_year DESC) as rn
                FROM fangraphs_prospect_grades fg
            ),
            mlb_ab_totals AS (
                SELECT
                    mlb_player_id,
                    SUM(at_bats) as total_ab
                FROM mlb_game_logs
                GROUP BY mlb_player_id
                HAVING SUM(at_bats) >= 130
            )
            SELECT
                lg.fg_player_id,
                lg.player_name,
                lg.report_year,
                lg.fv,
                lg.hit_future,
                lg.game_pwr_future,
                lg.raw_pwr_future,
                lg.spd_future,
                lg.fld_future,
                lg.arm,
                lg.pitch_sel,
                lg.bat_ctrl,
                lg.frame,
                lg.athleticism,
                lg.performance,
                lg.hard_hit_pct,
                lg.top_100_rank,
                lg.age,
                p.mlb_player_id
            FROM latest_grades lg
            INNER JOIN prospects p ON p.fg_player_id = lg.fg_player_id
            LEFT JOIN mlb_ab_totals ab ON ab.mlb_player_id::varchar = p.mlb_player_id
            WHERE lg.rn = 1
              AND p.mlb_player_id IS NOT NULL
              AND ab.mlb_player_id IS NULL  -- Exclude players with 130+ MLB AB
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df


def calculate_fangraphs_score(fg_df):
    """
    Calculate FanGraphs-based score from expert grades.

    Based on ML findings:
    - Age: 21.4% importance
    - Performance grade: 13.4% importance
    - FV: 8.4% importance
    - Power grades: ~12% combined
    - Speed: 7.5%
    - Top 100 rank: 7.9%

    We'll create a composite score emphasizing the most predictive grades.
    """

    # Start with FV as base (normalized to 0-100 scale)
    # FV range is typically 40-80, with 50 = MLB average
    fv_score = ((fg_df['fv'].fillna(40) - 40) / 40) * 100

    # Tool grades contribution (40-80 scale)
    def normalize_tool(series):
        return ((series.fillna(40) - 40) / 40) * 100

    hit_score = normalize_tool(fg_df['hit_future'])
    power_score = normalize_tool(fg_df['game_pwr_future']) * 0.6 + normalize_tool(fg_df['raw_pwr_future']) * 0.4
    speed_score = normalize_tool(fg_df['spd_future'])
    field_score = normalize_tool(fg_df['fld_future'])

    # Physical/intangibles (0-3 scale typically)
    perf_score = (fg_df['performance'].fillna(0) / 3) * 100
    frame_score = (fg_df['frame'].fillna(0) / 3) * 100
    athleticism_score = (fg_df['athleticism'].fillna(0) / 3) * 100

    # Top 100 bonus (inverse rank, 0-100)
    top100_score = (101 - fg_df['top_100_rank'].fillna(101))

    # Age adjustment (younger = better)
    # Typical prospect age: 18-24
    # Peak value at age 19-20
    age_score = 100 - ((fg_df['age'].fillna(22) - 19).abs() * 10).clip(0, 100)

    # Weighted composite (FV-focused to fix tool grade override issue)
    # FV is the industry consensus grade - should be primary driver
    composite_score = (
        fv_score * 0.50 +           # Overall grade (PRIMARY - increased from 20%)
        power_score * 0.12 +         # Power tools (most correlated with OPS)
        hit_score * 0.10 +           # Hit tool
        speed_score * 0.08 +         # Speed
        perf_score * 0.08 +          # Performance grade
        age_score * 0.05 +           # Age (reduced from 15% to prevent young age bias)
        top100_score * 0.05 +        # Industry consensus
        field_score * 0.02 +         # Defense
        athleticism_score * 0.00     # Athleticism (removed - often missing/negative)
    )

    return composite_score


async def get_mlb_graduates():
    """Get players with 130+ MLB at-bats to exclude."""
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT mlb_player_id, SUM(at_bats) as total_ab
            FROM mlb_game_logs
            GROUP BY mlb_player_id
            HAVING SUM(at_bats) >= 130
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return set(df['mlb_player_id'].astype(str))


async def generate_v7_rankings():
    """Generate V7 rankings: 50% FG grades + 40% V4 + 10% V5."""

    print('=' * 80)
    print('PROSPECT RANKINGS V7: FANGRAPHS INTEGRATED')
    print('=' * 80)
    print('\nFormula: 50% FanGraphs Grades + 40% V4 Performance + 10% V5 ML')
    print('Baseline: Prospects without FG grades get FV~35-40 equivalent')
    print('\n' + '=' * 80)

    # Load all components
    print('\nLoading V6 rankings (contains V4 and V5)...')
    v6_df = load_v6_rankings()
    print(f'  Loaded {len(v6_df)} prospects from V6')

    print('Loading FanGraphs grades...')
    fg_df = await load_fangraphs_grades()
    print(f'  Loaded {len(fg_df)} prospects with FanGraphs grades')

    print('Identifying MLB graduates (130+ AB)...')
    mlb_graduates = await get_mlb_graduates()
    print(f'  Found {len(mlb_graduates)} players to exclude')

    # Calculate FanGraphs scores
    print('\nCalculating FanGraphs composite scores...')
    fg_df['fg_score'] = calculate_fangraphs_score(fg_df)
    fg_df['fg_score_normalized'] = (fg_df['fg_score'] / fg_df['fg_score'].max()) * 100

    # Merge all data
    print('Merging rankings...')

    # Start with V6 as base (all prospects with performance data)
    # Filter out MLB graduates (130+ AB)
    v6_df['mlb_player_id'] = v6_df['mlb_player_id'].astype(str)
    df = v6_df[~v6_df['mlb_player_id'].isin(mlb_graduates)].copy()

    excluded_count = len(v6_df) - len(df)
    print(f'  Excluded {excluded_count} MLB graduates from V6')
    print(f'  Working with {len(df)} true prospects')

    # Merge FanGraphs grades (where available)
    fg_df['mlb_player_id'] = fg_df['mlb_player_id'].astype(str)
    fg_merge = fg_df[['mlb_player_id', 'player_name', 'fv', 'report_year', 'fg_score', 'fg_score_normalized']].copy()

    df = df.merge(
        fg_merge,
        on='mlb_player_id',
        how='left',
        suffixes=('', '_fg')
    )

    # For prospects without FanGraphs grades, assign baseline score
    # Baseline = FV 35-40 equivalent (below-average prospect, not yet shown enough quality)
    # This is approximately 20-25% of max FG score
    baseline_fg_score = 25.0  # Conservative baseline for ungraded prospects

    df['fg_score_normalized'] = df['fg_score_normalized'].fillna(baseline_fg_score)
    df['has_fg_grade'] = df['fv'].notna()

    # Use V6 name when FanGraphs player_name is missing
    df['player_name'] = df['player_name'].fillna(df['name'])

    print(f'  {df["has_fg_grade"].sum()} prospects with FanGraphs grades')
    print(f'  {(~df["has_fg_grade"]).sum()} prospects assigned baseline grade (FV~35-40 equivalent)')

    # Normalize V4 and V5 to 0-100 scale
    df['v4_normalized'] = (df['v4_score'] / df['v4_score'].max()) * 100 if len(df[df['v4_score'].notna()]) > 0 else 0
    df['v5_normalized'] = (df['v5_score'] / df['v5_score'].max()) * 100 if len(df[df['v5_score'].notna()]) > 0 else 0

    # Calculate V7 score
    # If missing V4 or V5, redistribute weight to FG grades
    df['has_v4'] = df['v4_score'].notna()
    df['has_v5'] = df['v5_score'].notna()

    def calc_v7_score(row):
        fg_weight = 0.50
        v4_weight = 0.40 if row['has_v4'] else 0
        v5_weight = 0.10 if row['has_v5'] else 0

        # Redistribute missing weights to FG
        if not row['has_v4']:
            fg_weight += 0.40
        if not row['has_v5']:
            fg_weight += 0.10

        score = (
            row['fg_score_normalized'] * fg_weight +
            row['v4_normalized'] * v4_weight +
            row['v5_normalized'] * v5_weight
        )
        return score

    df['v7_score'] = df.apply(calc_v7_score, axis=1)

    # Rank
    df = df.sort_values('v7_score', ascending=False)
    df['v7_rank'] = range(1, len(df) + 1)

    print(f'\nGenerated V7 rankings for {len(df)} prospects')

    # Stats
    print('\n' + '=' * 80)
    print('RANKING STATISTICS')
    print('=' * 80)
    print(f'Total prospects: {len(df)}')
    print(f'  With FG grades: {len(df)} (100%)')
    print(f'  With V4 scores: {df["has_v4"].sum()} ({df["has_v4"].sum()/len(df)*100:.1f}%)')
    print(f'  With V5 scores: {df["has_v5"].sum()} ({df["has_v5"].sum()/len(df)*100:.1f}%)')
    print(f'  With all three: {len(df[df["has_v4"] & df["has_v5"]])} ({len(df[df["has_v4"] & df["has_v5"]])/len(df)*100:.1f}%)')

    # Show top 20
    print('\n' + '=' * 80)
    print('TOP 20 PROSPECTS (V7 Rankings)')
    print('=' * 80)
    print(f'{"Rank":<6} {"Player":<25} {"FV":<4} {"Year":<6} {"FG":<7} {"V4":<7} {"V5":<7} {"V7":<7}')
    print('-' * 80)

    top_20 = df.head(20)
    for _, row in top_20.iterrows():
        rank = int(row['v7_rank'])
        name = row['player_name'][:24]
        fv = int(row['fv']) if pd.notna(row['fv']) else '-'
        year = int(row['report_year']) if pd.notna(row['report_year']) else '-'
        fg = f"{row['fg_score_normalized']:.1f}"
        v4 = f"{row['v4_normalized']:.1f}" if row['has_v4'] else '-'
        v5 = f"{row['v5_normalized']:.1f}" if row['has_v5'] else '-'
        v7 = f"{row['v7_score']:.1f}"

        print(f'{rank:<6} {name:<25} {str(fv):<4} {str(year):<6} {fg:<7} {v4:<7} {v5:<7} {v7:<7}')

    # Save to database
    print('\n' + '=' * 80)
    print('SAVING TO DATABASE')
    print('=' * 80)

    async with engine.begin() as conn:
        # Create V7 table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prospect_rankings_v7 (
                id SERIAL PRIMARY KEY,
                mlb_player_id VARCHAR(50) UNIQUE,
                player_name VARCHAR(255),
                fv INTEGER,
                report_year INTEGER,
                fg_score FLOAT,
                v4_score FLOAT,
                v5_score FLOAT,
                v7_score FLOAT,
                v7_rank INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

        # Insert data
        for _, row in df.iterrows():
            await conn.execute(text("""
                INSERT INTO prospect_rankings_v7
                (mlb_player_id, player_name, fv, report_year, fg_score, v4_score, v5_score, v7_score, v7_rank, updated_at)
                VALUES (:mlb_player_id, :player_name, :fv, :report_year, :fg_score, :v4_score, :v5_score, :v7_score, :v7_rank, NOW())
                ON CONFLICT (mlb_player_id) DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    fv = EXCLUDED.fv,
                    report_year = EXCLUDED.report_year,
                    fg_score = EXCLUDED.fg_score,
                    v4_score = EXCLUDED.v4_score,
                    v5_score = EXCLUDED.v5_score,
                    v7_score = EXCLUDED.v7_score,
                    v7_rank = EXCLUDED.v7_rank,
                    updated_at = NOW()
            """), {
                'mlb_player_id': row['mlb_player_id'],
                'player_name': row['player_name'] if pd.notna(row['player_name']) else row['name'],
                'fv': int(row['fv']) if pd.notna(row['fv']) else None,
                'report_year': int(row['report_year']) if pd.notna(row['report_year']) else None,
                'fg_score': float(row['fg_score_normalized']),
                'v4_score': float(row['v4_normalized']) if row['has_v4'] else None,
                'v5_score': float(row['v5_normalized']) if row['has_v5'] else None,
                'v7_score': float(row['v7_score']),
                'v7_rank': int(row['v7_rank'])
            })

    print(f'Saved {len(df)} prospects to prospect_rankings_v7 table')

    # Export to CSV
    csv_file = 'prospect_rankings_v7_fangraphs_integrated.csv'
    export_df = df[['v7_rank', 'mlb_player_id', 'player_name', 'fv', 'report_year',
                     'fg_score_normalized', 'v4_normalized', 'v5_normalized', 'v7_score']].copy()
    export_df.columns = ['rank', 'mlb_player_id', 'name', 'fv', 'fg_year', 'fg_score', 'v4_score', 'v5_score', 'v7_score']
    export_df.to_csv(csv_file, index=False)

    print(f'Exported to {csv_file}')

    # Key insights
    print('\n' + '=' * 80)
    print('KEY INSIGHTS')
    print('=' * 80)

    # Correlation analysis
    if len(df[df['has_v4'] & df['has_v5']]) > 10:
        subset = df[df['has_v4'] & df['has_v5']]
        fg_v4_corr = subset['fg_score_normalized'].corr(subset['v4_normalized'])
        fg_v5_corr = subset['fg_score_normalized'].corr(subset['v5_normalized'])
        v4_v5_corr = subset['v4_normalized'].corr(subset['v5_normalized'])

        print('\nCorrelations between ranking systems:')
        print(f'  FG vs V4: r={fg_v4_corr:.3f}')
        print(f'  FG vs V5: r={fg_v5_corr:.3f}')
        print(f'  V4 vs V5: r={v4_v5_corr:.3f}')

    # Biggest movers
    if len(df[df['has_v4']]) > 0:
        df['v4_rank_approx'] = df['v4_normalized'].rank(ascending=False, na_option='bottom')
        df['rank_change'] = df['v4_rank_approx'] - df['v7_rank']

        print('\nBiggest risers (V7 vs V4):')
        risers = df[df['has_v4']].nlargest(5, 'rank_change')
        for _, row in risers.iterrows():
            print(f'  {row["player_name"]:<25} FV:{int(row["fv"]):>2} (#{int(row["v7_rank"])} in V7, ~#{int(row["v4_rank_approx"])} in V4, +{int(row["rank_change"])})')

    print('\n' + '=' * 80)
    print('V7 RANKINGS COMPLETE')
    print('=' * 80)
    print('\nFanGraphs expert grades now comprise 50% of prospect rankings.')
    print('This gives professional scouting evaluations a large weight in the system.')


if __name__ == '__main__':
    asyncio.run(generate_v7_rankings())
