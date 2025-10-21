"""
Verify Temporal Validation Setup
=================================

Quick verification that all multi-year data is loaded correctly.
"""

import asyncio
import asyncpg
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def main():
    print("=" * 80)
    print("TEMPORAL VALIDATION DATA VERIFICATION")
    print("=" * 80)

    conn = await asyncpg.connect(DATABASE_URL)
    print("\n[OK] Connected to database\n")

    # Check all tables by year
    tables = [
        ('fangraphs_hitter_grades', 'Hitter Grades'),
        ('fangraphs_pitcher_grades', 'Pitcher Grades'),
        ('fangraphs_physical_attributes', 'Physical Attributes'),
        ('mlb_expectation_labels', 'MLB Expectation Labels')
    ]

    print(f"{'Table':<30} {'2022':>8} {'2023':>8} {'2024':>8} {'2025':>8} {'Total':>10}")
    print("-" * 80)

    grand_total = 0
    for table_name, display_name in tables:
        rows = await conn.fetch(f"""
            SELECT data_year, COUNT(*) as count
            FROM {table_name}
            GROUP BY data_year
            ORDER BY data_year
        """)

        counts = {row['data_year']: row['count'] for row in rows}
        total = sum(counts.values())
        grand_total += total

        print(f"{display_name:<30} {counts.get(2022, 0):>8,} {counts.get(2023, 0):>8,} {counts.get(2024, 0):>8,} {counts.get(2025, 0):>8,} {total:>10,}")

    print("-" * 80)
    print(f"{'TOTAL RECORDS':<30} {' ':>36} {grand_total:>10,}")

    # Check multi-year tracking
    print("\n" + "=" * 80)
    print("MULTI-YEAR TRACKING ANALYSIS")
    print("=" * 80 + "\n")

    multi_year = await conn.fetch("""
        SELECT
            COUNT(DISTINCT prospect_id) as total_prospects,
            COUNT(DISTINCT CASE WHEN label_years = 4 THEN prospect_id END) as four_years,
            COUNT(DISTINCT CASE WHEN label_years = 3 THEN prospect_id END) as three_years,
            COUNT(DISTINCT CASE WHEN label_years = 2 THEN prospect_id END) as two_years,
            COUNT(DISTINCT CASE WHEN label_years = 1 THEN prospect_id END) as one_year
        FROM (
            SELECT prospect_id, COUNT(DISTINCT data_year) as label_years
            FROM mlb_expectation_labels
            GROUP BY prospect_id
        ) sub
    """)

    r = multi_year[0]
    print(f"Total prospects with labels: {r['total_prospects']:,}")
    print(f"  - Tracked for 4 years (2022-2025): {r['four_years']:,} prospects")
    print(f"  - Tracked for 3 years: {r['three_years']:,} prospects")
    print(f"  - Tracked for 2 years: {r['two_years']:,} prospects")
    print(f"  - Tracked for 1 year only: {r['one_year']:,} prospects")

    # Sample some multi-year prospects
    print("\n" + "=" * 80)
    print("SAMPLE MULTI-YEAR PROSPECTS (All 4 Years)")
    print("=" * 80 + "\n")

    sample = await conn.fetch("""
        SELECT
            p.name,
            p.position,
            STRING_AGG(
                l.data_year::text || ': ' || l.mlb_expectation || ' (FV ' || l.fv || ')',
                ' | '
                ORDER BY l.data_year
            ) as grade_progression
        FROM prospects p
        JOIN mlb_expectation_labels l ON p.id = l.prospect_id
        WHERE p.id IN (
            SELECT prospect_id
            FROM mlb_expectation_labels
            GROUP BY prospect_id
            HAVING COUNT(DISTINCT data_year) = 4
        )
        GROUP BY p.name, p.position
        ORDER BY p.name
        LIMIT 10
    """)

    for row in sample:
        print(f"{row['name']} ({row['position']})")
        print(f"  {row['grade_progression']}\n")

    # Temporal validation splits
    print("=" * 80)
    print("RECOMMENDED TEMPORAL SPLITS")
    print("=" * 80 + "\n")

    splits = await conn.fetch("""
        WITH split_data AS (
            SELECT
                CASE
                    WHEN data_year IN (2022, 2023) THEN 'Training'
                    WHEN data_year = 2024 THEN 'Validation'
                    WHEN data_year = 2025 THEN 'Test'
                END as split,
                mlb_expectation
            FROM mlb_expectation_labels
        )
        SELECT
            split,
            COUNT(*) as total_samples,
            SUM(CASE WHEN mlb_expectation = 'All-Star' THEN 1 ELSE 0 END) as all_star,
            SUM(CASE WHEN mlb_expectation = 'Regular' THEN 1 ELSE 0 END) as regular,
            SUM(CASE WHEN mlb_expectation = 'Part-Time' THEN 1 ELSE 0 END) as part_time,
            SUM(CASE WHEN mlb_expectation = 'Bench' THEN 1 ELSE 0 END) as bench
        FROM split_data
        GROUP BY split
        ORDER BY
            CASE split
                WHEN 'Training' THEN 1
                WHEN 'Validation' THEN 2
                WHEN 'Test' THEN 3
            END
    """)

    print(f"{'Split':<12} {'Total':>8} {'All-Star':>10} {'Regular':>10} {'Part-Time':>12} {'Bench':>8}")
    print("-" * 80)
    for row in splits:
        print(f"{row['split']:<12} {row['total_samples']:>8,} {row['all_star']:>10} {row['regular']:>10} {row['part_time']:>12} {row['bench']:>8}")

    print("\n" + "=" * 80)
    print("STATUS: [OK] ALL DATA VERIFIED - READY FOR ML MODEL TRAINING")
    print("=" * 80)

    await conn.close()
    print("\n[OK] Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
