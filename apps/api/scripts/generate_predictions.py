"""
Generate ML predictions for all prospects using trained model.
"""

import sys
import os
import json
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

from sqlalchemy import text
from app.db.database import get_db_sync

# ML imports
import xgboost as xgb
import joblib


def load_model():
    """Load the trained model, encoder, and feature names."""
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')

    model_path = os.path.join(model_dir, 'prospect_model_latest.json')
    encoder_path = os.path.join(model_dir, 'label_encoder_latest.pkl')
    features_path = os.path.join(model_dir, 'feature_names_latest.json')

    print(f"Loading model from: {model_path}")

    model = xgb.XGBClassifier()
    model.load_model(model_path)

    label_encoder = joblib.load(encoder_path)

    with open(features_path, 'r') as f:
        feature_names = json.load(f)

    print(f"Model loaded: {len(feature_names)} features, {len(label_encoder.classes_)} classes")
    print(f"Classes: {label_encoder.classes_}")

    return model, label_encoder, feature_names


def generate_predictions(model, label_encoder, feature_names, db):
    """Generate predictions for all prospects."""
    print("\n" + "=" * 80)
    print("GENERATING PREDICTIONS")
    print("=" * 80)

    # Load all prospects with features
    query = text("""
        SELECT
            p.id, p.name, p.position,
            mf.feature_vector
        FROM ml_features mf
        INNER JOIN prospects p ON p.id = mf.prospect_id
        WHERE mf.as_of_year = 2024
        ORDER BY p.id
    """)

    result = db.execute(query)
    rows = result.fetchall()

    print(f"\nLoaded {len(rows)} prospects with features")

    # FV mapping
    fv_map = {
        'Elite': 70,
        'Star': 60,
        'Solid': 50,
        'Role Player': 45,
        'Org Filler': 40
    }

    predictions_saved = 0
    predictions_failed = 0

    for i, (prospect_id, name, position, feature_vector) in enumerate(rows, 1):
        try:
            # Extract features in correct order
            feature_list = []
            for feat_name in feature_names:
                val = feature_vector.get(feat_name)
                feature_list.append(0.0 if val is None else float(val))

            X = np.array([feature_list])

            # Predict
            pred_encoded = model.predict(X)[0]
            pred_proba = model.predict_proba(X)[0]

            # Decode
            pred_tier = label_encoder.inverse_transform([pred_encoded])[0]
            confidence = float(pred_proba[pred_encoded])
            predicted_fv = fv_map.get(pred_tier, 50)

            # Save to database - use raw SQL to avoid transaction issues
            # First delete any existing prediction
            delete_sql = f"""
                DELETE FROM ml_predictions
                WHERE prospect_id = {prospect_id}
                AND model_version = 'v1.0'
            """
            db.execute(text(delete_sql))

            # Then insert new prediction
            insert_sql = f"""
                INSERT INTO ml_predictions (
                    prospect_id, model_version, prediction_date,
                    predicted_tier, predicted_fv, confidence_score,
                    created_at, updated_at
                ) VALUES (
                    {prospect_id}, 'v1.0', NOW(),
                    '{pred_tier}', {predicted_fv}, {confidence},
                    NOW(), NOW()
                )
            """
            db.execute(text(insert_sql))

            predictions_saved += 1

            # Commit every 50 to avoid long transactions
            if predictions_saved % 50 == 0:
                db.commit()
                print(f"  [{i}/{len(rows)}] Saved {predictions_saved} predictions...")

        except Exception as e:
            predictions_failed += 1
            if predictions_failed <= 5:  # Only show first 5 errors
                print(f"  Error predicting for {name}: {e}")
            continue

    # Final commit
    db.commit()

    print("\n" + "=" * 80)
    print("PREDICTION SUMMARY")
    print("=" * 80)
    print(f"Total prospects: {len(rows)}")
    print(f"Predictions saved: {predictions_saved}")
    print(f"Predictions failed: {predictions_failed}")
    print(f"Success rate: {predictions_saved/len(rows)*100:.1f}%")

    # Show distribution
    query = text("""
        SELECT predicted_tier, COUNT(*) as count
        FROM ml_predictions
        WHERE model_version = 'v1.0'
        GROUP BY predicted_tier
        ORDER BY
            CASE predicted_tier
                WHEN 'Elite' THEN 1
                WHEN 'Star' THEN 2
                WHEN 'Solid' THEN 3
                WHEN 'Role Player' THEN 4
                WHEN 'Org Filler' THEN 5
            END
    """)

    result = db.execute(query)
    rows = result.fetchall()

    print("\nPrediction Distribution:")
    for tier, count in rows:
        print(f"  {tier}: {count} ({count/predictions_saved*100:.1f}%)")


def main():
    print("=" * 80)
    print("ML PREDICTION GENERATION")
    print("=" * 80)

    db = get_db_sync()

    try:
        # Load model
        model, label_encoder, feature_names = load_model()

        # Generate predictions
        generate_predictions(model, label_encoder, feature_names, db)

        print("\nPredictions generated successfully!")

    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
