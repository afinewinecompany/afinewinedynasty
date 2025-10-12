#!/usr/bin/env python3
"""
Test the Fangraphs median fallback system.

Shows:
1. Median grade calculations
2. Match vs fallback statistics
3. Feature distribution comparison
"""

import asyncio
import pandas as pd
import numpy as np
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'ml_pipeline'))
from app.db.database import engine
from sqlalchemy import text
from feature_engineering_with_fangraphs import FangraphsFeatureEngineer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_median_fallback():
    """Test the median fallback system."""

    engineer = FangraphsFeatureEngineer()

    # Load Fangraphs data (this also calculates medians)
    await engineer.load_fangraphs_data()

    # Display calculated medians
    print("\n" + "="*80)
    print("CALCULATED MEDIAN GRADES (for fallback)")
    print("="*80)

    if engineer.median_grades:
        print(f"FV (Future Value): {engineer.median_grades.get('fv', 45):.0f}")
        print(f"Hit Tool: {engineer.median_grades.get('hit_future', 50):.0f}")
        print(f"Game Power: {engineer.median_grades.get('game_pwr_future', 50):.0f}")
        print(f"Raw Power: {engineer.median_grades.get('raw_pwr_future', 50):.0f}")
        print(f"Speed: {engineer.median_grades.get('spd_future', 50):.0f}")
        print(f"Fielding: {engineer.median_grades.get('fld_future', 50):.0f}")

        # For pitchers
        if engineer.median_grades.get('fb_future'):
            print(f"\nPitching Grades:")
            print(f"Fastball: {engineer.median_grades.get('fb_future', 50):.0f}")
            print(f"Slider: {engineer.median_grades.get('sl_future', 50):.0f}")
            print(f"Curveball: {engineer.median_grades.get('cb_future', 50):.0f}")
            print(f"Changeup: {engineer.median_grades.get('ch_future', 50):.0f}")
            print(f"Command: {engineer.median_grades.get('cmd_future', 50):.0f}")

    # Test matching on sample players
    print("\n" + "="*80)
    print("TESTING MATCH VS FALLBACK")
    print("="*80)

    # Get sample players from different levels
    async with engine.begin() as conn:
        # Get top AAA prospects
        result = await conn.execute(text("""
            SELECT DISTINCT mlb_player_id
            FROM milb_game_logs
            WHERE season = 2024
            AND level = 'AAA'
            AND plate_appearances > 200
            ORDER BY ops DESC
            LIMIT 10
        """))
        aaa_players = [row[0] for row in result.fetchall()]

        # Get random A-ball players
        result = await conn.execute(text("""
            SELECT DISTINCT mlb_player_id
            FROM milb_game_logs
            WHERE season = 2024
            AND level = 'A'
            AND plate_appearances > 200
            ORDER BY RANDOM()
            LIMIT 10
        """))
        a_players = [row[0] for row in result.fetchall()]

    # Test each group
    print("\nTop AAA Players (more likely to match):")
    aaa_matched = 0
    for player_id in aaa_players:
        features = await engineer.create_player_features(player_id)
        if features:
            match_status = features.get('has_fg_grades', 0)
            if match_status == 1:
                status = "MATCHED"
                aaa_matched += 1
            elif match_status == 0.5:
                status = "FALLBACK (median)"
            else:
                status = "NO DATA"

            print(f"  Player {player_id}: {status} - FV={features.get('fg_fv', 0)*10:.0f}")

    print(f"\nMatch rate for AAA: {aaa_matched}/{len(aaa_players)} ({aaa_matched/len(aaa_players)*100:.0f}%)")

    print("\nRandom A-Ball Players (less likely to match):")
    a_matched = 0
    for player_id in a_players:
        features = await engineer.create_player_features(player_id)
        if features:
            match_status = features.get('has_fg_grades', 0)
            if match_status == 1:
                status = "MATCHED"
                a_matched += 1
            elif match_status == 0.5:
                status = "FALLBACK (median)"
            else:
                status = "NO DATA"

            print(f"  Player {player_id}: {status} - FV={features.get('fg_fv', 0)*10:.0f}")

    print(f"\nMatch rate for A-Ball: {a_matched}/{len(a_players)} ({a_matched/len(a_players)*100:.0f}%)")

    # Test feature distributions
    print("\n" + "="*80)
    print("FEATURE DISTRIBUTION ANALYSIS")
    print("="*80)

    # Create features for a larger sample
    all_features = []
    match_count = 0
    fallback_count = 0

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT DISTINCT mlb_player_id
            FROM milb_game_logs
            WHERE season = 2024
            AND plate_appearances > 100
            ORDER BY RANDOM()
            LIMIT 100
        """))
        sample_players = [row[0] for row in result.fetchall()]

    for player_id in sample_players:
        features = await engineer.create_player_features(player_id)
        if features:
            all_features.append(features)
            if features.get('has_fg_grades', 0) == 1:
                match_count += 1
            elif features.get('has_fg_grades', 0) == 0.5:
                fallback_count += 1

    df = pd.DataFrame(all_features)

    print(f"\nTotal players processed: {len(df)}")
    print(f"Matched to Fangraphs: {match_count} ({match_count/len(df)*100:.1f}%)")
    print(f"Using median fallback: {fallback_count} ({fallback_count/len(df)*100:.1f}%)")
    print(f"No grades: {len(df) - match_count - fallback_count}")

    # Show distribution of key features
    print("\nFeature Value Distribution:")
    fg_features = ['fg_fv', 'fg_hit_future', 'fg_power_future', 'fg_speed_future']

    for feat in fg_features:
        if feat in df.columns:
            matched_vals = df[df['has_fg_grades'] == 1][feat].dropna()
            fallback_vals = df[df['has_fg_grades'] == 0.5][feat].dropna()

            print(f"\n{feat}:")
            if len(matched_vals) > 0:
                print(f"  Matched players - Mean: {matched_vals.mean():.3f}, Std: {matched_vals.std():.3f}")
            if len(fallback_vals) > 0:
                print(f"  Fallback players - Mean: {fallback_vals.mean():.3f}, Std: {fallback_vals.std():.3f}")


async def main():
    """Run tests."""
    await test_median_fallback()


if __name__ == "__main__":
    asyncio.run(main())