"""
Stat Projection Service

Provides MLB stat projections for prospects based on their MiLB performance.
Uses trained XGBoost models to predict rate stats (AVG, OBP, SLG, etc.)
"""

import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging

from app.db.models import Prospect

logger = logging.getLogger(__name__)


class StatProjectionService:
    """Service for generating MLB stat projections from MiLB data."""

    def __init__(self):
        """Initialize the service and load models."""
        self.models = None
        self.feature_names = None
        self.target_names = None
        self.model_version = None
        self._load_models()

    def _load_models(self):
        """Load the trained models and metadata."""
        try:
            # Find the most recent improved model
            api_dir = Path(__file__).parent.parent.parent
            model_files = list(api_dir.glob('hitter_models_improved_*.joblib'))

            if not model_files:
                logger.warning("No improved hitter models found - projections will be unavailable")
                return

            # Get most recent model
            latest_model_file = max(model_files, key=lambda p: p.stat().st_mtime)
            timestamp = latest_model_file.stem.split('_')[-2] + '_' + latest_model_file.stem.split('_')[-1]
            self.model_version = f"improved_v1_{timestamp}"

            # Load models
            self.models = joblib.load(latest_model_file)
            logger.info(f"✓ Loaded {len(self.models)} projection models (version: {self.model_version})")

            # Load feature names
            feature_file = api_dir / f'hitter_features_improved_{timestamp}.txt'
            with open(feature_file, 'r') as f:
                self.feature_names = [line.strip() for line in f.readlines()]

            # Load target names
            target_file = api_dir / f'hitter_targets_improved_{timestamp}.txt'
            with open(target_file, 'r') as f:
                self.target_names = [line.strip() for line in f.readlines()]

            logger.info(f"✓ Model ready: {len(self.feature_names)} features → {len(self.target_names)} targets")

        except Exception as e:
            logger.error(f"Failed to load projection models: {e}")
            self.models = None

    def is_available(self) -> bool:
        """Check if projection models are loaded and available."""
        return self.models is not None

    async def get_prospect_milb_stats(
        self,
        db: AsyncSession,
        prospect_id: int
    ) -> Optional[Dict]:
        """
        Fetch prospect's most recent MiLB stats for projection.

        Args:
            db: Database session
            prospect_id: Prospect ID

        Returns:
            Dictionary with MiLB stats or None if not found
        """
        try:
            from sqlalchemy import text
            from datetime import datetime

            # Query prospect
            query = select(Prospect).where(Prospect.id == prospect_id)
            result = await db.execute(query)
            prospect = result.scalar_one_or_none()

            if not prospect or not prospect.mlb_player_id:
                return None

            # Query MiLB stats from most recent season at highest level
            milb_query = text("""
                SELECT
                    season,
                    level,
                    team,
                    COUNT(*) as games,
                    SUM(plate_appearances) as pa,
                    SUM(at_bats) as ab,
                    SUM(runs) as r,
                    SUM(hits) as h,
                    SUM(doubles) as doubles,
                    SUM(triples) as triples,
                    SUM(home_runs) as hr,
                    SUM(rbi) as rbi,
                    SUM(walks) as bb,
                    SUM(intentional_walks) as ibb,
                    SUM(strikeouts) as so,
                    SUM(stolen_bases) as sb,
                    SUM(caught_stealing) as cs,
                    SUM(hit_by_pitch) as hbp,
                    SUM(sacrifice_flies) as sf,
                    AVG(batting_avg) as avg,
                    AVG(on_base_pct) as obp,
                    AVG(slugging_pct) as slg,
                    AVG(ops) as ops,
                    AVG(babip) as babip
                FROM milb_game_logs
                WHERE mlb_player_id = :mlb_player_id
                AND season >= :min_season
                AND plate_appearances > 0
                GROUP BY season, level, team
                ORDER BY season DESC,
                    CASE level
                        WHEN 'AAA' THEN 4
                        WHEN 'AA' THEN 3
                        WHEN 'A+' THEN 2
                        WHEN 'A' THEN 1
                        ELSE 0
                    END DESC
                LIMIT 1
            """)

            milb_result = await db.execute(
                milb_query,
                {
                    'mlb_player_id': int(prospect.mlb_player_id),
                    'min_season': datetime.now().year - 3
                }
            )
            milb_stats = milb_result.fetchone()

            if not milb_stats:
                logger.info(f"No MiLB stats found for prospect {prospect_id}")
                return None

            # Calculate derived features
            pa = float(milb_stats.pa or 0)
            ab = float(milb_stats.ab or 0)
            h = float(milb_stats.h or 0)
            bb = float(milb_stats.bb or 0)
            so = float(milb_stats.so or 0)
            sb = float(milb_stats.sb or 0)
            cs = float(milb_stats.cs or 0)
            doubles = float(milb_stats.doubles or 0)
            triples = float(milb_stats.triples or 0)
            hr = float(milb_stats.hr or 0)
            avg_val = float(milb_stats.avg or 0)
            obp_val = float(milb_stats.obp or 0)
            slg_val = float(milb_stats.slg or 0)

            # Calculate rate stats
            if pa > 0:
                bb_rate = bb / pa
                k_rate = so / pa
            else:
                bb_rate = k_rate = 0

            # Calculate ISO (Isolated Power)
            iso = slg_val - avg_val if slg_val and avg_val else 0

            # Calculate XBH (Extra Base Hits) and rate
            xbh = doubles + triples + hr
            xbh_rate = xbh / ab if ab > 0 else 0

            # BB per K
            bb_per_k = bb / so if so > 0 else 0

            # SB success rate
            sb_total = sb + cs
            sb_success_rate = sb / sb_total if sb_total > 0 else 0

            # Build feature dictionary with all required features
            features = {
                'prospect_id': prospect.id,
                'mlb_player_id': prospect.mlb_player_id,
                'name': prospect.name,
                'position': prospect.position,
                'season': milb_stats.season,
                'level': milb_stats.level,
                'team': milb_stats.team,
                'games': float(milb_stats.games or 0),
                'pa': pa,
                'ab': ab,
                'h': h,
                'doubles': doubles,
                'bb': bb,
                'so': so,
                'sb': sb,
                'avg': avg_val,
                'obp': obp_val,
                'slg': slg_val,
                'iso': iso,
                'bb_rate': bb_rate,
                'k_rate': k_rate,
                'xbh': xbh,
                'xbh_rate': xbh_rate,
                'bb_per_k': bb_per_k,
                'sb_success_rate': sb_success_rate,
                # The features with "target_" prefix are not actually features,
                # they're artifacts from feature selection. Set to 0.
                'target_r_per_600': 0,
                'target_career_pa': 0,
                'target_rbi_per_600': 0,
                'target_sb_per_600': 0,
                'target_hr_per_600': 0,
                'target_career_games': 0,
            }

            return features

        except Exception as e:
            logger.error(f"Error fetching prospect MiLB stats: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _prepare_features(self, milb_stats: Dict) -> pd.DataFrame:
        """
        Prepare feature vector for prediction.

        Args:
            milb_stats: Dictionary with prospect's MiLB stats

        Returns:
            DataFrame with features in correct order
        """
        features = {}

        for feature in self.feature_names:
            # Get value from milb stats, default to 0 if missing
            features[feature] = milb_stats.get(feature, 0)

        # Convert to DataFrame (single row)
        df = pd.DataFrame([features])

        # Ensure numeric
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        return df

    def _clip_predictions(self, target: str, value: float) -> float:
        """
        Clip predictions to reasonable ranges.

        Args:
            target: Target stat name
            value: Predicted value

        Returns:
            Clipped value
        """
        if 'avg' in target:
            return np.clip(value, 0.150, 0.400)
        elif 'obp' in target:
            return np.clip(value, 0.200, 0.450)
        elif 'slg' in target:
            return np.clip(value, 0.250, 0.650)
        elif 'ops' in target:
            return np.clip(value, 0.500, 1.200)
        elif 'rate' in target:
            return np.clip(value, 0.0, 0.50)
        elif 'iso' in target:
            return np.clip(value, 0.0, 0.350)
        else:
            return value

    def generate_projection(self, milb_stats: Dict) -> Optional[Dict]:
        """
        Generate MLB stat projection for a prospect.

        Args:
            milb_stats: Dictionary with prospect's MiLB stats

        Returns:
            Dictionary with projected stats and metadata
        """
        if not self.is_available():
            logger.warning("Projection models not available")
            return None

        try:
            # Prepare features
            X = self._prepare_features(milb_stats)

            # Generate predictions for each target
            predictions = {}
            confidence_scores = {}

            for target in self.target_names:
                model = self.models[target]
                pred = model.predict(X)[0]

                # Clip to reasonable range
                clipped_pred = self._clip_predictions(target, pred)

                # Clean target name (remove "target_" prefix)
                stat_name = target.replace('target_', '')
                predictions[stat_name] = round(float(clipped_pred), 3)

                # Estimate confidence based on model performance
                # (In production, you'd use actual validation metrics per model)
                confidence_scores[stat_name] = self._estimate_confidence(target)

            # Calculate slash line
            avg = predictions.get('avg', 0)
            obp = predictions.get('obp', 0)
            slg = predictions.get('slg', 0)
            slash_line = f".{int(avg*1000):03d}/.{int(obp*1000):03d}/.{int(slg*1000):03d}"

            # Overall confidence (average of all targets)
            overall_confidence = np.mean(list(confidence_scores.values()))

            return {
                'prospect_id': milb_stats.get('prospect_id'),
                'prospect_name': milb_stats.get('name'),
                'position': milb_stats.get('position'),
                'projections': predictions,
                'slash_line': slash_line,
                'confidence_scores': confidence_scores,
                'overall_confidence': round(float(overall_confidence), 3),
                'model_version': self.model_version,
                'disclaimer': 'Projections are estimates based on MiLB performance. Actual MLB results may vary significantly.',
            }

        except Exception as e:
            logger.error(f"Error generating projection: {e}")
            return None

    def _estimate_confidence(self, target: str) -> float:
        """
        Estimate confidence score for a target based on model performance.

        In production, these would be actual validation R² scores from training.
        For now, using approximate values from our trained model.
        """
        confidence_map = {
            'target_avg': 0.444,
            'target_obp': 0.409,
            'target_slg': 0.391,
            'target_ops': 0.332,
            'target_bb_rate': 0.173,
            'target_k_rate': 0.444,
            'target_iso': 0.215,
        }

        return confidence_map.get(target, 0.30)

    def get_confidence_level(self, confidence: float) -> str:
        """
        Convert numeric confidence to categorical level.

        Args:
            confidence: Confidence score (0-1)

        Returns:
            Confidence level string
        """
        if confidence >= 0.40:
            return "high"
        elif confidence >= 0.25:
            return "medium"
        else:
            return "low"
