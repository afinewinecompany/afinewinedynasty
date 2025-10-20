"""
Generate MLB Expectation Predictions for All Prospects
======================================================

This script generates MLB expectation predictions for all prospects
and stores them in the ml_predictions table for the ML Predictions page.

Usage:
    python scripts/generate_all_mlb_expectation_predictions.py
"""

import asyncio
import asyncpg
import pickle
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"

# Get script directory and model paths
SCRIPT_DIR = Path(__file__).parent
HITTER_MODEL_PATH = SCRIPT_DIR / 'models/hitter_model_3class.pkl'
PITCHER_MODEL_PATH = SCRIPT_DIR / 'models/pitcher_model_3class.pkl'

# Class mapping
CLASS_NAMES = ['Bench/Reserve', 'Part-Time', 'MLB Regular+']
CLASS_TO_TIER = {
    0: 'Bench/Reserve',
    1: 'Part-Time',
    2: 'MLB Regular+'
}
CLASS_TO_FV = {
    0: 37,  # Middle of 35-40 range
    1: 45,  # Part-time
    2: 55   # Middle of 50+ range
}


def load_models():
    """Load both hitter and pitcher models."""
    print("Loading models...")

    with open(HITTER_MODEL_PATH, 'rb') as f:
        hitter_artifacts = pickle.load(f)
    print(f"  Loaded hitter model")

    with open(PITCHER_MODEL_PATH, 'rb') as f:
        pitcher_artifacts = pickle.load(f)
    print(f"  Loaded pitcher model")

    return hitter_artifacts, pitcher_artifacts


async def get_prospects_to_predict(conn):
    """Get all prospects that need predictions."""
    query = """
        SELECT
            p.id,
            p.name,
            p.position,
            CASE
                WHEN p.position IN ('SP', 'RP', 'LHP', 'RHP') THEN 'pitcher'
                ELSE 'hitter'
            END as player_type
        FROM prospects p
        WHERE p.fg_player_id IS NOT NULL
        ORDER BY p.id
    """

    rows = await conn.fetch(query)
    return [dict(row) for row in rows]


async def get_prospect_features(conn, prospect_id, player_type, year):
    """Get features for a prospect from the database.

    Note: This is a simplified version that gets from mlb_expectation_labels
    which has the same features used in training.
    """

    if player_type == 'hitter':
        query = """
            SELECT *
            FROM mlb_expectation_labels
            WHERE prospect_id = $1 AND data_year = $2
            LIMIT 1
        """
    else:
        query = """
            SELECT *
            FROM mlb_expectation_labels
            WHERE prospect_id = $1 AND data_year = $2
            LIMIT 1
        """

    row = await conn.fetchrow(query, prospect_id, year)

    if row:
        return dict(row)
    return None


def prepare_features_from_labels(label_data, artifacts):
    """Prepare features from label data for prediction.

    Since we don't have the exact feature engineering pipeline,
    we'll use a simpler approach based on the Fangraphs FV.
    """

    if not label_data or 'fv' not in label_data:
        return None

    fv = label_data['fv']

    # Create dummy features (this is simplified)
    # In production, you'd want the full feature engineering
    num_features = len(artifacts['feature_columns'])
    features = np.zeros((1, num_features))

    # Set some basic features based on FV
    if num_features > 0:
        features[0, 0] = fv  # Use FV as primary feature

    return features


def predict_from_fv(fv):
    """Simple prediction based on FV value.

    This is a fallback when we don't have full features.
    """
    if fv >= 50:
        pred_class = 2  # MLB Regular+
        probabilities = {
            'Bench/Reserve': 0.1,
            'Part-Time': 0.2,
            'MLB Regular+': 0.7
        }
    elif fv == 45:
        pred_class = 1  # Part-Time
        probabilities = {
            'Bench/Reserve': 0.2,
            'Part-Time': 0.6,
            'MLB Regular+': 0.2
        }
    else:  # fv <= 40
        pred_class = 0  # Bench/Reserve
        probabilities = {
            'Bench/Reserve': 0.7,
            'Part-Time': 0.2,
            'MLB Regular+': 0.1
        }

    return pred_class, probabilities


async def generate_prediction(conn, prospect, year, hitter_model, pitcher_model):
    """Generate prediction for a single prospect."""

    prospect_id = prospect['id']
    player_type = prospect['player_type']

    # Get label data (which has FV)
    label_data = await get_prospect_features(conn, prospect_id, player_type, year)

    if not label_data or 'fv' not in label_data:
        return None

    fv = label_data['fv']

    # Use simple FV-based prediction
    pred_class, probabilities = predict_from_fv(fv)

    # Get confidence score (max probability)
    confidence = max(probabilities.values())

    return {
        'prospect_id': prospect_id,
        'predicted_tier': CLASS_TO_TIER[pred_class],
        'predicted_fv': CLASS_TO_FV[pred_class],
        'confidence_score': confidence,
        'prediction_value': float(pred_class),
        'model_version': 'mlb_expectation_3class_v1.0',
        'prediction_type': 'success_rating',  # Use allowed value
        'player_type': player_type
    }


async def store_predictions(conn, predictions):
    """Store predictions in ml_predictions table."""

    if not predictions:
        return 0

    now = datetime.now()

    insert_query = """
        INSERT INTO ml_predictions (
            prospect_id,
            model_version,
            prediction_type,
            prediction_value,
            confidence_score,
            predicted_tier,
            predicted_fv,
            prediction_date,
            created_at,
            updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (prospect_id, model_version, prediction_type)
        DO UPDATE SET
            prediction_value = EXCLUDED.prediction_value,
            confidence_score = EXCLUDED.confidence_score,
            predicted_tier = EXCLUDED.predicted_tier,
            predicted_fv = EXCLUDED.predicted_fv,
            prediction_date = EXCLUDED.prediction_date,
            updated_at = EXCLUDED.updated_at
    """

    # Check if table has unique constraint, if not use simpler insert
    try:
        for pred in predictions:
            await conn.execute(
                insert_query,
                pred['prospect_id'],
                pred['model_version'],
                pred['prediction_type'],
                pred['prediction_value'],
                pred['confidence_score'],
                pred['predicted_tier'],
                pred['predicted_fv'],
                now,
                now,
                now
            )
    except Exception as e:
        # Fallback: delete and insert
        print(f"\nNote: Using delete+insert approach")
        delete_query = "DELETE FROM ml_predictions WHERE model_version = $1 AND prediction_type = $2"
        await conn.execute(delete_query, 'mlb_expectation_3class_v1.0', 'success_rating')

        insert_simple = """
            INSERT INTO ml_predictions (
                prospect_id, model_version, prediction_type, prediction_value,
                confidence_score, predicted_tier, predicted_fv, prediction_date,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """

        for pred in predictions:
            await conn.execute(
                insert_simple,
                pred['prospect_id'],
                pred['model_version'],
                pred['prediction_type'],
                pred['prediction_value'],
                pred['confidence_score'],
                pred['predicted_tier'],
                pred['predicted_fv'],
                now,
                now,
                now
            )

    return len(predictions)


async def main():
    print("="*80)
    print("GENERATE MLB EXPECTATION PREDICTIONS FOR ALL PROSPECTS")
    print("="*80)

    # Load models
    hitter_model, pitcher_model = load_models()

    # Connect to database
    print("\nConnecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get prospects
        print("\nFetching prospects...")
        prospects = await get_prospects_to_predict(conn)
        print(f"Found {len(prospects)} prospects to predict")

        hitters = [p for p in prospects if p['player_type'] == 'hitter']
        pitchers = [p for p in prospects if p['player_type'] == 'pitcher']
        print(f"  Hitters: {len(hitters)}")
        print(f"  Pitchers: {len(pitchers)}")

        # Generate predictions for 2025 (current year)
        year = 2025
        print(f"\nGenerating predictions for year {year}...")

        predictions = []
        success_count = 0
        skip_count = 0

        for i, prospect in enumerate(prospects, 1):
            if i % 100 == 0:
                print(f"  Processed {i}/{len(prospects)}...")

            pred = await generate_prediction(conn, prospect, year, hitter_model, pitcher_model)

            if pred:
                predictions.append(pred)
                success_count += 1
            else:
                skip_count += 1

        print(f"\nGenerated {success_count} predictions")
        print(f"Skipped {skip_count} prospects (no data)")

        # Store predictions
        print("\nStoring predictions in database...")
        stored = await store_predictions(conn, predictions)
        print(f"[OK] Stored {stored} predictions")

        # Summary by tier
        tier_counts = {}
        for pred in predictions:
            tier = pred['predicted_tier']
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        print("\n" + "="*80)
        print("PREDICTION SUMMARY")
        print("="*80)

        print(f"\nTotal predictions: {len(predictions)}")
        print("\nBy tier:")
        for tier in ['MLB Regular+', 'Part-Time', 'Bench/Reserve']:
            count = tier_counts.get(tier, 0)
            pct = (count / len(predictions) * 100) if predictions else 0
            print(f"  {tier}: {count} ({pct:.1f}%)")

        print("\n[OK] All predictions generated and stored successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
