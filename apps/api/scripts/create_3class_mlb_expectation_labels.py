"""
Create 3-Class MLB Expectation Labels
======================================

This script creates a SIMPLIFIED 3-class labeling system that solves
the fundamental problem: 0 All-Star training examples.

New Class System:
- Class 0: Bench/Reserve (FV 35-40)
- Class 1: Part-Time Player (FV 45)
- Class 2: MLB Regular+ (FV 50+, combines Regular 50-55 + All-Star 60+)

Expected improvement:
- 4-class system: 0.697 F1 (0 All-Stars → 0% recall)
- 3-class system: 0.72-0.75 F1 (30 MLB Regular+ examples)

Database: Railway PostgreSQL
"""

import asyncio
import asyncpg
from datetime import datetime

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def create_3class_labels_table(conn):
    """
    Create new table for 3-class labels.
    """
    print("\n" + "="*80)
    print("CREATING 3-CLASS LABELS TABLE")
    print("="*80)

    # Drop existing table if it exists
    await conn.execute("""
        DROP TABLE IF EXISTS mlb_expectation_labels_3class;
    """)

    # Create new table
    await conn.execute("""
        CREATE TABLE mlb_expectation_labels_3class (
            id SERIAL PRIMARY KEY,
            prospect_id INTEGER NOT NULL,
            data_year INTEGER NOT NULL,
            target INTEGER NOT NULL,
            target_label VARCHAR(50) NOT NULL,
            fangraphs_fv INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(prospect_id, data_year)
        );
    """)

    print("[OK] Created mlb_expectation_labels_3class table")


def map_fv_to_3class(fv: int) -> tuple[int, str]:
    """
    Map Fangraphs FV to 3-class system.

    Args:
        fv: Fangraphs Future Value (35-80)

    Returns:
        (target_class, label_name)

    Mapping:
        FV 35-40 → Class 0 (Bench/Reserve)
        FV 45    → Class 1 (Part-Time)
        FV 50+   → Class 2 (MLB Regular+)
    """
    if fv >= 50:
        return 2, "MLB Regular+"
    elif fv == 45:
        return 1, "Part-Time"
    else:  # fv <= 40
        return 0, "Bench/Reserve"


async def generate_labels_for_year(conn, year: int) -> dict:
    """
    Generate 3-class labels for a specific year.

    Returns:
        Dictionary with counts by class
    """
    print(f"\n{'='*80}")
    print(f"GENERATING {year} LABELS (3-CLASS)")
    print(f"{'='*80}")

    # Get all prospects with Fangraphs grades for this year
    hitters = await conn.fetch("""
        SELECT
            p.id as prospect_id,
            fg.fangraphs_player_id,
            fg.fv
        FROM prospects p
        JOIN fangraphs_hitter_grades fg ON p.fg_player_id = fg.fangraphs_player_id
        WHERE fg.data_year = $1
        AND fg.fv IS NOT NULL
    """, year)

    pitchers = await conn.fetch("""
        SELECT
            p.id as prospect_id,
            fg.fangraphs_player_id,
            fg.fv
        FROM prospects p
        JOIN fangraphs_pitcher_grades fg ON p.fg_player_id = fg.fangraphs_player_id
        WHERE fg.data_year = $1
        AND fg.fv IS NOT NULL
    """, year)

    all_prospects = list(hitters) + list(pitchers)
    print(f"\nFound {len(hitters)} hitters and {len(pitchers)} pitchers = {len(all_prospects)} total")

    if len(all_prospects) == 0:
        print(f"[SKIP] No prospects found for {year}")
        return {}

    # Generate labels
    class_counts = {0: 0, 1: 0, 2: 0}
    inserted = 0

    for prospect in all_prospects:
        fv = prospect['fv']
        prospect_id = prospect['prospect_id']

        # Map to 3-class system
        target, label = map_fv_to_3class(fv)

        # Insert into database
        await conn.execute("""
            INSERT INTO mlb_expectation_labels_3class
            (prospect_id, data_year, target, target_label, fangraphs_fv)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (prospect_id, data_year) DO UPDATE SET
                target = EXCLUDED.target,
                target_label = EXCLUDED.target_label,
                fangraphs_fv = EXCLUDED.fangraphs_fv
        """, prospect_id, year, target, label, fv)

        class_counts[target] += 1
        inserted += 1

    print(f"[OK] Inserted {inserted} labels for {year}")

    print(f"\n{year} Class Distribution:")
    print(f"  MLB Regular+    {class_counts[2]:>4} (FV 50+)")
    print(f"  Part-Time       {class_counts[1]:>4} (FV 45)")
    print(f"  Bench/Reserve   {class_counts[0]:>4} (FV 35-40)")

    return class_counts


async def verify_data(conn):
    """
    Verify label counts and distribution.
    """
    print("\n" + "="*80)
    print("3-CLASS LABEL VERIFICATION")
    print("="*80)

    # Labels by year
    print("\nLabels by Year:")
    year_counts = await conn.fetch("""
        SELECT data_year, COUNT(*) as count
        FROM mlb_expectation_labels_3class
        GROUP BY data_year
        ORDER BY data_year
    """)

    for row in year_counts:
        print(f"  {row['data_year']}: {row['count']} labeled prospects")

    # Class distribution by year
    print("\nClass Distribution by Year:")
    print(f"{'Year':<8} {'MLB Reg+':<12} {'Part-Time':<12} {'Bench':<12}")
    print("-" * 50)

    for year_row in year_counts:
        year = year_row['data_year']

        class_dist = await conn.fetch("""
            SELECT target, COUNT(*) as count
            FROM mlb_expectation_labels_3class
            WHERE data_year = $1
            GROUP BY target
            ORDER BY target DESC
        """, year)

        counts = {0: 0, 1: 0, 2: 0}
        for row in class_dist:
            counts[row['target']] = row['count']

        print(f"{year:<8} {counts[2]:>11} {counts[1]:>11} {counts[0]:>11}")

    # Overall totals
    total_counts = await conn.fetch("""
        SELECT target, target_label, COUNT(*) as count
        FROM mlb_expectation_labels_3class
        GROUP BY target, target_label
        ORDER BY target DESC
    """)

    print("\nOverall Class Distribution:")
    total = sum(row['count'] for row in total_counts)
    for row in total_counts:
        pct = row['count'] / total * 100
        print(f"  Class {row['target']} ({row['target_label']:<15}): {row['count']:>4} ({pct:>5.1f}%)")

    # Multi-year prospects
    multi_year = await conn.fetchval("""
        SELECT COUNT(DISTINCT prospect_id)
        FROM mlb_expectation_labels_3class
    """)
    print(f"\nTotal unique prospects with labels: {multi_year}")


async def main():
    print("="*80)
    print("3-CLASS MLB EXPECTATION LABEL GENERATION")
    print("="*80)

    print("\nClass System:")
    print("  Class 0: Bench/Reserve (FV 35-40)")
    print("  Class 1: Part-Time Player (FV 45)")
    print("  Class 2: MLB Regular+ (FV 50+, includes All-Stars)")

    print("\nExpected Training Distribution (2022-2023):")
    print("  Bench/Reserve:  ~218 samples")
    print("  Part-Time:      ~90 samples")
    print("  MLB Regular+:   ~30 samples (vs 0 All-Stars in 4-class!)")

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    print("\n[OK] Connected to database")

    try:
        # Create table
        await create_3class_labels_table(conn)

        # Generate labels for each year
        years = [2022, 2023, 2024, 2025]
        all_counts = {}

        for year in years:
            counts = await generate_labels_for_year(conn, year)
            all_counts[year] = counts

        # Verify all data
        await verify_data(conn)

        print("\n" + "="*80)
        print("3-CLASS LABEL GENERATION COMPLETE")
        print("="*80)

        # Training data analysis
        train_years = [2022, 2023]
        train_totals = {0: 0, 1: 0, 2: 0}

        for year in train_years:
            if year in all_counts:
                for cls, count in all_counts[year].items():
                    train_totals[cls] += count

        print(f"\nTraining Data ({', '.join(map(str, train_years))}):")
        print(f"  MLB Regular+:   {train_totals[2]:>3} samples")
        print(f"  Part-Time:      {train_totals[1]:>3} samples")
        print(f"  Bench/Reserve:  {train_totals[0]:>3} samples")
        print(f"  Total:          {sum(train_totals.values()):>3} samples")

        print("\n✅ Key Improvement:")
        print("   4-class had 0 All-Star training examples")
        print(f"   3-class has {train_totals[2]} MLB Regular+ training examples")
        print("   This should enable prediction of top-tier prospects!")

        print("\nNext Steps:")
        print("  1. Run create_ml_training_data_3class.py to generate ML datasets")
        print("  2. Train 3-class Random Forest baseline")
        print("  3. Expected improvement: 0.72-0.75 F1 (vs 0.697 baseline)")
        print("  4. Then try XGBoost for additional 0.74-0.78 F1")

    finally:
        await conn.close()
        print("\n[OK] Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
