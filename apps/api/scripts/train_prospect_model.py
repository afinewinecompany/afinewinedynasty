"""
Train ML model to predict prospect success using 2024 data.

This script trains an XGBoost model using scouting Future Value (FV) as the label.
We'll predict FV tiers: Elite (70+), Star (60-65), Solid (50-55), Role Player (45), Org Filler (<45)
"""

import sys
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

from sqlalchemy import text
from app.db.database import get_db_sync

# ML imports
try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
    from sklearn.preprocessing import LabelEncoder
    import joblib
except ImportError as e:
    print(f"Missing ML libraries: {e}")
    print("Install with: pip install xgboost scikit-learn joblib")
    sys.exit(1)


def load_training_data(db):
    """Load prospects with features and scouting grades."""
    query = text("""
        SELECT
            p.id, p.name, p.position,
            mf.bio_features, mf.scouting_features,
            mf.milb_performance, mf.milb_progression,
            mf.milb_consistency, mf.derived_features,
            mf.feature_vector,
            sg.future_value, sg.risk_level
        FROM ml_features mf
        INNER JOIN prospects p ON p.id = mf.prospect_id
        INNER JOIN scouting_grades sg ON sg.prospect_id = p.id
        WHERE mf.as_of_year = 2024
        AND sg.ranking_year = 2024
        AND sg.future_value IS NOT NULL
        AND sg.hit_future IS NOT NULL  -- Ensure complete scouting
    """)

    result = db.execute(query)
    rows = result.fetchall()

    print(f"Loaded {len(rows)} prospects with complete features and scouting grades")

    return rows


def prepare_features(rows):
    """Convert JSONB features to numpy array."""
    feature_vectors = []
    labels = []
    prospect_info = []

    for row in rows:
        prospect_id, name, position, bio, scouting, milb_perf, milb_prog, milb_cons, derived, feature_vector, fv, risk = row

        # Extract all features from feature_vector
        features_dict = feature_vector

        # Convert to list, handling None values
        feature_list = []
        feature_names = sorted(features_dict.keys())

        for feat_name in feature_names:
            val = features_dict[feat_name]
            if val is None:
                feature_list.append(0.0)  # Impute None as 0
            else:
                feature_list.append(float(val))

        feature_vectors.append(feature_list)
        labels.append(fv)
        prospect_info.append({
            'id': prospect_id,
            'name': name,
            'position': position,
            'fv': fv,
            'risk': risk
        })

    X = np.array(feature_vectors)
    y = np.array(labels)

    print(f"\nFeature matrix shape: {X.shape}")
    print(f"Labels shape: {y.shape}")
    print(f"Feature names: {len(feature_names)}")

    return X, y, feature_names, prospect_info


def create_fv_tiers(fv_values):
    """Convert Future Value to categorical tiers."""
    tiers = []
    for fv in fv_values:
        if fv >= 70:
            tiers.append('Elite')
        elif fv >= 60:
            tiers.append('Star')
        elif fv >= 50:
            tiers.append('Solid')
        elif fv >= 45:
            tiers.append('Role Player')
        else:
            tiers.append('Org Filler')

    return np.array(tiers)


def train_model(X, y, feature_names):
    """Train XGBoost classifier."""
    print("\n" + "=" * 80)
    print("TRAINING XGBOOST MODEL")
    print("=" * 80)

    # Convert to tiers
    y_tiers = create_fv_tiers(y)

    # Encode labels
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y_tiers)

    print(f"\nLabel distribution:")
    unique, counts = np.unique(y_tiers, return_counts=True)
    for label, count in zip(unique, counts):
        print(f"  {label}: {count} ({count/len(y_tiers)*100:.1f}%)")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )

    print(f"\nTrain set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")

    # Train XGBoost
    print("\nTraining XGBoost...")

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='multi:softmax',
        num_class=len(label_encoder.classes_),
        random_state=42,
        eval_metric='mlogloss'
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    # Evaluate
    y_pred = model.predict(X_test)

    print("\n" + "=" * 80)
    print("MODEL EVALUATION")
    print("=" * 80)

    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nAccuracy: {accuracy:.3f}")

    print("\nClassification Report:")
    print(classification_report(
        y_test, y_pred,
        target_names=label_encoder.classes_,
        zero_division=0
    ))

    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(cm)

    # Feature importance
    print("\n" + "=" * 80)
    print("TOP 20 FEATURE IMPORTANCE")
    print("=" * 80)

    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:20]

    for i, idx in enumerate(indices, 1):
        print(f"{i:2d}. {feature_names[idx]:30s} {importances[idx]:.4f}")

    return model, label_encoder, X_test, y_test, y_pred


def save_model(model, label_encoder, feature_names):
    """Save trained model to disk."""
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    os.makedirs(model_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save model
    model_path = os.path.join(model_dir, f'prospect_model_{timestamp}.json')
    model.save_model(model_path)
    print(f"\nModel saved to: {model_path}")

    # Save label encoder
    encoder_path = os.path.join(model_dir, f'label_encoder_{timestamp}.pkl')
    joblib.dump(label_encoder, encoder_path)
    print(f"Label encoder saved to: {encoder_path}")

    # Save feature names
    features_path = os.path.join(model_dir, f'feature_names_{timestamp}.json')
    with open(features_path, 'w') as f:
        json.dump(feature_names, f, indent=2)
    print(f"Feature names saved to: {features_path}")

    # Save latest symlinks
    latest_model = os.path.join(model_dir, 'prospect_model_latest.json')
    latest_encoder = os.path.join(model_dir, 'label_encoder_latest.pkl')
    latest_features = os.path.join(model_dir, 'feature_names_latest.json')

    # Copy to latest
    import shutil
    shutil.copy(model_path, latest_model)
    shutil.copy(encoder_path, latest_encoder)
    shutil.copy(features_path, latest_features)

    print(f"\nLatest model symlinks created")

    return model_path


def save_predictions_to_db(model, label_encoder, feature_names, db):
    """Generate and save predictions for all 2024 prospects."""
    print("\n" + "=" * 80)
    print("GENERATING PREDICTIONS FOR ALL PROSPECTS")
    print("=" * 80)

    # Load all prospects with features
    query = text("""
        SELECT
            p.id, p.name, p.position,
            mf.feature_vector
        FROM ml_features mf
        INNER JOIN prospects p ON p.id = mf.prospect_id
        WHERE mf.as_of_year = 2024
    """)

    result = db.execute(query)
    rows = result.fetchall()

    print(f"\nGenerating predictions for {len(rows)} prospects...")

    predictions_saved = 0

    for prospect_id, name, position, feature_vector in rows:
        try:
            # Extract features
            feature_list = []
            for feat_name in sorted(feature_vector.keys()):
                val = feature_vector[feat_name]
                feature_list.append(0.0 if val is None else float(val))

            X = np.array([feature_list])

            # Predict
            pred_encoded = model.predict(X)[0]
            pred_proba = model.predict_proba(X)[0]

            # Decode
            pred_tier = label_encoder.inverse_transform([pred_encoded])[0]
            confidence = float(pred_proba[pred_encoded])

            # Map tier to FV estimate
            fv_map = {
                'Elite': 70,
                'Star': 60,
                'Solid': 50,
                'Role Player': 45,
                'Org Filler': 40
            }
            predicted_fv = fv_map.get(pred_tier, 50)

            # Save to database
            check_sql = text("""
                SELECT id FROM ml_predictions
                WHERE prospect_id = :prospect_id
                AND model_version = 'v1.0'
            """)

            result = db.execute(check_sql, {'prospect_id': prospect_id})
            existing = result.fetchone()

            if existing:
                # Update
                update_sql = f"""
                    UPDATE ml_predictions SET
                        predicted_tier = '{pred_tier}',
                        predicted_fv = {predicted_fv},
                        confidence_score = {confidence},
                        prediction_date = NOW(),
                        updated_at = NOW()
                    WHERE id = {existing[0]}
                """
                db.execute(text(update_sql))
            else:
                # Insert
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

            if predictions_saved % 100 == 0:
                db.commit()
                print(f"  Saved {predictions_saved} predictions...")

        except Exception as e:
            print(f"  Error predicting for {name}: {e}")
            continue

    db.commit()
    print(f"\nSaved {predictions_saved} predictions to database")


def main():
    print("=" * 80)
    print("PROSPECT ML MODEL TRAINING")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model: XGBoost Multi-class Classifier")
    print(f"Labels: Future Value Tiers")
    print("=" * 80)

    db = get_db_sync()

    try:
        # Load data
        rows = load_training_data(db)

        if len(rows) < 50:
            print(f"\nERROR: Only {len(rows)} prospects found. Need at least 50 for training.")
            return

        # Prepare features
        X, y, feature_names, prospect_info = prepare_features(rows)

        # Train model
        model, label_encoder, X_test, y_test, y_pred = train_model(X, y, feature_names)

        # Save model
        model_path = save_model(model, label_encoder, feature_names)

        # Generate predictions for all prospects
        save_predictions_to_db(model, label_encoder, feature_names, db)

        print("\n" + "=" * 80)
        print("TRAINING COMPLETE")
        print("=" * 80)
        print(f"\nModel saved to: {model_path}")
        print(f"Predictions saved to ml_predictions table")
        print("\nYou can now use this model to predict prospect outcomes!")

    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
