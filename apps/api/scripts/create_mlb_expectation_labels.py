"""
Create MLB Expectation Classification Labels
=============================================

This script creates the 4-class target labels from Fangraphs FV grades:
- All-Star (FV 60+)
- Regular (FV 50-55)
- Part-Time (FV 45)
- Bench (FV 35-40)

Database: Railway PostgreSQL
Author: BMad Party Mode Team
Date: 2025-10-19
"""

import asyncio
import asyncpg
import pandas as pd

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


def map_fv_to_expectation(fv):
    """
    Map Fangraphs Future Value (FV) to MLB Expectation class

    Args:
        fv: Future Value grade (35-70)

    Returns:
        str: One of 'All-Star', 'Regular', 'Part-Time', 'Bench'
    """
    if fv is None:
        return None

    if fv >= 60:
        return 'All-Star'
    elif fv >= 50:
        return 'Regular'
    elif fv >= 45:
        return 'Part-Time'
    else:  # FV 35-40
        return 'Bench'


def map_expectation_to_numeric(expectation):
    """
    Map expectation class to numeric label for ML models

    Returns:
        int: 0=Bench, 1=Part-Time, 2=Regular, 3=All-Star
    """
    mapping = {
        'Bench': 0,
        'Part-Time': 1,
        'Regular': 2,
        'All-Star': 3
    }
    return mapping.get(expectation)


async def generate_hitter_labels(conn):
    """
    Generate MLB expectation labels for all hitters
    """
    print("\n" + "="*80)
    print("GENERATING HITTER MLB EXPECTATION LABELS")
    print("="*80 + "\n")

    query = """
    SELECT
        p.id as prospect_id,
        p.name,
        p.position,
        fg.fangraphs_player_id,
        fg.fv,
        fg.top_100_rank,
        fg.hit_future,
        fg.game_power_future,
        fg.speed_future
    FROM prospects p
    JOIN fangraphs_hitter_grades fg ON p.fg_player_id = fg.fangraphs_player_id
    WHERE fg.fv IS NOT NULL
    ORDER BY fg.fv DESC NULLS LAST
    """

    rows = await conn.fetch(query)
    df = pd.DataFrame(rows, columns=[
        'prospect_id', 'name', 'position', 'fangraphs_player_id', 'fv',
        'top_100_rank', 'hit_future', 'game_power_future', 'speed_future'
    ])

    # Create expectation labels
    df['mlb_expectation'] = df['fv'].apply(map_fv_to_expectation)
    df['mlb_expectation_numeric'] = df['mlb_expectation'].apply(map_expectation_to_numeric)

    # Show distribution
    print("Hitter Class Distribution:")
    print(df['mlb_expectation'].value_counts().sort_index())
    print(f"\nTotal: {len(df)} hitters with FV grades\n")

    # Show examples from each class
    print("Example Hitters by Class:")
    print("-" * 80)
    for expectation in ['All-Star', 'Regular', 'Part-Time', 'Bench']:
        examples = df[df['mlb_expectation'] == expectation].head(3)
        if not examples.empty:
            print(f"\n{expectation}:")
            for _, row in examples.iterrows():
                print(f"  - {row['name']:30s} FV {row['fv']:2.0f}  "
                      f"Hit:{row['hit_future']:2.0f} Pwr:{row['game_power_future']:2.0f} Spd:{row['speed_future']:2.0f}")

    return df


async def generate_pitcher_labels(conn):
    """
    Generate MLB expectation labels for all pitchers
    """
    print("\n" + "="*80)
    print("GENERATING PITCHER MLB EXPECTATION LABELS")
    print("="*80 + "\n")

    query = """
    SELECT
        p.id as prospect_id,
        p.name,
        p.position,
        fg.fangraphs_player_id,
        fg.fv,
        fg.top_100_rank,
        fg.fb_future,
        fg.cmd_future,
        fg.velocity_sits_high,
        GREATEST(
            COALESCE(fg.sl_future, 0),
            COALESCE(fg.cb_future, 0),
            COALESCE(fg.ch_future, 0)
        ) as best_secondary
    FROM prospects p
    JOIN fangraphs_pitcher_grades fg ON p.fg_player_id = fg.fangraphs_player_id
    WHERE fg.fv IS NOT NULL
    ORDER BY fg.fv DESC NULLS LAST
    """

    rows = await conn.fetch(query)
    df = pd.DataFrame(rows, columns=[
        'prospect_id', 'name', 'position', 'fangraphs_player_id', 'fv',
        'top_100_rank', 'fb_future', 'cmd_future', 'velocity_sits_high', 'best_secondary'
    ])

    # Create expectation labels
    df['mlb_expectation'] = df['fv'].apply(map_fv_to_expectation)
    df['mlb_expectation_numeric'] = df['mlb_expectation'].apply(map_expectation_to_numeric)

    # Show distribution
    print("Pitcher Class Distribution:")
    print(df['mlb_expectation'].value_counts().sort_index())
    print(f"\nTotal: {len(df)} pitchers with FV grades\n")

    # Show examples from each class
    print("Example Pitchers by Class:")
    print("-" * 80)
    for expectation in ['All-Star', 'Regular', 'Part-Time', 'Bench']:
        examples = df[df['mlb_expectation'] == expectation].head(3)
        if not examples.empty:
            print(f"\n{expectation}:")
            for _, row in examples.iterrows():
                velo = row['velocity_sits_high'] if pd.notna(row['velocity_sits_high']) else 0
                print(f"  - {row['name']:30s} FV {row['fv']:2.0f}  "
                      f"FB:{row['fb_future']:2.0f} CMD:{row['cmd_future']:2.0f} "
                      f"Velo:{velo:.0f} 2nd:{row['best_secondary']:2.0f}")

    return df


async def create_labels_table(conn):
    """
    Create a database table to store ML expectation labels
    """
    print("\n" + "="*80)
    print("CREATING MLB EXPECTATION LABELS TABLE")
    print("="*80 + "\n")

    # Create table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS mlb_expectation_labels (
            id SERIAL PRIMARY KEY,
            prospect_id INTEGER REFERENCES prospects(id) ON DELETE CASCADE,

            -- Label info
            mlb_expectation VARCHAR(20) NOT NULL,  -- 'All-Star', 'Regular', 'Part-Time', 'Bench'
            mlb_expectation_numeric INTEGER NOT NULL,  -- 0-3 for ML models

            -- Source
            fv INTEGER NOT NULL,  -- Future Value grade from Fangraphs
            data_year INTEGER NOT NULL DEFAULT 2025,

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Constraints
            CONSTRAINT valid_expectation CHECK (
                mlb_expectation IN ('All-Star', 'Regular', 'Part-Time', 'Bench')
            ),
            CONSTRAINT valid_numeric CHECK (
                mlb_expectation_numeric BETWEEN 0 AND 3
            ),
            CONSTRAINT valid_fv CHECK (
                fv BETWEEN 35 AND 70
            ),

            -- One label per prospect per year
            UNIQUE(prospect_id, data_year)
        );
    """)

    # Create indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_expectation_labels_prospect
        ON mlb_expectation_labels(prospect_id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_expectation_labels_class
        ON mlb_expectation_labels(mlb_expectation);
    """)

    print("[OK] Created mlb_expectation_labels table")


async def insert_labels(conn, df, is_hitter=True):
    """
    Insert labels into database
    """
    player_type = "hitters" if is_hitter else "pitchers"
    print(f"\nInserting {len(df)} {player_type} labels into database...")

    inserted = 0
    for _, row in df.iterrows():
        try:
            await conn.execute("""
                INSERT INTO mlb_expectation_labels (
                    prospect_id,
                    mlb_expectation,
                    mlb_expectation_numeric,
                    fv,
                    data_year
                ) VALUES ($1, $2, $3, $4, 2025)
                ON CONFLICT (prospect_id, data_year) DO UPDATE SET
                    mlb_expectation = EXCLUDED.mlb_expectation,
                    mlb_expectation_numeric = EXCLUDED.mlb_expectation_numeric,
                    fv = EXCLUDED.fv,
                    updated_at = CURRENT_TIMESTAMP
            """,
                int(row['prospect_id']),
                row['mlb_expectation'],
                int(row['mlb_expectation_numeric']),
                int(row['fv'])
            )
            inserted += 1
        except Exception as e:
            print(f"[SKIP] {row['name']}: {str(e)}")

    print(f"[OK] Inserted {inserted} labels")


async def show_summary(conn):
    """
    Show final summary statistics
    """
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80 + "\n")

    # Overall distribution
    result = await conn.fetch("""
        SELECT
            mlb_expectation,
            COUNT(*) as count,
            ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 1) as pct
        FROM mlb_expectation_labels
        WHERE data_year = 2025
        GROUP BY mlb_expectation
        ORDER BY
            CASE mlb_expectation
                WHEN 'All-Star' THEN 1
                WHEN 'Regular' THEN 2
                WHEN 'Part-Time' THEN 3
                WHEN 'Bench' THEN 4
            END
    """)

    print("Overall Distribution (2025):")
    print("-" * 60)
    total = 0
    for row in result:
        print(f"  {row['mlb_expectation']:15s} {row['count']:4d} ({row['pct']:5.1f}%)")
        total += row['count']
    print(f"  {'TOTAL':15s} {total:4d}")

    # By position
    print("\n\nDistribution by Player Type:")
    print("-" * 60)

    hitters = await conn.fetch("""
        SELECT
            mlb_expectation,
            COUNT(*) as count
        FROM mlb_expectation_labels l
        JOIN prospects p ON l.prospect_id = p.id
        WHERE l.data_year = 2025
        AND p.position NOT IN ('SP', 'RP')
        GROUP BY mlb_expectation
        ORDER BY
            CASE mlb_expectation
                WHEN 'All-Star' THEN 1
                WHEN 'Regular' THEN 2
                WHEN 'Part-Time' THEN 3
                WHEN 'Bench' THEN 4
            END
    """)

    pitchers = await conn.fetch("""
        SELECT
            mlb_expectation,
            COUNT(*) as count
        FROM mlb_expectation_labels l
        JOIN prospects p ON l.prospect_id = p.id
        WHERE l.data_year = 2025
        AND p.position IN ('SP', 'RP')
        GROUP BY mlb_expectation
        ORDER BY
            CASE mlb_expectation
                WHEN 'All-Star' THEN 1
                WHEN 'Regular' THEN 2
                WHEN 'Part-Time' THEN 3
                WHEN 'Bench' THEN 4
            END
    """)

    print(f"\n{'Class':<15s} {'Hitters':<10s} {'Pitchers':<10s}")
    print("-" * 40)

    hitter_dict = {row['mlb_expectation']: row['count'] for row in hitters}
    pitcher_dict = {row['mlb_expectation']: row['count'] for row in pitchers}

    for exp in ['All-Star', 'Regular', 'Part-Time', 'Bench']:
        h_count = hitter_dict.get(exp, 0)
        p_count = pitcher_dict.get(exp, 0)
        print(f"{exp:<15s} {h_count:<10d} {p_count:<10d}")

    print("\n" + "="*80)
    print("LABELS READY FOR MACHINE LEARNING!")
    print("="*80)
    print("\nNext Steps:")
    print("1. Export labels with features for ML training")
    print("2. Handle class imbalance (SMOTE, class weights)")
    print("3. Train multi-class classifier")
    print("4. Evaluate with weighted F1-score")
    print("5. Compare predictions to Fangraphs FV consensus")


async def main():
    """
    Main execution
    """
    print("="*80)
    print("MLB EXPECTATION CLASSIFICATION - LABEL GENERATION")
    print("="*80)

    conn = await asyncpg.connect(DATABASE_URL)
    print("\n[OK] Connected to database")

    # Create table
    await create_labels_table(conn)

    # Generate hitter labels
    hitters_df = await generate_hitter_labels(conn)

    # Generate pitcher labels
    pitchers_df = await generate_pitcher_labels(conn)

    # Insert into database
    await insert_labels(conn, hitters_df, is_hitter=True)
    await insert_labels(conn, pitchers_df, is_hitter=False)

    # Show summary
    await show_summary(conn)

    # Export to CSV for ML training
    all_df = pd.concat([hitters_df, pitchers_df], ignore_index=True)
    all_df.to_csv('mlb_expectation_labels_2025.csv', index=False)
    print(f"\n[OK] Exported labels to mlb_expectation_labels_2025.csv")

    await conn.close()
    print("\n[OK] Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
