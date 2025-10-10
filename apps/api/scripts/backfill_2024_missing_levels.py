#!/usr/bin/env python3
"""
Backfill missing 2024 MiLB data for Rookie, Rookie+, and Winter levels.
This script specifically targets the levels that were not collected in the original 2024 run.
"""

import sys
import os
import argparse
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collect_all_milb_gamelog_v2 import MiLBGameLogCollector
import asyncio


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/backfill_2024_missing_levels.log')
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Run the backfill for missing 2024 levels."""
    parser = argparse.ArgumentParser(
        description='Backfill missing 2024 MiLB data for Rookie/Winter levels'
    )
    parser.add_argument(
        '--concurrent',
        type=int,
        default=5,
        help='Number of concurrent player requests (default: 5)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from previous state if available'
    )
    args = parser.parse_args()

    # Target the specific missing levels for 2024
    # Note: We map Winter to sport_id 17, and Rookie/Rookie+ to 15/16
    missing_levels = ['Rookie', 'Rookie+', 'Winter']

    logger.info("=" * 80)
    logger.info("BACKFILL 2024 MISSING LEVELS")
    logger.info("=" * 80)
    logger.info(f"Target levels: {', '.join(missing_levels)}")
    logger.info(f"Concurrent limit: {args.concurrent}")
    logger.info("=" * 80)

    # Create collector for 2024 season with specific levels
    collector = MiLBGameLogCollector(
        season=2024,
        levels=missing_levels,
        concurrent_limit=args.concurrent,
        resume_file='resume_2024_backfill.json' if args.resume else None
    )

    async with collector:
        # Discover and collect players
        all_players = await collector.discover_players()

        if not all_players:
            logger.warning("No players found for the specified levels in 2024")
            logger.info("This might mean:")
            logger.info("1. These leagues didn't operate in 2024")
            logger.info("2. Different sport IDs are needed")
            logger.info("3. Data is not available in the MLB API")
            return

        logger.info(f"Found {len(all_players)} players to process")

        # Process all players
        await collector.process_all_players(all_players)

        # Print final statistics
        collector.print_summary()

        logger.info("=" * 80)
        logger.info("BACKFILL COMPLETED")
        logger.info("=" * 80)


if __name__ == "__main__":
    # Windows-specific event loop policy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())