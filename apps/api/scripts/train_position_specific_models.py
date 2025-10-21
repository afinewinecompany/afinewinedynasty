"""
Train Position-Specific Models for Hitter Prospects
===================================================

This script trains separate Random Forest models for each position group:
- IF (Infielders): SS, 2B, 3B
- OF (Outfielders): CF, RF, LF
- C (Catchers): C
- Corner: 1B, DH

Expected improvement: +0.05-0.10 F1 over baseline (0.684)
Target: 0.72-0.76 F1 overall
"""

import pandas as pd
import numpy as np
import sys
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    classification_report,
    f1_score,
    confusion_matrix,
    accuracy_score
)
from imblearn.over_sampling import SMOTE
import warnings
warnings.filterwarnings('ignore')

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')


POSITION_GROUPS = ['IF', 'OF', 'C', 'Corner']


def load_and_preprocess_data(file_path, fit_imputer=None, fit_scaler=None, required_columns=None):
    """Load CSV and preprocess features."""
    print(f"\nLoading: {file_path}")
    df = pd.read_csv(file_path)

    # Separate columns
    metadata_cols = ['prospect_id', 'data_year', 'name', 'position', 'fangraphs_id']
    target_cols = ['target', 'target_label', 'fangraphs_fv']

    # Keep metadata
    metadata = df[metadata_cols + target_cols].copy()
    y = df['target'].values

    # Get features
    feature_cols = [c for c in df.columns if c not in metadata_cols + target_cols]
    X = df[feature_cols].copy()

    # Align columns if needed
    if required_columns is not None:
        for col in required_columns:
            if col not in X.columns:
                X[col] = np.nan
        X = X[required_columns]
    else:
        # Drop 100% missing columns
        missing_pct = X.isnull().sum() / len(X) * 100
        cols_to_drop = missing_pct[missing_pct == 100].index.tolist()
        if cols_to_drop:
            X = X.drop(columns=cols_to_drop)

    print(f"  Loaded: {len(X):,} samples, {len(X.columns)} features")
    print(f"  Class distribution: {np.bincount(y)}")

    # Impute missing values
    if fit_imputer is None:
        imputer = SimpleImputer(strategy='median')
        X_imputed = imputer.fit_transform(X)
    else:
        imputer = fit_imputer
        X_imputed = imputer.transform(X)

    X_imputed = pd.DataFrame(X_imputed, columns=X.columns)

    # Scale features
    if fit_scaler is None:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_imputed)
    else:
        scaler = fit_scaler
        X_scaled = scaler.transform(X_imputed)

    X_scaled = pd.DataFrame(X_scaled, columns=X.columns)

    return X_scaled, y, metadata, imputer, scaler, X.columns.tolist()


def apply_smote(X_train, y_train, position_group):
    """Apply SMOTE with position-specific strategy."""
    print("\n" + "=" * 80)
    print(f"APPLYING SMOTE FOR CLASS IMBALANCE ({position_group})")
    print("=" * 80)

    print(f"\nOriginal class distribution:")
    class_counts = np.bincount(y_train)
    for i, count in enumerate(class_counts):
        pct = count / len(y_train) * 100
        print(f"  Class {i}: {count:>4} ({pct:>5.1f}%)")

    # Position-specific SMOTE strategies
    # Catchers and Corner: Small samples, more conservative
    # IF and OF: Larger samples, more aggressive
    if position_group in ['C', 'Corner']:
        target_pct = 0.15  # 15% of majority class
    else:
        target_pct = 0.20  # 20% of majority class

    max_count = class_counts.max()
    sampling_strategy = {}

    for i in range(len(class_counts)):
        if class_counts[i] < max_count * target_pct and class_counts[i] >= 6:
            sampling_strategy[i] = int(max_count * target_pct)

    if sampling_strategy:
        print(f"\nSMOTE sampling strategy: {sampling_strategy}")
        smote = SMOTE(sampling_strategy=sampling_strategy, random_state=42)
        X_resampled, y_resampled = smote.fit_resample(X_train, y_train)

        print(f"\nResampled class distribution:")
        for i, count in enumerate(np.bincount(y_resampled)):
            pct = count / len(y_resampled) * 100
            print(f"  Class {i}: {count:>4} ({pct:>5.1f}%)")

        print(f"\n[OK] SMOTE complete: {len(X_train):,} -> {len(X_resampled):,} samples")
        return X_resampled, y_resampled
    else:
        print("\n[SKIP] SMOTE not needed")
        return X_train, y_train


def train_random_forest(X_train, y_train, X_val, y_val, position_group):
    """Train Random Forest for specific position group."""
    print("\n" + "=" * 80)
    print(f"TRAINING RANDOM FOREST CLASSIFIER ({position_group})")
    print("=" * 80)

    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=20,
        min_samples_leaf=10,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1,
        verbose=0
    )

    print("\nTraining...")
    rf.fit(X_train, y_train)
    print("[OK] Training complete")

    # Training performance
    y_train_pred = rf.predict(X_train)
    train_f1 = f1_score(y_train, y_train_pred, average='weighted')
    train_acc = accuracy_score(y_train, y_train_pred)

    print(f"\nTraining Set Performance:")
    print(f"  Accuracy: {train_acc:.3f}")
    print(f"  Weighted F1: {train_f1:.3f}")

    # Validation performance
    y_val_pred = rf.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='weighted')
    val_acc = accuracy_score(y_val, y_val_pred)

    print(f"\nValidation Set Performance:")
    print(f"  Accuracy: {val_acc:.3f}")
    print(f"  Weighted F1: {val_f1:.3f}")

    return rf, y_val_pred


def evaluate_model(y_true, y_pred, position_group, dataset_name="Test"):
    """Comprehensive model evaluation."""
    print("\n" + "=" * 80)
    print(f"{dataset_name.upper()} SET EVALUATION ({position_group})")
    print("=" * 80)

    acc = accuracy_score(y_true, y_pred)
    f1_weighted = f1_score(y_true, y_pred, average='weighted')
    f1_macro = f1_score(y_true, y_pred, average='macro')

    print(f"\nOverall Metrics:")
    print(f"  Accuracy:       {acc:.3f}")
    print(f"  Weighted F1:    {f1_weighted:.3f}")
    print(f"  Macro F1:       {f1_macro:.3f}")

    # Per-class metrics
    class_names = ['Bench', 'Part-Time', 'Regular', 'All-Star']
    print(f"\nDetailed Classification Report:")
    # Use labels parameter to handle missing classes
    print(classification_report(y_true, y_pred, labels=[0, 1, 2, 3], target_names=class_names, digits=3, zero_division=0))

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2, 3])
    print(f"\nConfusion Matrix:")
    print(f"         Predicted:")
    print(f"           Bench  Part   Reg   AllStar")
    for i, label in enumerate(class_names):
        print(f"Actual {label:<10} {cm[i][0]:>5} {cm[i][1]:>5} {cm[i][2]:>5} {cm[i][3]:>5}")

    return f1_weighted, acc


def analyze_feature_importance(model, feature_names, position_group, top_n=15):
    """Analyze position-specific feature importance."""
    importances = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    print(f"\nTop {top_n} Features for {position_group}:")
    for i, (idx, row) in enumerate(importances.head(top_n).iterrows(), 1):
        print(f"  {i:>2}. {row['feature']:<35} {row['importance']:.4f}")

    return importances


def train_position_model(position_group, timestamp):
    """Train model for a single position group."""
    print("\n" + "=" * 80)
    print(f"POSITION GROUP: {position_group}")
    print("=" * 80)

    # Load data
    train_file = f'ml_data_hitters_{position_group}_train_{timestamp}.csv'
    val_file = f'ml_data_hitters_{position_group}_val_{timestamp}.csv'
    test_file = f'ml_data_hitters_{position_group}_test_{timestamp}.csv'

    # Preprocess
    X_train, y_train, metadata_train, imputer, scaler, train_columns = load_and_preprocess_data(train_file)
    X_val, y_val, metadata_val, _, _, _ = load_and_preprocess_data(val_file, imputer, scaler, train_columns)
    X_test, y_test, metadata_test, _, _, _ = load_and_preprocess_data(test_file, imputer, scaler, train_columns)

    # Apply SMOTE
    X_train_resampled, y_train_resampled = apply_smote(X_train, y_train, position_group)

    # Train
    model, y_val_pred = train_random_forest(
        X_train_resampled, y_train_resampled,
        X_val, y_val, position_group
    )

    # Feature importance
    feature_importances = analyze_feature_importance(model, X_train.columns, position_group)

    # Validation evaluation
    val_f1, val_acc = evaluate_model(y_val, y_val_pred, position_group, "Validation")

    # Test evaluation
    print("\n" + "=" * 80)
    print(f"FINAL TEST SET EVALUATION ({position_group})")
    print("=" * 80)

    y_test_pred = model.predict(X_test)
    test_f1, test_acc = evaluate_model(y_test, y_test_pred, position_group, "Test")

    return {
        'position_group': position_group,
        'model': model,
        'imputer': imputer,
        'scaler': scaler,
        'feature_columns': train_columns,
        'feature_importances': feature_importances,
        'train_samples': len(X_train),
        'val_samples': len(X_val),
        'test_samples': len(X_test),
        'val_f1': val_f1,
        'val_acc': val_acc,
        'test_f1': test_f1,
        'test_acc': test_acc,
        'y_test': y_test,
        'y_test_pred': y_test_pred,
        'metadata_test': metadata_test
    }


def calculate_overall_metrics(position_results):
    """Calculate weighted overall metrics across all positions."""
    print("\n" + "=" * 80)
    print("OVERALL POSITION-SPECIFIC MODEL PERFORMANCE")
    print("=" * 80)

    # Combine all test predictions
    all_y_test = []
    all_y_pred = []
    all_metadata = []

    for result in position_results:
        all_y_test.extend(result['y_test'])
        all_y_pred.extend(result['y_test_pred'])
        all_metadata.append(result['metadata_test'])

    all_y_test = np.array(all_y_test)
    all_y_pred = np.array(all_y_pred)
    all_metadata = pd.concat(all_metadata, ignore_index=True)

    # Overall metrics
    overall_f1 = f1_score(all_y_test, all_y_pred, average='weighted')
    overall_acc = accuracy_score(all_y_test, all_y_pred)

    print(f"\nOverall Test Set Performance:")
    print(f"  Total samples: {len(all_y_test):,}")
    print(f"  Accuracy:      {overall_acc:.3f}")
    print(f"  Weighted F1:   {overall_f1:.3f}")

    # Per-class metrics
    class_names = ['Bench', 'Part-Time', 'Regular', 'All-Star']
    print(f"\nOverall Classification Report:")
    print(classification_report(all_y_test, all_y_pred, target_names=class_names, digits=3, zero_division=0))

    # Confusion matrix
    cm = confusion_matrix(all_y_test, all_y_pred, labels=[0, 1, 2, 3])
    print(f"\nOverall Confusion Matrix:")
    print(f"         Predicted:")
    print(f"           Bench  Part   Reg   AllStar")
    for i, label in enumerate(class_names):
        print(f"Actual {label:<10} {cm[i][0]:>5} {cm[i][1]:>5} {cm[i][2]:>5} {cm[i][3]:>5}")

    return overall_f1, overall_acc, all_metadata


def main():
    print("=" * 80)
    print("POSITION-SPECIFIC MODEL TRAINING")
    print("=" * 80)

    timestamp = '20251019_223446'  # From dataset creation

    # Train models for each position group
    position_results = []

    for position_group in POSITION_GROUPS:
        result = train_position_model(position_group, timestamp)
        position_results.append(result)

    # Calculate overall performance
    overall_f1, overall_acc, all_metadata = calculate_overall_metrics(position_results)

    # Summary table
    print("\n" + "=" * 80)
    print("POSITION-SPECIFIC MODEL SUMMARY")
    print("=" * 80)

    print(f"\n{'Position':<10} {'Train':<7} {'Val':<7} {'Test':<7} {'Val F1':<8} {'Test F1':<8}")
    print("-" * 70)

    for result in position_results:
        print(f"{result['position_group']:<10} "
              f"{result['train_samples']:>6} "
              f"{result['val_samples']:>6} "
              f"{result['test_samples']:>6} "
              f"{result['val_f1']:>7.3f} "
              f"{result['test_f1']:>7.3f}")

    print("-" * 70)
    print(f"{'OVERALL':<10} {'':<7} {'':<7} {sum(r['test_samples'] for r in position_results):>6} "
          f"{'':<8} {overall_f1:>7.3f}")

    # Comparison to baseline
    print("\n" + "=" * 80)
    print("COMPARISON TO BASELINE")
    print("=" * 80)

    baseline_f1 = 0.684
    improvement = overall_f1 - baseline_f1

    print(f"\nBaseline (position-agnostic):  {baseline_f1:.3f}")
    print(f"Position-specific:             {overall_f1:.3f}")
    print(f"Improvement:                   {improvement:+.3f}")

    if improvement >= 0.05:
        status = "✅ EXCELLENT"
        print(f"\n{status}: Achieved +{improvement:.3f} F1 improvement!")
        print(f"Position-specific modeling significantly outperforms baseline.")
    elif improvement >= 0.03:
        status = "✅ SUCCESS"
        print(f"\n{status}: Achieved +{improvement:.3f} F1 improvement!")
    elif improvement > 0:
        status = "⚠️  MARGINAL"
        print(f"\n{status}: Only +{improvement:.3f} F1 improvement.")
    else:
        status = "❌ FAILED"
        print(f"\n{status}: No improvement over baseline.")

    print("\n" + "=" * 80)
    print("COMPLETE")
    print("=" * 80)

    if improvement >= 0.03:
        print("\nNext Steps (Phase 3):")
        print("  1. Try XGBoost with hyperparameter tuning")
        print("  2. Expected additional gain: +0.03-0.05 F1")
        print("  3. Target: 0.75-0.80 F1")
    else:
        print("\nRecommendations:")
        print("  1. Analyze position-specific feature importance differences")
        print("  2. Consider position-specific feature engineering")
        print("  3. Investigate alternative class imbalance strategies")


if __name__ == "__main__":
    main()
