"""
Create Multi-Year MLB Expectation Labels (2022-2025)
====================================================

Generate MLB expectation labels for all years of Fangraphs data.
This enables proper temporal validation for ML models.

Database: Railway PostgreSQL
Author: BMad Party Mode Team
Date: 2025-10-19
"""

import asyncio
import asyncpg
import pandas as pd

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


def map_fv_to_expectation(fv):
    """Map FV to MLB Expectation class"""
    if fv is None:
        return None
    if fv >= 60:
        return 'All-Star'
    elif fv >= 50:
        return 'Regular'
    elif fv >= 45:
        return 'Part-Time'
    else:
        return 'Bench'


def map_expectation_to_numeric(expectation):
    """Map expectation to numeric (0=Bench, 1=Part-Time, 2=Regular, 3=All-Star)"""
    mapping = {
        'Bench': 0,
        'Part-Time': 1,
        'Regular': 2,
        'All-Star': 3
    }
    return mapping.get(expectation)


async def generate_labels_for_year(conn, year: int):
    """Generate labels for a specific year"""
    print(f"\n{'='*80}")
    print(f"GENERATING {year} LABELS")
    print(f"{'='*80}\n")

    # Get hitters for this year
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

    # Get pitchers for this year
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

    total = len(hitters) + len(pitchers)
    print(f"Found {len(hitters)} hitters and {len(pitchers)} pitchers = {total} total")

    # Insert labels
    inserted = 0
    for player in list(hitters) + list(pitchers):
        expectation = map_fv_to_expectation(player['fv'])
        expectation_num = map_expectation_to_numeric(expectation)

        try:
            await conn.execute("""
                INSERT INTO mlb_expectation_labels (
                    prospect_id,
                    mlb_expectation,
                    mlb_expectation_numeric,
                    fv,
                    data_year
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (prospect_id, data_year) DO UPDATE SET
                    mlb_expectation = EXCLUDED.mlb_expectation,
                    mlb_expectation_numeric = EXCLUDED.mlb_expectation_numeric,
                    fv = EXCLUDED.fv,
                    updated_at = CURRENT_TIMESTAMP
            """,
                int(player['prospect_id']),
                expectation,
                int(expectation_num),
                int(player['fv']),
                year
            )
            inserted += 1
        except Exception as e:
            print(f"[SKIP] Prospect {player['prospect_id']}: {str(e)}")

    print(f"[OK] Inserted {inserted:,} labels for {year}")

    # Show distribution
    dist = await conn.fetch("""
        SELECT
            mlb_expectation,
            COUNT(*) as count
        FROM mlb_expectation_labels
        WHERE data_year = $1
        GROUP BY mlb_expectation
        ORDER BY
            CASE mlb_expectation
                WHEN 'All-Star' THEN 1
                WHEN 'Regular' THEN 2
                WHEN 'Part-Time' THEN 3
                WHEN 'Bench' THEN 4
            END
    """, year)

    print(f"\n{year} Class Distribution:")
    for row in dist:
        print(f"  {row['mlb_expectation']:12s} {row['count']:4d}")

    return inserted


async def generate_summary(conn):
    """Generate final summary"""
    print("\n" + "="*80)
    print("MULTI-YEAR LABEL GENERATION COMPLETE")
    print("="*80 + "\n")

    # Labels by year
    print("Labels by Year:")
    year_result = await conn.fetch("""
        SELECT data_year, COUNT(*) as count
        FROM mlb_expectation_labels
        GROUP BY data_year
        ORDER BY data_year
    """)
    for row in year_result:
        print(f"  {row['data_year']}: {row['count']:,} labeled prospects")

    # Prospects with labels across multiple years
    print("\nProspects with Multi-Year Labels:")
    multi_year = await conn.fetch("""
        SELECT
            COUNT(DISTINCT prospect_id) as total_prospects,
            COUNT(DISTINCT CASE WHEN label_years >= 4 THEN prospect_id END) as four_years,
            COUNT(DISTINCT CASE WHEN label_years >= 3 THEN prospect_id END) as three_years,
            COUNT(DISTINCT CASE WHEN label_years >= 2 THEN prospect_id END) as two_years
        FROM (
            SELECT prospect_id, COUNT(DISTINCT data_year) as label_years
            FROM mlb_expectation_labels
            GROUP BY prospect_id
        ) sub
    """)

    r = multi_year[0]
    print(f"  Total prospects with labels: {r['total_prospects']:,}")
    print(f"  Prospects with 4 years: {r['four_years']:,}")
    print(f"  Prospects with 3 years: {r['three_years']:,}")
    print(f"  Prospects with 2 years: {r['two_years']:,}")

    # Class distribution over time
    print("\nClass Distribution by Year:")
    dist_result = await conn.fetch("""
        SELECT
            data_year,
            SUM(CASE WHEN mlb_expectation = 'All-Star' THEN 1 ELSE 0 END) as all_star,
            SUM(CASE WHEN mlb_expectation = 'Regular' THEN 1 ELSE 0 END) as regular,
            SUM(CASE WHEN mlb_expectation = 'Part-Time' THEN 1 ELSE 0 END) as part_time,
            SUM(CASE WHEN mlb_expectation = 'Bench' THEN 1 ELSE 0 END) as bench
        FROM mlb_expectation_labels
        GROUP BY data_year
        ORDER BY data_year
    """)

    print(f"\n{'Year':6s} {'All-Star':>10s} {'Regular':>10s} {'Part-Time':>10s} {'Bench':>10s}")
    print("-" * 50)
    for row in dist_result:
        print(f"{row['data_year']}  {row['all_star']:10d} {row['regular']:10d} {row['part_time']:10d} {row['bench']:10d}")

    print("\n" + "="*80)
    print("TEMPORAL VALIDATION NOW POSSIBLE!")
    print("="*80)
    print("\nRecommended splits:")
    print("  Train: 2022-2023 data")
    print("  Validation: 2024 data")
    print("  Test: 2025 data (true holdout)")
    print("\nExample query to get training data:")
    print("""
    SELECT *
    FROM mlb_expectation_labels l
    JOIN prospects p ON l.prospect_id = p.id
    WHERE l.data_year IN (2022, 2023)
    """)


async def main():
    """Main execution"""
    print("="*80)
    print("MULTI-YEAR MLB EXPECTATION LABEL GENERATION")
    print("="*80)

    conn = await asyncpg.connect(DATABASE_URL)
    print("\n[OK] Connected to database")

    # Generate labels for each year
    total_inserted = 0
    for year in [2022, 2023, 2024, 2025]:
        inserted = await generate_labels_for_year(conn, year)
        total_inserted += inserted

    # Generate summary
    await generate_summary(conn)

    print(f"\n[OK] Total labels created: {total_inserted:,}")

    await conn.close()
    print("\n[OK] Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
