"""
Build Training Dataset for MLB Stat Projections
================================================

This script creates a training dataset for predicting actual MLB stats
from MiLB performance data.

Strategy:
1. Find all prospects with BOTH MiLB and MLB data (ground truth)
2. Extract MiLB features from season BEFORE MLB debut
3. Calculate MLB career stats as prediction targets
4. Save dataset for model training

Output: CSV file with features (X) and targets (Y) for regression

Usage:
    python scripts/build_stat_projection_training_data.py
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def find_milb_to_mlb_transitions(conn):
    """
    Find all prospects who have BOTH MiLB and MLB game logs.

    These are our training samples - we know their MiLB stats and
    their actual MLB outcomes.
    """
    print("\n" + "="*80)
    print("FINDING MiLB → MLB TRANSITIONS")
    print("="*80)

    query = """
        WITH milb_prospects AS (
            SELECT DISTINCT
                p.id as prospect_id,
                p.mlb_player_id::integer as mlb_player_id,
                p.name,
                p.position,
                p.fg_player_id,
                MIN(milb.season) as first_milb_season,
                MAX(milb.season) as last_milb_season,
                COUNT(DISTINCT milb.id) as milb_game_count
            FROM prospects p
            INNER JOIN milb_game_logs milb
                ON p.mlb_player_id::integer = milb.mlb_player_id
            WHERE p.mlb_player_id IS NOT NULL
                AND p.mlb_player_id ~ '^[0-9]+$'  -- Only numeric IDs
                AND milb.season IS NOT NULL
            GROUP BY p.id, p.mlb_player_id, p.name, p.position, p.fg_player_id
        ),
        mlb_prospects AS (
            SELECT DISTINCT
                p.mlb_player_id::integer as mlb_player_id,
                MIN(mlb.season) as mlb_debut_season,
                MAX(mlb.season) as last_mlb_season,
                COUNT(DISTINCT mlb.id) as mlb_game_count
            FROM prospects p
            INNER JOIN mlb_game_logs mlb
                ON p.mlb_player_id::integer = mlb.mlb_player_id
            WHERE p.mlb_player_id IS NOT NULL
                AND p.mlb_player_id ~ '^[0-9]+$'  -- Only numeric IDs
                AND mlb.season IS NOT NULL
            GROUP BY p.mlb_player_id
        )
        SELECT
            milb.prospect_id,
            milb.mlb_player_id,
            milb.name,
            milb.position,
            milb.fg_player_id,
            milb.first_milb_season,
            milb.last_milb_season,
            milb.milb_game_count,
            mlb.mlb_debut_season,
            mlb.last_mlb_season,
            mlb.mlb_game_count
        FROM milb_prospects milb
        INNER JOIN mlb_prospects mlb
            ON milb.mlb_player_id = mlb.mlb_player_id
        WHERE mlb.mlb_game_count >= 20  -- At least 20 MLB games for meaningful stats
        ORDER BY mlb.mlb_game_count DESC
    """

    rows = await conn.fetch(query)
    prospects = [dict(row) for row in rows]

    print(f"\n[OK] Found {len(prospects)} prospects with MiLB → MLB transitions")
    print(f"     (Minimum 20 MLB games for training)")

    # Stats breakdown
    hitters = [p for p in prospects if p['position'] not in ['SP', 'RP', 'LHP', 'RHP']]
    pitchers = [p for p in prospects if p['position'] in ['SP', 'RP', 'LHP', 'RHP']]

    print(f"\n     Hitters: {len(hitters)}")
    print(f"     Pitchers: {len(pitchers)}")

    return prospects


async def extract_milb_features_before_debut(conn, mlb_player_id, debut_season, position):
    """
    Extract MiLB features from the season(s) BEFORE MLB debut.

    Strategy:
    - Use last 1-2 seasons before debut at highest level (AAA/AA preferred)
    - Extract comprehensive stats and derived metrics
    - Include Fangraphs grades if available
    """

    # Get MiLB stats from season before debut
    pre_debut_season = debut_season - 1

    query = """
        SELECT
            season,
            level,
            team,
            COUNT(*) as games,
            SUM(plate_appearances) as pa,
            SUM(at_bats) as ab,
            SUM(runs) as r,
            SUM(hits) as h,
            SUM(doubles) as doubles,
            SUM(triples) as triples,
            SUM(home_runs) as hr,
            SUM(rbi) as rbi,
            SUM(walks) as bb,
            SUM(intentional_walks) as ibb,
            SUM(strikeouts) as so,
            SUM(stolen_bases) as sb,
            SUM(caught_stealing) as cs,
            SUM(hit_by_pitch) as hbp,
            SUM(sacrifice_flies) as sf,
            AVG(batting_avg) as avg,
            AVG(on_base_pct) as obp,
            AVG(slugging_pct) as slg,
            AVG(ops) as ops,
            AVG(babip) as babip
        FROM milb_game_logs
        WHERE mlb_player_id = $1
            AND season = $2
            AND plate_appearances > 0
        GROUP BY season, level, team
        ORDER BY
            CASE level
                WHEN 'AAA' THEN 4
                WHEN 'AA' THEN 3
                WHEN 'A+' THEN 2
                WHEN 'A' THEN 1
                ELSE 0
            END DESC
        LIMIT 1
    """

    row = await conn.fetchrow(query, mlb_player_id, pre_debut_season)

    if not row:
        # Try 2 years before debut if no data 1 year before
        row = await conn.fetchrow(query, mlb_player_id, pre_debut_season - 1)

    if not row:
        # Try 3 years before
        row = await conn.fetchrow(query, mlb_player_id, pre_debut_season - 2)

    if not row:
        # Last resort: try debut year itself (spring training MiLB games)
        row = await conn.fetchrow(query, mlb_player_id, debut_season)

    if not row:
        return None

    features = dict(row)

    # Add derived features - handle None values
    if features.get('pa', 0) and features['pa'] > 0:
        # Calculate ISO (Isolated Power = SLG - AVG)
        slg = features.get('slg') or 0
        avg = features.get('avg') or 0
        features['iso'] = slg - avg

        # Calculate rate stats
        bb = features.get('bb') or 0
        so = features.get('so') or 0
        hr = features.get('hr') or 0
        sb = features.get('sb') or 0
        cs = features.get('cs') or 0
        doubles = features.get('doubles') or 0
        triples = features.get('triples') or 0
        ab = features.get('ab') or 0
        pa = features.get('pa') or 1

        features['bb_rate'] = bb / pa
        features['k_rate'] = so / pa

        features['power_speed_number'] = (
            (2 * hr * sb) / (hr + sb) if (hr + sb) > 0 else 0
        )
        features['bb_per_k'] = bb / so if so > 0 else 0
        features['xbh'] = doubles + triples + hr
        features['xbh_rate'] = features['xbh'] / ab if ab > 0 else 0
        features['sb_success_rate'] = sb / (sb + cs) if (sb + cs) > 0 else 0

    # Get Fangraphs grades if available
    fg_query = """
        SELECT
            hit_future,
            game_power_future,
            raw_power_future,
            speed_future,
            fielding_future
        FROM fangraphs_hitter_grades
        WHERE fangraphs_player_id = $1
            AND data_year <= $2
        ORDER BY data_year DESC
        LIMIT 1
    """

    # Get fg_player_id from prospects table
    fg_id_row = await conn.fetchrow(
        "SELECT fg_player_id FROM prospects WHERE mlb_player_id::integer = $1",
        mlb_player_id
    )

    if fg_id_row and fg_id_row['fg_player_id']:
        fg_row = await conn.fetchrow(fg_query, fg_id_row['fg_player_id'], debut_season - 1)
        if fg_row:
            features.update(dict(fg_row))

    return features


async def extract_pitcher_milb_features_before_debut(conn, mlb_player_id, debut_season):
    """Extract MiLB pitching features before MLB debut."""

    pre_debut_season = debut_season - 1

    query = """
        SELECT
            season,
            level,
            COUNT(*) as games,
            SUM(innings_pitched) as ip,
            SUM(hits) as h,
            SUM(runs) as r,
            SUM(earned_runs) as er,
            SUM(walks) as bb,
            SUM(strikeouts) as so,
            SUM(home_runs) as hr,
            SUM(pitches_thrown) as pitches,
            SUM(strikes) as strikes,
            SUM(batters_faced) as batters_faced
        FROM milb_pitcher_appearances
        WHERE mlb_player_id = $1
            AND season = $2
            AND innings_pitched > 0
        GROUP BY season, level
        ORDER BY
            CASE level
                WHEN 'AAA' THEN 4
                WHEN 'AA' THEN 3
                WHEN 'A+' THEN 2
                WHEN 'A' THEN 1
                ELSE 0
            END DESC
        LIMIT 1
    """

    row = await conn.fetchrow(query, mlb_player_id, pre_debut_season)

    if not row:
        row = await conn.fetchrow(query, mlb_player_id, pre_debut_season - 1)

    if not row:
        row = await conn.fetchrow(query, mlb_player_id, pre_debut_season - 2)

    if not row:
        row = await conn.fetchrow(query, mlb_player_id, debut_season)

    if not row:
        return None

    features = dict(row)

    # Derived features - handle None values
    ip = features.get('ip') or 0
    so = features.get('so') or 0
    bb = features.get('bb') or 0
    hr = features.get('hr') or 0
    h = features.get('h') or 0
    er = features.get('er') or 0
    batters_faced = features.get('batters_faced') or 0

    if ip > 0:
        features['k_per_9'] = (so / ip) * 9
        features['bb_per_9'] = (bb / ip) * 9
        features['hr_per_9'] = (hr / ip) * 9
        features['k_bb_ratio'] = so / bb if bb > 0 else 0
        features['era'] = (er / ip) * 9
        features['whip'] = (h + bb) / ip

        # Calculate rate stats
        if batters_faced > 0:
            features['k_rate'] = so / batters_faced
            features['bb_rate'] = bb / batters_faced
        else:
            # Fallback estimation
            estimated_bf = (ip * 3) + h + bb
            features['k_rate'] = so / estimated_bf if estimated_bf > 0 else 0
            features['bb_rate'] = bb / estimated_bf if estimated_bf > 0 else 0
    else:
        features['k_per_9'] = 0
        features['bb_per_9'] = 0
        features['hr_per_9'] = 0
        features['k_bb_ratio'] = 0
        features['era'] = 0
        features['whip'] = 0
        features['k_rate'] = 0
        features['bb_rate'] = 0

    # Get Fangraphs pitch grades
    fg_id_row = await conn.fetchrow(
        "SELECT fg_player_id FROM prospects WHERE mlb_player_id::integer = $1",
        mlb_player_id
    )

    if fg_id_row and fg_id_row['fg_player_id']:
        fg_query = """
            SELECT
                fastball_future,
                curveball_future,
                slider_future,
                changeup_future,
                command_future
            FROM fangraphs_pitcher_grades
            WHERE fangraphs_player_id = $1
                AND data_year <= $2
            ORDER BY data_year DESC
            LIMIT 1
        """
        fg_row = await conn.fetchrow(fg_query, fg_id_row['fg_player_id'], debut_season - 1)
        if fg_row:
            features.update(dict(fg_row))

    return features


async def calculate_mlb_career_stats_hitter(conn, mlb_player_id):
    """
    Calculate MLB career stats as prediction targets for hitters.

    Uses peak 3 consecutive years or first 3 years, whichever is better.
    """

    query = """
        SELECT
            season,
            SUM(plate_appearances) as pa,
            SUM(at_bats) as ab,
            SUM(runs) as r,
            SUM(hits) as h,
            SUM(doubles) as doubles,
            SUM(triples) as triples,
            SUM(home_runs) as hr,
            SUM(rbi) as rbi,
            SUM(walks) as bb,
            SUM(strikeouts) as so,
            SUM(stolen_bases) as sb,
            SUM(caught_stealing) as cs,
            AVG(batting_avg) as avg,
            AVG(on_base_pct) as obp,
            AVG(slugging_pct) as slg,
            AVG(ops) as ops
        FROM mlb_game_logs
        WHERE mlb_player_id = $1
            AND plate_appearances > 0
        GROUP BY season
        ORDER BY season
    """

    rows = await conn.fetch(query, mlb_player_id)

    if not rows or len(rows) < 1:
        return None

    # Convert to DataFrame for easier analysis
    df = pd.DataFrame([dict(r) for r in rows])

    # Calculate career totals
    total_games = len(rows)
    total_pa = df['pa'].sum()

    # Use first 3 years or all years if less than 3
    years_to_use = min(3, len(df))
    peak_df = df.head(years_to_use)

    # Calculate average stats per 600 PA
    total_peak_pa = peak_df['pa'].sum()

    if total_peak_pa < 100:  # Not enough data
        return None

    # Rate stats (averages)
    targets = {
        'target_avg': peak_df['h'].sum() / peak_df['ab'].sum() if peak_df['ab'].sum() > 0 else 0,
        'target_obp': (peak_df['h'].sum() + peak_df['bb'].sum()) / total_peak_pa,
        'target_slg': peak_df['slg'].mean(),
        'target_ops': peak_df['ops'].mean(),
        'target_bb_rate': peak_df['bb'].sum() / total_peak_pa,
        'target_k_rate': peak_df['so'].sum() / total_peak_pa,

        # Counting stats per 600 PA
        'target_hr_per_600': (peak_df['hr'].sum() / total_peak_pa) * 600,
        'target_sb_per_600': (peak_df['sb'].sum() / total_peak_pa) * 600,
        'target_rbi_per_600': (peak_df['rbi'].sum() / total_peak_pa) * 600,
        'target_r_per_600': (peak_df['r'].sum() / total_peak_pa) * 600,

        # Career totals
        'target_career_games': total_games * 10,  # Rough estimate (10 games per row)
        'target_career_pa': total_pa,
    }

    # Calculate ISO
    if peak_df['ab'].sum() > 0:
        targets['target_iso'] = targets['target_slg'] - targets['target_avg']
    else:
        targets['target_iso'] = 0

    return targets


async def calculate_mlb_career_stats_pitcher(conn, mlb_player_id):
    """Calculate MLB career stats as prediction targets for pitchers."""

    query = """
        SELECT
            season,
            COUNT(*) as g,
            SUM(innings_pitched) as ip,
            SUM(hits) as h,
            SUM(runs) as r,
            SUM(earned_runs) as er,
            SUM(walks) as bb,
            SUM(strikeouts) as so,
            SUM(home_runs) as hr,
            SUM(saves) as saves
        FROM mlb_pitcher_appearances
        WHERE mlb_player_id = $1
            AND innings_pitched > 0
        GROUP BY season
        ORDER BY season
    """

    rows = await conn.fetch(query, mlb_player_id)

    if not rows or len(rows) < 1:
        return None

    df = pd.DataFrame([dict(r) for r in rows])

    # Use first 3 years or all if less
    years_to_use = min(3, len(df))
    peak_df = df.head(years_to_use)

    total_ip = peak_df['ip'].sum()

    if total_ip < 20:  # Not enough data
        return None

    total_games = len(rows)
    total_career_ip = df['ip'].sum()

    # Calculate targets from peak years
    peak_er = peak_df['er'].sum()
    peak_h = peak_df['h'].sum()
    peak_bb = peak_df['bb'].sum()
    peak_so = peak_df['so'].sum()
    peak_hr = peak_df['hr'].sum()

    targets = {
        'target_era': (peak_er / total_ip) * 9 if total_ip > 0 else 0,
        'target_whip': (peak_h + peak_bb) / total_ip if total_ip > 0 else 0,
        'target_k_per_9': (peak_so / total_ip) * 9 if total_ip > 0 else 0,
        'target_bb_per_9': (peak_bb / total_ip) * 9 if total_ip > 0 else 0,
        'target_hr_per_9': (peak_hr / total_ip) * 9 if total_ip > 0 else 0,
        'target_k_bb_ratio': peak_so / peak_bb if peak_bb > 0 else 0,
        'target_fip': ((13*peak_hr + 3*peak_bb - 2*peak_so) / total_ip) + 3.10 if total_ip > 0 else 0,  # FIP constant ~3.10

        # Career totals
        'target_career_games': total_games,
        'target_career_ip': total_career_ip,

        # Additional metrics
        'target_saves': peak_df['saves'].sum() if 'saves' in peak_df.columns else 0,
    }

    return targets


async def build_training_dataset():
    """Main function to build complete training dataset."""

    print("="*80)
    print("MLB STAT PROJECTION - TRAINING DATA BUILDER")
    print("="*80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Step 1: Find prospects with MiLB → MLB transitions
        prospects = await find_milb_to_mlb_transitions(conn)

        # Step 2: Build training data
        print("\n" + "="*80)
        print("EXTRACTING FEATURES AND TARGETS")
        print("="*80)

        hitter_data = []
        pitcher_data = []

        for i, prospect in enumerate(prospects, 1):
            if i % 50 == 0:
                print(f"\nProcessed {i}/{len(prospects)}...")

            mlb_player_id = prospect['mlb_player_id']
            position = prospect['position']
            debut_season = prospect['mlb_debut_season']

            # Determine if hitter or pitcher
            is_pitcher = position in ['SP', 'RP', 'LHP', 'RHP']

            if is_pitcher:
                # Extract pitcher features
                features = await extract_pitcher_milb_features_before_debut(
                    conn, mlb_player_id, debut_season
                )
                if not features:
                    continue

                # Calculate MLB targets
                targets = await calculate_mlb_career_stats_pitcher(conn, mlb_player_id)
                if not targets:
                    continue

                # Combine
                row = {
                    'prospect_id': prospect['prospect_id'],
                    'mlb_player_id': mlb_player_id,
                    'name': prospect['name'],
                    'position': position,
                    **features,
                    **targets
                }
                pitcher_data.append(row)

            else:
                # Extract hitter features
                features = await extract_milb_features_before_debut(
                    conn, mlb_player_id, debut_season, position
                )
                if not features:
                    continue

                # Calculate MLB targets
                targets = await calculate_mlb_career_stats_hitter(conn, mlb_player_id)
                if not targets:
                    continue

                # Combine
                row = {
                    'prospect_id': prospect['prospect_id'],
                    'mlb_player_id': mlb_player_id,
                    'name': prospect['name'],
                    'position': position,
                    **features,
                    **targets
                }
                hitter_data.append(row)

        print(f"\n[OK] Extraction complete!")
        print(f"     Hitters: {len(hitter_data)} training samples")
        print(f"     Pitchers: {len(pitcher_data)} training samples")

        # Step 3: Save datasets
        print("\n" + "="*80)
        print("SAVING TRAINING DATASETS")
        print("="*80)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if hitter_data:
            hitter_df = pd.DataFrame(hitter_data)
            hitter_file = f'stat_projection_hitters_train_{timestamp}.csv'
            hitter_df.to_csv(hitter_file, index=False)
            print(f"\n[OK] Saved: {hitter_file}")
            print(f"     Samples: {len(hitter_df)}")
            print(f"     Features: {len([c for c in hitter_df.columns if not c.startswith('target_') and c not in ['prospect_id', 'mlb_player_id', 'name', 'position']])}")
            print(f"     Targets: {len([c for c in hitter_df.columns if c.startswith('target_')])}")

        if pitcher_data:
            pitcher_df = pd.DataFrame(pitcher_data)
            pitcher_file = f'stat_projection_pitchers_train_{timestamp}.csv'
            pitcher_df.to_csv(pitcher_file, index=False)
            print(f"\n[OK] Saved: {pitcher_file}")
            print(f"     Samples: {len(pitcher_df)}")
            print(f"     Features: {len([c for c in pitcher_df.columns if not c.startswith('target_') and c not in ['prospect_id', 'mlb_player_id', 'name', 'position']])}")
            print(f"     Targets: {len([c for c in pitcher_df.columns if c.startswith('target_')])}")

        print("\n" + "="*80)
        print("TRAINING DATA BUILD COMPLETE!")
        print("="*80)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(build_training_dataset())
