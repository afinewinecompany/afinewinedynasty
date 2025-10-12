#!/usr/bin/env python3
"""
ML Projection API Integration

Provides unified interface for generating player projections using trained models.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import pickle
import asyncio
from datetime import datetime
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db.database import engine
from sqlalchemy import text

# Import ML pipeline modules
from feature_engineering import FeatureEngineer
from calculate_advanced_metrics import AdvancedMetricsCalculator
from age_curve_model import AgeAdjustedProjector
from player_similarity import PlayerSimilarityEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ProjectionAPI:
    """Unified API for player projections."""

    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.metrics_calculator = AdvancedMetricsCalculator()
        self.age_projector = AgeAdjustedProjector()
        self.similarity_engine = PlayerSimilarityEngine(n_comps=5)

        self.wrc_model = None
        self.woba_model = None
        self.mlb_comparison_db = None

    async def initialize(self):
        """Load models and prepare comparison database."""

        # Load trained models
        try:
            with open('wrc_plus_projection_model.pkl', 'rb') as f:
                self.wrc_model = pickle.load(f)
            logger.info("Loaded wRC+ projection model")
        except FileNotFoundError:
            logger.warning("wRC+ model not found - predictions will use fallback")

        try:
            with open('woba_projection_model.pkl', 'rb') as f:
                self.woba_model = pickle.load(f)
            logger.info("Loaded wOBA projection model")
        except FileNotFoundError:
            logger.warning("wOBA model not found - predictions will use fallback")

        # Build MLB comparison database
        self.mlb_comparison_db = await self.similarity_engine.build_mlb_database(min_games=50)
        logger.info(f"Built comparison database with {len(self.mlb_comparison_db)} MLB players")

    async def get_full_projection(self, player_id: int) -> Dict:
        """
        Generate comprehensive projection for a player.

        Returns:
            - Current performance metrics
            - ML-based projections (wRC+, wOBA)
            - Year-by-year career arc projections
            - 5 most similar MLB players
            - Confidence scores
        """

        logger.info(f"Generating projection for player {player_id}")

        # Get current performance
        current_stats = await self._get_current_stats(player_id)

        if not current_stats:
            return {
                'error': f'No data found for player {player_id}',
                'player_id': player_id
            }

        # Get ML projections
        ml_projections = await self._get_ml_projections(player_id, current_stats)

        # Get career arc projections
        career_projections = await self._get_career_projections(
            player_id,
            current_stats,
            ml_projections
        )

        # Get similar players
        similar_players = await self._get_similar_players(player_id, current_stats)

        # Get player info
        player_info = await self._get_player_info(player_id)

        # Combine everything
        projection = {
            'player_id': player_id,
            'player_info': player_info,
            'current_performance': current_stats,
            'ml_projections': ml_projections,
            'career_arc': career_projections,
            'similar_players': similar_players,
            'generated_at': datetime.now().isoformat(),
            'confidence': self._calculate_overall_confidence(
                current_stats,
                ml_projections
            )
        }

        return projection

    async def _get_current_stats(self, player_id: int) -> Dict:
        """Get current season statistics."""

        query = """
            WITH current_stats AS (
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
                    AVG(batting_avg) as avg,
                    AVG(obp) as obp,
                    AVG(slg) as slg,
                    AVG(ops) as ops,
                    MAX(level) as highest_level
                FROM milb_game_logs
                WHERE mlb_player_id = :player_id
                AND season = 2024
                AND plate_appearances > 0
                GROUP BY mlb_player_id
            )
            SELECT
                *,
                (slg - avg) as iso_power,
                bb::float / NULLIF(pa, 0) as bb_rate,
                so::float / NULLIF(pa, 0) as k_rate,
                hr::float / NULLIF(ab, 0) as hr_rate,
                sb::float / NULLIF(pa, 0) as sb_rate
            FROM current_stats
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"player_id": player_id}
            )
            row = result.fetchone()

        if not row:
            return {}

        # Calculate advanced metrics
        stats = dict(row._mapping)

        # Calculate wOBA
        woba = self.metrics_calculator.calculate_woba({
            'plate_appearances': stats['pa'],
            'at_bats': stats['ab'],
            'hits': stats['h'],
            'doubles': stats['d'],
            'triples': stats['t'],
            'home_runs': stats['hr'],
            'walks': stats['bb'],
            'hit_by_pitch': 0,  # Would need to add to query
            'sacrifice_flies': 0
        })

        stats['woba'] = woba

        # Get league average for wRC+ calculation
        level = stats['highest_level']
        league_avg = await self.metrics_calculator.calculate_league_averages(level)
        stats['wrc_plus'] = self.metrics_calculator.calculate_wrc_plus(
            woba,
            league_avg['woba']
        )

        return stats

    async def _get_ml_projections(self, player_id: int, current_stats: Dict) -> Dict:
        """Get ML model projections."""

        projections = {}

        # Get features
        features = await self.feature_engineer.create_player_features(player_id)

        if not features:
            # Fallback to simple projections
            return self._get_fallback_projections(current_stats)

        # Prepare feature vector
        feature_df = pd.DataFrame([features])

        # wRC+ projection
        if self.wrc_model:
            try:
                wrc_pred = self._predict_with_model(
                    self.wrc_model,
                    feature_df
                )
                projections['wrc_plus'] = round(wrc_pred)
                projections['wrc_plus_confidence'] = self.wrc_model.get(
                    'test_performance', {}
                ).get('r2', 0.7)
            except Exception as e:
                logger.error(f"Error predicting wRC+: {str(e)}")
                projections['wrc_plus'] = round(current_stats.get('wrc_plus', 100))

        # wOBA projection
        if self.woba_model:
            try:
                woba_pred = self._predict_with_model(
                    self.woba_model,
                    feature_df
                )
                projections['woba'] = round(woba_pred, 3)
                projections['woba_confidence'] = self.woba_model.get(
                    'test_performance', {}
                ).get('r2', 0.7)
            except Exception as e:
                logger.error(f"Error predicting wOBA: {str(e)}")
                projections['woba'] = round(current_stats.get('woba', .320), 3)

        # Peak projections
        age = features.get('estimated_age', 22)
        peak_age = 27 if age < 27 else age + 1

        projections['peak_wrc_plus'] = round(
            projections.get('wrc_plus', 100) * (1.0 + max(0, (peak_age - age) * 0.03))
        )
        projections['peak_age'] = peak_age

        return projections

    def _predict_with_model(self, model_package: Dict, feature_df: pd.DataFrame) -> float:
        """Make prediction using loaded model."""

        # Get expected features
        feature_cols = model_package['feature_cols']

        # Prepare features
        X = pd.get_dummies(
            feature_df[feature_cols],
            columns=['highest_level']  # Handle categorical
        ).fillna(0)

        # Ensure all expected columns present
        ensemble = model_package['ensemble']
        expected_cols = ensemble['models'][0][1].feature_names_in_

        for col in expected_cols:
            if col not in X.columns:
                X[col] = 0
        X = X[expected_cols]

        # Make ensemble prediction
        predictions = np.zeros(len(X))

        for (name, model), weight in zip(ensemble['models'], ensemble['weights']):
            if name == 'neural_net':
                pred = model.predict(ensemble['scaler'].transform(X))
            else:
                pred = model.predict(X)
            predictions += weight * pred

        return predictions[0]

    def _get_fallback_projections(self, current_stats: Dict) -> Dict:
        """Simple fallback projections when ML models unavailable."""

        # Simple age adjustment
        age_factor = 1.1  # Assume 10% improvement

        return {
            'wrc_plus': round(current_stats.get('wrc_plus', 100) * age_factor),
            'woba': round(current_stats.get('woba', .320) * age_factor, 3),
            'peak_wrc_plus': round(current_stats.get('wrc_plus', 100) * 1.2),
            'peak_age': 27,
            'method': 'fallback'
        }

    async def _get_career_projections(
        self,
        player_id: int,
        current_stats: Dict,
        ml_projections: Dict
    ) -> List[Dict]:
        """Generate year-by-year career projections."""

        # Get player age
        age_query = """
            SELECT
                MIN(season) as first_season,
                MAX(season) as last_season,
                COUNT(DISTINCT season) as seasons
            FROM milb_game_logs
            WHERE mlb_player_id = :player_id
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(age_query),
                {"player_id": player_id}
            )
            age_data = result.fetchone()

        # Estimate current age
        if age_data:
            seasons_played = age_data.seasons
            current_age = 18 + seasons_played
        else:
            current_age = 22

        # Prepare stats for projection
        projection_stats = {
            'wrc_plus': ml_projections.get('wrc_plus', 100),
            'woba': ml_projections.get('woba', .320),
            'batting_avg': current_stats.get('avg', .250),
            'obp': current_stats.get('obp', .320),
            'slg': current_stats.get('slg', .400),
            'hr_rate': current_stats.get('hr_rate', 0.03),
            'sb_rate': current_stats.get('sb_rate', 0.02),
            'walk_rate': current_stats.get('bb_rate', 0.08),
            'strikeout_rate': current_stats.get('k_rate', 0.22),
            'war': ml_projections.get('wrc_plus', 100) / 20
        }

        # Generate projections
        projections = self.age_projector.project_career_arc(
            current_stats=projection_stats,
            current_age=current_age,
            position='SS',  # Would need position from database
            years_ahead=12
        )

        return projections

    async def _get_similar_players(self, player_id: int, current_stats: Dict) -> List[Dict]:
        """Find 5 most similar MLB players."""

        # Get prospect features
        prospect_features = await self.similarity_engine.get_prospect_features(player_id)

        if not prospect_features:
            # Use current stats as features
            prospect_features = {
                'player_id': player_id,
                'avg': current_stats.get('avg', .250),
                'obp': current_stats.get('obp', .320),
                'slg': current_stats.get('slg', .400),
                'ops': current_stats.get('ops', .720),
                'bb_rate': current_stats.get('bb_rate', 0.08),
                'k_rate': current_stats.get('k_rate', 0.22),
                'sb_rate': current_stats.get('sb_rate', 0.02),
                'hr_rate': current_stats.get('hr_rate', 0.03),
                'iso_power': current_stats.get('iso_power', 0.15)
            }

        # Find similar players
        comparisons = self.similarity_engine.find_similar_players(
            prospect_features,
            self.mlb_comparison_db
        )

        # Add player names (would need name lookup in real implementation)
        for comp in comparisons:
            comp['player_name'] = f"Player {comp['player_id']}"

        return comparisons

    async def _get_player_info(self, player_id: int) -> Dict:
        """Get basic player information."""

        query = """
            SELECT
                mlb_player_id,
                MIN(season) as first_season,
                MAX(season) as last_season,
                MAX(level) as current_level,
                COUNT(DISTINCT season) as seasons_played,
                SUM(games) as total_games,
                SUM(plate_appearances) as total_pa
            FROM (
                SELECT
                    mlb_player_id,
                    season,
                    level,
                    COUNT(*) as games,
                    SUM(plate_appearances) as plate_appearances
                FROM milb_game_logs
                WHERE mlb_player_id = :player_id
                GROUP BY mlb_player_id, season, level
            ) t
            GROUP BY mlb_player_id
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"player_id": player_id}
            )
            row = result.fetchone()

        if row:
            return dict(row._mapping)
        return {'mlb_player_id': player_id}

    def _calculate_overall_confidence(
        self,
        current_stats: Dict,
        ml_projections: Dict
    ) -> float:
        """Calculate overall confidence in projections."""

        confidence = 0.5

        # Games played
        games = current_stats.get('games', 0)
        if games > 100:
            confidence += 0.15
        elif games > 50:
            confidence += 0.10

        # Level
        level = current_stats.get('highest_level', 'A')
        if level in ['AAA', 'MLB']:
            confidence += 0.15
        elif level == 'AA':
            confidence += 0.10

        # Model confidence
        model_conf = ml_projections.get('wrc_plus_confidence', 0.7)
        confidence += model_conf * 0.2

        return min(0.95, confidence)

    async def batch_project_players(
        self,
        player_ids: List[int],
        simplified: bool = True
    ) -> List[Dict]:
        """Generate projections for multiple players."""

        projections = []

        for i, player_id in enumerate(player_ids):
            if i % 10 == 0:
                logger.info(f"Processing player {i}/{len(player_ids)}")

            try:
                if simplified:
                    # Get just key metrics
                    proj = await self.get_simplified_projection(player_id)
                else:
                    proj = await self.get_full_projection(player_id)

                projections.append(proj)

            except Exception as e:
                logger.error(f"Error projecting player {player_id}: {str(e)}")
                continue

        return projections

    async def get_simplified_projection(self, player_id: int) -> Dict:
        """Get simplified projection with just key metrics."""

        current = await self._get_current_stats(player_id)
        ml_proj = await self._get_ml_projections(player_id, current)

        return {
            'player_id': player_id,
            'current_wrc_plus': current.get('wrc_plus', 0),
            'projected_wrc_plus': ml_proj.get('wrc_plus', 100),
            'peak_wrc_plus': ml_proj.get('peak_wrc_plus', 100),
            'projected_woba': ml_proj.get('woba', .320),
            'confidence': ml_proj.get('wrc_plus_confidence', 0.7)
        }


async def demo_api():
    """Demo the projection API."""

    api = ProjectionAPI()
    await api.initialize()

    # Get top AAA prospect
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

    # Generate full projection
    logger.info(f"Generating projection for player {player_id}...")
    projection = await api.get_full_projection(player_id)

    # Display results
    print("\n" + "="*80)
    print(f"COMPLETE PROJECTION FOR PLAYER {player_id}")
    print("="*80)

    print("\nCURRENT PERFORMANCE (2024):")
    current = projection['current_performance']
    print(f"  Games: {current.get('games', 0)}")
    print(f"  AVG/OBP/SLG: {current.get('avg', 0):.3f}/{current.get('obp', 0):.3f}/{current.get('slg', 0):.3f}")
    print(f"  wRC+: {current.get('wrc_plus', 0)}")
    print(f"  wOBA: {current.get('woba', 0):.3f}")

    print("\nML PROJECTIONS:")
    ml = projection['ml_projections']
    print(f"  Projected wRC+: {ml.get('wrc_plus', 'N/A')}")
    print(f"  Projected wOBA: {ml.get('woba', 'N/A')}")
    print(f"  Peak wRC+: {ml.get('peak_wrc_plus', 'N/A')} (age {ml.get('peak_age', 'N/A')})")

    print("\nCAREER ARC (Next 5 Years):")
    for proj in projection['career_arc'][:5]:
        print(f"  Age {proj['age']} ({proj['season']}): wRC+ {proj['projected_wrc_plus']} [{proj['confidence_band']['lower']}-{proj['confidence_band']['upper']}]")

    print("\nSIMILAR MLB PLAYERS:")
    for i, comp in enumerate(projection['similar_players'], 1):
        print(f"  {i}. Player {comp['player_id']} (Similarity: {comp['similarity_score']:.3f})")
        print(f"     Similar traits: {', '.join(comp['key_similarities'])}")
        stats = comp['mlb_stats']
        print(f"     MLB: {stats['avg']:.3f}/{stats['obp']:.3f}/{stats['slg']:.3f}, {stats['hr']} HR")

    print(f"\nOverall Confidence: {projection['confidence']:.1%}")


if __name__ == "__main__":
    asyncio.run(demo_api())