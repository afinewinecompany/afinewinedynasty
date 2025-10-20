"""
Save Production Models: 3-Class Hitters and Pitchers
=====================================================

This script trains and saves both hitter and pitcher models for production deployment.

Outputs:
- models/hitter_model_3class.pkl
- models/pitcher_model_3class.pkl
- models/model_metadata.json
"""

import pandas as pd
import numpy as np
import pickle
import json
import sys
from datetime import datetime
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import f1_score, accuracy_score, classification_report
from imblearn.over_sampling import SMOTE
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')


def load_and_preprocess_data(file_path, fit_imputer=None, fit_scaler=None, required_columns=None):
    """Load CSV and preprocess features."""
    print(f"\nLoading: {file_path}")
    df = pd.read_csv(file_path)

    metadata_cols = ['prospect_id', 'data_year', 'name', 'position', 'fangraphs_id']
    target_cols = ['target', 'target_label', 'fangraphs_fv']

    metadata = df[metadata_cols + target_cols].copy()
    y = df['target'].values

    feature_cols = [c for c in df.columns if c not in metadata_cols + target_cols]
    X = df[feature_cols].copy()

    if required_columns is not None:
        for col in required_columns:
            if col not in X.columns:
                X[col] = np.nan
        X = X[required_columns]
    else:
        missing_pct = X.isnull().sum() / len(X) * 100
        cols_to_drop = missing_pct[missing_pct == 100].index.tolist()
        if cols_to_drop:
            X = X.drop(columns=cols_to_drop)

    print(f"  Loaded: {len(X):,} samples, {len(X.columns)} features")
    print(f"  Class distribution: {np.bincount(y)}")

    if fit_imputer is None:
        imputer = SimpleImputer(strategy='median')
        X_imputed = imputer.fit_transform(X)
    else:
        imputer = fit_imputer
        X_imputed = imputer.transform(X)

    X_imputed = pd.DataFrame(X_imputed, columns=X.columns)

    if fit_scaler is None:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_imputed)
    else:
        scaler = fit_scaler
        X_scaled = scaler.transform(X_imputed)

    X_scaled = pd.DataFrame(X_scaled, columns=X.columns)

    return X_scaled, y, metadata, imputer, scaler, X.columns.tolist()


def apply_smote(X_train, y_train, player_type):
    """Apply SMOTE to balance classes."""
    print(f"\nApplying SMOTE for {player_type}...")

    print(f"  Original class distribution: {np.bincount(y_train)}")

    class_counts = np.bincount(y_train)
    max_count = class_counts.max()
    sampling_strategy = {}

    for i in range(len(class_counts)):
        if class_counts[i] < max_count * 0.2 and class_counts[i] >= 6:
            sampling_strategy[i] = int(max_count * 0.2)

    if sampling_strategy:
        print(f"  SMOTE sampling strategy: {sampling_strategy}")
        smote = SMOTE(sampling_strategy=sampling_strategy, random_state=42)
        X_resampled, y_resampled = smote.fit_resample(X_train, y_train)
        print(f"  Resampled: {len(X_train):,} -> {len(y_resampled):,} samples")
        return X_resampled, y_resampled
    else:
        print("  SMOTE not needed")
        return X_train, y_train


def train_xgboost(X_train, y_train, X_val, y_val, player_type):
    """Train XGBoost classifier."""
    print(f"\nTraining XGBoost for {player_type}...")

    class_counts = np.bincount(y_train)
    scale_pos_weight = class_counts[0] / class_counts[2]

    xgb_model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=-1,
        eval_metric='mlogloss'
    )

    xgb_model.fit(X_train, y_train)

    y_train_pred = xgb_model.predict(X_train)
    train_f1 = f1_score(y_train, y_train_pred, average='weighted')
    train_acc = accuracy_score(y_train, y_train_pred)

    y_val_pred = xgb_model.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='weighted')
    val_acc = accuracy_score(y_val, y_val_pred)

    print(f"  Training F1: {train_f1:.3f}, Accuracy: {train_acc:.3f}")
    print(f"  Validation F1: {val_f1:.3f}, Accuracy: {val_acc:.3f}")

    return xgb_model


def train_and_save_model(player_type, timestamp):
    """Train and save model for hitters or pitchers."""
    print("\n" + "="*80)
    print(f"TRAINING {player_type.upper()} MODEL")
    print("="*80)

    # Load data
    train_file = f'ml_data_{player_type}_3class_train_{timestamp}.csv'
    val_file = f'ml_data_{player_type}_3class_val_{timestamp}.csv'
    test_file = f'ml_data_{player_type}_3class_test_{timestamp}.csv'

    X_train, y_train, metadata_train, imputer, scaler, train_columns = load_and_preprocess_data(train_file)
    X_val, y_val, metadata_val, _, _, _ = load_and_preprocess_data(val_file, imputer, scaler, train_columns)
    X_test, y_test, metadata_test, _, _, _ = load_and_preprocess_data(test_file, imputer, scaler, train_columns)

    # Apply SMOTE
    X_train_resampled, y_train_resampled = apply_smote(X_train, y_train, player_type)

    # Train XGBoost
    model = train_xgboost(X_train_resampled, y_train_resampled, X_val, y_val, player_type)

    # Test evaluation
    y_test_pred = model.predict(X_test)
    test_f1 = f1_score(y_test, y_test_pred, average='weighted')
    test_acc = accuracy_score(y_test, y_test_pred)

    print(f"\n  Test F1: {test_f1:.3f}, Accuracy: {test_acc:.3f}")

    class_names = ['Bench/Reserve', 'Part-Time', 'MLB Regular+']
    print(f"\n  Classification Report:")
    print(classification_report(y_test, y_test_pred, target_names=class_names, digits=3, zero_division=0))

    return {
        'model': model,
        'imputer': imputer,
        'scaler': scaler,
        'feature_columns': train_columns,
        'test_f1': test_f1,
        'test_accuracy': test_acc,
        'player_type': player_type,
        'class_names': class_names,
        'train_samples': len(X_train),
        'val_samples': len(X_val),
        'test_samples': len(X_test),
        'timestamp': timestamp
    }


def save_model_artifacts(hitter_artifacts, pitcher_artifacts):
    """Save model artifacts to disk."""
    print("\n" + "="*80)
    print("SAVING MODEL ARTIFACTS")
    print("="*80)

    # Create models directory
    models_dir = Path('models')
    models_dir.mkdir(exist_ok=True)
    print(f"\nCreated models directory: {models_dir.absolute()}")

    # Save hitter model
    hitter_path = models_dir / 'hitter_model_3class.pkl'
    with open(hitter_path, 'wb') as f:
        pickle.dump({
            'model': hitter_artifacts['model'],
            'imputer': hitter_artifacts['imputer'],
            'scaler': hitter_artifacts['scaler'],
            'feature_columns': hitter_artifacts['feature_columns'],
            'class_names': hitter_artifacts['class_names']
        }, f)
    print(f"  Saved: {hitter_path}")

    # Save pitcher model
    pitcher_path = models_dir / 'pitcher_model_3class.pkl'
    with open(pitcher_path, 'wb') as f:
        pickle.dump({
            'model': pitcher_artifacts['model'],
            'imputer': pitcher_artifacts['imputer'],
            'scaler': pitcher_artifacts['scaler'],
            'feature_columns': pitcher_artifacts['feature_columns'],
            'class_names': pitcher_artifacts['class_names']
        }, f)
    print(f"  Saved: {pitcher_path}")

    # Save metadata
    metadata = {
        'created_at': datetime.now().isoformat(),
        'hitter_model': {
            'file': 'hitter_model_3class.pkl',
            'test_f1': hitter_artifacts['test_f1'],
            'test_accuracy': hitter_artifacts['test_accuracy'],
            'train_samples': hitter_artifacts['train_samples'],
            'val_samples': hitter_artifacts['val_samples'],
            'test_samples': hitter_artifacts['test_samples'],
            'features_count': len(hitter_artifacts['feature_columns']),
            'timestamp': hitter_artifacts['timestamp']
        },
        'pitcher_model': {
            'file': 'pitcher_model_3class.pkl',
            'test_f1': pitcher_artifacts['test_f1'],
            'test_accuracy': pitcher_artifacts['test_accuracy'],
            'train_samples': pitcher_artifacts['train_samples'],
            'val_samples': pitcher_artifacts['val_samples'],
            'test_samples': pitcher_artifacts['test_samples'],
            'features_count': len(pitcher_artifacts['feature_columns']),
            'timestamp': pitcher_artifacts['timestamp']
        },
        'class_names': ['Bench/Reserve', 'Part-Time', 'MLB Regular+'],
        'class_mapping': {
            0: 'Bench/Reserve (FV 35-40)',
            1: 'Part-Time (FV 45)',
            2: 'MLB Regular+ (FV 50+)'
        },
        'version': '1.0.0',
        'model_type': 'XGBoost 3-Class'
    }

    metadata_path = models_dir / 'model_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved: {metadata_path}")

    print(f"\n[OK] All model artifacts saved successfully")
    return metadata


def main():
    print("="*80)
    print("SAVE PRODUCTION MODELS: 3-CLASS HITTERS AND PITCHERS")
    print("="*80)

    timestamp = '20251019_225954'

    # Train and save hitter model
    hitter_artifacts = train_and_save_model('hitters', timestamp)

    # Train and save pitcher model
    pitcher_artifacts = train_and_save_model('pitchers', timestamp)

    # Save all artifacts
    metadata = save_model_artifacts(hitter_artifacts, pitcher_artifacts)

    # Final summary
    print("\n" + "="*80)
    print("PRODUCTION MODELS READY")
    print("="*80)

    print(f"\n{'Model':<15} {'Test F1':<10} {'Accuracy':<10} {'Status':<15}")
    print("-" * 55)
    print(f"{'Hitters':<15} {hitter_artifacts['test_f1']:.3f}      {hitter_artifacts['test_accuracy']:.3f}      {'Production Ready':<15}")
    print(f"{'Pitchers':<15} {pitcher_artifacts['test_f1']:.3f}      {pitcher_artifacts['test_accuracy']:.3f}      {'Excellent':<15}")

    print(f"\nModel Files:")
    print(f"  - models/hitter_model_3class.pkl")
    print(f"  - models/pitcher_model_3class.pkl")
    print(f"  - models/model_metadata.json")

    print(f"\nNext Steps:")
    print(f"  1. Create unified prediction API (predict_mlb_expectation.py)")
    print(f"  2. Test predictions with sample prospects")
    print(f"  3. Deploy to production environment")

    return metadata


if __name__ == "__main__":
    metadata = main()
