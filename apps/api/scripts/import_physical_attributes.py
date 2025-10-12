#!/usr/bin/env python3
"""
Import physical attributes data from FanGraphs phys files.
This updates the existing fangraphs_unified_grades table with height/weight and other physical data.
"""

import pandas as pd
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def import_phys_file(filepath: str, year: int):
    """Import a physical attributes CSV file."""

    logger.info(f"Importing phys file: {filepath}")
    df = pd.read_csv(filepath)

    logger.info(f"Columns in file: {df.columns.tolist()}")
    logger.info(f"Sample data:\n{df.head()}")

    # Standardize column names
    df = df.rename(columns={
        'Name': 'player_name',
        'PlayerId': 'fg_player_id',
        'Pos': 'position',
        'Age': 'age',
        'Frame': 'frame',
        'Athl': 'athleticism',
        'Levers': 'levers',
        'Arm': 'arm_strength',
        'Perf': 'performance',
        'Delivery': 'delivery'
    })

    # Convert numeric columns
    numeric_cols = ['age', 'frame', 'athleticism', 'arm_strength', 'performance', 'delivery']

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Update records in database
    async with engine.begin() as conn:
        updated = 0
        not_found = 0

        for _, row in df.iterrows():
            try:
                fg_player_id = row.get('fg_player_id')
                if pd.isna(fg_player_id):
                    continue

                # Update both hitter and pitcher records for this player/year
                result = await conn.execute(text("""
                    UPDATE fangraphs_unified_grades
                    SET
                        frame = :frame,
                        athleticism = :athleticism,
                        levers = :levers,
                        arm_strength = :arm_strength,
                        performance = :performance,
                        delivery = :delivery
                    WHERE fg_player_id = :fg_player_id
                      AND year = :year
                """), {
                    'fg_player_id': str(fg_player_id),
                    'year': year,
                    'frame': int(row.get('frame')) if pd.notna(row.get('frame')) else None,
                    'athleticism': int(row.get('athleticism')) if pd.notna(row.get('athleticism')) else None,
                    'levers': row.get('levers') if pd.notna(row.get('levers')) else None,
                    'arm_strength': int(row.get('arm_strength')) if pd.notna(row.get('arm_strength')) else None,
                    'performance': int(row.get('performance')) if pd.notna(row.get('performance')) else None,
                    'delivery': int(row.get('delivery')) if pd.notna(row.get('delivery')) else None
                })

                rows_updated = result.rowcount
                if rows_updated > 0:
                    updated += rows_updated
                else:
                    not_found += 1

            except Exception as e:
                logger.error(f"Error updating phys for {row.get('player_name')}: {str(e)}")
                continue

    logger.info(f"Updated {updated} records from {year} phys file ({not_found} players not found)")
    return updated


async def add_phys_columns():
    """Add physical attribute columns to the table if they don't exist."""

    async with engine.begin() as conn:
        # Check if columns already exist
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'fangraphs_unified_grades'
              AND column_name IN ('frame', 'athleticism', 'levers', 'arm_strength', 'performance', 'delivery')
        """))
        existing_cols = [row[0] for row in result.fetchall()]

        columns_to_add = [
            ('frame', 'INTEGER'),
            ('athleticism', 'INTEGER'),
            ('levers', 'VARCHAR(20)'),
            ('arm_strength', 'INTEGER'),
            ('performance', 'INTEGER'),
            ('delivery', 'INTEGER')
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_cols:
                logger.info(f"Adding column: {col_name}")
                await conn.execute(text(f"""
                    ALTER TABLE fangraphs_unified_grades
                    ADD COLUMN {col_name} {col_type}
                """))
            else:
                logger.info(f"Column already exists: {col_name}")


async def verify_import():
    """Verify the import results."""

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                year,
                COUNT(*) as total_records,
                COUNT(CASE WHEN frame IS NOT NULL THEN 1 END) as has_frame,
                COUNT(CASE WHEN athleticism IS NOT NULL THEN 1 END) as has_athleticism,
                COUNT(CASE WHEN levers IS NOT NULL THEN 1 END) as has_levers,
                COUNT(CASE WHEN arm_strength IS NOT NULL THEN 1 END) as has_arm
            FROM fangraphs_unified_grades
            GROUP BY year
            ORDER BY year
        """))

        print("\n" + "="*80)
        print("PHYSICAL ATTRIBUTES COVERAGE BY YEAR")
        print("="*80)
        print("Year | Total | Frame | Athleticism | Levers | Arm Strength")
        print("-----|-------|-------|-------------|--------|-------------")

        for row in result.fetchall():
            print(f"{row[0]} | {row[1]:>5,} | {row[2]:>5,} | {row[3]:>11,} | {row[4]:>6,} | {row[5]:>12,}")

        # Sample data
        result = await conn.execute(text("""
            SELECT player_name, position, year, frame, athleticism, levers, arm_strength
            FROM fangraphs_unified_grades
            WHERE frame IS NOT NULL
              AND year = 2025
            LIMIT 10
        """))

        print("\n=== Sample 2025 Players with Physical Attributes ===")
        for row in result.fetchall():
            print(f"{row[0]:25s} {row[1]:3s} {row[2]} - Frame:{row[3]} Ath:{row[4]} Levers:{row[5]} Arm:{row[6]}")


async def main():
    """Import all physical attributes files."""

    downloads_dir = r"C:\Users\lilra\Downloads"

    print("Adding physical attribute columns to table...")
    await add_phys_columns()

    total_updated = 0

    # Process each year
    for year in [2022, 2023, 2024, 2025]:
        phys_file = os.path.join(downloads_dir, f"fangraphs-the-board-all-{year}-phys.csv")
        if os.path.exists(phys_file):
            updated = await import_phys_file(phys_file, year)
            total_updated += updated
        else:
            logger.warning(f"Phys file not found: {phys_file}")

    # Verify results
    await verify_import()

    print(f"\nTotal records updated: {total_updated:,}")
    logger.info("Physical attributes import complete!")


if __name__ == "__main__":
    asyncio.run(main())
