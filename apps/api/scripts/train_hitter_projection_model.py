"""
Train Hitter Stat Projection Model
===================================

This script trains a multi-output regression model to predict MLB hitting stats
from MiLB performance data.

Model: XGBoost Multi-Output Regressor
Targets: 13 MLB career stats (AVG, OBP, SLG, OPS, etc.)
Features: 37 MiLB stats + derived metrics + Fangraphs grades

Usage:
    python scripts/train_hitter_projection_model.py
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import xgboost as xgb
import joblib
from datetime import datetime
import sys
import codecs
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def load_training_data():
    """Load the most recent hitter training dataset."""

    # Find most recent training file
    script_dir = Path(__file__).parent
    api_dir = script_dir.parent

    training_files = list(api_dir.glob('stat_projection_hitters_train_*.csv'))

    if not training_files:
        raise FileNotFoundError("No hitter training data found!")

    # Get most recent file
    latest_file = max(training_files, key=lambda p: p.stat().st_mtime)

    print(f"Loading training data: {latest_file.name}")

    df = pd.read_csv(latest_file)

    return df, latest_file.stem


def prepare_features_and_targets(df):
    """Split dataframe into features (X) and targets (Y)."""

    # Target columns (what we're predicting)
    target_cols = [
        'target_avg', 'target_obp', 'target_slg', 'target_ops',
        'target_bb_rate', 'target_k_rate', 'target_hr_per_600',
        'target_sb_per_600', 'target_rbi_per_600', 'target_r_per_600',
        'target_career_games', 'target_career_pa', 'target_iso'
    ]

    # Metadata columns (not used as features)
    metadata_cols = ['prospect_id', 'mlb_player_id', 'name', 'position']

    # Categorical columns to drop (or could encode, but dropping is simpler)
    categorical_cols = ['level', 'team']

    # All other columns are features
    feature_cols = [col for col in df.columns
                   if col not in target_cols
                   and col not in metadata_cols
                   and col not in categorical_cols]

    X = df[feature_cols].copy()
    y = df[target_cols].copy()
    metadata = df[metadata_cols].copy()

    # Handle missing values in features
    X = X.fillna(0)

    # Handle missing values in targets (shouldn't happen, but just in case)
    y = y.fillna(0)

    # Ensure all features are numeric
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)

    print(f"\nFeatures: {len(feature_cols)} columns")
    print(f"  (Dropped categorical: {categorical_cols})")
    print(f"Targets: {len(target_cols)} columns")
    print(f"Samples: {len(df)} rows")

    return X, y, metadata, feature_cols, target_cols


def train_model(X_train, y_train, X_val, y_val):
    """Train XGBoost multi-output regression model."""

    print("\n" + "="*80)
    print("TRAINING MODEL")
    print("="*80)

    # XGBoost base estimator
    base_estimator = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )

    # Multi-output wrapper
    model = MultiOutputRegressor(base_estimator, n_jobs=-1)

    print("\nTraining XGBoost Multi-Output Regressor...")
    print(f"  Estimators: 200")
    print(f"  Max depth: 6")
    print(f"  Learning rate: 0.05")
    print(f"  Training samples: {len(X_train)}")
    print(f"  Validation samples: {len(X_val)}")

    # Train
    model.fit(X_train, y_train)

    print("\n✅ Training complete!")

    return model


def evaluate_model(model, X_train, y_train, X_val, y_val, target_cols):
    """Evaluate model performance on train and validation sets."""

    print("\n" + "="*80)
    print("MODEL EVALUATION")
    print("="*80)

    # Predictions
    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)

    # Metrics for each target
    print("\n{:<25s} {:>10s} {:>10s} {:>10s} {:>10s}".format(
        "Target", "Train R²", "Val R²", "Train MAE", "Val MAE"
    ))
    print("-"*70)

    results = {}

    for i, target in enumerate(target_cols):
        # R² scores
        train_r2 = r2_score(y_train.iloc[:, i], y_train_pred[:, i])
        val_r2 = r2_score(y_val.iloc[:, i], y_val_pred[:, i])

        # MAE scores
        train_mae = mean_absolute_error(y_train.iloc[:, i], y_train_pred[:, i])
        val_mae = mean_absolute_error(y_val.iloc[:, i], y_val_pred[:, i])

        # RMSE scores
        train_rmse = np.sqrt(mean_squared_error(y_train.iloc[:, i], y_train_pred[:, i]))
        val_rmse = np.sqrt(mean_squared_error(y_val.iloc[:, i], y_val_pred[:, i]))

        print(f"{target:<25s} {train_r2:>10.3f} {val_r2:>10.3f} {train_mae:>10.4f} {val_mae:>10.4f}")

        results[target] = {
            'train_r2': train_r2,
            'val_r2': val_r2,
            'train_mae': train_mae,
            'val_mae': val_mae,
            'train_rmse': train_rmse,
            'val_rmse': val_rmse
        }

    # Overall averages
    avg_train_r2 = np.mean([r['train_r2'] for r in results.values()])
    avg_val_r2 = np.mean([r['val_r2'] for r in results.values()])

    print("-"*70)
    print(f"{'AVERAGE':<25s} {avg_train_r2:>10.3f} {avg_val_r2:>10.3f}")

    return results


def save_model(model, feature_cols, target_cols, dataset_name):
    """Save trained model and metadata."""

    print("\n" + "="*80)
    print("SAVING MODEL")
    print("="*80)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save model
    model_path = f'hitter_projection_model_{timestamp}.joblib'
    joblib.dump(model, model_path)
    print(f"\n✅ Model saved: {model_path}")

    # Save feature names
    feature_path = f'hitter_projection_features_{timestamp}.txt'
    with open(feature_path, 'w') as f:
        f.write('\n'.join(feature_cols))
    print(f"✅ Features saved: {feature_path}")

    # Save target names
    target_path = f'hitter_projection_targets_{timestamp}.txt'
    with open(target_path, 'w') as f:
        f.write('\n'.join(target_cols))
    print(f"✅ Targets saved: {target_path}")

    return model_path, feature_path, target_path


def main():
    """Main training pipeline."""

    print("="*80)
    print("HITTER STAT PROJECTION MODEL - TRAINING")
    print("="*80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Step 1: Load data
    print("="*80)
    print("1. LOADING TRAINING DATA")
    print("="*80)

    df, dataset_name = load_training_data()

    # Step 2: Prepare features and targets
    print("\n" + "="*80)
    print("2. PREPARING FEATURES AND TARGETS")
    print("="*80)

    X, y, metadata, feature_cols, target_cols = prepare_features_and_targets(df)

    # Step 3: Split into train/validation
    print("\n" + "="*80)
    print("3. SPLITTING DATA")
    print("="*80)

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"\nTraining set: {len(X_train)} samples ({len(X_train)/len(X)*100:.1f}%)")
    print(f"Validation set: {len(X_val)} samples ({len(X_val)/len(X)*100:.1f}%)")

    # Step 4: Train model
    model = train_model(X_train, y_train, X_val, y_val)

    # Step 5: Evaluate
    results = evaluate_model(model, X_train, y_train, X_val, y_val, target_cols)

    # Step 6: Save model
    model_path, feature_path, target_path = save_model(
        model, feature_cols, target_cols, dataset_name
    )

    # Step 7: Summary
    print("\n" + "="*80)
    print("TRAINING SUMMARY")
    print("="*80)

    print(f"""
MODEL DETAILS:
- Algorithm: XGBoost Multi-Output Regressor
- Features: {len(feature_cols)}
- Targets: {len(target_cols)}
- Training samples: {len(X_train)}
- Validation samples: {len(X_val)}

PERFORMANCE:
- Average validation R²: {np.mean([r['val_r2'] for r in results.values()]):.3f}
- Best target: {max(results.items(), key=lambda x: x[1]['val_r2'])[0]} (R² = {max(r['val_r2'] for r in results.values()):.3f})
- Worst target: {min(results.items(), key=lambda x: x[1]['val_r2'])[0]} (R² = {min(r['val_r2'] for r in results.values()):.3f})

FILES SAVED:
- Model: {model_path}
- Features: {feature_path}
- Targets: {target_path}

NEXT STEPS:
1. Deploy model to API endpoint
2. Create prediction function in backend
3. Build frontend Projections page
4. Generate projections for current prospects
    """)

    print("="*80)
    print("HITTER MODEL TRAINING COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    main()
