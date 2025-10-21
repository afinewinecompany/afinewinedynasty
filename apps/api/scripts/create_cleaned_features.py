"""
Remove Redundant Features from Enhanced Dataset
================================================

This script:
1. Removes redundant features that hurt model performance
2. Keeps only the best version of correlated features
3. Creates cleaned datasets for position-specific modeling

Redundant features to remove:
- power_speed_number (keep power_speed_number_v2)
- contact_profile_* one-hot features (low importance, redundant with hit/power grades)
"""

import pandas as pd
import numpy as np
from datetime import datetime

def remove_redundant_features(df, feature_columns):
    """
    Remove redundant features, keep only best versions.

    Args:
        df: DataFrame with all features
        feature_columns: List of feature column names

    Returns:
        df with redundant features removed
    """
    print("\nRemoving redundant features...")

    # Features to remove (identified from feature importance analysis)
    redundant_features = [
        'power_speed_number',  # Keep power_speed_number_v2 (13.75% vs 1.42% importance)
        'contact_profile_average',  # Low importance, redundant with hit/power ratio
        'contact_profile_balanced',
        'contact_profile_contact',
        'contact_profile_slugger'
    ]

    # Remove redundant features
    features_removed = []
    for feat in redundant_features:
        if feat in feature_columns:
            features_removed.append(feat)

    print(f"  Removing {len(features_removed)} redundant features:")
    for feat in features_removed:
        print(f"    - {feat}")

    # Keep only non-redundant features
    cleaned_features = [f for f in feature_columns if f not in redundant_features]

    print(f"\n  Original features: {len(feature_columns)}")
    print(f"  Cleaned features:  {len(cleaned_features)}")
    print(f"  Removed:          {len(features_removed)}")

    return df[cleaned_features], cleaned_features


def process_split(input_file, output_file):
    """
    Process a single train/val/test split.
    """
    print(f"\nProcessing: {input_file}")

    # Load data
    df = pd.read_csv(input_file)
    print(f"  Loaded: {len(df):,} samples, {len(df.columns)} columns")

    # Separate metadata and features
    metadata_cols = ['prospect_id', 'data_year', 'name', 'position', 'fangraphs_id']
    target_cols = ['target', 'target_label', 'fangraphs_fv']

    feature_cols = [c for c in df.columns if c not in metadata_cols + target_cols]

    # Remove redundant features
    df_features, cleaned_features = remove_redundant_features(df[feature_cols], feature_cols)

    # Recombine with metadata and target
    df_cleaned = pd.concat([
        df[metadata_cols + target_cols],
        df_features
    ], axis=1)

    # Save cleaned dataset
    df_cleaned.to_csv(output_file, index=False)
    print(f"  Saved: {output_file}")
    print(f"  Shape: {df_cleaned.shape}")

    return df_cleaned


def main():
    print("=" * 80)
    print("REMOVE REDUNDANT FEATURES - CREATE CLEANED DATASETS")
    print("=" * 80)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Process all three splits
    splits = [
        ('ml_data_hitters_enhanced_train_20251019_222539.csv',
         f'ml_data_hitters_cleaned_train_{timestamp}.csv'),
        ('ml_data_hitters_enhanced_val_20251019_222540.csv',
         f'ml_data_hitters_cleaned_val_{timestamp}.csv'),
        ('ml_data_hitters_enhanced_test_20251019_222541.csv',
         f'ml_data_hitters_cleaned_test_{timestamp}.csv')
    ]

    cleaned_datasets = []
    for input_file, output_file in splits:
        df_cleaned = process_split(input_file, output_file)
        cleaned_datasets.append((output_file, df_cleaned))

    # Summary
    print("\n" + "=" * 80)
    print("CLEANING COMPLETE")
    print("=" * 80)

    print("\nCleaned datasets created:")
    for output_file, df in cleaned_datasets:
        print(f"  {output_file}")
        print(f"    Samples: {len(df):,}")
        print(f"    Features: {len([c for c in df.columns if c not in ['prospect_id', 'data_year', 'name', 'position', 'fangraphs_id', 'target', 'target_label', 'fangraphs_fv']])}")

    print("\n" + "=" * 80)
    print("Next Steps:")
    print("  1. Create position-specific datasets from cleaned data")
    print("  2. Train position-specific models")
    print("  3. Expected improvement: +0.05-0.10 F1")
    print("=" * 80)


if __name__ == "__main__":
    main()
