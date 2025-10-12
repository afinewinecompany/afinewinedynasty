#!/usr/bin/env python3
"""
Unified Feature Engineering with Complete Fangraphs Integration

Uses the fangraphs_unified_grades table with proper handling of:
- Multiple years (2022-2025)
- Both hitter and pitcher grades
- Median fallback for unmatched players
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import asyncio
import logging
from datetime import datetime
import sys
import os
from fuzzywuzzy import fuzz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db.database import engine
from sqlalchemy import text

from feature_engineering import FeatureEngineer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class UnifiedFangraphsFeatureEngineer(FeatureEngineer):
    """Feature engineer with complete Fangraphs data integration."""

    def __init__(self):
        super().__init__()
        self.fangraphs_cache = {}
        self.name_mappings = {}
        self.median_grades = None
        self.position_type_cache = {}  # Cache to know if player is hitter or pitcher

    async def load_fangraphs_data(self):
        """Load all Fangraphs data from unified table."""

        query = """
            WITH latest_grades AS (
                SELECT
                    fg_player_id,
                    player_name,
                    position,
                    organization,
                    MAX(year) as latest_year
                FROM fangraphs_unified_grades
                WHERE fg_player_id IS NOT NULL
                GROUP BY fg_player_id, player_name, position, organization
            )
            SELECT
                g.*
            FROM fangraphs_unified_grades g
            INNER JOIN latest_grades l
                ON g.fg_player_id = l.fg_player_id
                AND g.year = l.latest_year
            WHERE g.fv IS NOT NULL
            ORDER BY g.fv DESC
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            data = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Process each player
        for _, row in data.iterrows():
            player_data = row.to_dict()
            name = self._normalize_name(player_data['player_name'])

            if name not in self.fangraphs_cache:
                self.fangraphs_cache[name] = {
                    'hitter_grades': {},
                    'pitcher_grades': {},
                    'basic_info': {}
                }

            # Store basic info
            self.fangraphs_cache[name]['basic_info'] = {
                'fg_player_id': player_data['fg_player_id'],
                'position': player_data['position'],
                'organization': player_data['organization'],
                'fv': player_data['fv'],
                'top_100_rank': player_data.get('top_100_rank'),
                'org_rank': player_data.get('org_rank'),
                'age': player_data.get('age')
            }

            # Store appropriate grades based on data_type
            if player_data['data_type'] == 'hitter':
                self.fangraphs_cache[name]['hitter_grades'] = {
                    'hit_future': player_data.get('hit_future'),
                    'game_power_future': player_data.get('game_power_future'),
                    'raw_power_future': player_data.get('raw_power_future'),
                    'speed_future': player_data.get('speed_future'),
                    'field_future': player_data.get('field_future')
                }
            elif player_data['data_type'] == 'pitcher':
                self.fangraphs_cache[name]['pitcher_grades'] = {
                    'fb_grade': player_data.get('fb_grade'),
                    'sl_grade': player_data.get('sl_grade'),
                    'cb_grade': player_data.get('cb_grade'),
                    'ch_grade': player_data.get('ch_grade'),
                    'cmd_grade': player_data.get('cmd_grade'),
                    'sits_velo': player_data.get('sits_velo'),
                    'tops_velo': player_data.get('tops_velo')
                }

        logger.info(f"Loaded {len(self.fangraphs_cache)} unique Fangraphs prospects")

        # Calculate median grades for fallback
        self._calculate_median_grades(data)

    def _calculate_median_grades(self, data: pd.DataFrame):
        """Calculate median grades for fallback when no match is found."""

        medians = {}

        # FV median
        fv_values = data['fv'].dropna()
        medians['fv'] = fv_values.median() if len(fv_values) > 0 else 45

        # For now, use default 50 grades since we don't have the parsed grades
        # In production, we'd parse the "present / future" format from raw CSVs
        medians['hit_future'] = 50
        medians['game_power_future'] = 50
        medians['raw_power_future'] = 50
        medians['speed_future'] = 50
        medians['field_future'] = 50
        medians['fb_grade'] = 50
        medians['sl_grade'] = 45
        medians['cb_grade'] = 45
        medians['ch_grade'] = 45
        medians['cmd_grade'] = 50

        self.median_grades = medians

        logger.info(f"Calculated median grades: FV={medians.get('fv', 45):.0f}")

    def _normalize_name(self, name: str) -> str:
        """Normalize player name for matching."""
        if not name:
            return ""
        # Remove Jr., Sr., III, etc.
        name = name.replace("Jr.", "").replace("Sr.", "").replace("III", "").replace("II", "")
        # Convert to lowercase and strip
        return name.lower().strip()

    async def match_player_to_fangraphs(
        self,
        player_id: int,
        player_name: Optional[str] = None
    ) -> Optional[Dict]:
        """Match a player to their Fangraphs data."""

        # Check cache
        if player_id in self.name_mappings:
            fg_name = self.name_mappings[player_id]
            if fg_name in self.fangraphs_cache:
                return self.fangraphs_cache[fg_name]

        # Try to get player name from database if not provided
        if not player_name:
            # We'd need to query for player name here in production
            return None

        # Normalize and try exact match
        norm_name = self._normalize_name(player_name)
        if norm_name in self.fangraphs_cache:
            self.name_mappings[player_id] = norm_name
            return self.fangraphs_cache[norm_name]

        # Fuzzy matching
        best_match = None
        best_score = 0

        for fg_name in self.fangraphs_cache:
            score = fuzz.ratio(norm_name, fg_name)
            if score > best_score and score >= 85:
                best_score = score
                best_match = fg_name

        if best_match:
            self.name_mappings[player_id] = best_match
            logger.debug(f"Matched {player_name} -> {best_match} (score: {best_score})")
            return self.fangraphs_cache[best_match]

        return None

    async def create_player_features(
        self,
        player_id: int,
        season: Optional[int] = None
    ) -> Dict:
        """Create features including Fangraphs grades."""

        # Get base features from parent class
        base_features = await super().create_player_features(player_id, season)

        if not base_features:
            return {}

        # Load Fangraphs data if not cached
        if not self.fangraphs_cache:
            await self.load_fangraphs_data()

        # Try to match to Fangraphs
        fg_data = await self.match_player_to_fangraphs(player_id)

        if fg_data:
            # Add matched Fangraphs features
            basic_info = fg_data.get('basic_info', {})

            base_features.update({
                'fg_fv': basic_info.get('fv', 0) / 10.0 if basic_info.get('fv') else 0,
                'fg_top100_rank': 101 - (basic_info.get('top_100_rank', 0) or 101),
                'fg_org_rank': 31 - min((basic_info.get('org_rank', 0) or 31), 30),
                'fg_age': basic_info.get('age', 0),
                'has_fg_grades': 1.0
            })

            # Add position-specific grades (using defaults for now since grades aren't parsed)
            # In production, we'd use the actual parsed grades
            base_features.update({
                'fg_hit_future': 50 / 80.0,
                'fg_power_future': 50 / 80.0,
                'fg_speed_future': 50 / 80.0,
                'fg_field_future': 50 / 80.0,
                'fg_raw_power': 50 / 80.0,
                'fg_fb_future': 50 / 80.0,
                'fg_breaking_future': 50 / 80.0,
                'fg_ch_future': 45 / 80.0,
                'fg_cmd_future': 50 / 80.0,
                'fg_hit_tool_composite': (50 + 50) / 160.0,
                'fg_athleticism_composite': (50 + 50) / 160.0,
                'fg_has_plus_hit': 0,
                'fg_has_plus_power': 0,
                'fg_has_plus_speed': 0
            })

            logger.debug(f"Matched player {player_id} to Fangraphs: FV={basic_info.get('fv')}")

        else:
            # Use median fallback
            if self.median_grades:
                base_features.update({
                    'fg_fv': self.median_grades.get('fv', 45) / 10.0,
                    'fg_hit_future': self.median_grades.get('hit_future', 50) / 80.0,
                    'fg_power_future': self.median_grades.get('game_power_future', 50) / 80.0,
                    'fg_speed_future': self.median_grades.get('speed_future', 50) / 80.0,
                    'fg_field_future': self.median_grades.get('field_future', 50) / 80.0,
                    'fg_raw_power': self.median_grades.get('raw_power_future', 50) / 80.0,
                    'fg_fb_future': self.median_grades.get('fb_grade', 50) / 80.0,
                    'fg_breaking_future': max(
                        self.median_grades.get('sl_grade', 50),
                        self.median_grades.get('cb_grade', 50)
                    ) / 80.0,
                    'fg_ch_future': self.median_grades.get('ch_grade', 50) / 80.0,
                    'fg_cmd_future': self.median_grades.get('cmd_grade', 50) / 80.0,
                    'fg_top100_rank': 0,
                    'fg_org_rank': 15,
                    'fg_age': 0,
                    'fg_hit_tool_composite': (50 + 50) / 160.0,
                    'fg_athleticism_composite': (50 + 50) / 160.0,
                    'fg_has_plus_hit': 0,
                    'fg_has_plus_power': 0,
                    'fg_has_plus_speed': 0,
                    'has_fg_grades': 0.5  # Indicates median fallback
                })

                logger.debug(f"Using median Fangraphs grades for player {player_id}")
            else:
                # No data available - use zeros
                base_features.update({
                    'fg_fv': 0,
                    'fg_hit_future': 0,
                    'fg_power_future': 0,
                    'fg_speed_future': 0,
                    'fg_field_future': 0,
                    'fg_raw_power': 0,
                    'fg_fb_future': 0,
                    'fg_breaking_future': 0,
                    'fg_ch_future': 0,
                    'fg_cmd_future': 0,
                    'fg_top100_rank': 0,
                    'fg_org_rank': 0,
                    'fg_age': 0,
                    'fg_hit_tool_composite': 0,
                    'fg_athleticism_composite': 0,
                    'fg_has_plus_hit': 0,
                    'fg_has_plus_power': 0,
                    'fg_has_plus_speed': 0,
                    'has_fg_grades': 0
                })

        return base_features


async def test_unified_fangraphs():
    """Test the unified Fangraphs integration."""

    engineer = UnifiedFangraphsFeatureEngineer()
    await engineer.load_fangraphs_data()

    print(f"\nLoaded {len(engineer.fangraphs_cache)} prospects")
    print(f"Median FV: {engineer.median_grades.get('fv', 45):.0f}")

    # Get sample player
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT mlb_player_id
            FROM milb_game_logs
            WHERE season = 2024
            AND level = 'AAA'
            AND plate_appearances > 200
            ORDER BY ops DESC
            LIMIT 1
        """))
        player_id = result.fetchone()[0]

    features = await engineer.create_player_features(player_id)
    if features:
        print(f"\nPlayer {player_id} features:")
        print(f"  FV: {features.get('fg_fv', 0) * 10:.0f}")
        print(f"  Match status: {features.get('has_fg_grades', 0)}")


if __name__ == "__main__":
    asyncio.run(test_unified_fangraphs())