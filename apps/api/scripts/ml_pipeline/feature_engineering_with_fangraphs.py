#!/usr/bin/env python3
"""
Enhanced Feature Engineering with Fangraphs Prospect Grades Integration

Extends the base feature engineering to include scouting grades from Fangraphs.
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


class FangraphsFeatureEngineer(FeatureEngineer):
    """Feature engineer with Fangraphs prospect grade integration."""

    def __init__(self):
        super().__init__()
        self.fangraphs_cache = {}
        self.name_mappings = {}
        self.median_grades = None  # Will store median values for fallback

    async def load_fangraphs_data(self):
        """Load all Fangraphs prospect grades into memory for matching."""

        query = """
            SELECT
                fg_player_id,
                player_name,
                organization,
                position,
                fv,
                hit_grade,
                power_grade,
                raw_power_grade,
                speed_grade,
                field_grade,
                fb_grade,
                sl_grade,
                cb_grade,
                ch_grade,
                cmd_grade,
                EXTRACT(YEAR FROM import_date) as report_year,
                top_100_rank,
                org_rank,
                age
            FROM fangraphs_prospect_grades
            WHERE fv IS NOT NULL
            ORDER BY import_date DESC, fv DESC
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            data = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Store by player name for fuzzy matching
        for _, row in data.iterrows():
            name = self._normalize_name(row['player_name'])
            if name not in self.fangraphs_cache:
                self.fangraphs_cache[name] = row.to_dict()

        logger.info(f"Loaded {len(self.fangraphs_cache)} unique Fangraphs prospects")

        # Calculate median grades for fallback
        self._calculate_median_grades(data)

    def _calculate_median_grades(self, data: pd.DataFrame):
        """Calculate median grades for fallback when no match is found."""

        # Calculate medians for all numeric grade columns
        grade_columns = [
            'fv', 'hit_future', 'game_pwr_future', 'raw_pwr_future',
            'spd_future', 'fld_future', 'fb_future', 'sl_future',
            'cb_future', 'ch_future', 'cmd_future'
        ]

        medians = {}
        for col in grade_columns:
            if col in data.columns:
                # Filter out nulls and zeros for more meaningful medians
                valid_values = data[col].dropna()
                valid_values = valid_values[valid_values > 0]
                if len(valid_values) > 0:
                    medians[col] = valid_values.median()
                else:
                    medians[col] = 45 if col == 'fv' else 50  # Default middle grades

        # Calculate median rankings
        medians['top_100_rank'] = None  # Most players aren't top 100
        medians['org_rank'] = 15  # Middle of organization rankings

        self.median_grades = medians

        logger.info(f"Calculated median grades: FV={medians.get('fv', 45):.0f}, "
                   f"Hit={medians.get('hit_future', 50):.0f}, "
                   f"Power={medians.get('game_pwr_future', 50):.0f}")

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
        """Match a player to their Fangraphs prospect grades."""

        # First try direct ID matching if we have a mapping
        if player_id in self.name_mappings:
            fg_name = self.name_mappings[player_id]
            if fg_name in self.fangraphs_cache:
                return self.fangraphs_cache[fg_name]

        # Get player name from database if not provided
        if not player_name:
            query = """
                SELECT DISTINCT player_name
                FROM milb_game_logs
                WHERE mlb_player_id = :player_id
                AND player_name IS NOT NULL
                LIMIT 1
            """
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(query),
                    {"player_id": player_id}
                )
                row = result.fetchone()
                if row:
                    player_name = row[0]

        if not player_name:
            return None

        # Normalize for matching
        norm_name = self._normalize_name(player_name)

        # Try exact match first
        if norm_name in self.fangraphs_cache:
            self.name_mappings[player_id] = norm_name
            return self.fangraphs_cache[norm_name]

        # Fuzzy matching
        best_match = None
        best_score = 0

        for fg_name in self.fangraphs_cache:
            score = fuzz.ratio(norm_name, fg_name)
            if score > best_score and score >= 85:  # 85% similarity threshold
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

        # Match to Fangraphs
        fg_data = await self.match_player_to_fangraphs(player_id)

        if fg_data:
            # Add Fangraphs features
            base_features.update({
                # Future Value - primary overall grade (20-80 scale)
                'fg_fv': fg_data.get('fv', 0) / 10.0,  # Normalize to 0-8 scale

                # Tool grades (20-80 scale, normalize to 0-1)
                'fg_hit_future': (fg_data.get('hit_future', 0) or 0) / 80.0,
                'fg_power_future': (fg_data.get('game_pwr_future', 0) or 0) / 80.0,
                'fg_speed_future': (fg_data.get('spd_future', 0) or 0) / 80.0,
                'fg_field_future': (fg_data.get('fld_future', 0) or 0) / 80.0,

                # Raw power can differ from game power
                'fg_raw_power': (fg_data.get('raw_pwr_future', 0) or 0) / 80.0,

                # Pitching grades if available
                'fg_fb_future': (fg_data.get('fb_future', 0) or 0) / 80.0,
                'fg_breaking_future': max(
                    (fg_data.get('sl_future', 0) or 0),
                    (fg_data.get('cb_future', 0) or 0)
                ) / 80.0,
                'fg_ch_future': (fg_data.get('ch_future', 0) or 0) / 80.0,
                'fg_cmd_future': (fg_data.get('cmd_future', 0) or 0) / 80.0,

                # Rankings
                'fg_top100_rank': 101 - (fg_data.get('top_100_rank', 0) or 101),  # Invert so higher is better
                'fg_org_rank': 31 - min((fg_data.get('org_rank', 0) or 31), 30),  # Invert, cap at 30

                # Composite scores
                'fg_hit_tool_composite': (
                    ((fg_data.get('hit_future', 0) or 0) +
                     (fg_data.get('game_pwr_future', 0) or 0)) / 160.0
                ),
                'fg_athleticism_composite': (
                    ((fg_data.get('spd_future', 0) or 0) +
                     (fg_data.get('fld_future', 0) or 0)) / 160.0
                ),

                # Flags for elite tools (60+ grade)
                'fg_has_plus_hit': 1 if (fg_data.get('hit_future', 0) or 0) >= 60 else 0,
                'fg_has_plus_power': 1 if (fg_data.get('game_pwr_future', 0) or 0) >= 60 else 0,
                'fg_has_plus_speed': 1 if (fg_data.get('spd_future', 0) or 0) >= 60 else 0,

                # Data quality indicator
                'has_fg_grades': 1
            })

            logger.debug(f"Added Fangraphs grades for player {player_id}: FV={fg_data.get('fv')}")

        else:
            # Use median Fangraphs features as fallback for unmatched players
            if self.median_grades:
                # Use median values - these represent a "typical" prospect
                base_features.update({
                    'fg_fv': self.median_grades.get('fv', 45) / 10.0,
                    'fg_hit_future': self.median_grades.get('hit_future', 50) / 80.0,
                    'fg_power_future': self.median_grades.get('game_pwr_future', 50) / 80.0,
                    'fg_speed_future': self.median_grades.get('spd_future', 50) / 80.0,
                    'fg_field_future': self.median_grades.get('fld_future', 50) / 80.0,
                    'fg_raw_power': self.median_grades.get('raw_pwr_future', 50) / 80.0,
                    'fg_fb_future': self.median_grades.get('fb_future', 50) / 80.0,
                    'fg_breaking_future': max(
                        self.median_grades.get('sl_future', 50),
                        self.median_grades.get('cb_future', 50)
                    ) / 80.0,
                    'fg_ch_future': self.median_grades.get('ch_future', 50) / 80.0,
                    'fg_cmd_future': self.median_grades.get('cmd_future', 50) / 80.0,

                    # Rankings - use middle values
                    'fg_top100_rank': 0,  # Not a top 100 prospect
                    'fg_org_rank': 15,  # Middle of org (out of ~30)

                    # Composite scores using median values
                    'fg_hit_tool_composite': (
                        (self.median_grades.get('hit_future', 50) +
                         self.median_grades.get('game_pwr_future', 50)) / 160.0
                    ),
                    'fg_athleticism_composite': (
                        (self.median_grades.get('spd_future', 50) +
                         self.median_grades.get('fld_future', 50)) / 160.0
                    ),

                    # No plus tools for median prospect
                    'fg_has_plus_hit': 0,
                    'fg_has_plus_power': 0,
                    'fg_has_plus_speed': 0,

                    # Indicator that these are median fallback values
                    'has_fg_grades': 0.5  # 0.5 indicates fallback median values
                })

                logger.debug(f"Using median Fangraphs grades for unmatched player {player_id}")
            else:
                # No median grades available - use zeros
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
                    'fg_hit_tool_composite': 0,
                    'fg_athleticism_composite': 0,
                    'fg_has_plus_hit': 0,
                    'fg_has_plus_power': 0,
                    'fg_has_plus_speed': 0,
                    'has_fg_grades': 0
                })

        return base_features

    async def create_training_features(
        self,
        min_pa: int = 100,
        seasons: List[int] = [2021, 2022, 2023, 2024, 2025]
    ) -> pd.DataFrame:
        """Create feature matrix for all qualifying players with Fangraphs integration."""

        # Load Fangraphs data
        await self.load_fangraphs_data()

        # Get qualifying players
        query = """
            SELECT DISTINCT mlb_player_id, player_name
            FROM milb_game_logs
            WHERE season IN :seasons
            AND plate_appearances > 0
            GROUP BY mlb_player_id, player_name
            HAVING SUM(plate_appearances) >= :min_pa
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"seasons": tuple(seasons), "min_pa": min_pa}
            )
            players = result.fetchall()

        logger.info(f"Creating features for {len(players)} qualifying players...")

        all_features = []
        fg_matched = 0

        for i, (player_id, player_name) in enumerate(players):
            if i % 100 == 0:
                logger.info(f"Processing player {i}/{len(players)} ({fg_matched} with FG grades)")

            try:
                features = await self.create_player_features(player_id)
                if features:
                    all_features.append(features)
                    if features.get('has_fg_grades', 0) == 1:
                        fg_matched += 1
            except Exception as e:
                logger.error(f"Error creating features for player {player_id}: {str(e)}")
                continue

        feature_df = pd.DataFrame(all_features)

        logger.info(f"Created features for {len(feature_df)} players")
        logger.info(f"Matched Fangraphs grades for {fg_matched} players ({fg_matched/len(feature_df)*100:.1f}%)")

        # Log feature importance of FG grades
        if fg_matched > 0:
            fg_cols = [col for col in feature_df.columns if col.startswith('fg_')]
            logger.info(f"Added {len(fg_cols)} Fangraphs features")

            # Check correlation with performance for players with grades
            if 'ops' in feature_df.columns:
                fg_players = feature_df[feature_df['has_fg_grades'] == 1]
                if len(fg_players) > 10:
                    fv_corr = fg_players['fg_fv'].corr(fg_players['ops'])
                    hit_corr = fg_players['fg_hit_future'].corr(fg_players['batting_avg'])
                    power_corr = fg_players['fg_power_future'].corr(fg_players.get('iso_power', fg_players['slg']))

                    logger.info("Fangraphs grade correlations:")
                    logger.info(f"  FV vs OPS: {fv_corr:.3f}")
                    logger.info(f"  Hit grade vs AVG: {hit_corr:.3f}")
                    logger.info(f"  Power grade vs ISO: {power_corr:.3f}")

        return feature_df


async def test_fangraphs_integration():
    """Test the Fangraphs feature integration."""

    engineer = FangraphsFeatureEngineer()

    # Test with a top prospect
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT fg.player_name, fg.fv, fg.organization
            FROM fangraphs_prospect_grades fg
            WHERE fg.fv >= 50
            AND fg.top_100_rank IS NOT NULL
            ORDER BY fg.top_100_rank
            LIMIT 5
        """))

        print("\n=== Top Fangraphs Prospects ===")
        top_prospects = []
        for row in result.fetchall():
            print(f"{row[0]} ({row[2]}): FV {row[1]}")
            top_prospects.append(row[0])

    # Try to match these prospects in MiLB data
    print("\n=== Matching to MiLB Data ===")

    for prospect_name in top_prospects:
        # Search for player in MiLB
        query = """
            SELECT DISTINCT mlb_player_id, player_name
            FROM milb_game_logs
            WHERE LOWER(player_name) LIKE LOWER(:name_pattern)
            AND season = 2024
            LIMIT 1
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"name_pattern": f"%{prospect_name.split()[-1]}%"}  # Search by last name
            )
            row = result.fetchone()

            if row:
                player_id, found_name = row
                print(f"\nFound: {found_name} (ID: {player_id})")

                # Get features with Fangraphs
                features = await engineer.create_player_features(player_id)

                if features and features.get('has_fg_grades'):
                    print(f"  FV: {features['fg_fv']*10:.0f}")
                    print(f"  Hit: {features['fg_hit_future']*80:.0f}")
                    print(f"  Power: {features['fg_power_future']*80:.0f}")
                    print(f"  Speed: {features['fg_speed_future']*80:.0f}")
                else:
                    print("  No Fangraphs match")
            else:
                print(f"\n{prospect_name}: Not found in MiLB data")


if __name__ == "__main__":
    asyncio.run(test_fangraphs_integration())