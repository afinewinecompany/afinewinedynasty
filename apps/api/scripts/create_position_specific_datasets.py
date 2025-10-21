"""
Create Position-Specific Datasets for Hitter Models
====================================================

This script splits cleaned hitter data into position groups:
- Infielders (IF): SS, 2B, 3B
- Outfielders (OF): CF, RF, LF
- Catchers (C): C
- Corner (1B): 1B, DH

Each position group will get its own model trained with position-specific
feature importance and SMOTE strategies.
"""

import pandas as pd
import numpy as np
from datetime import datetime

# Position groupings
POSITION_GROUPS = {
    'IF': ['SS', '2B', '3B'],
    'OF': ['CF', 'RF', 'LF'],
    'C': ['C'],
    'Corner': ['1B', 'DH']
}


def analyze_position_distribution(df):
    """
    Analyze how prospects are distributed across positions.
    """
    print("\nPosition Distribution Analysis:")
    print("=" * 80)

    position_counts = df['position'].value_counts()
    print("\nIndividual Positions:")
    for pos, count in position_counts.items():
        pct = count / len(df) * 100
        print(f"  {pos:<4} {count:>4} ({pct:>5.1f}%)")

    print("\nPosition Groups:")
    for group, positions in POSITION_GROUPS.items():
        group_df = df[df['position'].isin(positions)]
        pct = len(group_df) / len(df) * 100
        print(f"  {group:<8} {len(group_df):>4} ({pct:>5.1f}%)")

        # Class distribution within group
        if len(group_df) > 0:
            class_dist = group_df['target'].value_counts().sort_index()
            class_str = ", ".join([f"{int(cls)}:{count}" for cls, count in class_dist.items()])
            print(f"           Class dist: {class_str}")


def create_position_group_dataset(df, group_name, positions, timestamp):
    """
    Create dataset for a single position group.

    Args:
        df: Full dataset
        group_name: Name of position group (IF/OF/C/Corner)
        positions: List of positions in this group
        timestamp: Timestamp for filename

    Returns:
        Filtered DataFrame
    """
    print(f"\n{group_name} ({', '.join(positions)}):")

    # Filter to this position group
    df_group = df[df['position'].isin(positions)].copy()

    print(f"  Total samples: {len(df_group):,}")

    if len(df_group) == 0:
        print(f"  [SKIP] No samples for {group_name}")
        return None

    # Class distribution
    class_dist = df_group['target'].value_counts().sort_index()
    print(f"  Class distribution:")
    class_names = ['Bench', 'Part-Time', 'Regular', 'All-Star']
    for cls in range(4):
        count = class_dist.get(cls, 0)
        pct = count / len(df_group) * 100 if len(df_group) > 0 else 0
        print(f"    {class_names[cls]:<12} {count:>3} ({pct:>5.1f}%)")

    return df_group


def process_split(input_file, split_name, timestamp):
    """
    Process a single split (train/val/test) and create position-specific files.

    Args:
        input_file: Path to cleaned CSV file
        split_name: Name of split (train/val/test)
        timestamp: Timestamp for output files

    Returns:
        Dictionary of {group_name: DataFrame}
    """
    print("\n" + "=" * 80)
    print(f"PROCESSING {split_name.upper()} SPLIT")
    print("=" * 80)

    # Load cleaned data
    df = pd.read_csv(input_file)
    print(f"\nLoaded: {input_file}")
    print(f"  Samples: {len(df):,}")
    print(f"  Features: {len([c for c in df.columns if c not in ['prospect_id', 'data_year', 'name', 'position', 'fangraphs_id', 'target', 'target_label', 'fangraphs_fv']])}")

    # Analyze position distribution
    analyze_position_distribution(df)

    # Create position-specific datasets
    print("\n" + "-" * 80)
    print("Creating Position-Specific Datasets:")
    print("-" * 80)

    position_datasets = {}
    output_files = {}

    for group_name, positions in POSITION_GROUPS.items():
        df_group = create_position_group_dataset(df, group_name, positions, timestamp)

        if df_group is not None and len(df_group) > 0:
            # Save to CSV
            output_file = f'ml_data_hitters_{group_name}_{split_name}_{timestamp}.csv'
            df_group.to_csv(output_file, index=False)
            print(f"  Saved: {output_file}")

            position_datasets[group_name] = df_group
            output_files[group_name] = output_file

    return position_datasets, output_files


def main():
    print("=" * 80)
    print("CREATE POSITION-SPECIFIC DATASETS")
    print("=" * 80)

    print("\nPosition Groups:")
    for group, positions in POSITION_GROUPS.items():
        print(f"  {group:<8} {', '.join(positions)}")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Process all three splits
    splits = [
        ('ml_data_hitters_cleaned_train_20251019_223355.csv', 'train'),
        ('ml_data_hitters_cleaned_val_20251019_223355.csv', 'val'),
        ('ml_data_hitters_cleaned_test_20251019_223355.csv', 'test')
    ]

    all_datasets = {}
    all_files = {}

    for input_file, split_name in splits:
        datasets, files = process_split(input_file, split_name, timestamp)
        all_datasets[split_name] = datasets
        all_files[split_name] = files

    # Summary
    print("\n" + "=" * 80)
    print("POSITION-SPECIFIC DATASETS CREATED")
    print("=" * 80)

    print("\nDataset Summary:")
    print(f"{'Group':<10} {'Train':<8} {'Val':<8} {'Test':<8} {'Total':<8}")
    print("-" * 50)

    for group_name in POSITION_GROUPS.keys():
        train_count = len(all_datasets['train'].get(group_name, [])) if group_name in all_datasets['train'] else 0
        val_count = len(all_datasets['val'].get(group_name, [])) if group_name in all_datasets['val'] else 0
        test_count = len(all_datasets['test'].get(group_name, [])) if group_name in all_datasets['test'] else 0
        total_count = train_count + val_count + test_count

        print(f"{group_name:<10} {train_count:>7} {val_count:>7} {test_count:>7} {total_count:>7}")

    print("\n" + "=" * 80)
    print("Files Created:")
    print("=" * 80)

    for split_name in ['train', 'val', 'test']:
        print(f"\n{split_name.upper()} Split:")
        for group_name, output_file in all_files.get(split_name, {}).items():
            print(f"  {output_file}")

    print("\n" + "=" * 80)
    print("COMPLETE")
    print("=" * 80)

    print("\nNext Steps:")
    print("  1. Train separate Random Forest model for each position group")
    print("  2. Position-specific feature importance analysis")
    print("  3. Position-specific SMOTE strategies")
    print("  4. Expected improvement: +0.05-0.10 F1 overall")

    print("\nKey Insights:")
    print("  - IF (SS/2B/3B): Highest variance, speed/defense important")
    print("  - OF (CF/RF/LF): Power-speed combo, athletic tools")
    print("  - C (Catchers): Defense-focused, small sample")
    print("  - Corner (1B/DH): Power-focused, lower variance")


if __name__ == "__main__":
    main()
