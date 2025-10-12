#!/usr/bin/env python3
"""
Player Similarity Engine

Finds the 5 most similar MLB players for each prospect based on:
- Statistical performance
- Age-relative development
- Tool grades (when available)
- Development trajectory
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import euclidean
import asyncio
from sqlalchemy import text
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PlayerSimilarityEngine:
    """Find similar players based on multiple factors."""

    def __init__(self, n_comps: int = 5):
        self.n_comps = n_comps
        self.scaler = StandardScaler()
        self.mlb_player_database = None
        self.feature_weights = {
            # Performance features (50%)
            'ops': 0.08,
            'woba': 0.08,
            'iso_power': 0.06,
            'bb_rate': 0.05,
            'k_rate': 0.05,
            'sb_rate': 0.03,
            'avg': 0.05,
            'obp': 0.05,
            'slg': 0.05,

            # Development features (30%)
            'age_relative': 0.10,
            'level_progression': 0.10,
            'improvement_rate': 0.10,

            # Tool grades if available (20%)
            'hit_tool': 0.04,
            'power_tool': 0.04,
            'speed_tool': 0.04,
            'field_tool': 0.04,
            'arm_tool': 0.04
        }

    async def build_mlb_database(self, min_games: int = 100) -> pd.DataFrame:
        """Build database of MLB players for comparison."""

        query = """
            WITH mlb_stats AS (
                SELECT
                    mlb_player_id,
                    COUNT(*) as games,
                    SUM(plate_appearances) as pa,
                    SUM(at_bats) as ab,
                    SUM(hits) as h,
                    SUM(doubles) as d,
                    SUM(triples) as t,
                    SUM(home_runs) as hr,
                    SUM(walks) as bb,
                    SUM(strikeouts) as so,
                    SUM(stolen_bases) as sb,
                    SUM(caught_stealing) as cs,
                    AVG(batting_avg) as avg,
                    AVG(obp) as obp,
                    AVG(slg) as slg,
                    AVG(ops) as ops
                FROM mlb_game_logs
                WHERE plate_appearances > 0
                GROUP BY mlb_player_id
                HAVING COUNT(*) >= :min_games
            )
            SELECT
                m.*,
                -- Calculate additional metrics
                (m.h - m.d - m.t - m.hr)::float / NULLIF(m.ab, 0) as single_rate,
                m.bb::float / NULLIF(m.pa, 0) as bb_rate,
                m.so::float / NULLIF(m.pa, 0) as k_rate,
                m.sb::float / NULLIF(m.pa, 0) as sb_rate,
                (m.slg - m.avg) as iso_power,
                m.hr::float / NULLIF(m.ab, 0) as hr_rate
            FROM mlb_stats m
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"min_games": min_games}
            )

            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Built MLB database with {len(df)} players")
        self.mlb_player_database = df

        return df

    async def get_prospect_features(self, player_id: int) -> Dict:
        """Get feature vector for a prospect."""

        query = """
            WITH player_stats AS (
                SELECT
                    mlb_player_id,
                    level,
                    season,
                    COUNT(*) as games,
                    SUM(plate_appearances) as pa,
                    SUM(at_bats) as ab,
                    SUM(hits) as h,
                    SUM(doubles) as d,
                    SUM(triples) as t,
                    SUM(home_runs) as hr,
                    SUM(walks) as bb,
                    SUM(strikeouts) as so,
                    SUM(stolen_bases) as sb,
                    AVG(batting_avg) as avg,
                    AVG(obp) as obp,
                    AVG(slg) as slg,
                    AVG(ops) as ops
                FROM milb_game_logs
                WHERE mlb_player_id = :player_id
                AND plate_appearances > 0
                GROUP BY mlb_player_id, level, season
            )
            SELECT
                mlb_player_id,
                AVG(games) as avg_games,
                SUM(pa) as total_pa,
                AVG(avg) as batting_avg,
                AVG(obp) as on_base_pct,
                AVG(slg) as slugging_pct,
                AVG(ops) as ops_plus,
                SUM(bb)::float / NULLIF(SUM(pa), 0) as bb_rate,
                SUM(so)::float / NULLIF(SUM(pa), 0) as k_rate,
                SUM(sb)::float / NULLIF(SUM(pa), 0) as sb_rate,
                SUM(hr)::float / NULLIF(SUM(ab), 0) as hr_rate,
                (AVG(slg) - AVG(avg)) as iso_power,
                COUNT(DISTINCT season) as seasons_played,
                MIN(season) as first_season,
                MAX(season) as last_season
            FROM player_stats
            GROUP BY mlb_player_id
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"player_id": player_id}
            )

            row = result.fetchone()

        if not row:
            return {}

        # Build feature dictionary
        features = {
            'player_id': row.mlb_player_id,
            'avg': row.batting_avg or 0,
            'obp': row.on_base_pct or 0,
            'slg': row.slugging_pct or 0,
            'ops': row.ops_plus or 0,
            'bb_rate': row.bb_rate or 0,
            'k_rate': row.k_rate or 0,
            'sb_rate': row.sb_rate or 0,
            'hr_rate': row.hr_rate or 0,
            'iso_power': row.iso_power or 0,
            'seasons': row.seasons_played
        }

        # Add age-relative features (would need birth date)
        features['age_relative'] = self._estimate_age_relative(
            row.first_season,
            row.last_season
        )

        return features

    def find_similar_players(
        self,
        prospect_features: Dict,
        mlb_database: Optional[pd.DataFrame] = None
    ) -> List[Dict]:
        """Find the N most similar MLB players."""

        if mlb_database is None:
            mlb_database = self.mlb_player_database

        if mlb_database is None or len(mlb_database) == 0:
            logger.error("No MLB database available for comparison")
            return []

        # Prepare feature vectors
        feature_cols = [
            'avg', 'obp', 'slg', 'ops',
            'bb_rate', 'k_rate', 'sb_rate',
            'hr_rate', 'iso_power'
        ]

        # Create prospect vector
        prospect_vector = np.array([
            prospect_features.get(col, 0) for col in feature_cols
        ]).reshape(1, -1)

        # Create MLB matrix
        mlb_matrix = mlb_database[feature_cols].values

        # Standardize features
        all_features = np.vstack([prospect_vector, mlb_matrix])
        all_scaled = self.scaler.fit_transform(all_features)

        prospect_scaled = all_scaled[0].reshape(1, -1)
        mlb_scaled = all_scaled[1:]

        # Calculate similarities using multiple methods
        similarities = self._calculate_composite_similarity(
            prospect_scaled,
            mlb_scaled,
            prospect_features,
            mlb_database
        )

        # Get top N similar players
        top_indices = similarities.argsort()[-self.n_comps:][::-1]

        # Build comparison results
        comparisons = []
        for idx in top_indices:
            mlb_player = mlb_database.iloc[idx]

            comparison = {
                'player_id': int(mlb_player['mlb_player_id']),
                'similarity_score': round(similarities[idx], 3),
                'key_similarities': self._identify_similar_traits(
                    prospect_features,
                    mlb_player
                ),
                'mlb_stats': {
                    'games': int(mlb_player.get('games', 0)),
                    'avg': round(mlb_player.get('avg', 0), 3),
                    'obp': round(mlb_player.get('obp', 0), 3),
                    'slg': round(mlb_player.get('slg', 0), 3),
                    'ops': round(mlb_player.get('ops', 0), 3),
                    'hr': int(mlb_player.get('hr', 0))
                }
            }

            comparisons.append(comparison)

        return comparisons[:self.n_comps]

    def _calculate_composite_similarity(
        self,
        prospect_vector: np.ndarray,
        mlb_matrix: np.ndarray,
        prospect_features: Dict,
        mlb_database: pd.DataFrame
    ) -> np.ndarray:
        """Calculate composite similarity using multiple methods."""

        # Cosine similarity (direction of stats profile)
        cosine_sim = cosine_similarity(prospect_vector, mlb_matrix)[0]

        # Euclidean distance (magnitude of difference)
        euclidean_distances = np.array([
            euclidean(prospect_vector[0], mlb_row)
            for mlb_row in mlb_matrix
        ])
        # Convert distance to similarity (0-1 scale)
        euclidean_sim = 1 / (1 + euclidean_distances)

        # Player type matching (power vs speed vs contact)
        type_sim = self._calculate_player_type_similarity(
            prospect_features,
            mlb_database
        )

        # Weighted combination
        composite = (
            0.5 * cosine_sim +
            0.3 * euclidean_sim +
            0.2 * type_sim
        )

        return composite

    def _calculate_player_type_similarity(
        self,
        prospect: Dict,
        mlb_database: pd.DataFrame
    ) -> np.ndarray:
        """Calculate similarity based on player type/profile."""

        similarities = []

        # Define player type based on key metrics
        prospect_type = self._get_player_type(prospect)

        for _, mlb_player in mlb_database.iterrows():
            mlb_type = self._get_player_type(mlb_player)

            # Type similarity
            if prospect_type == mlb_type:
                type_score = 1.0
            elif self._are_types_similar(prospect_type, mlb_type):
                type_score = 0.7
            else:
                type_score = 0.3

            similarities.append(type_score)

        return np.array(similarities)

    def _get_player_type(self, player_stats: Dict) -> str:
        """Categorize player type based on stats profile."""

        hr_rate = player_stats.get('hr_rate', 0)
        sb_rate = player_stats.get('sb_rate', 0)
        k_rate = player_stats.get('k_rate', 0)
        bb_rate = player_stats.get('bb_rate', 0)
        avg = player_stats.get('avg', 0)

        # Power hitter
        if hr_rate > 0.04:
            return 'power'

        # Speedster
        elif sb_rate > 0.05:
            return 'speed'

        # Contact hitter
        elif avg > 0.280 and k_rate < 0.18:
            return 'contact'

        # Patient hitter
        elif bb_rate > 0.10:
            return 'patient'

        # Balanced
        else:
            return 'balanced'

    def _are_types_similar(self, type1: str, type2: str) -> bool:
        """Check if two player types are similar."""

        similar_types = {
            'power': ['balanced'],
            'speed': ['contact'],
            'contact': ['speed', 'balanced'],
            'patient': ['contact', 'balanced'],
            'balanced': ['power', 'contact', 'patient']
        }

        return type2 in similar_types.get(type1, [])

    def _identify_similar_traits(self, prospect: Dict, mlb_player: pd.Series) -> List[str]:
        """Identify key similar traits between players."""

        traits = []

        # Compare key metrics
        if abs(prospect.get('ops', 0) - mlb_player.get('ops', 0)) < 0.05:
            traits.append('ops')

        if abs(prospect.get('bb_rate', 0) - mlb_player.get('bb_rate', 0)) < 0.02:
            traits.append('plate_discipline')

        if abs(prospect.get('k_rate', 0) - mlb_player.get('k_rate', 0)) < 0.03:
            traits.append('contact')

        if abs(prospect.get('iso_power', 0) - mlb_player.get('iso_power', 0)) < 0.03:
            traits.append('power')

        if abs(prospect.get('sb_rate', 0) - mlb_player.get('sb_rate', 0)) < 0.02:
            traits.append('speed')

        # Player type
        if self._get_player_type(prospect) == self._get_player_type(mlb_player):
            traits.append('profile')

        return traits[:3]  # Return top 3 traits

    def _estimate_age_relative(self, first_season: int, last_season: int) -> float:
        """Estimate age-relative performance."""

        # Rough estimate: assume 18 years old in first pro season
        seasons_played = last_season - first_season + 1
        estimated_age = 18 + seasons_played

        # Compare to typical age (22 for prospects)
        return 22 / estimated_age if estimated_age > 0 else 1.0


async def demo_similarity():
    """Demo the player similarity engine."""

    engine = PlayerSimilarityEngine(n_comps=5)

    # Build MLB database
    logger.info("Building MLB player database...")
    await engine.build_mlb_database(min_games=50)

    # Get a sample prospect
    async with engine.engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT mlb_player_id
            FROM milb_game_logs
            WHERE season = 2024
            AND level = 'AAA'
            AND plate_appearances > 100
            ORDER BY ops DESC
            LIMIT 1
        """))

        prospect_id = result.fetchone()[0]

    # Get prospect features
    logger.info(f"Getting features for prospect {prospect_id}...")
    prospect_features = await engine.get_prospect_features(prospect_id)

    # Find similar players
    logger.info("Finding similar MLB players...")
    comparisons = engine.find_similar_players(prospect_features)

    # Display results
    print("\n" + "=" * 80)
    print(f"TOP 5 MLB COMPARISONS FOR PLAYER {prospect_id}")
    print("=" * 80)

    for i, comp in enumerate(comparisons, 1):
        print(f"\n{i}. Player ID: {comp['player_id']}")
        print(f"   Similarity Score: {comp['similarity_score']}")
        print(f"   Similar Traits: {', '.join(comp['key_similarities'])}")
        print(f"   MLB Stats: {comp['mlb_stats']['games']} games, "
              f"{comp['mlb_stats']['avg']:.3f}/{comp['mlb_stats']['obp']:.3f}/"
              f"{comp['mlb_stats']['slg']:.3f}, {comp['mlb_stats']['hr']} HR")


if __name__ == "__main__":
    asyncio.run(demo_similarity())