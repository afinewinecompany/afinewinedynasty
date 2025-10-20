"""
Unified MLB Expectation Prediction API
======================================

Predict MLB expectation for any prospect (hitter or pitcher) using saved production models.

Usage:
    python predict_mlb_expectation.py --prospect-id 12345 --year 2024
    python predict_mlb_expectation.py --prospect-id 12345 --year 2024 --output json

Returns prediction with probabilities for all 3 classes.
"""

import asyncio
import asyncpg
import argparse
import pickle
import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"

# Model paths
HITTER_MODEL_PATH = Path('models/hitter_model_3class.pkl')
PITCHER_MODEL_PATH = Path('models/pitcher_model_3class.pkl')


def load_model(player_type):
    """Load saved model artifacts."""
    if player_type == 'hitter':
        model_path = HITTER_MODEL_PATH
    else:
        model_path = PITCHER_MODEL_PATH

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}. Run save_production_models.py first.")

    with open(model_path, 'rb') as f:
        artifacts = pickle.load(f)

    return artifacts


async def get_prospect_info(conn, prospect_id):
    """Get prospect basic info and determine if hitter or pitcher."""
    query = """
        SELECT
            p.id,
            p.name,
            p.position,
            p.fg_player_id,
            CASE
                WHEN p.position IN ('SP', 'RP', 'LHP', 'RHP') THEN 'pitcher'
                ELSE 'hitter'
            END as player_type
        FROM prospects p
        WHERE p.id = $1
    """

    row = await conn.fetchrow(query, prospect_id)

    if not row:
        raise ValueError(f"Prospect {prospect_id} not found in database")

    return dict(row)


async def get_hitter_features(conn, prospect_id, year):
    """Get hitter features from database."""
    query = """
        WITH fangraphs_data AS (
            SELECT
                fg.fangraphs_player_id,
                fg.hit_current, fg.hit_future,
                fg.game_power_current, fg.game_power_future,
                fg.raw_power_current, fg.raw_power_future,
                fg.speed_current, fg.speed_future,
                fg.fielding_current, fg.fielding_future,
                fg.arm_current, fg.arm_future,
                fg.fangraphs_fv,
                fg.data_year,
                pa.frame_current, pa.frame_future,
                pa.athleticism_current, pa.athleticism_future
            FROM fangraphs_hitter_grades fg
            LEFT JOIN fangraphs_physical_attributes pa
                ON fg.fangraphs_player_id = pa.fangraphs_player_id
                AND fg.data_year = pa.data_year
            WHERE fg.data_year = $2
        ),
        milb_stats AS (
            SELECT
                mlb_player_id,
                season,
                AVG(games_played) as avg_games,
                AVG(plate_appearances) as avg_pa,
                AVG(runs) as avg_runs,
                AVG(hits) as avg_hits,
                AVG(doubles) as avg_2b,
                AVG(triples) as avg_3b,
                AVG(home_runs) as avg_hr,
                AVG(rbis) as avg_rbi,
                AVG(walks) as avg_bb,
                AVG(strikeouts) as avg_so,
                AVG(stolen_bases) as avg_sb,
                AVG(caught_stealing) as avg_cs,
                AVG(batting_avg) as avg_ba,
                AVG(on_base_pct) as avg_obp,
                AVG(slugging_pct) as avg_slg,
                AVG(on_base_plus_slugging) as avg_ops
            FROM milb_batter_game_logs
            WHERE season = $2
            GROUP BY mlb_player_id, season
        )
        SELECT
            p.id as prospect_id,
            p.name,
            p.position,
            fd.*,
            ms.*
        FROM prospects p
        LEFT JOIN fangraphs_data fd ON p.fg_player_id = fd.fangraphs_player_id
        LEFT JOIN milb_stats ms ON p.mlb_player_id = ms.mlb_player_id
        WHERE p.id = $1
    """

    row = await conn.fetchrow(query, prospect_id, year)

    if not row:
        raise ValueError(f"No data found for prospect {prospect_id} in year {year}")

    return dict(row)


async def get_pitcher_features(conn, prospect_id, year):
    """Get pitcher features from database."""
    query = """
        WITH fangraphs_data AS (
            SELECT
                fg.fangraphs_player_id,
                fg.fastball_current, fg.fastball_future,
                fg.curveball_current, fg.curveball_future,
                fg.slider_current, fg.slider_future,
                fg.changeup_current, fg.changeup_future,
                fg.other_current, fg.other_future,
                fg.command_current, fg.command_future,
                fg.fangraphs_fv,
                fg.data_year,
                pa.frame_current, pa.frame_future,
                pa.athleticism_current, pa.athleticism_future
            FROM fangraphs_pitcher_grades fg
            LEFT JOIN fangraphs_physical_attributes pa
                ON fg.fangraphs_player_id = pa.fangraphs_player_id
                AND fg.data_year = pa.data_year
            WHERE fg.data_year = $2
        ),
        milb_stats AS (
            SELECT
                mlb_player_id,
                season,
                AVG(games_played) as avg_games,
                AVG(games_started) as avg_gs,
                AVG(wins) as avg_w,
                AVG(losses) as avg_l,
                AVG(saves) as avg_sv,
                AVG(innings_pitched) as avg_ip,
                AVG(hits_allowed) as avg_h,
                AVG(runs_allowed) as avg_r,
                AVG(earned_runs) as avg_er,
                AVG(walks) as avg_bb,
                AVG(strikeouts) as avg_so,
                AVG(home_runs_allowed) as avg_hr,
                AVG(era) as avg_era,
                AVG(whip) as avg_whip
            FROM milb_pitcher_game_logs
            WHERE season = $2
            GROUP BY mlb_player_id, season
        )
        SELECT
            p.id as prospect_id,
            p.name,
            p.position,
            fd.*,
            ms.*
        FROM prospects p
        LEFT JOIN fangraphs_data fd ON p.fg_player_id = fd.fangraphs_player_id
        LEFT JOIN milb_stats ms ON p.mlb_player_id = ms.mlb_player_id
        WHERE p.id = $1
    """

    row = await conn.fetchrow(query, prospect_id, year)

    if not row:
        raise ValueError(f"No data found for prospect {prospect_id} in year {year}")

    return dict(row)


def prepare_features(data_dict, artifacts):
    """Prepare features for prediction."""
    # Remove metadata columns
    metadata_cols = ['prospect_id', 'name', 'position', 'data_year', 'fangraphs_player_id', 'fangraphs_fv', 'mlb_player_id', 'season']

    feature_data = {k: v for k, v in data_dict.items() if k not in metadata_cols}

    # Create dataframe with all required columns
    df = pd.DataFrame([feature_data])

    # Align columns with training data
    for col in artifacts['feature_columns']:
        if col not in df.columns:
            df[col] = np.nan

    df = df[artifacts['feature_columns']]

    # Impute and scale
    X_imputed = artifacts['imputer'].transform(df)
    X_scaled = artifacts['scaler'].transform(X_imputed)

    return X_scaled


async def predict(prospect_id, year, output_format='text'):
    """Main prediction function."""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get prospect info
        prospect_info = await get_prospect_info(conn, prospect_id)
        player_type = prospect_info['player_type']

        # Load appropriate model
        artifacts = load_model(player_type)

        # Get features
        if player_type == 'hitter':
            features = await get_hitter_features(conn, prospect_id, year)
        else:
            features = await get_pitcher_features(conn, prospect_id, year)

        # Prepare features
        X = prepare_features(features, artifacts)

        # Make prediction
        prediction = artifacts['model'].predict(X)[0]
        probabilities = artifacts['model'].predict_proba(X)[0]

        # Create result
        result = {
            'prospect_id': prospect_id,
            'name': prospect_info['name'],
            'position': prospect_info['position'],
            'player_type': player_type,
            'year': year,
            'prediction': {
                'class': int(prediction),
                'label': artifacts['class_names'][prediction],
                'probabilities': {
                    artifacts['class_names'][i]: float(prob)
                    for i, prob in enumerate(probabilities)
                }
            },
            'timestamp': datetime.now().isoformat()
        }

        if output_format == 'json':
            print(json.dumps(result, indent=2))
        else:
            print("\n" + "="*80)
            print("MLB EXPECTATION PREDICTION")
            print("="*80)
            print(f"\nProspect: {result['name']} ({result['position']})")
            print(f"Player Type: {result['player_type'].title()}")
            print(f"Year: {result['year']}")
            print(f"\nPrediction: {result['prediction']['label']}")
            print(f"\nProbabilities:")
            for class_name, prob in result['prediction']['probabilities'].items():
                print(f"  {class_name:<20} {prob:.1%}")
            print("\n" + "="*80)

        return result

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description='Predict MLB expectation for a prospect')
    parser.add_argument('--prospect-id', type=int, required=True, help='Prospect ID')
    parser.add_argument('--year', type=int, required=True, help='Year for prediction')
    parser.add_argument('--output', choices=['text', 'json'], default='text', help='Output format')

    args = parser.parse_args()

    try:
        result = asyncio.run(predict(args.prospect_id, args.year, args.output))
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
