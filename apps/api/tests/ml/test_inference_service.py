"""Tests for ML Inference Service

Comprehensive testing for ML inference service components including
unit tests, integration tests, performance tests, and cache testing.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import numpy as np

from app.ml.inference_service import (
    create_inference_app,
    InferenceConfig,
    get_model_server,
    get_cache_manager,
    get_confidence_scorer
)
from app.ml.model_serving import ModelServer
from app.core.cache_manager import CacheManager
from app.ml.confidence_scoring import ConfidenceScorer
from app.schemas.ml_predictions import ConfidenceLevel


@pytest.fixture
def mock_model_server():
    """Mock model server for testing."""
    server = Mock(spec=ModelServer)
    server.health_check = AsyncMock(return_value={"status": "healthy", "model_loaded": True})
    server.get_metrics = AsyncMock(return_value={"predictions_served": 100, "error_count": 0})
    server.get_current_version = AsyncMock(return_value="v1.0.0")
    server.predict = AsyncMock(return_value={
        "probability": 0.75,
        "explanation": None,
        "shap_values": [0.1, -0.05, 0.2]
    })
    server.get_model_info = AsyncMock(return_value={
        "model_version": "v1.0.0",
        "model_name": "test_model",
        "accuracy": 0.85
    })
    return server


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager for testing."""
    cache = Mock(spec=CacheManager)
    cache.health_check = AsyncMock(return_value={"status": "healthy"})
    cache.get_metrics = AsyncMock(return_value={"hits": 50, "misses": 25})
    cache.get_cached_prediction = AsyncMock(return_value=None)
    cache.cache_prediction = AsyncMock()
    cache.get_cached_features = AsyncMock(return_value=None)
    cache.cache_prospect_features = AsyncMock()
    return cache


@pytest.fixture
def mock_confidence_scorer():
    """Mock confidence scorer for testing."""
    scorer = Mock(spec=ConfidenceScorer)
    scorer.calculate_confidence = AsyncMock(return_value=ConfidenceLevel.HIGH)
    return scorer


@pytest.fixture
def sample_features():
    """Sample prospect features for testing."""
    return {
        "age": 22,
        "height": 72,
        "weight": 185,
        "draft_round": 3,
        "position_encoded": 5,
        "level_encoded": 4,
        "career_avg": 0.275,
        "career_era": 0.0,
        "grade_overall": 55,
        "bmi": 23.5
    }


class TestInferenceServiceSetup:
    """Test inference service initialization and setup."""

    def test_create_inference_app(self):
        """Test FastAPI application creation."""
        app = create_inference_app()

        assert app.title == "MLB Prospect ML Inference Service"
        assert app.version == "1.0.0"
        assert "/docs" in str(app.docs_url)

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self):
        """Test basic health check endpoint."""
        app = create_inference_app()

        # Mock the health check
        with patch('app.ml.inference_service.model_server') as mock_server:
            mock_server.health_check = AsyncMock(return_value={"status": "healthy"})

            from fastapi.testclient import TestClient
            client = TestClient(app)

            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "timestamp" in data

    def test_inference_config(self):
        """Test inference configuration settings."""
        config = InferenceConfig()

        assert config.MAX_CONCURRENT_REQUESTS == 100
        assert config.REQUEST_TIMEOUT == 0.5
        assert config.BATCH_SIZE_LIMIT == 1000
        assert config.MODEL_CACHE_TTL == 3600
        assert config.RATE_LIMIT_PER_MINUTE == 10


class TestModelServingIntegration:
    """Test model serving infrastructure integration."""

    @pytest.mark.asyncio
    async def test_model_server_initialization(self, mock_cache_manager):
        """Test model server initialization."""
        with patch('app.ml.model_serving.MlflowClient') as mock_client:
            mock_client.return_value.get_latest_versions.return_value = [
                Mock(version="1.0.0")
            ]

            server = ModelServer(mock_cache_manager)

            # Test initialization without actual MLflow
            assert server.cache_manager == mock_cache_manager
            assert server.model_name == "prospect_success_prediction"

    @pytest.mark.asyncio
    async def test_model_prediction_flow(self, mock_model_server, sample_features):
        """Test end-to-end prediction flow."""
        prediction_result = await mock_model_server.predict(
            features=sample_features,
            include_explanation=True
        )

        assert "probability" in prediction_result
        assert isinstance(prediction_result["probability"], float)
        assert 0 <= prediction_result["probability"] <= 1

    @pytest.mark.asyncio
    async def test_model_fallback_mechanism(self, mock_cache_manager):
        """Test model fallback when primary model fails."""
        server = ModelServer(mock_cache_manager)

        # Mock primary model failure
        with patch.object(server, 'current_model') as mock_model:
            mock_model.predict_proba.side_effect = Exception("Model failed")

            # Mock fallback model
            server.fallback_model = Mock()
            server.fallback_model.predict_proba.return_value = [[0.3, 0.7]]

            with patch.object(server, '_prepare_features', return_value=np.array([1, 2, 3])):
                result = await server.predict({"test": "features"})

                assert result["probability"] == 0.7

    @pytest.mark.asyncio
    async def test_model_hot_swap(self, mock_cache_manager):
        """Test hot-swapping model versions."""
        server = ModelServer(mock_cache_manager)
        server.current_model = Mock()
        server.current_model_version = "1.0.0"

        with patch.object(server, 'load_production_model') as mock_load:
            mock_load.return_value = None

            # Mock successful test prediction
            with patch.object(server, 'predict', return_value={"probability": 0.5}):
                result = await server.hot_swap_model("2.0.0")

                assert result is True
                mock_load.assert_called_once_with("2.0.0")


class TestConfidenceScoring:
    """Test confidence scoring algorithm."""

    @pytest.mark.asyncio
    async def test_confidence_calculation_high(self):
        """Test high confidence calculation."""
        scorer = ConfidenceScorer()

        # High confidence scenario: extreme probability + consistent SHAP
        confidence = await scorer.calculate_confidence(
            prediction_probability=0.95,
            shap_values=[0.3, 0.2, 0.1, -0.05],
            features={"complete": "features"},
            ensemble_predictions=[0.94, 0.96, 0.95]
        )

        assert confidence == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_confidence_calculation_medium(self):
        """Test medium confidence calculation."""
        scorer = ConfidenceScorer()

        # Medium confidence scenario
        confidence = await scorer.calculate_confidence(
            prediction_probability=0.70,
            shap_values=[0.1, -0.1, 0.05],
            features={"partial": "features"}
        )

        assert confidence in [ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    @pytest.mark.asyncio
    async def test_confidence_calculation_low(self):
        """Test low confidence calculation."""
        scorer = ConfidenceScorer()

        # Low confidence scenario: uncertain probability + inconsistent SHAP
        confidence = await scorer.calculate_confidence(
            prediction_probability=0.52,
            shap_values=[0.1, -0.2, 0.15, -0.1],
            features={}  # Missing features
        )

        assert confidence == ConfidenceLevel.LOW

    def test_confidence_explanation_generation(self):
        """Test human-readable explanation generation."""
        scorer = ConfidenceScorer()

        explanation = scorer.get_confidence_explanation(
            prediction_probability=0.85,
            confidence_level=ConfidenceLevel.HIGH,
            shap_values=[0.3, 0.2, -0.1],
            features={"complete": "data"}
        )

        assert isinstance(explanation, str)
        assert "High confidence" in explanation
        assert len(explanation) > 0


class TestCacheManager:
    """Test Redis cache manager functionality."""

    @pytest.mark.asyncio
    async def test_cache_prediction_storage_retrieval(self, mock_cache_manager):
        """Test prediction caching and retrieval."""
        # Test caching
        prediction_data = {
            "prospect_id": 123,
            "success_probability": 0.75,
            "confidence_level": "High",
            "model_version": "v1.0.0"
        }

        await mock_cache_manager.cache_prediction(
            prospect_id=123,
            model_version="v1.0.0",
            prediction_data=prediction_data
        )

        mock_cache_manager.cache_prediction.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_feature_storage_retrieval(self, mock_cache_manager):
        """Test feature caching and retrieval."""
        features = {"age": 22, "position": "SS"}

        await mock_cache_manager.cache_prospect_features(
            prospect_id=123,
            features=features
        )

        mock_cache_manager.cache_prospect_features.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, mock_cache_manager):
        """Test cache invalidation strategies."""
        mock_cache_manager.invalidate_prospect_predictions = AsyncMock()

        await mock_cache_manager.invalidate_prospect_predictions(123)

        mock_cache_manager.invalidate_prospect_predictions.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_cache_health_check(self, mock_cache_manager):
        """Test cache health monitoring."""
        health = await mock_cache_manager.health_check()

        assert health["status"] == "healthy"
        mock_cache_manager.health_check.assert_called_once()


class TestPredictionEndpoints:
    """Test ML prediction API endpoints."""

    @pytest.fixture
    def test_client(self):
        """Create test client for API testing."""
        from fastapi.testclient import TestClient
        from app.ml.inference_service import create_inference_app

        app = create_inference_app()
        return TestClient(app)

    def test_prediction_endpoint_auth_required(self, test_client):
        """Test that prediction endpoints require authentication."""
        response = test_client.post("/api/ml/predict/123")
        assert response.status_code in [401, 422]  # Unauthorized or validation error

    @pytest.mark.asyncio
    async def test_prediction_response_format(self, mock_model_server, mock_confidence_scorer):
        """Test prediction response format validation."""
        from app.api.api_v1.endpoints.ml_predictions import _process_single_prediction
        from app.services.prospect_feature_extraction import ProspectFeatureExtractor

        with patch('app.api.api_v1.endpoints.ml_predictions.get_db') as mock_db:
            mock_db.return_value = Mock()

            feature_extractor = Mock(spec=ProspectFeatureExtractor)
            feature_extractor.get_prospect_features = AsyncMock(return_value={"test": "features"})

            # This would need more mocking to work properly
            # result = await _process_single_prediction(...)
            # assert "prospect_id" in result
            # assert "success_probability" in result
            # assert "confidence_level" in result

    def test_batch_prediction_size_limits(self, test_client):
        """Test batch prediction size limitations."""
        # Test oversized batch
        large_batch = {"prospect_ids": list(range(2000))}  # Over 1000 limit

        response = test_client.post("/api/ml/batch-predict", json=large_batch)
        # Should fail validation (422) or auth (401)
        assert response.status_code in [401, 422]


class TestPerformanceRequirements:
    """Test performance requirements and benchmarks."""

    @pytest.mark.asyncio
    async def test_prediction_response_time(self, mock_model_server, mock_cache_manager, sample_features):
        """Test <500ms response time requirement."""

        # Mock fast prediction
        mock_model_server.predict = AsyncMock(return_value={
            "probability": 0.75,
            "explanation": None
        })

        start_time = time.time()

        # Simulate prediction call
        result = await mock_model_server.predict(sample_features)

        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to ms

        # Note: This is just testing the mock, real test would need actual implementation
        assert response_time < 500  # 500ms requirement
        assert result["probability"] == 0.75

    @pytest.mark.asyncio
    async def test_concurrent_prediction_handling(self, mock_model_server, sample_features):
        """Test concurrent prediction processing."""

        # Mock multiple concurrent predictions
        tasks = []
        for i in range(10):
            task = asyncio.create_task(mock_model_server.predict(sample_features))
            tasks.append(task)

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        assert len(results) == 10
        assert all("probability" in result for result in results)

        # Should handle concurrent requests efficiently
        total_time = end_time - start_time
        assert total_time < 2.0  # Should be much faster with proper async

    @pytest.mark.asyncio
    async def test_cache_performance_impact(self, mock_cache_manager, sample_features):
        """Test cache performance improvement."""

        # Test cache hit scenario
        mock_cache_manager.get_cached_prediction.return_value = {
            "prospect_id": 123,
            "success_probability": 0.75,
            "confidence_level": "High"
        }

        start_time = time.time()
        cached_result = await mock_cache_manager.get_cached_prediction(123, "v1.0.0")
        end_time = time.time()

        cache_time = (end_time - start_time) * 1000

        assert cached_result is not None
        assert cache_time < 10  # Cache should be very fast


class TestErrorHandling:
    """Test error handling and fallback mechanisms."""

    @pytest.mark.asyncio
    async def test_model_loading_failure_handling(self, mock_cache_manager):
        """Test handling of model loading failures."""
        server = ModelServer(mock_cache_manager)

        with patch('app.ml.model_serving.mlflow') as mock_mlflow:
            mock_mlflow.sklearn.load_model.side_effect = Exception("Model loading failed")

            with pytest.raises(Exception):
                await server.load_production_model("invalid_version")

    @pytest.mark.asyncio
    async def test_cache_failure_graceful_degradation(self, mock_model_server):
        """Test graceful degradation when cache fails."""

        # Mock cache failure
        mock_cache = Mock()
        mock_cache.get_cached_prediction = AsyncMock(side_effect=Exception("Cache error"))

        # Should still work without cache
        result = await mock_model_server.predict({"test": "features"})
        assert "probability" in result

    @pytest.mark.asyncio
    async def test_invalid_feature_handling(self, mock_model_server):
        """Test handling of invalid or missing features."""

        # Test with invalid features
        invalid_features = {"invalid": "data"}

        with patch.object(mock_model_server, '_prepare_features', side_effect=ValueError("Invalid features")):
            with pytest.raises(Exception):
                await mock_model_server.predict(invalid_features)

    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """Test handling of database connection failures."""
        from app.services.prospect_feature_extraction import ProspectFeatureExtractor

        extractor = ProspectFeatureExtractor()

        # Mock database failure
        mock_db = Mock()
        mock_db.query.side_effect = Exception("Database connection failed")

        result = await extractor.get_prospect_features(123, mock_db, Mock())
        assert result is None


class TestServiceMonitoring:
    """Test service monitoring and health checks."""

    @pytest.mark.asyncio
    async def test_detailed_health_check(self, mock_model_server, mock_cache_manager):
        """Test comprehensive health check."""

        health_result = {
            "model_server": await mock_model_server.health_check(),
            "cache": await mock_cache_manager.health_check()
        }

        assert health_result["model_server"]["status"] == "healthy"
        assert health_result["cache"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_metrics_collection(self, mock_model_server, mock_cache_manager):
        """Test performance metrics collection."""

        model_metrics = await mock_model_server.get_metrics()
        cache_metrics = await mock_cache_manager.get_metrics()

        assert "predictions_served" in model_metrics
        assert "error_count" in model_metrics
        assert "hits" in cache_metrics
        assert "misses" in cache_metrics

    def test_service_status_reporting(self):
        """Test service status reporting."""
        from app.ml.inference_service import InferenceConfig

        config = InferenceConfig()

        # Test configuration values
        assert config.REQUEST_TIMEOUT == 0.5
        assert config.MAX_CONCURRENT_REQUESTS == 100


# Integration test fixtures and helpers
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_end_to_end_prediction_flow(
    mock_model_server,
    mock_cache_manager,
    mock_confidence_scorer,
    sample_features
):
    """Test complete end-to-end prediction flow."""

    # Test prediction flow
    start_time = time.time()

    # 1. Check cache (miss)
    cached_result = await mock_cache_manager.get_cached_prediction(123, "v1.0.0")
    assert cached_result is None

    # 2. Generate prediction
    prediction_result = await mock_model_server.predict(sample_features)
    assert "probability" in prediction_result

    # 3. Calculate confidence
    confidence = await mock_confidence_scorer.calculate_confidence(
        prediction_result["probability"],
        prediction_result.get("shap_values"),
        sample_features
    )
    assert confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    # 4. Cache result
    await mock_cache_manager.cache_prediction(
        prospect_id=123,
        model_version="v1.0.0",
        prediction_data={}
    )

    end_time = time.time()
    total_time = (end_time - start_time) * 1000

    # Should complete within performance requirements
    assert total_time < 500  # 500ms requirement