#!/usr/bin/env python3
"""
Enhanced Player ID Mapping: Fangraphs → MLB Stats API
======================================================
Uses multiple data sources to map prospect IDs:
1. Pybaseball Chadwick register (26k players, 100% FG/MLB coverage)
2. MLB player lookup CSV (512k players, includes MiLB IDs)
3. Name-based fuzzy matching as fallback

Usage:
    python map_player_ids_enhanced.py
"""

import sys
import os
import logging
from typing import Optional, Dict
import pandas as pd
from fuzzywuzzy import fuzz

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


class EnhancedPlayerIDMapper:
    """Maps Fangraphs IDs to MLB IDs using multiple data sources."""

    def __init__(self):
        self.chadwick_df = None
        self.mlb_lookup_df = None

    def load_data_sources(self):
        """Load all player ID mapping data sources."""

        # 1. Load Chadwick Bureau register (via pybaseball)
        logger.info("Loading Chadwick Bureau register...")
        self.chadwick_df = pyb.chadwick_register()
        logger.info(f"  Loaded {len(self.chadwick_df)} players from Chadwick")

        # 2. Try to load MLB player lookup CSV if available
        lookup_path = "C:/Users/lilra/myprojects/mlb-player-lookup/mlb-player-lookup/data/combined_people.csv"
        if os.path.exists(lookup_path):
            logger.info("Loading MLB player lookup database...")
            self.mlb_lookup_df = pd.read_csv(lookup_path)
            logger.info(f"  Loaded {len(self.mlb_lookup_df)} players from MLB lookup")
        else:
            logger.warning("  MLB player lookup CSV not found, skipping")

    def map_by_fangraphs_id(self, fg_id: str) -> Optional[int]:
        """
        Map Fangraphs ID to MLB ID using direct ID lookup.

        Returns:
            MLB player ID (int) or None
        """
        # Skip international amateurs (sa prefix)
        if str(fg_id).startswith('sa'):
            return None

        try:
            fg_id_int = int(fg_id)
        except (ValueError, TypeError):
            return None

        # Try Chadwick register first
        match = self.chadwick_df[self.chadwick_df['key_fangraphs'] == fg_id_int]
        if not match.empty:
            mlb_id = match.iloc[0]['key_mlbam']
            if pd.notna(mlb_id):
                return int(mlb_id)

        # Try MLB lookup database
        if self.mlb_lookup_df is not None:
            match = self.mlb_lookup_df[self.mlb_lookup_df['key_fangraphs'] == fg_id_int]
            if not match.empty:
                mlb_id = match.iloc[0]['key_mlbam']
                if pd.notna(mlb_id):
                    return int(mlb_id)

        return None

    def map_by_name(self, name: str, fg_id: str) -> Optional[int]:
        """
        Map by fuzzy name matching as fallback.

        Only used when direct ID mapping fails.
        Uses high threshold (>95) to avoid false positives.
        """
        # Skip if international amateur
        if str(fg_id).startswith('sa'):
            return None

        # Clean name for matching
        name_clean = name.strip().lower()

        # Try exact name match in Chadwick
        for _, row in self.chadwick_df.iterrows():
            full_name = f"{row['name_first']} {row['name_last']}".lower()

            # Use fuzzy matching with high threshold
            similarity = fuzz.ratio(name_clean, full_name)

            if similarity > 95:  # Very high threshold to avoid false positives
                mlb_id = row['key_mlbam']
                if pd.notna(mlb_id):
                    logger.info(f"    Fuzzy match: '{name}' → '{row['name_first']} {row['name_last']}' (score: {similarity})")
                    return int(mlb_id)

        return None

    def update_prospects_with_mlb_ids(self):
        """Update all prospects in database with MLB player IDs."""

        db = get_db_sync()

        try:
            # Load data sources
            self.load_data_sources()

            # Get prospects to map
            query = text("""
                SELECT id, fg_player_id, name, position
                FROM prospects
                WHERE fg_player_id IS NOT NULL
                AND (mlb_player_id IS NULL OR mlb_player_id = '')
                ORDER BY id
            """)

            result = db.execute(query)
            prospects = result.fetchall()

            logger.info(f"\nFound {len(prospects)} prospects to map")
            logger.info("=" * 60)

            mapped_by_id = 0
            mapped_by_name = 0
            international_amateurs = 0
            not_found = 0

            for prospect_id, fg_id, name, position in prospects:
                # Try direct FG ID mapping first
                mlb_id = self.map_by_fangraphs_id(fg_id)

                if mlb_id:
                    # Update prospect
                    update_query = text("""
                        UPDATE prospects
                        SET mlb_player_id = :mlb_id
                        WHERE id = :prospect_id
                    """)
                    db.execute(update_query, {'mlb_id': str(mlb_id), 'prospect_id': prospect_id})
                    mapped_by_id += 1
                    logger.info(f"  [ID] {name} ({position}): FG={fg_id} → MLB={mlb_id}")

                elif str(fg_id).startswith('sa'):
                    international_amateurs += 1
                    if international_amateurs <= 5:  # Only log first 5
                        logger.debug(f"  [IA] {name} ({position}): FG={fg_id} - International amateur")

                else:
                    # Try fuzzy name matching as last resort
                    mlb_id = self.map_by_name(name, fg_id)

                    if mlb_id:
                        update_query = text("""
                            UPDATE prospects
                            SET mlb_player_id = :mlb_id
                            WHERE id = :prospect_id
                        """)
                        db.execute(update_query, {'mlb_id': str(mlb_id), 'prospect_id': prospect_id})
                        mapped_by_name += 1
                        logger.info(f"  [NAME] {name} ({position}): FG={fg_id} → MLB={mlb_id}")
                    else:
                        not_found += 1
                        if not_found <= 5:  # Only log first 5
                            logger.debug(f"  [X] {name} ({position}): FG={fg_id} - Not found")

            # Commit all updates
            db.commit()

            logger.info("\n" + "=" * 60)
            logger.info("Mapping complete!")
            logger.info(f"  Mapped by ID: {mapped_by_id}")
            logger.info(f"  Mapped by name: {mapped_by_name}")
            logger.info(f"  International amateurs (no MLB ID): {international_amateurs}")
            logger.info(f"  Not found: {not_found}")
            logger.info(f"  Total processed: {len(prospects)}")

        except Exception as e:
            logger.error(f"Error during mapping: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()


def verify_mappings():
    """Verify final mapping coverage."""
    db = get_db_sync()

    try:
        query = text("""
            SELECT
                COUNT(*) as total_prospects,
                COUNT(fg_player_id) as have_fg_id,
                COUNT(mlb_player_id) as have_mlb_id,
                COUNT(CASE WHEN fg_player_id LIKE 'sa%' THEN 1 END) as international_amateurs
            FROM prospects
        """)

        result = db.execute(query)
        row = result.fetchone()

        logger.info("\n" + "=" * 60)
        logger.info("Prospect ID Coverage:")
        logger.info(f"  Total prospects: {row[0]}")
        logger.info(f"  Have Fangraphs ID: {row[1]} ({row[1]/row[0]*100:.1f}%)")
        logger.info(f"  Have MLB player ID: {row[2]} ({row[2]/row[0]*100:.1f}%)")
        logger.info(f"  International amateurs: {row[3]} ({row[3]/row[0]*100:.1f}%)")
        logger.info("=" * 60)

    finally:
        db.close()


def main():
    """Main execution."""
    logger.info("=" * 60)
    logger.info("Enhanced Player ID Mapping")
    logger.info("=" * 60)

    mapper = EnhancedPlayerIDMapper()
    mapper.update_prospects_with_mlb_ids()

    verify_mappings()


if __name__ == "__main__":
    main()
