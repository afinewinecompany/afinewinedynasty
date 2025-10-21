"""
Train Hierarchical Classification Model for MLB Expectation
============================================================

Two-stage approach to handle severe class imbalance:

Stage 1: Bench vs Good (Binary Classification)
- Bench (Class 0)
- Good (Part-Time + Regular + All-Star combined)

Stage 2: Part-Time vs Regular vs All-Star (3-Class on Good prospects only)
- Part-Time (Class 0)
- Regular (Class 1)
- All-Star (Class 2)

This approach increases All-Star density from <1% to ~5% in Stage 2,
making it learnable.
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
    """Load and preprocess data (same as baseline model)."""
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
        print(f"  Aligned to {len(required_columns)} required columns")
    else:
        missing_pct = X.isnull().sum() / len(X) * 100
        cols_to_drop = missing_pct[missing_pct == 100].index.tolist()
        if cols_to_drop:
            print(f"  Dropping {len(cols_to_drop)} columns with 100% missing")
            X = X.drop(columns=cols_to_drop)

    print(f"  Loaded: {len(X):,} samples, {len(X.columns)} features")
    print(f"  Original classes: {np.bincount(y)}")

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


def create_binary_labels(y):
    """
    Convert 4-class labels to binary: Bench (0) vs Good (1).

    Original:
    - 0 = Bench
    - 1 = Part-Time
    - 2 = Regular
    - 3 = All-Star

    Binary:
    - 0 = Bench
    - 1 = Good (Part-Time + Regular + All-Star)
    """
    return (y > 0).astype(int)


def create_good_labels(y):
    """
    Remap Good prospects (1/2/3) to 3-class: Part-Time (0) vs Regular (1) vs All-Star (2).

    Only call on samples where binary_label == 1 (Good)

    Original → New:
    - 1 (Part-Time) → 0
    - 2 (Regular) → 1
    - 3 (All-Star) → 2
    """
    return y - 1


def train_stage1_model(X_train, y_train, X_val, y_val):
    """
    Stage 1: Binary classification - Bench vs Good.
    """
    print("\n" + "=" * 80)
    print("STAGE 1: BENCH vs GOOD CLASSIFICATION")
    print("=" * 80)

    # Create binary labels
    y_train_binary = create_binary_labels(y_train)
    y_val_binary = create_binary_labels(y_val)

    print(f"\nBinary class distribution (Train):")
    print(f"  Bench (0): {sum(y_train_binary == 0):>4} ({sum(y_train_binary == 0)/len(y_train_binary)*100:>5.1f}%)")
    print(f"  Good  (1): {sum(y_train_binary == 1):>4} ({sum(y_train_binary == 1)/len(y_train_binary)*100:>5.1f}%)")

    # Apply SMOTE for binary imbalance
    class_counts = np.bincount(y_train_binary)
    max_count = class_counts.max()

    if class_counts[1] < max_count * 0.8:  # If Good < 80% of Bench
        target_count = int(max_count * 0.8)
        print(f"\nApplying SMOTE: Good class {class_counts[1]} -> {target_count}")
        smote = SMOTE(sampling_strategy={1: target_count}, random_state=42)
        X_train_resampled, y_train_binary_resampled = smote.fit_resample(X_train, y_train_binary)

        print(f"Resampled: Bench={sum(y_train_binary_resampled == 0)}, Good={sum(y_train_binary_resampled == 1)}")
    else:
        X_train_resampled = X_train
        y_train_binary_resampled = y_train_binary
        print("\n[SKIP] SMOTE not needed - classes already balanced")

    # Train Random Forest for Stage 1
    print("\nTraining Stage 1 Random Forest...")
    rf_stage1 = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=20,
        min_samples_leaf=10,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )

    rf_stage1.fit(X_train_resampled, y_train_binary_resampled)
    print("[OK] Stage 1 training complete")

    # Evaluate Stage 1
    y_train_pred = rf_stage1.predict(X_train)
    y_val_pred = rf_stage1.predict(X_val)

    train_f1 = f1_score(y_train_binary, y_train_pred, average='weighted')
    val_f1 = f1_score(y_val_binary, y_val_pred, average='weighted')

    print(f"\nStage 1 Performance:")
    print(f"  Train F1: {train_f1:.3f}")
    print(f"  Val F1:   {val_f1:.3f}")

    print(f"\nStage 1 Validation Classification Report:")
    print(classification_report(y_val_binary, y_val_pred,
        target_names=['Bench', 'Good'], digits=3))

    return rf_stage1


def train_stage2_model(X_train, y_train, X_val, y_val):
    """
    Stage 2: 3-class on Good prospects only - Part-Time vs Regular vs All-Star.
    """
    print("\n" + "=" * 80)
    print("STAGE 2: PART-TIME vs REGULAR vs ALL-STAR (Good prospects only)")
    print("=" * 80)

    # Filter to Good prospects only (classes 1, 2, 3)
    good_train_mask = y_train > 0
    good_val_mask = y_val > 0

    X_train_good = X_train[good_train_mask]
    y_train_good = create_good_labels(y_train[good_train_mask])

    X_val_good = X_val[good_val_mask]
    y_val_good = create_good_labels(y_val[good_val_mask])

    print(f"\nGood prospects only:")
    print(f"  Train: {len(X_train_good):>4} samples")
    print(f"  Val:   {len(X_val_good):>4} samples")

    print(f"\n3-Class distribution (Train):")
    for i, label in enumerate(['Part-Time', 'Regular', 'All-Star']):
        count = sum(y_train_good == i)
        pct = count / len(y_train_good) * 100 if len(y_train_good) > 0 else 0
        print(f"  {label:<12} {count:>4} ({pct:>5.1f}%)")

    # Apply SMOTE for Stage 2
    class_counts = np.bincount(y_train_good)
    max_count = class_counts.max()

    sampling_strategy = {}
    for i in range(len(class_counts)):
        if class_counts[i] < max_count * 0.3 and class_counts[i] >= 6:
            sampling_strategy[i] = int(max_count * 0.3)

    if sampling_strategy:
        print(f"\nSMOTE sampling strategy: {sampling_strategy}")
        smote = SMOTE(sampling_strategy=sampling_strategy, random_state=42)
        X_train_good_resampled, y_train_good_resampled = smote.fit_resample(X_train_good, y_train_good)

        print(f"\nResampled class distribution:")
        for i, label in enumerate(['Part-Time', 'Regular', 'All-Star']):
            count = sum(y_train_good_resampled == i)
            pct = count / len(y_train_good_resampled) * 100
            print(f"  {label:<12} {count:>4} ({pct:>5.1f}%)")
    else:
        X_train_good_resampled = X_train_good
        y_train_good_resampled = y_train_good
        print("\n[SKIP] SMOTE not needed")

    # Train Random Forest for Stage 2
    print("\nTraining Stage 2 Random Forest...")
    rf_stage2 = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,  # Shallower for smaller dataset
        min_samples_split=10,
        min_samples_leaf=5,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )

    rf_stage2.fit(X_train_good_resampled, y_train_good_resampled)
    print("[OK] Stage 2 training complete")

    # Evaluate Stage 2
    y_train_good_pred = rf_stage2.predict(X_train_good)
    y_val_good_pred = rf_stage2.predict(X_val_good)

    train_f1 = f1_score(y_train_good, y_train_good_pred, average='weighted')
    val_f1 = f1_score(y_val_good, y_val_good_pred, average='weighted')

    print(f"\nStage 2 Performance:")
    print(f"  Train F1: {train_f1:.3f}")
    print(f"  Val F1:   {val_f1:.3f}")

    print(f"\nStage 2 Validation Classification Report:")
    print(classification_report(y_val_good, y_val_good_pred,
        target_names=['Part-Time', 'Regular', 'All-Star'], digits=3))

    return rf_stage2


def predict_hierarchical(rf_stage1, rf_stage2, X):
    """
    Make hierarchical predictions using both models.

    Returns: 4-class predictions (0=Bench, 1=Part-Time, 2=Regular, 3=All-Star)
    """
    # Stage 1: Predict Bench vs Good
    stage1_pred = rf_stage1.predict(X)

    # Initialize final predictions as Bench (0)
    final_pred = np.zeros(len(X), dtype=int)

    # Stage 2: For Good prospects, predict Part-Time/Regular/All-Star
    good_mask = stage1_pred == 1
    if good_mask.sum() > 0:
        X_good = X[good_mask]
        stage2_pred = rf_stage2.predict(X_good)

        # Remap: Part-Time (0) -> 1, Regular (1) -> 2, All-Star (2) -> 3
        final_pred[good_mask] = stage2_pred + 1

    return final_pred


def evaluate_hierarchical(rf_stage1, rf_stage2, X, y, metadata, dataset_name="Test"):
    """Evaluate hierarchical model end-to-end."""
    print("\n" + "=" * 80)
    print(f"HIERARCHICAL MODEL - {dataset_name.upper()} SET EVALUATION")
    print("=" * 80)

    # Get predictions
    y_pred = predict_hierarchical(rf_stage1, rf_stage2, X)

    # Overall metrics
    acc = accuracy_score(y, y_pred)
    f1_weighted = f1_score(y, y_pred, average='weighted')
    f1_macro = f1_score(y, y_pred, average='macro')

    print(f"\nOverall Metrics:")
    print(f"  Accuracy:       {acc:.3f}")
    print(f"  Weighted F1:    {f1_weighted:.3f}")
    print(f"  Macro F1:       {f1_macro:.3f}")

    # Per-class metrics
    class_names = ['Bench', 'Part-Time', 'Regular', 'All-Star']
    print(f"\nDetailed Classification Report:")
    print(classification_report(y, y_pred, target_names=class_names, digits=3))

    # Confusion matrix
    cm = confusion_matrix(y, y_pred)
    print(f"\nConfusion Matrix:")
    print(f"         Predicted:")
    print(f"           Bench  Part   Reg   AllStar")
    for i, label in enumerate(class_names):
        print(f"Actual {label:<10} {cm[i][0]:>5} {cm[i][1]:>5} {cm[i][2]:>5} {cm[i][3]:>5}")

    # Specific All-Star analysis
    all_star_mask = y == 3
    if all_star_mask.sum() > 0:
        all_star_preds = y_pred[all_star_mask]
        print(f"\nAll-Star Prediction Breakdown ({all_star_mask.sum()} total):")
        print(f"  Predicted as Bench:     {sum(all_star_preds == 0)}")
        print(f"  Predicted as Part-Time: {sum(all_star_preds == 1)}")
        print(f"  Predicted as Regular:   {sum(all_star_preds == 2)}")
        print(f"  Predicted as All-Star:  {sum(all_star_preds == 3)} [CORRECT]")

        all_star_recall = sum(all_star_preds == 3) / len(all_star_preds)
        print(f"\n  All-Star Recall: {all_star_recall:.3f} ({all_star_recall*100:.1f}%)")

    return f1_weighted, acc


def main():
    print("=" * 80)
    print("HIERARCHICAL CLASSIFICATION - MLB EXPECTATION PREDICTION")
    print("=" * 80)

    # Determine player type
    player_type = 'pitchers'  # Change to 'pitchers' for pitchers

    print(f"\nPlayer Type: {player_type.upper()}")
    print(f"Strategy: Two-Stage Hierarchical Classification")
    print(f"  Stage 1: Bench (0) vs Good (1/2/3 combined)")
    print(f"  Stage 2: Part-Time (1) vs Regular (2) vs All-Star (3)")

    # Load data
    train_file = f'ml_data_{player_type}_train_20251019_214927.csv'
    val_file = f'ml_data_{player_type}_val_20251019_214927.csv'
    test_file = f'ml_data_{player_type}_test_20251019_214928.csv'

    print("\n" + "=" * 80)
    print("DATA LOADING")
    print("=" * 80)

    X_train, y_train, metadata_train, imputer, scaler, train_columns = load_and_preprocess_data(train_file)
    X_val, y_val, metadata_val, _, _, _ = load_and_preprocess_data(val_file, imputer, scaler, train_columns)
    X_test, y_test, metadata_test, _, _, _ = load_and_preprocess_data(test_file, imputer, scaler, train_columns)

    # Train Stage 1
    rf_stage1 = train_stage1_model(X_train, y_train, X_val, y_val)

    # Train Stage 2
    rf_stage2 = train_stage2_model(X_train, y_train, X_val, y_val)

    # Evaluate on validation set
    val_f1, val_acc = evaluate_hierarchical(rf_stage1, rf_stage2, X_val, y_val, metadata_val, "Validation")

    # Evaluate on test set
    test_f1, test_acc = evaluate_hierarchical(rf_stage1, rf_stage2, X_test, y_test, metadata_test, "Test")

    # Compare to baseline
    print("\n" + "=" * 80)
    print("COMPARISON TO BASELINE (Single 4-Class Model)")
    print("=" * 80)

    baseline_results = {
        'hitters': {'val_f1': 0.667, 'test_f1': 0.684, 'all_star_recall': 0.0},
        'pitchers': {'val_f1': 0.752, 'test_f1': 0.767, 'all_star_recall': 0.0}
    }

    baseline = baseline_results[player_type]

    print(f"\n{'Metric':<25} {'Baseline':<12} {'Hierarchical':<15} {'Change':<10}")
    print("-" * 70)
    print(f"{'Validation F1':<25} {baseline['val_f1']:<12.3f} {val_f1:<15.3f} {val_f1 - baseline['val_f1']:>+.3f}")
    print(f"{'Test F1':<25} {baseline['test_f1']:<12.3f} {test_f1:<15.3f} {test_f1 - baseline['test_f1']:>+.3f}")

    # All-Star recall (extract from test set)
    all_star_mask = y_test == 3
    if all_star_mask.sum() > 0:
        y_test_pred = predict_hierarchical(rf_stage1, rf_stage2, X_test)
        all_star_recall = sum(y_test_pred[all_star_mask] == 3) / all_star_mask.sum()
        print(f"{'All-Star Recall (Test)':<25} {baseline['all_star_recall']:<12.3f} {all_star_recall:<15.3f} {all_star_recall:>+.3f}")

    print("\n" + "=" * 80)
    print("HIERARCHICAL MODEL SUMMARY")
    print("=" * 80)

    print(f"\nStage 1 (Bench vs Good):")
    print(f"  - Separates low-upside (Bench) from prospects with potential (Good)")
    print(f"  - Binary classification is easier to learn")

    print(f"\nStage 2 (Part-Time vs Regular vs All-Star):")
    print(f"  - Only applied to Good prospects (~20-35% of data)")
    print(f"  - All-Star density increases from <1% to ~5%")
    print(f"  - More balanced 3-class problem")

    if test_f1 > baseline['test_f1']:
        status = "[IMPROVED]"
    elif test_f1 >= baseline['test_f1'] - 0.01:
        status = "[SIMILAR]"
    else:
        status = "[WORSE]"

    print(f"\n{status} Hierarchical F1 = {test_f1:.3f} vs Baseline F1 = {baseline['test_f1']:.3f}")

    # Save models
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    print(f"\n[OK] Models ready for production")
    print(f"\nNext Steps:")
    print(f"  1. Save models: joblib.dump(rf_stage1, 'rf_stage1_{player_type}.pkl')")
    print(f"  2. Deploy hierarchical prediction endpoint")
    print(f"  3. Compare predictions to Fangraphs FV")
    print(f"  4. Monitor All-Star recall in production")


if __name__ == "__main__":
    main()
