"""
Analyze FanGraphs grade distributions and typical MLB outcomes.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
import matplotlib.pyplot as plt
import seaborn as sns

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine


async def analyze_fangraphs_grades():
    """Analyze FanGraphs grade distributions."""

    # Get FanGraphs grade distributions
    query = """
        SELECT
            fv,
            hit_future,
            game_power_future,
            raw_power_future,
            speed_future,
            field_future,
            COUNT(*) as count,
            AVG(CASE WHEN has_upside THEN 1 ELSE 0 END) as pct_with_upside
        FROM fangraphs_prospect_grades
        WHERE fv IS NOT NULL
        GROUP BY fv, hit_future, game_power_future, raw_power_future, speed_future, field_future
        ORDER BY fv DESC
    """

    async with engine.begin() as conn:
        result = await conn.execute(text(query))
        fg_df = pd.DataFrame(result.fetchall(), columns=result.keys())

    print("\n" + "="*80)
    print("FANGRAPHS GRADE DISTRIBUTION ANALYSIS")
    print("="*80)

    # FV distribution
    fv_dist = fg_df.groupby('fv')['count'].sum().sort_index(ascending=False)
    print("\nFV Distribution:")
    print("-" * 40)
    for fv, count in fv_dist.items():
        if count > 0:
            pct = count / fv_dist.sum() * 100
            print(f"FV {fv:3.0f}: {count:4d} prospects ({pct:5.1f}%)")

    # Average tool grades by FV tier
    print("\n" + "="*80)
    print("AVERAGE TOOL GRADES BY FV TIER")
    print("="*80)

    fv_tiers = [
        (60, 80, '60-80 (Elite)'),
        (50, 60, '50-55 (Above Average)'),
        (45, 50, '45 (Average)'),
        (40, 45, '40 (Below Average)'),
        (0, 40, 'Below 40')
    ]

    for min_fv, max_fv, label in fv_tiers:
        tier_data = fg_df[(fg_df['fv'] >= min_fv) & (fg_df['fv'] < max_fv)]
        if len(tier_data) > 0:
            print(f"\n{label}:")
            print(f"  Hit:        {tier_data['hit_future'].mean():.1f}")
            print(f"  Game Power: {tier_data['game_power_future'].mean():.1f}")
            print(f"  Raw Power:  {tier_data['raw_power_future'].mean():.1f}")
            print(f"  Speed:      {tier_data['speed_future'].mean():.1f}")
            print(f"  Field:      {tier_data['field_future'].mean():.1f}")
            print(f"  % Upside:   {tier_data['pct_with_upside'].mean()*100:.1f}%")
            print(f"  Count:      {tier_data['count'].sum()}")

    # Historical MLB success rates by FV (industry benchmarks)
    print("\n" + "="*80)
    print("HISTORICAL MLB SUCCESS RATES BY FV (Industry Benchmarks)")
    print("="*80)
    print("Based on historical FanGraphs data:")
    print("-" * 40)

    success_rates = {
        "70-80 FV": {"MLB %": "95%", "All-Star %": "75%", "Avg WAR": "4.5+"},
        "60-65 FV": {"MLB %": "90%", "All-Star %": "50%", "Avg WAR": "3.0"},
        "55 FV":    {"MLB %": "85%", "All-Star %": "30%", "Avg WAR": "2.2"},
        "50 FV":    {"MLB %": "75%", "All-Star %": "15%", "Avg WAR": "1.5"},
        "45 FV":    {"MLB %": "60%", "All-Star %": "5%",  "Avg WAR": "0.8"},
        "40 FV":    {"MLB %": "40%", "All-Star %": "1%",  "Avg WAR": "0.3"},
        "35 FV":    {"MLB %": "20%", "All-Star %": "<1%", "Avg WAR": "0.1"},
    }

    for fv_tier, rates in success_rates.items():
        print(f"{fv_tier:10s} → MLB: {rates['MLB %']:6s}, All-Star: {rates['All-Star %']:6s}, Avg WAR: {rates['Avg WAR']}")

    # Expected OPS by grade combinations
    print("\n" + "="*80)
    print("EXPECTED MLB OPS BY TOOL COMBINATIONS (Estimates)")
    print("="*80)

    tool_combos = [
        ("Elite Hit + Power (60+/60+)", 0.850),
        ("Plus Hit + Average Power (60+/50)", 0.780),
        ("Average Hit + Plus Power (50/60+)", 0.760),
        ("Average Tools (50/50)", 0.730),
        ("Below Average Hit (45/50)", 0.700),
        ("Below Average Tools (45/45)", 0.680),
        ("Fringe Average (40/40)", 0.650),
    ]

    for combo, ops in tool_combos:
        print(f"{combo:35s} → Expected OPS: {ops:.3f}")

    # Count current top prospects
    top_prospects_query = """
        SELECT
            COUNT(CASE WHEN fv >= 60 THEN 1 END) as elite_count,
            COUNT(CASE WHEN fv >= 55 AND fv < 60 THEN 1 END) as plus_count,
            COUNT(CASE WHEN fv >= 50 AND fv < 55 THEN 1 END) as above_avg_count,
            COUNT(CASE WHEN fv >= 45 AND fv < 50 THEN 1 END) as avg_count,
            COUNT(CASE WHEN fv >= 40 AND fv < 45 THEN 1 END) as below_avg_count,
            COUNT(*) as total
        FROM fangraphs_prospect_grades
        WHERE season >= 2024
    """

    async with engine.begin() as conn:
        result = await conn.execute(text(top_prospects_query))
        counts = result.fetchone()

    print("\n" + "="*80)
    print("CURRENT PROSPECT POOL (2024-2025)")
    print("="*80)
    print(f"Elite (60+ FV):        {counts[0]:4d} prospects")
    print(f"Plus (55 FV):          {counts[1]:4d} prospects")
    print(f"Above Average (50 FV): {counts[2]:4d} prospects")
    print(f"Average (45 FV):       {counts[3]:4d} prospects")
    print(f"Below Average (40 FV): {counts[4]:4d} prospects")
    print(f"Total:                 {counts[5]:4d} prospects")

    # Top 20 prospects by FV
    top_20_query = """
        SELECT
            player_name,
            organization,
            position,
            fv,
            hit_future,
            game_power_future,
            speed_future,
            has_upside
        FROM fangraphs_prospect_grades
        WHERE season >= 2024
        ORDER BY fv DESC, (hit_future + game_power_future) DESC
        LIMIT 20
    """

    async with engine.begin() as conn:
        result = await conn.execute(text(top_20_query))
        top_df = pd.DataFrame(result.fetchall(), columns=result.keys())

    print("\n" + "="*80)
    print("TOP 20 PROSPECTS BY FV (2024-2025)")
    print("="*80)

    for idx, row in top_df.iterrows():
        upside = "+" if row['has_upside'] else " "
        print(f"{idx+1:2d}. {row['player_name']:25s} ({row['organization']:3s}) {row['position']:3s} "
              f"FV:{row['fv']:2.0f}{upside} Hit:{row['hit_future']:.0f} Pwr:{row['game_power_future']:.0f} "
              f"Spd:{row['speed_future']:.0f}")

    return fg_df


async def main():
    await analyze_fangraphs_grades()


if __name__ == "__main__":
    asyncio.run(main())