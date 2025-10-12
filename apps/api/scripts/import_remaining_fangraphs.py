#!/usr/bin/env python3
"""
Import remaining Fangraphs data (2023-2025).
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from import_all_fangraphs_data import import_hitters_file, import_pitchers_file, analyze_import_results
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    """Import remaining years."""

    downloads_dir = r"C:\Users\lilra\Downloads"

    # Process remaining years
    for year in [2023, 2024, 2025]:
        logger.info(f"\nProcessing year {year}...")

        # Import hitters
        hitters_file = os.path.join(downloads_dir, f"fangraphs-the-board-hitters-{year}.csv")
        if os.path.exists(hitters_file):
            await import_hitters_file(hitters_file, year)

        # Import pitchers
        pitchers_file = os.path.join(downloads_dir, f"fangraphs-the-board-pitchers-{year}.csv")
        if os.path.exists(pitchers_file):
            await import_pitchers_file(pitchers_file, year)

    # Analyze results
    await analyze_import_results()


if __name__ == "__main__":
    asyncio.run(main())