#!/usr/bin/env python3
"""
Collect MLB Statcast pitching data for all pitchers from 2021-2025.
Uses Baseball Savant API to fetch detailed pitch-level data.
"""

import sys
import os
import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
import json
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/mlb_statcast_pitching.log')
    ]
)
logger = logging.getLogger(__name__)


class MLBStatcastPitchingCollector:
    """Collector for MLB Statcast pitching data."""

    BASE_URL = "https://baseballsavant.mlb.com/statcast_search/csv"

    def __init__(self, season_start: int = 2021, season_end: int = 2025):
        self.season_start = season_start
        self.season_end = season_end
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_pitchers = set()
        self.failed_pitchers = set()

    async def __aenter__(self):
        """Initialize session."""
        timeout = aiohttp.ClientTimeout(total=120)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up session."""
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def get_pitchers_from_mlb_logs(self) -> List[int]:
        """Get list of pitchers from MLB game logs."""
        async with engine.connect() as conn:
            # Get pitchers who have pitched in MLB games
            result = await conn.execute(text("""
                SELECT DISTINCT mlb_player_id
                FROM mlb_game_logs
                WHERE season BETWEEN :start_season AND :end_season
                AND mlb_player_id IS NOT NULL
                ORDER BY mlb_player_id
            """), {
                'start_season': self.season_start,
                'end_season': self.season_end
            })

            pitchers = [row[0] for row in result]
            logger.info(f"Found {len(pitchers)} potential pitchers in MLB game logs")
            return pitchers

    async def check_existing_data(self, pitcher_id: int) -> bool:
        """Check if pitcher already has Statcast data."""
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT COUNT(*)
                FROM mlb_statcast_pitching
                WHERE mlb_player_id = :pitcher_id
                AND season BETWEEN :start_season AND :end_season
            """), {
                'pitcher_id': pitcher_id,
                'start_season': self.season_start,
                'end_season': self.season_end
            })

            count = result.scalar()
            return count > 0

    async def fetch_statcast_data(self, pitcher_id: int, season: int) -> Optional[pd.DataFrame]:
        """Fetch Statcast pitching data for a pitcher in a season."""
        try:
            params = {
                'all': 'true',
                'type': 'pitcher',
                'player_id': pitcher_id,
                'season': season,
                'player_type': 'pitcher',
                'min_pitches': '1'
            }

            async with self.session.get(self.BASE_URL, params=params) as response:
                if response.status == 200:
                    content = await response.text()
                    if content and len(content) > 100:  # Has actual data
                        # Parse CSV data
                        from io import StringIO
                        df = pd.read_csv(StringIO(content))

                        if not df.empty:
                            logger.debug(f"Found {len(df)} pitches for pitcher {pitcher_id} in {season}")
                            return df

            return None

        except Exception as e:
            logger.error(f"Error fetching data for pitcher {pitcher_id} in {season}: {str(e)}")
            return None

    async def save_statcast_data(self, pitcher_id: int, df: pd.DataFrame) -> int:
        """Save Statcast data to database."""
        if df.empty:
            return 0

        records_saved = 0

        async with engine.begin() as conn:
            for _, row in df.iterrows():
                try:
                    # Prepare record - map Baseball Savant columns to our schema
                    record = {
                        'mlb_player_id': pitcher_id,
                        'season': int(row.get('game_year', 0)) if pd.notna(row.get('game_year')) else None,
                        'game_date': pd.to_datetime(row.get('game_date')).date() if pd.notna(row.get('game_date')) else None,
                        'sv_id': str(row.get('sv_id', '')) if pd.notna(row.get('sv_id')) else None,
                        'pitch_type': str(row.get('pitch_type', '')) if pd.notna(row.get('pitch_type')) else None,
                        'pitch_name': str(row.get('pitch_name', '')) if pd.notna(row.get('pitch_name')) else None,
                        'release_speed': float(row.get('release_speed')) if pd.notna(row.get('release_speed')) else None,
                        'release_pos_x': float(row.get('release_pos_x')) if pd.notna(row.get('release_pos_x')) else None,
                        'release_pos_y': float(row.get('release_pos_y')) if pd.notna(row.get('release_pos_y')) else None,
                        'release_pos_z': float(row.get('release_pos_z')) if pd.notna(row.get('release_pos_z')) else None,
                        'release_spin_rate': float(row.get('release_spin_rate')) if pd.notna(row.get('release_spin_rate')) else None,
                        'release_extension': float(row.get('release_extension')) if pd.notna(row.get('release_extension')) else None,
                        'events': str(row.get('events', '')) if pd.notna(row.get('events')) else None,
                        'description': str(row.get('description', '')) if pd.notna(row.get('description')) else None,
                        'zone': int(row.get('zone')) if pd.notna(row.get('zone')) else None,
                        'stand': str(row.get('stand', '')) if pd.notna(row.get('stand')) else None,
                        'type': str(row.get('type', '')) if pd.notna(row.get('type')) else None,
                        'balls': int(row.get('balls')) if pd.notna(row.get('balls')) else None,
                        'strikes': int(row.get('strikes')) if pd.notna(row.get('strikes')) else None,
                        'pfx_x': float(row.get('pfx_x')) if pd.notna(row.get('pfx_x')) else None,
                        'pfx_z': float(row.get('pfx_z')) if pd.notna(row.get('pfx_z')) else None,
                        'plate_x': float(row.get('plate_x')) if pd.notna(row.get('plate_x')) else None,
                        'plate_z': float(row.get('plate_z')) if pd.notna(row.get('plate_z')) else None,
                        'vx0': float(row.get('vx0')) if pd.notna(row.get('vx0')) else None,
                        'vy0': float(row.get('vy0')) if pd.notna(row.get('vy0')) else None,
                        'vz0': float(row.get('vz0')) if pd.notna(row.get('vz0')) else None,
                        'ax': float(row.get('ax')) if pd.notna(row.get('ax')) else None,
                        'ay': float(row.get('ay')) if pd.notna(row.get('ay')) else None,
                        'az': float(row.get('az')) if pd.notna(row.get('az')) else None,
                        'effective_speed': float(row.get('effective_speed')) if pd.notna(row.get('effective_speed')) else None,
                        'launch_speed': float(row.get('launch_speed')) if pd.notna(row.get('launch_speed')) else None,
                        'launch_angle': float(row.get('launch_angle')) if pd.notna(row.get('launch_angle')) else None,
                        'hit_distance_sc': float(row.get('hit_distance_sc')) if pd.notna(row.get('hit_distance_sc')) else None
                    }

                    # Insert record
                    await conn.execute(text("""
                        INSERT INTO mlb_statcast_pitching
                        (mlb_player_id, season, game_date, sv_id, pitch_type, pitch_name,
                         release_speed, release_pos_x, release_pos_y, release_pos_z,
                         release_spin_rate, release_extension, events, description,
                         zone, stand, type, balls, strikes, pfx_x, pfx_z, plate_x, plate_z,
                         vx0, vy0, vz0, ax, ay, az, effective_speed, launch_speed,
                         launch_angle, hit_distance_sc)
                        VALUES
                        (:mlb_player_id, :season, :game_date, :sv_id, :pitch_type, :pitch_name,
                         :release_speed, :release_pos_x, :release_pos_y, :release_pos_z,
                         :release_spin_rate, :release_extension, :events, :description,
                         :zone, :stand, :type, :balls, :strikes, :pfx_x, :pfx_z, :plate_x, :plate_z,
                         :vx0, :vy0, :vz0, :ax, :ay, :az, :effective_speed, :launch_speed,
                         :launch_angle, :hit_distance_sc)
                        ON CONFLICT (sv_id) DO NOTHING
                    """), record)

                    records_saved += 1

                except Exception as e:
                    logger.debug(f"Error saving pitch record: {str(e)[:100]}")
                    continue

        return records_saved

    async def collect_pitcher(self, pitcher_id: int) -> int:
        """Collect all Statcast data for a pitcher."""
        # Check if already has data
        if await self.check_existing_data(pitcher_id):
            logger.debug(f"Pitcher {pitcher_id} already has Statcast data")
            self.processed_pitchers.add(pitcher_id)
            return 0

        total_saved = 0

        # Collect for each season
        for season in range(self.season_start, self.season_end + 1):
            df = await self.fetch_statcast_data(pitcher_id, season)

            if df is not None and not df.empty:
                saved = await self.save_statcast_data(pitcher_id, df)
                total_saved += saved
                logger.info(f"Saved {saved} pitches for pitcher {pitcher_id} in {season}")

            # Rate limiting
            await asyncio.sleep(0.5)

        if total_saved > 0:
            self.processed_pitchers.add(pitcher_id)
            logger.info(f"Total saved for pitcher {pitcher_id}: {total_saved} pitches")
        else:
            self.failed_pitchers.add(pitcher_id)

        return total_saved

    async def collect_all_pitchers(self, limit: Optional[int] = None):
        """Collect Statcast data for all pitchers."""
        pitchers = await self.get_pitchers_from_mlb_logs()

        if limit:
            pitchers = pitchers[:limit]

        logger.info(f"Starting collection for {len(pitchers)} pitchers")

        total_pitches = 0
        for i, pitcher_id in enumerate(pitchers, 1):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(pitchers)} pitchers processed")

            pitches_saved = await self.collect_pitcher(pitcher_id)
            total_pitches += pitches_saved

            # Rate limiting between pitchers
            await asyncio.sleep(1.0)

        logger.info("=" * 80)
        logger.info(f"Collection complete!")
        logger.info(f"Pitchers processed: {len(self.processed_pitchers)}")
        logger.info(f"Pitchers failed: {len(self.failed_pitchers)}")
        logger.info(f"Total pitches saved: {total_pitches}")
        logger.info("=" * 80)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Collect MLB Statcast pitching data')
    parser.add_argument('--start', type=int, default=2021, help='Start season')
    parser.add_argument('--end', type=int, default=2025, help='End season')
    parser.add_argument('--limit', type=int, help='Limit number of pitchers to collect')

    args = parser.parse_args()

    async with MLBStatcastPitchingCollector(args.start, args.end) as collector:
        await collector.collect_all_pitchers(limit=args.limit)


if __name__ == "__main__":
    # Windows-specific event loop policy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())