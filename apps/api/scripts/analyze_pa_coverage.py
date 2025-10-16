#!/usr/bin/env python3
"""
Analyze PA coverage for prospects to identify data availability issues.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

# Convert async URL to sync
db_url = os.getenv('SQLALCHEMY_DATABASE_URI').replace('postgresql+asyncpg://', 'postgresql://')
engine = create_engine(db_url)

print("\n" + "="*80)
print("PA Coverage Analysis for Prospects")
print("="*80)

with engine.connect() as conn:
    # 1. Get prospects with game logs but no PA data
    print("\n[1] Checking prospects with game logs vs PA data...")
    query = text("""
        WITH prospect_games AS (
            SELECT
                p.mlb_player_id,
                p.name,
                p.position,
                COUNT(DISTINCT g.game_pk) as game_log_count,
                MIN(g.season) as first_season,
                MAX(g.season) as last_season
            FROM prospects p
            INNER JOIN milb_game_logs g ON g.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
            WHERE p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id != ''
            GROUP BY p.mlb_player_id, p.name, p.position
            HAVING COUNT(DISTINCT g.game_pk) > 10
        ),
        prospect_pas AS (
            SELECT
                mlb_player_id,
                COUNT(DISTINCT game_pk) as pa_game_count,
                COUNT(*) as total_pas
            FROM milb_plate_appearances
            GROUP BY mlb_player_id
        )
        SELECT
            pg.mlb_player_id,
            pg.name,
            pg.position,
            pg.game_log_count,
            pg.first_season,
            pg.last_season,
            COALESCE(pp.pa_game_count, 0) as pa_game_count,
            COALESCE(pp.total_pas, 0) as total_pas,
            CASE
                WHEN pp.mlb_player_id IS NULL THEN 'NO_PA_DATA'
                WHEN pp.pa_game_count < pg.game_log_count * 0.5 THEN 'LOW_COVERAGE'
                ELSE 'GOOD_COVERAGE'
            END as coverage_status
        FROM prospect_games pg
        LEFT JOIN prospect_pas pp ON pp.mlb_player_id = CAST(pg.mlb_player_id AS INTEGER)
        ORDER BY coverage_status, pg.game_log_count DESC
    """)

    result = conn.execute(query)
    df = pd.DataFrame(result.fetchall(), columns=result.keys())

    # Summary stats
    no_pa = df[df['coverage_status'] == 'NO_PA_DATA']
    low_coverage = df[df['coverage_status'] == 'LOW_COVERAGE']
    good_coverage = df[df['coverage_status'] == 'GOOD_COVERAGE']

    print(f"\nCoverage Summary:")
    print(f"  NO PA DATA: {len(no_pa)} prospects ({len(no_pa)/len(df)*100:.1f}%)")
    print(f"  LOW COVERAGE: {len(low_coverage)} prospects ({len(low_coverage)/len(df)*100:.1f}%)")
    print(f"  GOOD COVERAGE: {len(good_coverage)} prospects ({len(good_coverage)/len(df)*100:.1f}%)")

    # 2. Sample prospects with no PA data (for API testing)
    print(f"\n[2] Sample prospects with NO PA data (10 examples):")
    print(f"{'Name':<25} {'Pos':<5} {'Games':<7} {'First-Last Season'}")
    print("-"*70)
    for _, row in no_pa.head(10).iterrows():
        print(f"{row['name']:<25} {row['position']:<5} {row['game_log_count']:<7} {row['first_season']}-{row['last_season']}")

    # Save sample for testing
    sample_file = Path(__file__).parent / "sample_missing_prospects.csv"
    no_pa.head(20).to_csv(sample_file, index=False)
    print(f"\nSaved 20 missing prospects to: {sample_file}")

    # 3. Coverage by season
    print(f"\n[3] PA coverage by season:")
    season_query = text("""
        WITH prospect_games_by_season AS (
            SELECT
                g.season,
                COUNT(DISTINCT p.mlb_player_id) as prospects_with_games,
                COUNT(DISTINCT g.game_pk) as total_games
            FROM prospects p
            INNER JOIN milb_game_logs g ON g.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
            WHERE p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id != ''
            GROUP BY g.season
        ),
        pa_by_season AS (
            SELECT
                season,
                COUNT(DISTINCT mlb_player_id) as prospects_with_pas,
                COUNT(DISTINCT game_pk) as games_with_pas,
                COUNT(*) as total_pas
            FROM milb_plate_appearances
            WHERE mlb_player_id IN (
                SELECT CAST(mlb_player_id AS INTEGER)
                FROM prospects
                WHERE mlb_player_id IS NOT NULL
                AND mlb_player_id != ''
            )
            GROUP BY season
        )
        SELECT
            pg.season,
            pg.prospects_with_games,
            pg.total_games,
            COALESCE(pp.prospects_with_pas, 0) as prospects_with_pas,
            COALESCE(pp.games_with_pas, 0) as games_with_pas,
            COALESCE(pp.total_pas, 0) as total_pas,
            ROUND(COALESCE(pp.prospects_with_pas, 0)::numeric / pg.prospects_with_games * 100, 1) as prospect_coverage_pct,
            ROUND(COALESCE(pp.games_with_pas, 0)::numeric / pg.total_games * 100, 1) as game_coverage_pct
        FROM prospect_games_by_season pg
        LEFT JOIN pa_by_season pp ON pp.season = pg.season
        ORDER BY pg.season DESC
    """)

    result = conn.execute(season_query)
    season_df = pd.DataFrame(result.fetchall(), columns=result.keys())

    print(f"\n{'Season':<8} {'Prospects':<12} {'PA Data':<12} {'Coverage %':<12} {'Games':<12} {'PA Games':<12} {'Game %'}")
    print("-"*100)
    for _, row in season_df.iterrows():
        print(f"{row['season']:<8} {row['prospects_with_games']:<12} {row['prospects_with_pas']:<12} "
              f"{row['prospect_coverage_pct']:<12} {row['total_games']:<12} {row['games_with_pas']:<12} {row['game_coverage_pct']}")

    # 4. Check if pitch data has PA coverage
    print(f"\n[4] Checking PA coverage in pitch data (is_final_pitch records):")
    pitch_pa_query = text("""
        SELECT
            season,
            COUNT(DISTINCT mlb_batter_id) as batters_with_pitch_data,
            COUNT(*) FILTER (WHERE is_final_pitch = true) as final_pitch_count,
            COUNT(DISTINCT CASE WHEN is_final_pitch = true THEN mlb_batter_id END) as batters_with_final_pitches
        FROM milb_batter_pitches
        WHERE mlb_batter_id IN (
            SELECT CAST(mlb_player_id AS INTEGER)
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
            AND mlb_player_id != ''
        )
        GROUP BY season
        ORDER BY season DESC
    """)

    result = conn.execute(pitch_pa_query)
    pitch_df = pd.DataFrame(result.fetchall(), columns=result.keys())

    print(f"\n{'Season':<8} {'Prospects':<15} {'Final Pitches':<15} {'(PA equivalents)'}")
    print("-"*60)
    for _, row in pitch_df.iterrows():
        print(f"{row['season']:<8} {row['batters_with_pitch_data']:<15} {row['final_pitch_count']:<15}")

    # 5. Combined coverage analysis
    print(f"\n[5] Combined PA + Pitch data coverage:")
    combined_query = text("""
        WITH all_coverage AS (
            SELECT
                CAST(p.mlb_player_id AS INTEGER) as player_id,
                p.name,
                p.position,
                CASE WHEN pa.mlb_player_id IS NOT NULL THEN 1 ELSE 0 END as has_pa_data,
                CASE WHEN bp.mlb_batter_id IS NOT NULL THEN 1 ELSE 0 END as has_pitch_data
            FROM prospects p
            LEFT JOIN (SELECT DISTINCT mlb_player_id FROM milb_plate_appearances) pa
                ON pa.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
            LEFT JOIN (SELECT DISTINCT mlb_batter_id FROM milb_batter_pitches) bp
                ON bp.mlb_batter_id = CAST(p.mlb_player_id AS INTEGER)
            WHERE p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id != ''
        )
        SELECT
            COUNT(*) as total_prospects,
            SUM(has_pa_data) as have_pa_data,
            SUM(has_pitch_data) as have_pitch_data,
            SUM(CASE WHEN has_pa_data = 1 OR has_pitch_data = 1 THEN 1 ELSE 0 END) as have_either,
            SUM(CASE WHEN has_pa_data = 0 AND has_pitch_data = 0 THEN 1 ELSE 0 END) as have_neither,
            ROUND(SUM(CASE WHEN has_pa_data = 1 OR has_pitch_data = 1 THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 1) as coverage_pct
        FROM all_coverage
    """)

    result = conn.execute(combined_query)
    row = result.fetchone()

    print(f"  Total prospects: {row[0]}")
    print(f"  Have PA data: {row[1]} ({row[1]/row[0]*100:.1f}%)")
    print(f"  Have pitch data: {row[2]} ({row[2]/row[0]*100:.1f}%)")
    print(f"  Have either PA or pitch data: {row[3]} ({row[5]}%)")
    print(f"  Have NO data: {row[4]} ({row[4]/row[0]*100:.1f}%)")

print("\n" + "="*80)
print("Analysis complete!")
print("="*80)
