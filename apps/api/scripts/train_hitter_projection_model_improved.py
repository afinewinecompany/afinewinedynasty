"""
Train Improved Hitter Stat Projection Model
============================================

This script trains an improved model with strategies to combat overfitting:
1. Reduced model complexity (fewer trees, lower depth)
2. Strong regularization
3. Feature selection (drop low-importance features)
4. Focus on rate stats only (AVG, OBP, SLG, K%, BB%)
5. Single-output models (separate model per target)

Usage:
    python scripts/train_hitter_projection_model_improved.py
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.ensemble import RandomForestRegressor
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
    script_dir = Path(__file__).parent
    api_dir = script_dir.parent

    training_files = list(api_dir.glob('stat_projection_hitters_train_*.csv'))
    if not training_files:
        raise FileNotFoundError("No hitter training data found!")

    latest_file = max(training_files, key=lambda p: p.stat().st_mtime)
    print(f"Loading training data: {latest_file.name}")

    df = pd.read_csv(latest_file)
    return df, latest_file.stem


def prepare_features_and_targets(df, focus_on_rate_stats=True):
    """Split dataframe into features (X) and targets (Y)."""

    # Focus on rate stats only (easier to predict than counting stats)
    if focus_on_rate_stats:
        target_cols = [
            'target_avg',
            'target_obp',
            'target_slg',
            'target_ops',
            'target_bb_rate',
            'target_k_rate',
            'target_iso'
        ]
        print("\n📊 Focusing on 7 rate stats (easier to predict)")
    else:
        target_cols = [
            'target_avg', 'target_obp', 'target_slg', 'target_ops',
            'target_bb_rate', 'target_k_rate', 'target_hr_per_600',
            'target_sb_per_600', 'target_rbi_per_600', 'target_r_per_600',
            'target_career_games', 'target_career_pa', 'target_iso'
        ]

    # Metadata columns (not features)
    metadata_cols = ['prospect_id', 'mlb_player_id', 'name', 'position']

    # Drop categorical columns
    categorical_cols = ['level', 'team']

    # All other columns are features
    feature_cols = [col for col in df.columns
                   if col not in target_cols
                   and col not in metadata_cols
                   and col not in categorical_cols]

    X = df[feature_cols].copy()
    y = df[target_cols].copy()
    metadata = df[metadata_cols].copy()

    # Handle missing values
    X = X.fillna(0)
    y = y.fillna(0)

    # Ensure all features are numeric
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)

    print(f"\nFeatures: {len(feature_cols)} columns")
    print(f"Targets: {len(target_cols)} columns")
    print(f"Samples: {len(df)} rows")

    return X, y, metadata, feature_cols, target_cols


def select_important_features(X, y, feature_cols, n_features=20):
    """Use Random Forest to select most important features."""

    print("\n" + "="*80)
    print("FEATURE SELECTION")
    print("="*80)

    print(f"\nTraining Random Forest to identify top {n_features} features...")

    # Train a simple RF to get feature importances
    rf = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42, n_jobs=-1)
    rf.fit(X, y.iloc[:, 0])  # Train on first target (avg)

    # Get feature importances
    importances = pd.DataFrame({
        'feature': feature_cols,
        'importance': rf.feature_importances_
    }).sort_values('importance', ascending=False)

    # Select top N features
    top_features = importances.head(n_features)['feature'].tolist()

    print(f"\n✅ Selected top {n_features} features:")
    for i, row in importances.head(n_features).iterrows():
        print(f"  {row['feature']:30s} {row['importance']:.4f}")

    return X[top_features], top_features


def train_single_output_model(X_train, y_train, X_val, y_val, target_name):
    """Train a single model for one target with regularization."""

    # Regularized XGBoost
    model = xgb.XGBRegressor(
        n_estimators=50,        # Reduced from 200
        max_depth=3,            # Reduced from 6
        learning_rate=0.1,      # Increased from 0.05 (fewer iterations)
        subsample=0.7,          # More aggressive subsampling
        colsample_bytree=0.7,   # More aggressive feature sampling
        min_child_weight=5,     # Regularization: require more samples per leaf
        reg_alpha=0.1,          # L1 regularization
        reg_lambda=1.0,         # L2 regularization
        random_state=42,
        n_jobs=-1
    )

    # Train
    model.fit(X_train, y_train)

    # Evaluate
    train_pred = model.predict(X_train)
    val_pred = model.predict(X_val)

    train_r2 = r2_score(y_train, train_pred)
    val_r2 = r2_score(y_val, val_pred)
    train_mae = mean_absolute_error(y_train, train_pred)
    val_mae = mean_absolute_error(y_val, val_pred)
    train_rmse = np.sqrt(mean_squared_error(y_train, train_pred))
    val_rmse = np.sqrt(mean_squared_error(y_val, val_pred))

    return model, {
        'train_r2': train_r2,
        'val_r2': val_r2,
        'train_mae': train_mae,
        'val_mae': val_mae,
        'train_rmse': train_rmse,
        'val_rmse': val_rmse,
        'overfit_gap': train_r2 - val_r2
    }


def train_all_models(X_train, y_train, X_val, y_val, target_cols):
    """Train separate models for each target."""

    print("\n" + "="*80)
    print("TRAINING MODELS (One per target with regularization)")
    print("="*80)

    print("\nModel Configuration:")
    print("  - Estimators: 50 (down from 200)")
    print("  - Max depth: 3 (down from 6)")
    print("  - Learning rate: 0.1 (up from 0.05)")
    print("  - Min child weight: 5 (regularization)")
    print("  - L1 reg (alpha): 0.1")
    print("  - L2 reg (lambda): 1.0")
    print("  - Subsample: 0.7")
    print("  - Colsample by tree: 0.7")

    models = {}
    results = {}

    for i, target in enumerate(target_cols, 1):
        print(f"\n[{i}/{len(target_cols)}] Training {target}...")

        model, metrics = train_single_output_model(
            X_train, y_train[target],
            X_val, y_val[target],
            target
        )

        models[target] = model
        results[target] = metrics

        print(f"  Train R²: {metrics['train_r2']:.3f}, Val R²: {metrics['val_r2']:.3f}, Gap: {metrics['overfit_gap']:.3f}")

    print("\n✅ All models trained!")

    return models, results


def evaluate_models(models, X_train, y_train, X_val, y_val, target_cols):
    """Evaluate all models and show results."""

    print("\n" + "="*80)
    print("MODEL EVALUATION")
    print("="*80)

    print("\n{:<20s} {:>10s} {:>10s} {:>10s} {:>10s} {:>10s}".format(
        "Target", "Train R²", "Val R²", "Overfit", "Val MAE", "Val RMSE"
    ))
    print("-"*80)

    results = {}

    for target in target_cols:
        model = models[target]

        train_pred = model.predict(X_train)
        val_pred = model.predict(X_val)

        train_r2 = r2_score(y_train[target], train_pred)
        val_r2 = r2_score(y_val[target], val_pred)
        val_mae = mean_absolute_error(y_val[target], val_pred)
        val_rmse = np.sqrt(mean_squared_error(y_val[target], val_pred))
        overfit_gap = train_r2 - val_r2

        print(f"{target:<20s} {train_r2:>10.3f} {val_r2:>10.3f} {overfit_gap:>10.3f} {val_mae:>10.4f} {val_rmse:>10.4f}")

        results[target] = {
            'train_r2': train_r2,
            'val_r2': val_r2,
            'val_mae': val_mae,
            'val_rmse': val_rmse,
            'overfit_gap': overfit_gap
        }

    # Overall statistics
    avg_train_r2 = np.mean([r['train_r2'] for r in results.values()])
    avg_val_r2 = np.mean([r['val_r2'] for r in results.values()])
    avg_overfit = np.mean([r['overfit_gap'] for r in results.values()])

    print("-"*80)
    print(f"{'AVERAGE':<20s} {avg_train_r2:>10.3f} {avg_val_r2:>10.3f} {avg_overfit:>10.3f}")

    return results


def save_models(models, feature_cols, target_cols):
    """Save all trained models."""

    print("\n" + "="*80)
    print("SAVING MODELS")
    print("="*80)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save models dictionary
    models_path = f'hitter_models_improved_{timestamp}.joblib'
    joblib.dump(models, models_path)
    print(f"\n✅ Models saved: {models_path}")

    # Save feature names
    feature_path = f'hitter_features_improved_{timestamp}.txt'
    with open(feature_path, 'w') as f:
        f.write('\n'.join(feature_cols))
    print(f"✅ Features saved: {feature_path}")

    # Save target names
    target_path = f'hitter_targets_improved_{timestamp}.txt'
    with open(target_path, 'w') as f:
        f.write('\n'.join(target_cols))
    print(f"✅ Targets saved: {target_path}")

    return models_path, feature_path, target_path


def main():
    """Main training pipeline."""

    print("="*80)
    print("IMPROVED HITTER STAT PROJECTION MODEL - TRAINING")
    print("="*80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nImprovements:")
    print("  ✓ Reduced model complexity (50 trees, depth 3)")
    print("  ✓ Strong regularization (L1 + L2 + min_child_weight)")
    print("  ✓ Feature selection (top 20 features)")
    print("  ✓ Single-output models (one per target)")
    print("  ✓ Focus on rate stats only (7 targets)")

    # Step 1: Load data
    print("\n" + "="*80)
    print("1. LOADING TRAINING DATA")
    print("="*80)

    df, dataset_name = load_training_data()

    # Step 2: Prepare features and targets (rate stats only)
    print("\n" + "="*80)
    print("2. PREPARING FEATURES AND TARGETS")
    print("="*80)

    X, y, metadata, feature_cols, target_cols = prepare_features_and_targets(df, focus_on_rate_stats=True)

    # Step 3: Split data
    print("\n" + "="*80)
    print("3. SPLITTING DATA")
    print("="*80)

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"\nTraining set: {len(X_train)} samples ({len(X_train)/len(X)*100:.1f}%)")
    print(f"Validation set: {len(X_val)} samples ({len(X_val)/len(X)*100:.1f}%)")

    # Step 4: Feature selection
    X_train_selected, selected_features = select_important_features(
        X_train, y_train, feature_cols, n_features=20
    )
    X_val_selected = X_val[selected_features]

    # Step 5: Train models
    models, train_results = train_all_models(
        X_train_selected, y_train, X_val_selected, y_val, target_cols
    )

    # Step 6: Evaluate
    eval_results = evaluate_models(
        models, X_train_selected, y_train, X_val_selected, y_val, target_cols
    )

    # Step 7: Save models
    models_path, feature_path, target_path = save_models(
        models, selected_features, target_cols
    )

    # Step 8: Summary
    print("\n" + "="*80)
    print("TRAINING SUMMARY")
    print("="*80)

    avg_val_r2 = np.mean([r['val_r2'] for r in eval_results.values()])
    avg_overfit = np.mean([r['overfit_gap'] for r in eval_results.values()])
    best_target = max(eval_results.items(), key=lambda x: x[1]['val_r2'])
    worst_target = min(eval_results.items(), key=lambda x: x[1]['val_r2'])

    print(f"""
MODEL DETAILS:
- Algorithm: XGBoost (regularized, one model per target)
- Features: {len(selected_features)} (selected from {len(feature_cols)})
- Targets: {len(target_cols)} rate stats
- Training samples: {len(X_train)}
- Validation samples: {len(X_val)}

PERFORMANCE:
- Average validation R²: {avg_val_r2:.3f}
- Average overfit gap: {avg_overfit:.3f}
- Best target: {best_target[0]} (R² = {best_target[1]['val_r2']:.3f})
- Worst target: {worst_target[0]} (R² = {worst_target[1]['val_r2']:.3f})

IMPROVEMENT vs BASELINE:
- Baseline Val R²: -0.013 (previous model)
- New Val R²: {avg_val_r2:.3f}
- Improvement: {avg_val_r2 - (-0.013):.3f} points

FILES SAVED:
- Models: {models_path}
- Features: {feature_path}
- Targets: {target_path}

NEXT STEPS:
1. If Val R² > 0.15: Deploy to API
2. If Val R² < 0.15: Need more data (Option C)
3. Create prediction API endpoint
4. Build frontend Projections page
    """)

    print("="*80)
    print("IMPROVED MODEL TRAINING COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    main()
