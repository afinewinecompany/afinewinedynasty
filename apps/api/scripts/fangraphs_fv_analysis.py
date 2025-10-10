"""
Simple FanGraphs FV analysis showing distributions and MLB outcome predictions.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine


async def analyze_fv_outcomes():
    """Analyze FV distributions and predict MLB outcomes."""

    print("\n" + "="*80)
    print("FANGRAPHS FV ANALYSIS - PREDICTING MLB SUCCESS")
    print("="*80)

    # Get FV distribution
    query = """
        SELECT
            fv,
            COUNT(*) as count,
            AVG(CASE WHEN has_upside THEN 1 ELSE 0 END) as pct_upside
        FROM fangraphs_prospect_grades
        WHERE fv IS NOT NULL
          AND season >= 2024
        GROUP BY fv
        ORDER BY fv DESC
    """

    async with engine.begin() as conn:
        result = await conn.execute(text(query))
        fv_df = pd.DataFrame(result.fetchall(), columns=result.keys())

    print("\n2024-2025 FV Distribution:")
    print("-" * 40)
    total = fv_df['count'].sum()
    for _, row in fv_df.iterrows():
        if row['count'] > 0:
            pct = row['count'] / total * 100
            upside_pct = row['pct_upside'] * 100
            print(f"FV {row['fv']:3.0f}: {row['count']:4d} prospects ({pct:5.1f}%), {upside_pct:4.1f}% with upside")

    # MLB outcome predictions by FV (industry benchmarks)
    print("\n" + "="*80)
    print("PREDICTED MLB OUTCOMES BY FV")
    print("="*80)

    fv_outcomes = {
        70: {"MLB%": 95, "AllStar%": 75, "AvgOPS": 0.850, "AvgWAR": 4.5, "Description": "Franchise Player"},
        65: {"MLB%": 92, "AllStar%": 60, "AvgOPS": 0.820, "AvgWAR": 3.5, "Description": "All-Star"},
        60: {"MLB%": 90, "AllStar%": 45, "AvgOPS": 0.800, "AvgWAR": 3.0, "Description": "Plus Regular"},
        55: {"MLB%": 85, "AllStar%": 30, "AvgOPS": 0.780, "AvgWAR": 2.2, "Description": "Above Average Regular"},
        50: {"MLB%": 75, "AllStar%": 15, "AvgOPS": 0.750, "AvgWAR": 1.5, "Description": "Average Regular"},
        45: {"MLB%": 60, "AllStar%": 5,  "AvgOPS": 0.720, "AvgWAR": 0.8, "Description": "Below Average Regular"},
        40: {"MLB%": 40, "AllStar%": 1,  "AvgOPS": 0.680, "AvgWAR": 0.3, "Description": "Bench/Utility"},
        35: {"MLB%": 20, "AllStar%": 0,  "AvgOPS": 0.650, "AvgWAR": 0.1, "Description": "Org Player"},
    }

    print("\nFV | MLB% | AS% | Proj OPS | Proj WAR | Description")
    print("-" * 65)
    for fv, outcomes in fv_outcomes.items():
        count = fv_df[fv_df['fv'] == fv]['count'].sum() if not fv_df.empty else 0
        print(f"{fv:2d} | {outcomes['MLB%']:3d}% | {outcomes['AllStar%']:2d}% | {outcomes['AvgOPS']:.3f}   | "
              f"{outcomes['AvgWAR']:4.1f}     | {outcomes['Description']} ({count} prospects)")

    # Apply predictions to current prospects
    query_prospects = """
        SELECT
            player_name,
            organization,
            position,
            fv,
            has_upside,
            season
        FROM fangraphs_prospect_grades
        WHERE fv IS NOT NULL
          AND season >= 2024
          AND fv >= 50
        ORDER BY fv DESC, player_name
    """

    async with engine.begin() as conn:
        result = await conn.execute(text(query_prospects))
        prospects_df = pd.DataFrame(result.fetchall(), columns=result.keys())

    # Add predictions
    prospects_df['predicted_ops'] = prospects_df['fv'].map(lambda x: fv_outcomes.get(int(x), {}).get('AvgOPS', 0.700))
    prospects_df['mlb_probability'] = prospects_df['fv'].map(lambda x: fv_outcomes.get(int(x), {}).get('MLB%', 50))
    prospects_df['predicted_war'] = prospects_df['fv'].map(lambda x: fv_outcomes.get(int(x), {}).get('AvgWAR', 0.5))

    # Adjust for upside
    prospects_df.loc[prospects_df['has_upside'] == True, 'predicted_ops'] *= 1.05
    prospects_df.loc[prospects_df['has_upside'] == True, 'predicted_war'] *= 1.10

    # Show top prospects
    print("\n" + "="*80)
    print("TOP 50+ FV PROSPECTS WITH MLB PROJECTIONS")
    print("="*80)

    print("\n{:<25} {:<4} {:<4} {:>3} {:>7} {:>8} {:>8}".format(
        "Player", "Org", "Pos", "FV", "Upside", "Proj OPS", "Proj WAR"))
    print("-" * 70)

    top_prospects = prospects_df.nlargest(30, 'fv')
    for _, p in top_prospects.iterrows():
        upside = "Yes" if p['has_upside'] else "No"
        print(f"{p['player_name'][:25]:<25} {p['organization']:<4} {p['position']:<4} "
              f"{p['fv']:3.0f} {upside:>7} {p['predicted_ops']:8.3f} {p['predicted_war']:8.1f}")

    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)

    fv_tiers = [
        (60, 80, "Elite (60+)"),
        (55, 60, "Plus (55)"),
        (50, 55, "Above Average (50)"),
        (45, 50, "Average (45)"),
        (40, 45, "Below Average (40)"),
    ]

    for min_fv, max_fv, label in fv_tiers:
        tier = prospects_df[(prospects_df['fv'] >= min_fv) & (prospects_df['fv'] < max_fv)]
        if len(tier) > 0:
            avg_ops = tier['predicted_ops'].mean()
            avg_war = tier['predicted_war'].mean()
            count = len(tier)
            print(f"{label:20s}: {count:3d} prospects, Avg Proj OPS: {avg_ops:.3f}, Avg Proj WAR: {avg_war:.1f}")

    # Save predictions
    prospects_df.to_csv('fangraphs_fv_predictions.csv', index=False)
    print(f"\nPredictions saved to fangraphs_fv_predictions.csv")

    return prospects_df


async def main():
    await analyze_fv_outcomes()


if __name__ == "__main__":
    asyncio.run(main())