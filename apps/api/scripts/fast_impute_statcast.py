"""Fast Statcast imputation using bulk operations."""
import asyncio
import pandas as pd
import numpy as np
import pickle
from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine

async def main():
    print('=' * 80)
    print('FAST STATCAST IMPUTATION')
    print('=' * 80)

    # Load models
    print('\n1. Loading trained models...')
    with open('statcast_imputation_models.pkl', 'rb') as f:
        model_data = pickle.load(f)
        models = model_data['models']
        feature_names = model_data['feature_names']
    print(f'   [OK] Loaded {len(models)} models')

    # Load hitter data
    print('\n2. Loading hitter data...')
    async with engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT
                m.mlb_player_id,
                SUM(m.plate_appearances) as total_pa,
                SUM(m.at_bats) as total_ab,
                SUM(m.hits) as total_h,
                SUM(m.doubles) as total_doubles,
                SUM(m.triples) as total_triples,
                SUM(m.home_runs) as total_hr,
                SUM(m.walks) as total_bb,
                SUM(m.strikeouts) as total_so,
                SUM(m.stolen_bases) as total_sb
            FROM milb_game_logs m
            WHERE m.plate_appearances > 0
            AND (COALESCE(m.games_pitched, 0) = 0)
            GROUP BY m.mlb_player_id
            HAVING SUM(m.plate_appearances) >= 100
        '''))
        rows = result.fetchall()

    df = pd.DataFrame(rows, columns=[
        'mlb_player_id', 'total_pa', 'total_ab', 'total_h', 'total_doubles',
        'total_triples', 'total_hr', 'total_bb', 'total_so', 'total_sb'
    ])
    print(f'   [OK] Loaded {len(df)} hitters')

    # Calculate features
    print('\n3. Calculating traditional features...')
    for col in df.columns:
        if col != 'mlb_player_id':
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['avg'] = df['total_h'] / df['total_ab'].replace(0, np.nan)
    df['obp'] = (df['total_h'] + df['total_bb']) / df['total_pa'].replace(0, np.nan)
    df['iso'] = ((df['total_doubles'] + df['total_triples']*2 + df['total_hr']*3) /
                 df['total_ab'].replace(0, np.nan))
    df['slg'] = ((df['total_h'] + df['total_doubles'] + df['total_triples']*2 + df['total_hr']*3) /
                 df['total_ab'].replace(0, np.nan))
    df['ops'] = df['obp'] + df['slg']
    df['bb_rate'] = df['total_bb'] / df['total_pa']
    df['so_rate'] = df['total_so'] / df['total_pa']
    df['contact_rate'] = 1 - df['so_rate']
    df['bb_so_ratio'] = df['total_bb'] / df['total_so'].replace(0, np.nan)
    df['hr_rate'] = df['total_hr'] / df['total_pa']
    df['hr_per_fb'] = df['total_hr'] / (df['total_hr'] + df['total_doubles'] + df['total_triples']).replace(0, np.nan)
    df['xbh_rate'] = (df['total_doubles'] + df['total_triples'] + df['total_hr']) / df['total_ab'].replace(0, np.nan)
    df['sb_rate'] = df['total_sb'] / df['total_pa']
    df['log_pa'] = np.log1p(df['total_pa'])
    df = df.fillna(0)
    print('   [OK] Features calculated')

    # Predict Statcast
    print('\n4. Predicting Statcast metrics with ML models...')
    X = df[feature_names]
    for metric, model in models.items():
        df[metric] = model.predict(X)
    print('   [OK] Predictions complete')

    # Save to database
    print('\n5. Saving to database (bulk insert)...')
    async with engine.begin() as conn:
        # Create table
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS milb_statcast_metrics_imputed (
                mlb_player_id INTEGER PRIMARY KEY,
                avg_ev FLOAT,
                max_ev FLOAT,
                hard_hit_pct FLOAT,
                barrel_pct FLOAT,
                avg_la FLOAT,
                statcast_source VARCHAR(20) DEFAULT 'imputed',
                created_at TIMESTAMP DEFAULT NOW()
            )
        '''))

        # Clear existing
        await conn.execute(text('TRUNCATE TABLE milb_statcast_metrics_imputed'))

        # Bulk insert (batch of 1000)
        insert_sql = text('''
            INSERT INTO milb_statcast_metrics_imputed
            (mlb_player_id, avg_ev, max_ev, hard_hit_pct, barrel_pct, avg_la)
            VALUES (:mlb_player_id, :avg_ev, :max_ev, :hard_hit_pct, :barrel_pct, :avg_la)
        ''')

        records = df[['mlb_player_id', 'avg_ev', 'max_ev', 'hard_hit_pct', 'barrel_pct', 'avg_la']].to_dict('records')

        # Insert in batches
        batch_size = 500
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            await conn.execute(insert_sql, batch)
            print(f'   Inserted {min(i+batch_size, len(records))}/{len(records)} records...')

    print(f'\n[COMPLETE] Imputed Statcast for {len(df)} hitters')
    print('=' * 80)

if __name__ == '__main__':
    asyncio.run(main())
