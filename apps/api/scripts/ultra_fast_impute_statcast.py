"""Ultra-fast Statcast imputation - optimized for speed."""
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
    print('FAST STATCAST IMPUTATION')
    print('=' * 60)

    # Load models
    print('\n1. Loading models...')
    with open('statcast_imputation_models.pkl', 'rb') as f:
        model_data = pickle.load(f)
        models = model_data['models']
        feature_names = model_data['feature_names']
    print(f'   [OK] Loaded {len(models)} models')

    # Load hitter data in ONE query
    print('\n2. Loading hitter data...')
    async with engine.connect() as conn:
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
    print('\n3. Calculating features...')
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
    print('   [OK]')

    # Predict
    print('\n4. Predicting Statcast...')
    X = df[feature_names]
    for metric, model in models.items():
        df[metric] = model.predict(X)
    print('   [OK]')

    # Save in ONE transaction
    print('\n5. Saving to database...')
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
        print('   [OK] Table created')

        # Clear
        await conn.execute(text('DELETE FROM milb_statcast_metrics_imputed'))
        print('   [OK] Cleared old data')

        # Bulk insert
        records = df[['mlb_player_id', 'avg_ev', 'max_ev', 'hard_hit_pct', 'barrel_pct', 'avg_la']].to_dict('records')

        batch_size = 1000
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            await conn.execute(
                text('''
                    INSERT INTO milb_statcast_metrics_imputed
                    (mlb_player_id, avg_ev, max_ev, hard_hit_pct, barrel_pct, avg_la)
                    VALUES (:mlb_player_id, :avg_ev, :max_ev, :hard_hit_pct, :barrel_pct, :avg_la)
                '''),
                batch
            )
            print(f'   Inserted {min(i+batch_size, len(records))}/{len(records)}')

    print(f'\n[COMPLETE] Imputed {len(df)} hitters')
    print('=' * 60)

if __name__ == '__main__':
    asyncio.run(main())
