#!/usr/bin/env python3
"""
Feature Engineering Pipeline for MiLB → MLB Projections

Creates comprehensive feature sets from raw game logs for ML training.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import asyncio
from sqlalchemy import text
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Create ML features from MiLB game logs."""

    def __init__(self):
        self.level_weights = {
            'MLB': 1.0,
            'AAA': 0.90,
            'AA': 0.80,
            'A+': 0.70,
            'A': 0.60,
            'Rookie+': 0.45,
            'Rookie': 0.40,
            'Winter': 0.85  # Winter leagues have good competition
        }

    async def create_player_features(self, player_id: int, season: Optional[int] = None) -> Dict:
        """Create comprehensive feature set for a player."""

        # Get player's game logs
        game_logs = await self.load_player_game_logs(player_id, season)

        if game_logs.empty:
            logger.warning(f"No game logs found for player {player_id}")
            return {}

        # Basic aggregations
        basic_features = self.calculate_basic_stats(game_logs)

        # Level-adjusted stats
        level_adjusted = self.calculate_level_adjusted_stats(game_logs)

        # Development trajectory
        trajectory = self.calculate_trajectory_features(game_logs)

        # Plate discipline
        discipline = self.calculate_discipline_features(game_logs)

        # Power metrics
        power = self.calculate_power_features(game_logs)

        # Age-relative performance
        age_features = await self.calculate_age_relative_features(game_logs)

        # Combine all features
        features = {
            **basic_features,
            **level_adjusted,
            **trajectory,
            **discipline,
            **power,
            **age_features,
            'player_id': player_id,
            'feature_date': datetime.now().isoformat()
        }

        return features

    async def load_player_game_logs(self, player_id: int, season: Optional[int] = None) -> pd.DataFrame:
        """Load game logs for a player."""

        query = """
            SELECT
                mlb_player_id,
                season,
                game_date,
                level,
                -- Hitting stats
                plate_appearances,
                at_bats,
                hits,
                doubles,
                triples,
                home_runs,
                rbi,
                walks,
                intentional_walks,
                strikeouts,
                stolen_bases,
                caught_stealing,
                hit_by_pitch,
                sacrifice_flies,
                sacrifice_hits,
                ground_into_double_play,
                -- Rate stats
                batting_avg,
                obp,
                slg,
                ops,
                babip,
                -- Pitching stats (for pitchers)
                innings_pitched,
                earned_runs,
                era,
                whip,
                strikeouts_per_9inn,
                walks_per_9inn
            FROM milb_game_logs
            WHERE mlb_player_id = :player_id
        """

        if season:
            query += " AND season = :season"

        query += " ORDER BY game_date"

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"player_id": player_id, "season": season} if season else {"player_id": player_id}
            )

            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        return df

    def calculate_basic_stats(self, game_logs: pd.DataFrame) -> Dict:
        """Calculate basic aggregated statistics."""

        # Remove null games
        hitting_logs = game_logs[game_logs['at_bats'].notna()].copy()

        if hitting_logs.empty:
            return {}

        # Aggregations
        total_pa = hitting_logs['plate_appearances'].sum()
        total_ab = hitting_logs['at_bats'].sum()
        total_hits = hitting_logs['hits'].sum()
        total_hr = hitting_logs['home_runs'].sum()
        total_bb = hitting_logs['walks'].sum()
        total_so = hitting_logs['strikeouts'].sum()
        total_sb = hitting_logs['stolen_bases'].sum()
        total_cs = hitting_logs['caught_stealing'].sum()

        # Calculate rates
        features = {
            'games_played': len(hitting_logs),
            'plate_appearances': total_pa,
            'batting_avg': total_hits / total_ab if total_ab > 0 else 0,
            'obp': hitting_logs['obp'].mean(),
            'slg': hitting_logs['slg'].mean(),
            'ops': hitting_logs['ops'].mean(),
            'iso_power': hitting_logs['slg'].mean() - (total_hits / total_ab if total_ab > 0 else 0),
            'walk_rate': total_bb / total_pa if total_pa > 0 else 0,
            'strikeout_rate': total_so / total_pa if total_pa > 0 else 0,
            'hr_rate': total_hr / total_ab if total_ab > 0 else 0,
            'sb_success_rate': total_sb / (total_sb + total_cs) if (total_sb + total_cs) > 0 else 0,
            'babip': hitting_logs['babip'].mean()
        }

        return features

    def calculate_level_adjusted_stats(self, game_logs: pd.DataFrame) -> Dict:
        """Calculate statistics adjusted for level of competition."""

        features = {}

        # Group by level
        for level, level_df in game_logs.groupby('level'):
            weight = self.level_weights.get(level, 0.5)

            if level_df['at_bats'].notna().any():
                level_ops = level_df['ops'].mean()
                features[f'{level.lower()}_games'] = len(level_df)
                features[f'{level.lower()}_ops'] = level_ops
                features[f'{level.lower()}_weighted_ops'] = level_ops * weight

        # Calculate weighted average OPS across all levels
        total_weight = 0
        weighted_sum = 0

        for level in self.level_weights:
            level_key = f'{level.lower()}_games'
            if level_key in features and features[level_key] > 0:
                games = features[level_key]
                weighted_ops = features.get(f'{level.lower()}_weighted_ops', 0)
                weighted_sum += weighted_ops * games
                total_weight += games * self.level_weights[level]

        features['level_adjusted_ops'] = weighted_sum / total_weight if total_weight > 0 else 0

        # Calculate highest level reached
        levels_played = [level for level in game_logs['level'].unique() if level]
        features['highest_level'] = self._get_highest_level(levels_played)

        return features

    def calculate_trajectory_features(self, game_logs: pd.DataFrame) -> Dict:
        """Calculate player development trajectory features."""

        features = {}

        # Group by season
        seasons = game_logs.groupby('season').agg({
            'ops': 'mean',
            'batting_avg': 'mean',
            'strikeout_rate': 'mean',
            'plate_appearances': 'sum'
        }).reset_index()

        if len(seasons) >= 2:
            # Year-over-year improvement
            latest_season = seasons.iloc[-1]
            previous_season = seasons.iloc[-2]

            features['ops_growth'] = (
                (latest_season['ops'] - previous_season['ops']) / previous_season['ops']
                if previous_season['ops'] > 0 else 0
            )

            features['k_rate_improvement'] = (
                previous_season['strikeout_rate'] - latest_season['strikeout_rate']
            )

            # Trend over all seasons (linear regression slope)
            if len(seasons) >= 3:
                from scipy import stats
                x = np.arange(len(seasons))
                slope, _, r_value, _, _ = stats.linregress(x, seasons['ops'].values)
                features['ops_trend'] = slope
                features['consistency'] = r_value ** 2  # R-squared as consistency metric

        # Monthly performance variance (consistency within season)
        game_logs['month'] = pd.to_datetime(game_logs['game_date']).dt.month
        monthly_ops = game_logs.groupby('month')['ops'].mean()
        features['monthly_ops_std'] = monthly_ops.std() if len(monthly_ops) > 1 else 0

        # Hot streak analysis
        game_logs['rolling_ops'] = game_logs['ops'].rolling(window=10, min_periods=5).mean()
        features['peak_10_game_ops'] = game_logs['rolling_ops'].max()
        features['valley_10_game_ops'] = game_logs['rolling_ops'].min()

        return features

    def calculate_discipline_features(self, game_logs: pd.DataFrame) -> Dict:
        """Calculate plate discipline features."""

        hitting_logs = game_logs[game_logs['plate_appearances'].notna()]

        if hitting_logs.empty:
            return {}

        total_pa = hitting_logs['plate_appearances'].sum()
        total_bb = hitting_logs['walks'].sum()
        total_so = hitting_logs['strikeouts'].sum()
        total_hbp = hitting_logs['hit_by_pitch'].sum()

        features = {
            'bb_rate': total_bb / total_pa if total_pa > 0 else 0,
            'k_rate': total_so / total_pa if total_pa > 0 else 0,
            'bb_k_ratio': total_bb / total_so if total_so > 0 else 0,
            'contact_rate': 1 - (total_so / total_pa) if total_pa > 0 else 0,
            'free_pass_rate': (total_bb + total_hbp) / total_pa if total_pa > 0 else 0
        }

        # Z-scores for discipline (how many std devs from league average)
        # These would need league averages from database
        features['bb_rate_plus'] = features['bb_rate'] / 0.08 * 100  # Assume 8% league average
        features['k_rate_plus'] = 0.22 / features['k_rate'] * 100 if features['k_rate'] > 0 else 0  # 22% league avg

        return features

    def calculate_power_features(self, game_logs: pd.DataFrame) -> Dict:
        """Calculate power-related features."""

        hitting_logs = game_logs[game_logs['at_bats'].notna()]

        if hitting_logs.empty:
            return {}

        total_ab = hitting_logs['at_bats'].sum()
        total_hits = hitting_logs['hits'].sum()
        total_2b = hitting_logs['doubles'].sum()
        total_3b = hitting_logs['triples'].sum()
        total_hr = hitting_logs['home_runs'].sum()

        # Calculate total bases
        singles = total_hits - total_2b - total_3b - total_hr
        total_bases = singles + (2 * total_2b) + (3 * total_3b) + (4 * total_hr)

        features = {
            'isolated_power': (total_bases - total_hits) / total_ab if total_ab > 0 else 0,
            'hr_per_ab': total_hr / total_ab if total_ab > 0 else 0,
            'xbh_rate': (total_2b + total_3b + total_hr) / total_hits if total_hits > 0 else 0,
            'slugging_pct': total_bases / total_ab if total_ab > 0 else 0,
            'hr_per_game': total_hr / len(hitting_logs) if len(hitting_logs) > 0 else 0
        }

        # Power trajectory
        seasons = hitting_logs.groupby('season')['home_runs'].sum()
        if len(seasons) >= 2:
            features['hr_growth_rate'] = (
                (seasons.iloc[-1] - seasons.iloc[-2]) / seasons.iloc[-2]
                if seasons.iloc[-2] > 0 else 0
            )

        return features

    async def calculate_age_relative_features(self, game_logs: pd.DataFrame) -> Dict:
        """Calculate age-relative performance features."""

        features = {}

        # Estimate age (would need birth date in real implementation)
        current_year = datetime.now().year
        seasons_played = game_logs['season'].nunique()
        latest_season = game_logs['season'].max()

        # Rough age estimate
        estimated_current_age = 18 + seasons_played  # Assume started at 18
        features['estimated_age'] = estimated_current_age

        # Age for level (comparing to typical age at each level)
        typical_ages = {
            'MLB': 27,
            'AAA': 24,
            'AA': 22,
            'A+': 21,
            'A': 20,
            'Rookie+': 19,
            'Rookie': 18
        }

        highest_level = self._get_highest_level(game_logs['level'].unique())
        typical_age = typical_ages.get(highest_level, 22)
        features['age_relative_to_level'] = estimated_current_age - typical_age
        features['young_for_level'] = 1 if features['age_relative_to_level'] < -1 else 0

        return features

    def _get_highest_level(self, levels: List[str]) -> str:
        """Get the highest level played."""

        level_order = ['MLB', 'AAA', 'AA', 'A+', 'A', 'Rookie+', 'Rookie', 'Winter']

        for level in level_order:
            if level in levels:
                return level

        return 'Unknown'

    async def create_training_dataset(self, player_ids: List[int]) -> pd.DataFrame:
        """Create feature dataset for multiple players."""

        all_features = []

        for i, player_id in enumerate(player_ids):
            if i % 100 == 0:
                logger.info(f"Processing player {i}/{len(player_ids)}")

            try:
                features = await self.create_player_features(player_id)
                if features:
                    all_features.append(features)
            except Exception as e:
                logger.error(f"Error processing player {player_id}: {str(e)}")
                continue

        df = pd.DataFrame(all_features)
        logger.info(f"Created feature dataset with {len(df)} players and {len(df.columns)} features")

        return df


async def main():
    """Test feature engineering pipeline."""

    engineer = FeatureEngineer()

    # Get sample of players
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT DISTINCT mlb_player_id
            FROM milb_game_logs
            WHERE season = 2024
            AND plate_appearances > 100
            ORDER BY RANDOM()
            LIMIT 10
        """))

        player_ids = [row[0] for row in result.fetchall()]

    # Create features
    logger.info(f"Creating features for {len(player_ids)} players...")
    df = await engineer.create_training_dataset(player_ids)

    # Save to CSV
    output_file = "ml_features_sample.csv"
    df.to_csv(output_file, index=False)
    logger.info(f"Saved features to {output_file}")

    # Display sample
    print("\nSample Features:")
    print(df[['player_id', 'batting_avg', 'ops', 'level_adjusted_ops', 'highest_level']].head())
    print(f"\nTotal features: {len(df.columns)}")


if __name__ == "__main__":
    asyncio.run(main())