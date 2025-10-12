"""Analyze MiLB to MLB transitions to build age-aware prediction model."""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine

async def main():
    print('MILB TO MLB TRANSITION ANALYSIS')
    print('=' * 80)

    # Find players with BOTH MiLB and MLB data
    async with engine.connect() as conn:
        result = await conn.execute(text('''
            WITH milb_players AS (
                SELECT DISTINCT mlb_player_id
                FROM milb_game_logs
                WHERE plate_appearances > 0
                AND (COALESCE(games_pitched, 0) = 0)
            ),
            mlb_players AS (
                SELECT DISTINCT mlb_player_id
                FROM mlb_game_logs
                WHERE plate_appearances > 0
            )
            SELECT COUNT(DISTINCT m.mlb_player_id) as transition_players
            FROM milb_players m
            INNER JOIN mlb_players mlb ON m.mlb_player_id = mlb.mlb_player_id
        '''))
        transition_count = result.scalar()

    print(f'\n1. Players with BOTH MiLB + MLB data: {transition_count}')

    # Get detailed transition data
    async with engine.connect() as conn:
        result = await conn.execute(text('''
            WITH milb_seasons AS (
                SELECT
                    m.mlb_player_id,
                    p.name as full_name,
                    m.season - EXTRACT(YEAR FROM p.birth_date) as age,
                    m.level,
                    m.season,
                    SUM(m.plate_appearances) as pa,
                    SUM(m.at_bats) as ab,
                    SUM(m.hits) as h,
                    SUM(m.doubles) as doubles,
                    SUM(m.triples) as triples,
                    SUM(m.home_runs) as hr,
                    SUM(m.walks) as bb,
                    SUM(m.strikeouts) as so,
                    SUM(m.stolen_bases) as sb
                FROM milb_game_logs m
                INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                WHERE m.plate_appearances > 0
                AND (COALESCE(m.games_pitched, 0) = 0)
                AND p.birth_date IS NOT NULL
                GROUP BY m.mlb_player_id, p.name, p.birth_date, m.level, m.season
                HAVING SUM(m.plate_appearances) >= 50
            ),
            mlb_seasons AS (
                SELECT
                    m.mlb_player_id,
                    p.name as full_name,
                    m.season - EXTRACT(YEAR FROM p.birth_date) as age,
                    m.season,
                    SUM(m.plate_appearances) as pa,
                    SUM(m.at_bats) as ab,
                    SUM(m.hits) as h,
                    SUM(m.doubles) as doubles,
                    SUM(m.triples) as triples,
                    SUM(m.home_runs) as hr,
                    SUM(m.walks) as bb,
                    SUM(m.strikeouts) as so,
                    SUM(m.stolen_bases) as sb
                FROM mlb_game_logs m
                INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                WHERE m.plate_appearances > 0
                AND p.birth_date IS NOT NULL
                GROUP BY m.mlb_player_id, p.name, p.birth_date, m.season
                HAVING SUM(m.plate_appearances) >= 50
            )
            SELECT
                milb.mlb_player_id,
                milb.full_name,
                milb.age as milb_age,
                milb.level as milb_level,
                milb.season as milb_season,
                milb.pa as milb_pa,
                milb.ab as milb_ab,
                milb.h as milb_h,
                milb.doubles as milb_2b,
                milb.triples as milb_3b,
                milb.hr as milb_hr,
                milb.bb as milb_bb,
                milb.so as milb_so,
                milb.sb as milb_sb,
                mlb.age as mlb_age,
                mlb.season as mlb_season,
                mlb.pa as mlb_pa,
                mlb.ab as mlb_ab,
                mlb.h as mlb_h,
                mlb.doubles as mlb_2b,
                mlb.triples as mlb_3b,
                mlb.hr as mlb_hr,
                mlb.bb as mlb_bb,
                mlb.so as mlb_so,
                mlb.sb as mlb_sb
            FROM milb_seasons milb
            INNER JOIN mlb_seasons mlb ON milb.mlb_player_id = mlb.mlb_player_id
            WHERE mlb.season >= milb.season
            AND mlb.age >= milb.age
            ORDER BY milb.mlb_player_id, milb.season, mlb.season
        '''))
        rows = result.fetchall()

    df = pd.DataFrame(rows, columns=[
        'mlb_player_id', 'full_name',
        'milb_age', 'milb_level', 'milb_season', 'milb_pa', 'milb_ab', 'milb_h',
        'milb_2b', 'milb_3b', 'milb_hr', 'milb_bb', 'milb_so', 'milb_sb',
        'mlb_age', 'mlb_season', 'mlb_pa', 'mlb_ab', 'mlb_h',
        'mlb_2b', 'mlb_3b', 'mlb_hr', 'mlb_bb', 'mlb_so', 'mlb_sb'
    ])

    print(f'\n2. Transition records found: {len(df)}')

    # Calculate stats
    for prefix in ['milb', 'mlb']:
        df[f'{prefix}_avg'] = df[f'{prefix}_h'] / df[f'{prefix}_ab'].replace(0, np.nan)
        df[f'{prefix}_obp'] = (df[f'{prefix}_h'] + df[f'{prefix}_bb']) / df[f'{prefix}_pa'].replace(0, np.nan)
        df[f'{prefix}_slg'] = (
            df[f'{prefix}_h'] + df[f'{prefix}_2b'] + df[f'{prefix}_3b']*2 + df[f'{prefix}_hr']*3
        ) / df[f'{prefix}_ab'].replace(0, np.nan)
        df[f'{prefix}_ops'] = df[f'{prefix}_obp'] + df[f'{prefix}_slg']
        df[f'{prefix}_iso'] = df[f'{prefix}_slg'] - df[f'{prefix}_avg']
        df[f'{prefix}_bb_rate'] = df[f'{prefix}_bb'] / df[f'{prefix}_pa']
        df[f'{prefix}_k_rate'] = df[f'{prefix}_so'] / df[f'{prefix}_pa']

    df = df.fillna(0)

    # Calculate age gap
    df['age_gap'] = df['mlb_age'] - df['milb_age']

    # Save
    df.to_csv('milb_to_mlb_transitions.csv', index=False)
    print(f'\n3. Saved to milb_to_mlb_transitions.csv')

    # Analysis
    print('\n' + '=' * 80)
    print('TRANSITION STATISTICS')
    print('=' * 80)

    print(f'\nUnique players: {df["mlb_player_id"].nunique()}')
    print(f'\nAge distribution at MiLB:')
    print(df['milb_age'].value_counts().sort_index().head(10))

    print(f'\nLevel distribution:')
    print(df['milb_level'].value_counts())

    print(f'\nAge gap distribution (MiLB age -> MLB age):')
    print(df['age_gap'].value_counts().sort_index().head(10))

    # Sample transitions
    print('\n' + '=' * 80)
    print('SAMPLE TRANSITIONS (AA age 20-21 -> MLB)')
    print('=' * 80)

    sample = df[
        (df['milb_level'].isin(['AA', 'AAA'])) &
        (df['milb_age'].between(20, 21)) &
        (df['age_gap'] <= 2)
    ].head(20)

    if len(sample) > 0:
        print(sample[[
            'full_name', 'milb_age', 'milb_level', 'milb_ops',
            'mlb_age', 'age_gap', 'mlb_ops'
        ]].to_string(index=False))

    print(f'\n[COMPLETE] Found {len(df)} MiLB->MLB transitions')

if __name__ == '__main__':
    asyncio.run(main())
