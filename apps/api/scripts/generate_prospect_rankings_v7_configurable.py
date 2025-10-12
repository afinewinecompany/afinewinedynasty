"""
Generate V7 Prospect Rankings with Configurable Weights

This script allows you to easily adjust the weights between:
- FanGraphs Expert Grades (scouting)
- V4 Performance-Based Rankings (MiLB stats)
- V5 ML Projection Rankings (ensemble predictions)

Usage:
  python generate_prospect_rankings_v7_configurable.py --fg 60 --v4 30 --v5 10
  python generate_prospect_rankings_v7_configurable.py --fg 40 --v4 50 --v5 10
"""

import pandas as pd
import numpy as np
import asyncio
from sqlalchemy import text
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine

# Import the core functions from the main V7 script
from generate_prospect_rankings_v7 import (
    load_v6_rankings,
    load_fangraphs_grades,
    get_mlb_graduates,
    calculate_fangraphs_score
)


async def generate_v7_configurable(fg_weight=0.50, v4_weight=0.40, v5_weight=0.10, output_suffix=''):
    """
    Generate V7 rankings with custom weights.

    Args:
        fg_weight: Weight for FanGraphs grades (0.0 to 1.0)
        v4_weight: Weight for V4 performance (0.0 to 1.0)
        v5_weight: Weight for V5 ML projection (0.0 to 1.0)
        output_suffix: Suffix for output filename
    """

    # Validate weights sum to 1.0
    total = fg_weight + v4_weight + v5_weight
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Weights must sum to 1.0, got {total}")

    print('=' * 80)
    print('PROSPECT RANKINGS V7: CONFIGURABLE WEIGHTS')
    print('=' * 80)
    print(f'\nFormula: {int(fg_weight*100)}% FanGraphs + {int(v4_weight*100)}% V4 + {int(v5_weight*100)}% V5')
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

    # Start with V6 as base, filter out MLB graduates
    v6_df['mlb_player_id'] = v6_df['mlb_player_id'].astype(str)
    df = v6_df[~v6_df['mlb_player_id'].isin(mlb_graduates)].copy()

    excluded_count = len(v6_df) - len(df)
    print(f'  Excluded {excluded_count} MLB graduates from V6')
    print(f'  Working with {len(df)} true prospects')

    # Merge FanGraphs grades
    fg_df['mlb_player_id'] = fg_df['mlb_player_id'].astype(str)
    fg_merge = fg_df[['mlb_player_id', 'player_name', 'fv', 'report_year', 'fg_score', 'fg_score_normalized']].copy()

    df = df.merge(
        fg_merge,
        on='mlb_player_id',
        how='left',
        suffixes=('', '_fg')
    )

    # Assign baseline for ungraded prospects
    baseline_fg_score = 25.0
    df['fg_score_normalized'] = df['fg_score_normalized'].fillna(baseline_fg_score)
    df['has_fg_grade'] = df['fv'].notna()
    df['player_name'] = df['player_name'].fillna(df['name'])

    print(f'  {df["has_fg_grade"].sum()} prospects with FanGraphs grades')
    print(f'  {(~df["has_fg_grade"]).sum()} prospects assigned baseline grade')

    # Normalize V4 and V5
    df['v4_normalized'] = (df['v4_score'] / df['v4_score'].max()) * 100
    df['v5_normalized'] = (df['v5_score'] / df['v5_score'].max()) * 100

    df['has_v4'] = df['v4_score'].notna()
    df['has_v5'] = df['v5_score'].notna()

    # Calculate V7 score with custom weights
    def calc_v7_score(row):
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

    # Show top 20
    print('\n' + '=' * 80)
    print('TOP 20 PROSPECTS')
    print('=' * 80)
    print(f'{"Rank":<6} {"Player":<25} {"FV":<4} {"FG":<7} {"V4":<7} {"V5":<7} {"V7":<7}')
    print('-' * 80)

    top_20 = df.head(20)
    for _, row in top_20.iterrows():
        rank = int(row['v7_rank'])
        name = row['player_name'][:24]
        fv = int(row['fv']) if pd.notna(row['fv']) else '-'
        fg = f"{row['fg_score_normalized']:.1f}"
        v4 = f"{row['v4_normalized']:.1f}"
        v5 = f"{row['v5_normalized']:.1f}"
        v7 = f"{row['v7_score']:.1f}"

        print(f'{rank:<6} {name:<25} {str(fv):<4} {fg:<7} {v4:<7} {v5:<7} {v7:<7}')

    # Show key test cases
    print('\n' + '=' * 80)
    print('KEY TEST CASES (Reimer vs Glod)')
    print('=' * 80)

    test_players = ['Reimer', 'Glod']
    for test_name in test_players:
        match = df[df['player_name'].str.contains(test_name, case=False, na=False)]
        if len(match) > 0:
            row = match.iloc[0]
            rank = int(row['v7_rank'])
            name = row['player_name'][:30]
            fv = int(row['fv']) if pd.notna(row['fv']) else 'Baseline'
            fg = row['fg_score_normalized']
            v4 = row['v4_normalized']
            v5 = row['v5_normalized']
            v7 = row['v7_score']

            print(f'{name:<30} Rank #{rank}')
            print(f'  FV:{fv} | FG:{fg:.2f} V4:{v4:.2f} V5:{v5:.2f} => V7:{v7:.2f}')

    # Export to CSV
    suffix = output_suffix if output_suffix else f'fg{int(fg_weight*100)}_v4{int(v4_weight*100)}_v5{int(v5_weight*100)}'
    csv_file = f'prospect_rankings_v7_{suffix}.csv'

    export_df = df[['v7_rank', 'mlb_player_id', 'player_name', 'fv', 'report_year',
                     'fg_score_normalized', 'v4_normalized', 'v5_normalized', 'v7_score']].copy()
    export_df.columns = ['rank', 'mlb_player_id', 'name', 'fv', 'fg_year', 'fg_score', 'v4_score', 'v5_score', 'v7_score']
    export_df.to_csv(csv_file, index=False)

    print(f'\n\nExported to {csv_file}')

    return df


async def main():
    parser = argparse.ArgumentParser(description='Generate V7 rankings with configurable weights')
    parser.add_argument('--fg', type=int, default=50, help='FanGraphs weight (0-100)')
    parser.add_argument('--v4', type=int, default=40, help='V4 performance weight (0-100)')
    parser.add_argument('--v5', type=int, default=10, help='V5 ML projection weight (0-100)')
    parser.add_argument('--output', type=str, default='', help='Output filename suffix')

    args = parser.parse_args()

    # Convert to decimals
    fg_weight = args.fg / 100.0
    v4_weight = args.v4 / 100.0
    v5_weight = args.v5 / 100.0

    print(f'\nGenerating rankings with weights: FG={args.fg}%, V4={args.v4}%, V5={args.v5}%\n')

    await generate_v7_configurable(fg_weight, v4_weight, v5_weight, args.output)


if __name__ == '__main__':
    asyncio.run(main())
