#!/usr/bin/env python3
"""
Map Fangraphs Player IDs to MLB Stats API Player IDs
====================================================
Uses pybaseball's Chadwick Bureau ID mapping to populate mlb_player_id
for all prospects in our database.

This enables collection of MiLB game logs from MLB Stats API.

Usage:
    python map_player_ids.py
"""

import sys
import os
import logging
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db_sync
from sqlalchemy import text
import pybaseball as pyb

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_player_id_mapping():
    """
    Get Chadwick Bureau player ID mapping table.

    This table maps IDs across multiple platforms:
    - key_mlbam: MLB Advanced Media (MLB Stats API)
    - key_fangraphs: Fangraphs
    - key_bbref: Baseball Reference
    - name_first, name_last: Player names
    """
    logger.info("Fetching Chadwick Bureau player ID mapping table...")

    # Cache is enabled by default in pybaseball
    mapping = pyb.chadwick_register()

    logger.info(f"Loaded {len(mapping)} player ID mappings")
    return mapping


def map_fangraphs_to_mlb_id(fangraphs_id: str, mapping_df) -> Optional[int]:
    """
    Map a Fangraphs player ID to MLB Stats API player ID.

    Args:
        fangraphs_id: Fangraphs player ID (string)
        mapping_df: Chadwick Bureau mapping dataframe

    Returns:
        MLB Stats API player ID (int) or None if not found
    """
    try:
        # Fangraphs ID is stored as string, convert for comparison
        fg_id_int = int(fangraphs_id)

        # Find matching row
        match = mapping_df[mapping_df['key_fangraphs'] == fg_id_int]

        if not match.empty:
            mlb_id = match.iloc[0]['key_mlbam']
            if not pyb.cache.config.enabled or (mlb_id and mlb_id > 0):
                return int(mlb_id)

    except (ValueError, TypeError, KeyError):
        pass

    return None


def update_prospects_with_mlb_ids():
    """
    Update all prospects in database with MLB player IDs from Fangraphs IDs.
    """
    db = get_db_sync()

    try:
        # Get Chadwick Bureau mapping
        mapping_df = get_player_id_mapping()

        # Get all prospects with Fangraphs IDs but no MLB player ID
        query = text("""
            SELECT id, fg_player_id, name
            FROM prospects
            WHERE fg_player_id IS NOT NULL
            AND (mlb_player_id IS NULL OR mlb_player_id = '')
            ORDER BY id
        """)

        result = db.execute(query)
        prospects = result.fetchall()

        logger.info(f"Found {len(prospects)} prospects to map")

        mapped_count = 0
        not_found_count = 0

        for prospect_id, fg_id, name in prospects:
            # Map Fangraphs ID to MLB ID
            mlb_id = map_fangraphs_to_mlb_id(fg_id, mapping_df)

            if mlb_id:
                # Update prospect with MLB player ID
                update_query = text("""
                    UPDATE prospects
                    SET mlb_player_id = :mlb_id
                    WHERE id = :prospect_id
                """)

                db.execute(update_query, {
                    'mlb_id': str(mlb_id),
                    'prospect_id': prospect_id
                })

                mapped_count += 1
                logger.info(f"  [{mapped_count}] Mapped {name}: FG={fg_id} → MLB={mlb_id}")
            else:
                not_found_count += 1
                if not_found_count <= 10:  # Only log first 10 not found
                    logger.warning(f"  No MLB ID found for {name} (FG ID: {fg_id})")

        # Commit all updates
        db.commit()

        logger.info(f"\nMapping complete!")
        logger.info(f"  Successfully mapped: {mapped_count}")
        logger.info(f"  Not found: {not_found_count}")
        logger.info(f"  Total processed: {len(prospects)}")

    except Exception as e:
        logger.error(f"Error during mapping: {str(e)}")
        db.rollback()
        raise

    finally:
        db.close()


def verify_mappings():
    """Verify that prospects now have MLB player IDs."""
    db = get_db_sync()

    try:
        # Count prospects with MLB IDs
        query = text("""
            SELECT
                COUNT(*) as total_prospects,
                COUNT(fg_player_id) as have_fg_id,
                COUNT(mlb_player_id) as have_mlb_id
            FROM prospects
        """)

        result = db.execute(query)
        row = result.fetchone()

        logger.info(f"\nProspect ID Coverage:")
        logger.info(f"  Total prospects: {row[0]}")
        logger.info(f"  Have Fangraphs ID: {row[1]} ({row[1]/row[0]*100:.1f}%)")
        logger.info(f"  Have MLB player ID: {row[2]} ({row[2]/row[0]*100:.1f}%)")

        # Sample some mapped prospects
        sample_query = text("""
            SELECT name, fg_player_id, mlb_player_id, position
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
            LIMIT 10
        """)

        result = db.execute(sample_query)
        rows = result.fetchall()

        logger.info(f"\nSample mapped prospects:")
        for name, fg_id, mlb_id, pos in rows:
            logger.info(f"  {name} ({pos}): FG={fg_id}, MLB={mlb_id}")

    finally:
        db.close()


def main():
    """Main execution."""
    logger.info("=" * 60)
    logger.info("Player ID Mapping: Fangraphs → MLB Stats API")
    logger.info("=" * 60)

    # Run mapping
    update_prospects_with_mlb_ids()

    # Verify results
    verify_mappings()

    logger.info("\n" + "=" * 60)
    logger.info("Mapping complete! Ready to collect MiLB game logs.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
