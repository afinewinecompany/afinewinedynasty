"""Model Serving Infrastructure

Handles ML model loading, caching, versioning, and serving with fallback
mechanisms and hot-swapping capabilities using MLflow model registry.
"""

import asyncio
import logging
import pickle
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json

import numpy as np
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
import joblib

from ..core.cache_manager import CacheManager
from ..core.config import settings
from ..schemas.ml_predictions import ModelInfo, PredictionExplanation, FeatureImportance

logger = logging.getLogger(__name__)


class ModelLoadError(Exception):
    """Exception raised when model loading fails."""
    pass


class ModelServer:
    """
    ML Model serving infrastructure with caching, versioning, and fallback support.

    Features:
    - MLflow model registry integration
    - Model caching with Redis
    - Hot-swapping without service restart
    - Fallback mechanisms for model failures
    - SHAP explanation generation
    - Performance monitoring
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache_manager = cache_manager
        self.mlflow_client = MlflowClient()
        self.current_model = None
        self.current_model_version = None
        self.current_model_info = None
        self.fallback_model = None
        self.model_cache_ttl = 3600  # 1 hour
        self.prediction_count = 0
        self.error_count = 0
        self.load_time = None

        # Performance tracking
        self.prediction_times = []
        self.last_health_check = None

        # Model configuration
        self.model_name = "prospect_success_prediction"
        self.fallback_enabled = True
        self.model_warmup_size = 10  # Number of predictions to warm up model

    async def initialize(self):
        """Initialize model server and load current production model."""
        try:
            logger.info("Initializing ML model server...")

            # Set MLflow tracking URI if configured
            if hasattr(settings, 'MLFLOW_TRACKING_URI'):
                mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)

            # Load current production model
            await self.load_production_model()

            # Load fallback model if enabled
            if self.fallback_enabled:
                await self.load_fallback_model()

            # Perform model warmup
            await self.warmup_model()

            logger.info("Model server initialization completed successfully")

        except Exception as e:
            logger.error(f"Failed to initialize model server: {e}")
            raise ModelLoadError(f"Model server initialization failed: {e}")

    async def load_production_model(self, version: Optional[str] = None):
        """
        Load production model from MLflow registry.

        Args:
            version: Specific model version to load. If None, loads latest production version.
        """
        try:
            start_time = time.time()

            # Determine version to load
            if version is None:
                # Get latest production version
                latest_versions = self.mlflow_client.get_latest_versions(
                    self.model_name,
                    stages=["Production"]
                )
                if not latest_versions:
                    raise ModelLoadError("No production model version found")
                version = latest_versions[0].version

            # Check cache first
            if self.cache_manager:
                cached_model = await self.cache_manager.get_cached_model(f"{self.model_name}:{version}")
                if cached_model:
                    logger.info(f"Loading model {version} from cache")
                    self.current_model = pickle.loads(cached_model)
                    self.current_model_version = version
                    await self._load_model_metadata(version)
                    return

            # Load from MLflow registry
            logger.info(f"Loading model {self.model_name} version {version} from MLflow")

            model_uri = f"models:/{self.model_name}/{version}"
            model = mlflow.sklearn.load_model(model_uri)

            # Cache the model
            if self.cache_manager:
                model_bytes = pickle.dumps(model)
                await self.cache_manager.cache_model(
                    f"{self.model_name}:{version}",
                    model_bytes,
                    ttl=self.model_cache_ttl
                )

            self.current_model = model
            self.current_model_version = version
            self.load_time = time.time() - start_time

            # Load model metadata
            await self._load_model_metadata(version)

            logger.info(f"Model {version} loaded successfully in {self.load_time:.2f}s")

        except Exception as e:
            logger.error(f"Failed to load production model: {e}")
            raise ModelLoadError(f"Production model loading failed: {e}")

    async def load_fallback_model(self):
        """Load a fallback model for when primary model fails."""
        try:
            # Try to load a previous stable version as fallback
            all_versions = self.mlflow_client.search_model_versions(
                f"name='{self.model_name}'"
            )

            # Sort by version number (descending) and find a stable version
            stable_versions = [
                v for v in all_versions
                if v.current_stage in ["Production", "Staging"] and v.version != self.current_model_version
            ]

            if stable_versions:
                fallback_version = sorted(stable_versions, key=lambda x: int(x.version), reverse=True)[0]
                model_uri = f"models:/{self.model_name}/{fallback_version.version}"
                self.fallback_model = mlflow.sklearn.load_model(model_uri)
                logger.info(f"Fallback model loaded: version {fallback_version.version}")
            else:
                logger.warning("No suitable fallback model found")

        except Exception as e:
            logger.warning(f"Failed to load fallback model: {e}")

    async def _load_model_metadata(self, version: str):
        """Load model metadata and information."""
        try:
            model_version = self.mlflow_client.get_model_version(self.model_name, version)
            run_id = model_version.run_id

            # Get run metrics and parameters
            run = self.mlflow_client.get_run(run_id)
            metrics = run.data.metrics
            params = run.data.params

            # Get model artifacts info
            artifacts = self.mlflow_client.list_artifacts(run_id)

            self.current_model_info = ModelInfo(
                model_version=version,
                model_name=self.model_name,
                trained_at=datetime.fromisoformat(model_version.creation_timestamp),
                accuracy=metrics.get("accuracy", 0.0),
                features_count=int(params.get("n_features", 0)),
                last_loaded=datetime.utcnow()
            )

        except Exception as e:
            logger.warning(f"Failed to load model metadata: {e}")
            # Create basic info if metadata loading fails
            self.current_model_info = ModelInfo(
                model_version=version,
                model_name=self.model_name,
                trained_at=datetime.utcnow(),
                accuracy=0.0,
                features_count=0,
                last_loaded=datetime.utcnow()
            )

    async def predict(
        self,
        features: Dict[str, Any],
        include_explanation: bool = False,
        model_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ML prediction with optional SHAP explanation.

        Args:
            features: Input features for prediction
            include_explanation: Whether to include SHAP explanation
            model_version: Specific model version to use

        Returns:
            Dictionary containing prediction probability and optional explanation
        """
        start_time = time.time()

        try:
            # Ensure correct model version is loaded
            if model_version and model_version != self.current_model_version:
                await self.load_production_model(model_version)

            # Validate model is loaded
            if self.current_model is None:
                raise ModelLoadError("No model loaded")

            # Prepare feature array
            feature_array = self._prepare_features(features)

            # Generate prediction
            try:
                prediction_proba = self.current_model.predict_proba([feature_array])[0][1]
            except Exception as e:
                logger.warning(f"Primary model prediction failed: {e}")
                # Try fallback model
                if self.fallback_model is not None:
                    logger.info("Using fallback model for prediction")
                    prediction_proba = self.fallback_model.predict_proba([feature_array])[0][1]
                else:
                    raise ModelLoadError("Both primary and fallback models failed")

            result = {
                "probability": float(prediction_proba),
                "model_version": self.current_model_version
            }

            # Generate SHAP explanation if requested
            if include_explanation:
                explanation = await self._generate_shap_explanation(feature_array, features)
                result["explanation"] = explanation
                result["shap_values"] = explanation.feature_importances if explanation else None

            # Track performance
            prediction_time = time.time() - start_time
            self.prediction_times.append(prediction_time)
            if len(self.prediction_times) > 1000:
                self.prediction_times = self.prediction_times[-1000:]  # Keep only last 1000

            self.prediction_count += 1

            return result

        except Exception as e:
            self.error_count += 1
            logger.error(f"Prediction failed: {e}")
            raise

    def _prepare_features(self, features: Dict[str, Any]) -> np.ndarray:
        """
        Prepare features for model input.

        Converts feature dictionary to numpy array in the correct order
        expected by the trained model.
        """
        try:
            # Define expected feature order (this should match training pipeline)
            expected_features = [
                "age", "height", "weight", "draft_round", "years_since_draft", "eta_years_remaining",
                "position_encoded", "level_encoded", "bats_left", "bats_right", "bats_switch",
                "throws_left", "throws_right", "career_pa", "career_ab", "career_avg", "career_obp",
                "career_hr_rate", "career_bb_rate", "career_k_rate", "career_sb_rate", "games_played",
                "recent_avg", "recent_ops", "career_ip", "career_era", "career_whip", "career_k9",
                "career_bb9", "games_pitched", "games_started", "recent_era", "recent_whip",
                "grade_hit", "grade_power", "grade_run", "grade_arm", "grade_field", "grade_overall",
                "grade_fastball", "grade_curveball", "grade_slider", "grade_changeup", "grade_control",
                "grade_age_days", "bmi", "hr_per_pa", "bb_per_k", "hitting_tool_avg",
                "defensive_tool_avg", "pitching_stuff_avg"
            ]

            # Create feature array with defaults for missing features
            feature_array = []
            for feature_name in expected_features:
                value = features.get(feature_name, 0.0)
                # Handle any non-numeric values
                try:
                    feature_array.append(float(value))
                except (ValueError, TypeError):
                    feature_array.append(0.0)

            return np.array(feature_array)

        except Exception as e:
            logger.error(f"Feature preparation failed: {e}")
            raise ValueError(f"Invalid features provided: {e}")

    async def _generate_shap_explanation(
        self,
        feature_array: np.ndarray,
        features_dict: Dict[str, Any]
    ) -> Optional[PredictionExplanation]:
        """Generate SHAP-based explanation for prediction."""
        try:
            # Import SHAP here to avoid startup dependency issues
            import shap

            # Create SHAP explainer for the current model
            # For performance, we'll use a simplified explainer
            explainer = shap.Explainer(self.current_model.predict_proba, feature_array.reshape(1, -1))

            # Generate SHAP values
            shap_values = explainer([feature_array])

            # Get SHAP values for positive class (success)
            shap_values_positive = shap_values[0][:, 1] if len(shap_values[0].shape) > 1 else shap_values[0]

            # Get feature names (same order as preparation)
            feature_names = [
                "age", "height", "weight", "draft_round", "years_since_draft", "eta_years_remaining",
                "position_encoded", "level_encoded", "bats_left", "bats_right", "bats_switch",
                "throws_left", "throws_right", "career_pa", "career_ab", "career_avg", "career_obp",
                "career_hr_rate", "career_bb_rate", "career_k_rate", "career_sb_rate", "games_played",
                "recent_avg", "recent_ops", "career_ip", "career_era", "career_whip", "career_k9",
                "career_bb9", "games_pitched", "games_started", "recent_era", "recent_whip",
                "grade_hit", "grade_power", "grade_run", "grade_arm", "grade_field", "grade_overall",
                "grade_fastball", "grade_curveball", "grade_slider", "grade_changeup", "grade_control",
                "grade_age_days", "bmi", "hr_per_pa", "bb_per_k", "hitting_tool_avg",
                "defensive_tool_avg", "pitching_stuff_avg"
            ]

            # Get top 10 most important features
            feature_importance_pairs = list(zip(feature_names, shap_values_positive, feature_array))
            feature_importance_pairs.sort(key=lambda x: abs(x[1]), reverse=True)

            top_features = []
            for feature_name, importance, value in feature_importance_pairs[:10]:
                top_features.append(FeatureImportance(
                    feature_name=feature_name,
                    importance=float(importance),
                    feature_value=float(value)
                ))

            # Generate narrative explanation
            narrative = self._generate_explanation_narrative(top_features)

            return PredictionExplanation(
                feature_importances=top_features,
                base_probability=float(explainer.expected_value[1] if hasattr(explainer, 'expected_value') else 0.5),
                narrative=narrative
            )

        except ImportError:
            logger.warning("SHAP not available for explanations")
            return None
        except Exception as e:
            logger.error(f"SHAP explanation generation failed: {e}")
            return None

    def _generate_explanation_narrative(self, top_features: List[FeatureImportance]) -> str:
        """Generate human-readable explanation from SHAP values."""
        try:
            positive_features = [f for f in top_features if f.importance > 0]
            negative_features = [f for f in top_features if f.importance < 0]

            narrative_parts = []

            if positive_features:
                pos_feature_names = [self._humanize_feature_name(f.feature_name) for f in positive_features[:3]]
                narrative_parts.append(f"Success probability increased by {', '.join(pos_feature_names)}")

            if negative_features:
                neg_feature_names = [self._humanize_feature_name(f.feature_name) for f in negative_features[:3]]
                narrative_parts.append(f"Success probability decreased by {', '.join(neg_feature_names)}")

            if not narrative_parts:
                return "Prediction based on balanced combination of prospect factors"

            return ". ".join(narrative_parts) + "."

        except Exception as e:
            logger.error(f"Narrative generation failed: {e}")
            return "Explanation generation failed"

    def _humanize_feature_name(self, feature_name: str) -> str:
        """Convert technical feature names to human-readable format."""
        humanization_map = {
            "grade_hit": "hitting ability",
            "grade_power": "power potential",
            "grade_run": "speed/baserunning",
            "grade_arm": "arm strength",
            "grade_field": "fielding ability",
            "grade_overall": "overall scouting grade",
            "grade_fastball": "fastball quality",
            "grade_curveball": "curveball quality",
            "grade_slider": "slider quality",
            "grade_changeup": "changeup quality",
            "grade_control": "pitching control",
            "career_avg": "career batting average",
            "career_era": "career ERA",
            "career_obp": "career on-base percentage",
            "recent_avg": "recent batting average",
            "recent_era": "recent ERA",
            "age": "current age",
            "draft_round": "draft position",
            "position_encoded": "field position",
            "level_encoded": "current level",
            "hitting_tool_avg": "hitting tools",
            "defensive_tool_avg": "defensive tools",
            "pitching_stuff_avg": "pitching repertoire"
        }

        return humanization_map.get(feature_name, feature_name.replace("_", " "))

    async def warmup_model(self):
        """Warm up model with sample predictions."""
        if self.current_model is None:
            return

        try:
            logger.info("Warming up model...")

            # Create sample features for warmup
            sample_features = {
                "age": 22, "height": 72, "weight": 185, "draft_round": 3,
                "years_since_draft": 2, "eta_years_remaining": 3, "position_encoded": 5,
                "level_encoded": 4, "bats_left": 0, "bats_right": 1, "bats_switch": 0,
                "throws_left": 0, "throws_right": 1, "career_pa": 500, "career_ab": 450,
                "career_avg": 0.275, "career_obp": 0.340, "career_hr_rate": 0.025,
                "career_bb_rate": 0.085, "career_k_rate": 0.210, "career_sb_rate": 0.80,
                "games_played": 120, "recent_avg": 0.285, "recent_ops": 0.780,
                "career_ip": 0, "career_era": 0, "career_whip": 0, "career_k9": 0,
                "career_bb9": 0, "games_pitched": 0, "games_started": 0,
                "recent_era": 0, "recent_whip": 0, "grade_hit": 55, "grade_power": 50,
                "grade_run": 60, "grade_arm": 55, "grade_field": 50, "grade_overall": 55,
                "grade_fastball": 50, "grade_curveball": 50, "grade_slider": 50,
                "grade_changeup": 50, "grade_control": 50, "grade_age_days": 30,
                "bmi": 23.5, "hr_per_pa": 0.025, "bb_per_k": 0.40,
                "hitting_tool_avg": 52.5, "defensive_tool_avg": 55.0, "pitching_stuff_avg": 50.0
            }

            # Perform warmup predictions
            for i in range(self.model_warmup_size):
                await self.predict(sample_features, include_explanation=(i == 0))

            logger.info(f"Model warmup completed with {self.model_warmup_size} predictions")

        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")

    async def hot_swap_model(self, new_version: str) -> bool:
        """
        Hot-swap to a new model version without service restart.

        Args:
            new_version: New model version to load

        Returns:
            bool: True if swap successful, False otherwise
        """
        try:
            logger.info(f"Attempting hot-swap to model version {new_version}")

            # Backup current model
            backup_model = self.current_model
            backup_version = self.current_model_version
            backup_info = self.current_model_info

            try:
                # Load new model
                await self.load_production_model(new_version)

                # Test new model with sample prediction
                sample_features = {"age": 22}  # Minimal test
                test_result = await self.predict(sample_features)

                logger.info(f"Hot-swap successful: model version {new_version} is now active")
                return True

            except Exception as e:
                # Restore backup on failure
                self.current_model = backup_model
                self.current_model_version = backup_version
                self.current_model_info = backup_info
                logger.error(f"Hot-swap failed, restored previous model: {e}")
                return False

        except Exception as e:
            logger.error(f"Hot-swap attempt failed: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on model server."""
        try:
            self.last_health_check = datetime.utcnow()

            health_info = {
                "status": "healthy",
                "model_loaded": self.current_model is not None,
                "model_version": self.current_model_version,
                "fallback_available": self.fallback_model is not None,
                "predictions_served": self.prediction_count,
                "error_count": self.error_count,
                "last_health_check": self.last_health_check.isoformat()
            }

            # Test model with simple prediction if loaded
            if self.current_model is not None:
                try:
                    # Quick test prediction
                    test_features = np.zeros(47)  # Assuming 47 features
                    _ = self.current_model.predict_proba([test_features])[0][1]
                    health_info["model_test"] = "passed"
                except Exception as e:
                    health_info["status"] = "unhealthy"
                    health_info["model_test"] = f"failed: {e}"

            return health_info

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model_loaded": False
            }

    async def get_model_info(self) -> ModelInfo:
        """Get current model information."""
        if self.current_model_info is None:
            raise ModelLoadError("No model loaded")
        return self.current_model_info

    async def get_current_version(self) -> str:
        """Get current model version."""
        if self.current_model_version is None:
            raise ModelLoadError("No model loaded")
        return self.current_model_version

    async def get_metrics(self) -> Dict[str, Any]:
        """Get model server performance metrics."""
        avg_prediction_time = (
            sum(self.prediction_times) / len(self.prediction_times)
            if self.prediction_times else 0
        )

        error_rate = (
            self.error_count / (self.prediction_count + self.error_count)
            if (self.prediction_count + self.error_count) > 0 else 0
        )

        return {
            "predictions_served": self.prediction_count,
            "error_count": self.error_count,
            "error_rate": error_rate,
            "average_prediction_time": avg_prediction_time,
            "model_load_time": self.load_time,
            "current_version": self.current_model_version,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None
        }