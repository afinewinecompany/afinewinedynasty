"""
Train Enhanced Baseline ML Model for MLB Expectation Classification
====================================================================

This script trains a Random Forest model using ENHANCED features (49 vs 35).

Enhanced features include:
- Original 35 features (scouting grades + stats)
- 13 new derived features (plus_tool_count, offensive_ceiling, etc.)

Target: Weighted F1 > 0.71 (improvement from 0.684 baseline)
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


def load_and_preprocess_data(file_path, fit_imputer=None, fit_scaler=None, required_columns=None):
    """
    Load CSV and preprocess features.

    Args:
        file_path: Path to CSV file
        fit_imputer: Pre-fitted imputer (for val/test sets)
        fit_scaler: Pre-fitted scaler (for val/test sets)
        required_columns: List of column names to keep (for consistency across splits)

    Returns:
        X, y, metadata, imputer, scaler, feature_columns
    """
    print(f"\nLoading: {file_path}")
    df = pd.read_csv(file_path)

    # Separate columns
    metadata_cols = ['prospect_id', 'data_year', 'name', 'position', 'fangraphs_id']
    target_cols = ['target', 'target_label', 'fangraphs_fv']

    # Keep metadata for later analysis
    metadata = df[metadata_cols + target_cols].copy()

    # Extract target
    y = df['target'].values

    # Get feature columns (numeric only for now)
    feature_cols = [c for c in df.columns if c not in metadata_cols + target_cols]
    X = df[feature_cols].copy()

    # If required_columns specified (val/test sets), align to those columns
    if required_columns is not None:
        # Add missing columns (fill with NaN)
        for col in required_columns:
            if col not in X.columns:
                X[col] = np.nan
        # Keep only required columns in same order
        X = X[required_columns]
        print(f"  Aligned to {len(required_columns)} required columns")
    else:
        # Drop columns that are 100% missing (train set only)
        missing_pct = X.isnull().sum() / len(X) * 100
        cols_to_drop = missing_pct[missing_pct == 100].index.tolist()
        if cols_to_drop:
            print(f"  Dropping {len(cols_to_drop)} columns with 100% missing: {cols_to_drop}")
            X = X.drop(columns=cols_to_drop)

    print(f"  Loaded: {len(X):,} samples, {len(X.columns)} features")
    print(f"  Class distribution: {np.bincount(y)}")

    # Handle missing values
    if fit_imputer is None:
        print("  Fitting imputer (median strategy)...")
        imputer = SimpleImputer(strategy='median')
        X_imputed = imputer.fit_transform(X)
    else:
        print("  Applying pre-fitted imputer...")
        imputer = fit_imputer
        X_imputed = imputer.transform(X)

    X_imputed = pd.DataFrame(X_imputed, columns=X.columns)

    # Normalize features (helps with feature importance interpretation)
    if fit_scaler is None:
        print("  Fitting scaler (standardization)...")
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_imputed)
    else:
        print("  Applying pre-fitted scaler...")
        scaler = fit_scaler
        X_scaled = scaler.transform(X_imputed)

    X_scaled = pd.DataFrame(X_scaled, columns=X.columns)

    return X_scaled, y, metadata, imputer, scaler, X.columns.tolist()


def apply_smote(X_train, y_train):
    """
    Apply SMOTE to balance classes in training set.

    Note: Only apply to training set, NEVER to validation/test!
    """
    print("\n" + "=" * 80)
    print("APPLYING SMOTE FOR CLASS IMBALANCE")
    print("=" * 80)

    print(f"\nOriginal class distribution:")
    for i, count in enumerate(np.bincount(y_train)):
        pct = count / len(y_train) * 100
        print(f"  Class {i}: {count:>4} ({pct:>5.1f}%)")

    # SMOTE with custom sampling strategy
    # Don't oversample to perfect balance - creates too many synthetic samples
    # Target: Make minority classes at least 20% of majority class
    # BUT skip classes with < 6 samples (SMOTE k_neighbors default is 5)
    class_counts = np.bincount(y_train)
    max_count = class_counts.max()

    sampling_strategy = {}
    for i in range(len(class_counts)):
        if class_counts[i] < max_count * 0.2 and class_counts[i] >= 6:
            sampling_strategy[i] = int(max_count * 0.2)

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
        print("\n[SKIP] SMOTE not needed - classes already balanced")
        return X_train, y_train


def train_random_forest(X_train, y_train, X_val, y_val):
    """
    Train Random Forest classifier with class weights.
    """
    print("\n" + "=" * 80)
    print("TRAINING RANDOM FOREST CLASSIFIER")
    print("=" * 80)

    print("\nHyperparameters:")
    print("  n_estimators: 200")
    print("  max_depth: 10")
    print("  min_samples_split: 20")
    print("  class_weight: balanced")
    print("  random_state: 42")

    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=20,
        min_samples_leaf=10,
        class_weight='balanced',  # Additional class weighting
        random_state=42,
        n_jobs=-1,
        verbose=1
    )

    print("\nTraining...")
    rf.fit(X_train, y_train)
    print("[OK] Training complete")

    # Evaluate on training set (sanity check)
    y_train_pred = rf.predict(X_train)
    train_f1 = f1_score(y_train, y_train_pred, average='weighted')
    train_acc = accuracy_score(y_train, y_train_pred)

    print(f"\nTraining Set Performance:")
    print(f"  Accuracy: {train_acc:.3f}")
    print(f"  Weighted F1: {train_f1:.3f}")

    # Evaluate on validation set
    y_val_pred = rf.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='weighted')
    val_acc = accuracy_score(y_val, y_val_pred)

    print(f"\nValidation Set Performance:")
    print(f"  Accuracy: {val_acc:.3f}")
    print(f"  Weighted F1: {val_f1:.3f}")

    return rf, y_val_pred


def evaluate_model(y_true, y_pred, dataset_name="Test"):
    """
    Comprehensive model evaluation.
    """
    print("\n" + "=" * 80)
    print(f"{dataset_name.upper()} SET EVALUATION")
    print("=" * 80)

    # Overall metrics
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
    print(classification_report(y_true, y_pred, target_names=class_names, digits=3))

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    print(f"\nConfusion Matrix:")
    print(f"         Predicted:")
    print(f"           Bench  Part   Reg   AllStar")
    for i, label in enumerate(class_names):
        print(f"Actual {label:<10} {cm[i][0]:>5} {cm[i][1]:>5} {cm[i][2]:>5} {cm[i][3]:>5}")

    return f1_weighted, acc


def analyze_feature_importance(model, feature_names, top_n=25):
    """
    Analyze and display feature importance.

    Focus on new enhanced features in top ranking.
    """
    print("\n" + "=" * 80)
    print("FEATURE IMPORTANCE ANALYSIS")
    print("=" * 80)

    importances = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    # Identify enhanced features
    enhanced_features = [
        'plus_tool_count', 'offensive_ceiling', 'defensive_floor',
        'hit_power_ratio', 'power_speed_number_v2', 'age_relative_ops',
        'levels_per_year', 'has_elite_tool', 'tool_variance',
        'contact_profile_average', 'contact_profile_balanced',
        'contact_profile_contact', 'contact_profile_slugger'
    ]

    print(f"\nTop {top_n} Most Important Features:")
    print(f"  {'Rank':<5} {'Feature':<35} {'Importance':<12} {'Type'}")
    print("  " + "-" * 70)

    for rank, (idx, row) in enumerate(importances.head(top_n).iterrows(), 1):
        is_enhanced = row['feature'] in enhanced_features
        feature_type = "[ENHANCED]" if is_enhanced else ""
        print(f"  {rank:>2}.   {row['feature']:<35} {row['importance']:.4f}     {feature_type}")

    # Summary of enhanced feature performance
    enhanced_in_top_n = sum(1 for f in importances.head(top_n)['feature'] if f in enhanced_features)
    print(f"\n[ENHANCED FEATURE SUMMARY]")
    print(f"  Enhanced features in top {top_n}: {enhanced_in_top_n}/{len(enhanced_features)}")

    # Total contribution of enhanced features
    enhanced_importance = importances[importances['feature'].isin(enhanced_features)]['importance'].sum()
    print(f"  Total importance contribution: {enhanced_importance:.4f} ({enhanced_importance*100:.1f}%)")

    return importances


def compare_to_baseline(test_f1, test_acc):
    """
    Compare enhanced model to original baseline.
    """
    print("\n" + "=" * 80)
    print("COMPARISON TO BASELINE MODEL")
    print("=" * 80)

    baseline_f1 = 0.684
    baseline_acc = 0.684

    f1_improvement = test_f1 - baseline_f1
    acc_improvement = test_acc - baseline_acc

    print(f"\n{'Metric':<20} {'Baseline':<12} {'Enhanced':<12} {'Change':<12}")
    print("-" * 60)
    print(f"{'Weighted F1':<20} {baseline_f1:.3f}        {test_f1:.3f}        {f1_improvement:+.3f}")
    print(f"{'Accuracy':<20} {baseline_acc:.3f}        {test_acc:.3f}        {acc_improvement:+.3f}")

    # Interpret results
    print(f"\n[IMPROVEMENT ANALYSIS]")
    if f1_improvement >= 0.03:
        print(f"  ✅ EXCELLENT: Enhanced features improved F1 by {f1_improvement:.3f} (target: +0.03)")
        print(f"     This validates the Phase 1 feature engineering approach!")
    elif f1_improvement >= 0.02:
        print(f"  ✅ GOOD: Enhanced features improved F1 by {f1_improvement:.3f}")
        print(f"     Close to target. Consider Phase 2 improvements.")
    elif f1_improvement > 0:
        print(f"  ⚠️  MARGINAL: Enhanced features improved F1 by {f1_improvement:.3f}")
        print(f"     Below target. Review feature engineering strategy.")
    else:
        print(f"  ❌ NO IMPROVEMENT: Enhanced features did not improve performance")
        print(f"     Need to investigate: Are enhanced features redundant?")


def analyze_errors(y_true, y_pred, metadata, top_n=20):
    """
    Analyze misclassified prospects.
    """
    print("\n" + "=" * 80)
    print("ERROR ANALYSIS")
    print("=" * 80)

    errors = metadata.copy()
    errors['predicted'] = y_pred
    errors['correct'] = (y_true == y_pred)

    misclassified = errors[~errors['correct']].copy()

    print(f"\nMisclassification Summary:")
    print(f"  Total samples: {len(errors):,}")
    print(f"  Correct: {sum(errors['correct']):,} ({sum(errors['correct'])/len(errors)*100:.1f}%)")
    print(f"  Misclassified: {len(misclassified):,} ({len(misclassified)/len(errors)*100:.1f}%)")

    # Map numeric to labels
    class_map = {0: 'Bench', 1: 'Part-Time', 2: 'Regular', 3: 'All-Star'}
    misclassified['predicted_label'] = misclassified['predicted'].map(class_map)

    print(f"\nTop {top_n} Misclassified Prospects (by FV):")
    print(f"{'Name':<25} {'Pos':<4} {'FV':<3} {'Actual':<12} {'Predicted':<12}")
    print("-" * 80)

    top_errors = misclassified.nlargest(top_n, 'fangraphs_fv')
    for _, row in top_errors.iterrows():
        print(f"{row['name']:<25} {row['position']:<4} {int(row['fangraphs_fv']):<3} "
              f"{row['target_label']:<12} {row['predicted_label']:<12}")

    return misclassified


def main():
    print("=" * 80)
    print("ENHANCED BASELINE MODEL TRAINING - MLB EXPECTATION CLASSIFICATION")
    print("=" * 80)

    player_type = 'hitters'
    print(f"\nPlayer Type: {player_type.upper()}")
    print(f"Features: 49 (35 original + 13 enhanced)")
    print(f"Target: 4-class MLB Expectation (Bench/Part-Time/Regular/All-Star)")
    print(f"Algorithm: Random Forest with SMOTE + Class Weights")
    print(f"\nExpected Improvement: +0.03-0.05 F1 (0.684 -> 0.71-0.73)")

    # Load enhanced data files
    train_file = 'ml_data_hitters_enhanced_train_20251019_222539.csv'
    val_file = 'ml_data_hitters_enhanced_val_20251019_222540.csv'
    test_file = 'ml_data_hitters_enhanced_test_20251019_222541.csv'

    # Step 1: Load and preprocess
    print("\n" + "=" * 80)
    print("STEP 1: DATA LOADING AND PREPROCESSING")
    print("=" * 80)

    X_train, y_train, metadata_train, imputer, scaler, train_columns = load_and_preprocess_data(train_file)
    X_val, y_val, metadata_val, _, _, _ = load_and_preprocess_data(val_file, imputer, scaler, train_columns)
    X_test, y_test, metadata_test, _, _, _ = load_and_preprocess_data(test_file, imputer, scaler, train_columns)

    # Step 2: Apply SMOTE to training set
    X_train_resampled, y_train_resampled = apply_smote(X_train, y_train)

    # Step 3: Train model
    model, y_val_pred = train_random_forest(
        X_train_resampled, y_train_resampled,
        X_val, y_val
    )

    # Step 4: Feature importance (focus on enhanced features)
    feature_importances = analyze_feature_importance(model, X_train.columns, top_n=25)

    # Step 5: Validation set evaluation
    val_f1, val_acc = evaluate_model(y_val, y_val_pred, "Validation")

    # Step 6: Error analysis on validation set
    val_errors = analyze_errors(y_val, y_val_pred, metadata_val)

    # Step 7: Test set evaluation (FINAL HOLDOUT)
    print("\n" + "=" * 80)
    print("FINAL TEST SET EVALUATION (HOLDOUT)")
    print("=" * 80)
    print("\nPredicting on test set...")

    y_test_pred = model.predict(X_test)
    test_f1, test_acc = evaluate_model(y_test, y_test_pred, "Test")

    # Test set error analysis
    test_errors = analyze_errors(y_test, y_test_pred, metadata_test)

    # Step 8: Compare to baseline
    compare_to_baseline(test_f1, test_acc)

    # Final summary
    print("\n" + "=" * 80)
    print("ENHANCED MODEL SUMMARY")
    print("=" * 80)

    print(f"\nModel: Random Forest (200 trees, max_depth=10)")
    print(f"Class Balancing: SMOTE + class_weight='balanced'")
    print(f"Player Type: {player_type.upper()}")
    print(f"Feature Count: {len(X_train.columns)} (35 original + 13 enhanced)")

    print(f"\nPerformance Summary:")
    print(f"  {'Dataset':<12} {'Samples':<8} {'Accuracy':<10} {'Weighted F1':<12}")
    print(f"  {'-'*50}")
    print(f"  {'Validation':<12} {len(X_val):>7,} {val_acc:>9.3f} {val_f1:>11.3f}")
    print(f"  {'Test':<12} {len(X_test):>7,} {test_acc:>9.3f} {test_f1:>11.3f}")

    # Success criteria check
    print(f"\nPhase 1 Success Criteria:")
    baseline_f1 = 0.684
    improvement = test_f1 - baseline_f1

    if improvement >= 0.03:
        status = "✅ SUCCESS"
        print(f"  {status}: Achieved +{improvement:.3f} F1 improvement (target: +0.03)")
        print(f"  Ready to proceed to Phase 2 (Position-specific models)")
    elif improvement >= 0.02:
        status = "⚠️  PARTIAL"
        print(f"  {status}: Achieved +{improvement:.3f} F1 improvement (below +0.03 target)")
        print(f"  Consider tuning before Phase 2")
    else:
        status = "❌ FAILED"
        print(f"  {status}: Only +{improvement:.3f} F1 improvement")
        print(f"  Need to revise feature engineering approach")

    # Save feature importance
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    importance_file = f'feature_importance_hitters_enhanced_{timestamp}.csv'
    feature_importances.to_csv(importance_file, index=False)
    print(f"\n[OK] Feature importance saved to: {importance_file}")

    # Save error analysis
    error_file = f'error_analysis_hitters_enhanced_{timestamp}.csv'
    test_errors.to_csv(error_file, index=False)
    print(f"[OK] Error analysis saved to: {error_file}")

    print("\n" + "=" * 80)
    print("ENHANCED MODEL TRAINING COMPLETE")
    print("=" * 80)

    if improvement >= 0.03:
        print(f"\nNext Steps (Phase 2):")
        print(f"  1. Create position-specific datasets (IF/OF/C/1B/3B)")
        print(f"  2. Train separate models for each position")
        print(f"  3. Expected improvement: +0.05-0.10 F1")
        print(f"  4. Target: 0.76-0.82 F1 (match pitcher performance)")
    else:
        print(f"\nNext Steps:")
        print(f"  1. Review feature importance - which enhanced features helped?")
        print(f"  2. Analyze misclassifications - any patterns?")
        print(f"  3. Consider alternative features or better SMOTE strategy")


if __name__ == "__main__":
    main()
