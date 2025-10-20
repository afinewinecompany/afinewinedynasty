"""
Convert Existing 4-Class Datasets to 3-Class
=============================================

Quick script to convert existing 4-class ML datasets to 3-class by remapping labels:
- Class 0 (Bench) → Class 0 (Bench/Reserve)
- Class 1 (Part-Time) → Class 1 (Part-Time)
- Class 2 (Regular) → Class 2 (MLB Regular+)
- Class 3 (All-Star) → Class 2 (MLB Regular+)
"""

import pandas as pd
from datetime import datetime

def convert_to_3class(input_file, output_file):
    """Convert 4-class dataset to 3-class."""
    print(f"\nConverting: {input_file}")

    df = pd.read_csv(input_file)

    # Show original distribution
    orig_dist = df['target'].value_counts().sort_index()
    print(f"  Original (4-class): {dict(orig_dist)}")

    # Remap: Regular (2) and All-Star (3) → MLB Regular+ (2)
    df['target'] = df['target'].apply(lambda x: 2 if x >= 2 else x)

    # Update target_label
    label_map = {0: 'Bench/Reserve', 1: 'Part-Time', 2: 'MLB Regular+'}
    df['target_label'] = df['target'].map(label_map)

    # Show new distribution
    new_dist = df['target'].value_counts().sort_index()
    print(f"  New (3-class):      {dict(new_dist)}")

    # Save
    df.to_csv(output_file, index=False)
    print(f"  Saved: {output_file} ({len(df)} rows)")

    return df


def main():
    print("="*80)
    print("CONVERT 4-CLASS DATASETS TO 3-CLASS")
    print("="*80)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Define input/output files
    files = [
        ('ml_data_hitters_train_20251019_225042.csv', f'ml_data_hitters_3class_train_{timestamp}.csv'),
        ('ml_data_hitters_val_20251019_225043.csv', f'ml_data_hitters_3class_val_{timestamp}.csv'),
        ('ml_data_hitters_test_20251019_225043.csv', f'ml_data_hitters_3class_test_{timestamp}.csv'),
        ('ml_data_pitchers_train_20251019_225042.csv', f'ml_data_pitchers_3class_train_{timestamp}.csv'),
        ('ml_data_pitchers_val_20251019_225043.csv', f'ml_data_pitchers_3class_val_{timestamp}.csv'),
        ('ml_data_pitchers_test_20251019_225043.csv', f'ml_data_pitchers_3class_test_{timestamp}.csv'),
    ]

    results = {}

    for input_file, output_file in files:
        try:
            df = convert_to_3class(input_file, output_file)
            player_type = 'hitters' if 'hitters' in input_file else 'pitchers'
            split = 'train' if 'train' in input_file else ('val' if 'val' in input_file else 'test')
            results[f"{player_type}_{split}"] = df
        except FileNotFoundError:
            print(f"  [SKIP] File not found: {input_file}")

    # Summary
    print("\n" + "="*80)
    print("CONVERSION COMPLETE")
    print("="*80)

    print(f"\n{'Split':<12} {'Hitters':<10} {'Pitchers':<10}")
    print("-" * 35)

    for split in ['train', 'val', 'test']:
        h_key = f"hitters_{split}"
        p_key = f"pitchers_{split}"
        h_count = len(results[h_key]) if h_key in results else 0
        p_count = len(results[p_key]) if p_key in results else 0
        print(f"{split.capitalize():<12} {h_count:>9} {p_count:>9}")

    # Show training class distribution
    if 'hitters_train' in results:
        train_h = results['hitters_train']
        train_dist_h = train_h['target'].value_counts().sort_index()

        print("\nTraining Data (Hitters) - 3-Class Distribution:")
        labels = {0: 'Bench/Reserve', 1: 'Part-Time', 2: 'MLB Regular+'}
        for cls, count in train_dist_h.items():
            pct = count / len(train_h) * 100
            print(f"  {labels[cls]:<18} {count:>3} ({pct:>5.1f}%)")

        print(f"\nKey Improvement:")
        print(f"  4-class: 0 All-Star training examples")
        print(f"  3-class: {train_dist_h.get(2, 0)} MLB Regular+ training examples")

    print("\nNext Steps:")
    print("  1. Train 3-class Random Forest baseline")
    print("  2. Expected: 0.72-0.75 F1")
    print("  3. Implement XGBoost: 0.74-0.78 F1")


if __name__ == "__main__":
    main()
