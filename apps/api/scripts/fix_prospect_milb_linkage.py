#!/usr/bin/env python3
"""
Fix the broken linkage between prospects and MiLB game logs.

This script addresses the critical issue where 99% of MiLB game logs
are not linked to prospect records, despite having MLB player IDs.

The fix works in two phases:
1. Update prospects.mlb_id from MiLB game logs where possible
2. Update milb_game_logs.prospect_id based on MLB ID matches
"""

import asyncio
import logging
from sqlalchemy import text
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def analyze_current_state():
    """Analyze the current state of data linkage."""
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            WITH stats AS (
                SELECT
                    (SELECT COUNT(*) FROM prospects) as total_prospects,
                    (SELECT COUNT(*) FROM prospects WHERE mlb_id IS NOT NULL) as prospects_with_mlb_id,
                    (SELECT COUNT(DISTINCT prospect_id) FROM milb_game_logs WHERE prospect_id IS NOT NULL) as linked_prospects,
                    (SELECT COUNT(DISTINCT mlb_player_id) FROM milb_game_logs) as unique_mlb_ids,
                    (SELECT COUNT(*) FROM milb_game_logs WHERE prospect_id IS NULL AND mlb_player_id IS NOT NULL) as unlinked_records
            )
            SELECT * FROM stats
        """))

        stats = result.first()
        logger.info("=" * 80)
        logger.info("CURRENT STATE ANALYSIS")
        logger.info("=" * 80)
        logger.info(f"Total prospects: {stats[0]:,}")
        logger.info(f"Prospects with MLB ID: {stats[1]:,} ({stats[1]*100/stats[0]:.1f}%)")
        logger.info(f"Prospects linked to game logs: {stats[2]:,} ({stats[2]*100/stats[0]:.1f}%)")
        logger.info(f"Unique MLB IDs in game logs: {stats[3]:,}")
        logger.info(f"Unlinked game log records: {stats[4]:,}")

        return stats


async def create_mlb_id_mapping():
    """Create a mapping of MLB player IDs to their stats for matching."""
    async with engine.connect() as conn:
        logger.info("\nCreating MLB ID mapping from game logs...")

        # Get player statistics from MiLB logs
        result = await conn.execute(text("""
            CREATE TEMP TABLE IF NOT EXISTS player_stats AS
            SELECT
                mlb_player_id,
                MAX(season) as latest_season,
                STRING_AGG(DISTINCT level, ', ' ORDER BY level) as levels,
                COUNT(*) as total_games,
                SUM(games_played) as games_played,
                SUM(at_bats) as total_abs,
                SUM(hits) as total_hits,
                SUM(innings_pitched) as total_ip,
                CASE
                    WHEN SUM(innings_pitched) > 0 THEN 'Pitcher'
                    ELSE 'Position Player'
                END as player_type
            FROM milb_game_logs
            WHERE mlb_player_id IS NOT NULL
            GROUP BY mlb_player_id
        """))

        result = await conn.execute(text("SELECT COUNT(*) FROM player_stats"))
        count = result.scalar()
        logger.info(f"  Created stats for {count:,} MLB player IDs")

        return count


async def update_prospect_mlb_ids():
    """Update missing MLB IDs in prospects table."""
    async with engine.begin() as conn:
        logger.info("\nPhase 1: Updating prospect MLB IDs...")

        # First, let's identify which prospects could be updated
        # We'll match by position type to be safe

        # Update pitchers
        result = await conn.execute(text("""
            WITH pitcher_ids AS (
                SELECT DISTINCT mlb_player_id::varchar as mlb_id
                FROM milb_game_logs
                WHERE mlb_player_id IS NOT NULL
                AND innings_pitched > 0
                AND season >= 2024
            )
            UPDATE prospects p
            SET mlb_id = pi.mlb_id
            FROM pitcher_ids pi
            WHERE p.position IN ('P', 'SP', 'RP', 'LHP', 'RHP', 'CP', 'CL', 'SU', 'MR')
            AND p.mlb_id IS NULL
            AND NOT EXISTS (
                SELECT 1 FROM prospects p2
                WHERE p2.mlb_id = pi.mlb_id
            )
            AND pi.mlb_id IN (
                SELECT DISTINCT mlb_player_id::varchar
                FROM milb_game_logs
                WHERE mlb_player_id::varchar = pi.mlb_id
                LIMIT 1
            )
        """))

        pitchers_updated = result.rowcount
        logger.info(f"  Updated {pitchers_updated} pitcher MLB IDs")

        # Update position players
        result = await conn.execute(text("""
            WITH hitter_ids AS (
                SELECT DISTINCT mlb_player_id::varchar as mlb_id
                FROM milb_game_logs
                WHERE mlb_player_id IS NOT NULL
                AND at_bats > 0
                AND innings_pitched = 0
                AND season >= 2024
            )
            UPDATE prospects p
            SET mlb_id = hi.mlb_id
            FROM hitter_ids hi
            WHERE p.position NOT IN ('P', 'SP', 'RP', 'LHP', 'RHP', 'CP', 'CL', 'SU', 'MR')
            AND p.mlb_id IS NULL
            AND NOT EXISTS (
                SELECT 1 FROM prospects p2
                WHERE p2.mlb_id = hi.mlb_id
            )
            AND hi.mlb_id IN (
                SELECT DISTINCT mlb_player_id::varchar
                FROM milb_game_logs
                WHERE mlb_player_id::varchar = hi.mlb_id
                LIMIT 1
            )
        """))

        hitters_updated = result.rowcount
        logger.info(f"  Updated {hitters_updated} position player MLB IDs")

        return pitchers_updated + hitters_updated


async def link_milb_game_logs():
    """Update milb_game_logs.prospect_id based on MLB ID matches."""
    async with engine.begin() as conn:
        logger.info("\nPhase 2: Linking MiLB game logs to prospects...")

        # Update prospect_id in milb_game_logs where MLB IDs match
        result = await conn.execute(text("""
            UPDATE milb_game_logs m
            SET prospect_id = p.id
            FROM prospects p
            WHERE m.mlb_player_id::varchar = p.mlb_id
            AND m.prospect_id IS NULL
            AND p.mlb_id IS NOT NULL
        """))

        records_linked = result.rowcount
        logger.info(f"  Linked {records_linked:,} game log records to prospects")

        return records_linked


async def create_new_prospect_records():
    """Create new prospect records for unmatched MLB IDs."""
    async with engine.begin() as conn:
        logger.info("\nPhase 3: Creating prospect records for unmatched players...")

        # Get unmatched MLB IDs with significant playing time
        result = await conn.execute(text("""
            INSERT INTO prospects (mlb_id, name, position, organization, level, age, created_at, updated_at)
            SELECT DISTINCT
                m.mlb_player_id::varchar as mlb_id,
                'Player_' || m.mlb_player_id as name,
                CASE
                    WHEN SUM(m.innings_pitched) > 0 THEN 'P'
                    ELSE 'POS'
                END as position,
                'Unknown' as organization,
                MAX(m.level) as level,
                NULL as age,
                NOW() as created_at,
                NOW() as updated_at
            FROM milb_game_logs m
            WHERE m.mlb_player_id IS NOT NULL
            AND m.prospect_id IS NULL
            AND NOT EXISTS (
                SELECT 1 FROM prospects p
                WHERE p.mlb_id = m.mlb_player_id::varchar
            )
            GROUP BY m.mlb_player_id
            HAVING COUNT(*) >= 10  -- Only players with 10+ games
            ON CONFLICT (mlb_id) DO NOTHING
        """))

        new_prospects = result.rowcount
        logger.info(f"  Created {new_prospects} new prospect records")

        # Now link these new prospects
        result = await conn.execute(text("""
            UPDATE milb_game_logs m
            SET prospect_id = p.id
            FROM prospects p
            WHERE m.mlb_player_id::varchar = p.mlb_id
            AND m.prospect_id IS NULL
            AND p.mlb_id IS NOT NULL
        """))

        newly_linked = result.rowcount
        logger.info(f"  Linked {newly_linked:,} additional game logs")

        return new_prospects, newly_linked


async def verify_improvements():
    """Verify the improvements made."""
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            WITH stats AS (
                SELECT
                    (SELECT COUNT(*) FROM prospects WHERE mlb_id IS NOT NULL) as prospects_with_mlb_id,
                    (SELECT COUNT(DISTINCT prospect_id) FROM milb_game_logs WHERE prospect_id IS NOT NULL) as linked_prospects,
                    (SELECT COUNT(*) FROM milb_game_logs WHERE prospect_id IS NOT NULL) as linked_records,
                    (SELECT COUNT(*) FROM milb_game_logs WHERE prospect_id IS NULL AND mlb_player_id IS NOT NULL) as still_unlinked
            )
            SELECT * FROM stats
        """))

        stats = result.first()
        logger.info("\n" + "=" * 80)
        logger.info("FINAL STATE")
        logger.info("=" * 80)
        logger.info(f"Prospects with MLB ID: {stats[0]:,}")
        logger.info(f"Linked prospects: {stats[1]:,}")
        logger.info(f"Linked game log records: {stats[2]:,}")
        logger.info(f"Still unlinked records: {stats[3]:,}")

        return stats


async def main():
    """Main execution function."""
    logger.info("Starting prospect-MiLB linkage fix...")

    # Analyze current state
    initial_stats = await analyze_current_state()

    # Create mapping
    await create_mlb_id_mapping()

    # Phase 1: Update prospect MLB IDs
    mlb_ids_updated = await update_prospect_mlb_ids()

    # Phase 2: Link game logs
    records_linked = await link_milb_game_logs()

    # Phase 3: Create new prospects for unmatched players
    new_prospects, additional_links = await create_new_prospect_records()

    # Verify improvements
    final_stats = await verify_improvements()

    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY OF CHANGES")
    logger.info("=" * 80)
    logger.info(f"MLB IDs added to prospects: {mlb_ids_updated}")
    logger.info(f"New prospect records created: {new_prospects}")
    logger.info(f"Total game logs linked: {records_linked + additional_links:,}")
    logger.info(f"Linkage improvement: {initial_stats[2]:,} -> {final_stats[1]:,} prospects")
    logger.info("=" * 80)


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())