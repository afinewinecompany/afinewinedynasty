"""
Populate MLB Player IDs using FanGraphs ID Mapping

This script uses the Chadwick Bureau registry to map FanGraphs IDs to MLB IDs.
This is much more reliable than name-based searching for minor league prospects.

Usage:
    python scripts/populate_mlb_ids_from_fangraphs.py [--limit N] [--dry-run]
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.database import engine

print("Loading Chadwick Bureau registry (this may take a moment)...")
import pybaseball as pyb
pyb.cache.enable()  # Enable caching for faster subsequent runs


async def populate_from_fangraphs(limit=None, dry_run=False):
    """Populate MLB player IDs using FanGraphs ID mapping."""

    # Load the Chadwick Bureau registry
    print("Downloading Chadwick Bureau player registry...")
    try:
        mapping = pyb.chadwick_register()
        print(f"Loaded {len(mapping)} player ID mappings\n")
    except Exception as e:
        print(f"Error loading Chadwick Bureau: {e}")
        return

    print("=" * 80)
    print("POPULATING MLB PLAYER IDs FROM FANGRAPHS MAPPING")
    print("=" * 80)

    if dry_run:
        print("[DRY RUN MODE - No database updates will be made]")

    print()

    async with engine.begin() as conn:
        # Get prospects with FanGraphs IDs but no MLB player ID
        query = """
            SELECT id, name, organization, fg_player_id, mlb_player_id
            FROM prospects
            WHERE fg_player_id IS NOT NULL
            AND mlb_player_id IS NULL
            ORDER BY id
        """

        if limit:
            query += f" LIMIT {limit}"

        result = await conn.execute(text(query))
        prospects = result.fetchall()

        print(f"Found {len(prospects)} prospects with FanGraphs IDs but no MLB IDs")

        if limit:
            print(f"(Limited to {limit} for testing)")

        print()

        matched = 0
        not_found = 0
        errors = 0

        for i, (prospect_id, name, org, fg_id, current_mlb_id) in enumerate(prospects, 1):
            try:
                # Convert FanGraphs ID to integer
                fg_id_int = int(fg_id)

                # Look up in Chadwick Bureau
                match = mapping[mapping['key_fangraphs'] == fg_id_int]

                if not match.empty and 'key_mlbam' in match.columns:
                    mlb_id = match.iloc[0]['key_mlbam']

                    # Check if it's a valid MLB ID
                    if mlb_id and mlb_id > 0:
                        mlb_id_str = str(int(mlb_id))

                        if not dry_run:
                            # Update database
                            await conn.execute(
                                text("""
                                    UPDATE prospects
                                    SET mlb_player_id = :mlb_id
                                    WHERE id = :id
                                """),
                                {'mlb_id': mlb_id_str, 'id': prospect_id}
                            )

                        matched += 1

                        # Print progress
                        if matched <= 20 or matched % 50 == 0:
                            status = "[DRY RUN] " if dry_run else ""
                            print(f"  {status}[{matched}] {name} ({org}) -> FG:{fg_id} = MLB ID:{mlb_id_str}")

                    else:
                        not_found += 1
                        if not_found <= 10:
                            print(f"  [NOT FOUND] {name} - FG ID {fg_id} has no MLB ID in registry")

                else:
                    not_found += 1
                    if not_found <= 10:
                        print(f"  [NOT FOUND] {name} - FG ID {fg_id} not in Chadwick Bureau")

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  [ERROR] {name}: {e}")

            # Progress indicator
            if i % 100 == 0:
                print(f"\n  [Progress: {i}/{len(prospects)}] Matched: {matched}, Not Found: {not_found}\n")

        print()
        print("=" * 80)
        print("RESULTS")
        print("=" * 80)

        # Get final counts
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(mlb_player_id) as with_mlb_id,
                COUNT(fg_player_id) as with_fg_id
            FROM prospects
        """))

        row = result.fetchone()
        total = row[0]
        with_mlb = row[1]
        with_fg = row[2]

        print(f"Total prospects in database: {total}")
        print(f"With FanGraphs ID: {with_fg} ({with_fg/total*100:.1f}%)")
        print(f"With MLB player ID: {with_mlb} ({with_mlb/total*100:.1f}%)")
        print(f"Still unmatched: {total - with_mlb}")
        print()
        print(f"This run:")
        print(f"  - Matched: {matched}")
        print(f"  - Not found: {not_found}")
        print(f"  - Errors: {errors}")

        if dry_run:
            print("\n[DRY RUN] No changes were made to the database")

        print()
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Populate MLB player IDs from FanGraphs IDs")
    parser.add_argument('--limit', type=int, help='Only process N prospects')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t update database')

    args = parser.parse_args()

    asyncio.run(populate_from_fangraphs(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
