"""FastAPI ML Inference Service

Provides real-time ML predictions with horizontal scaling capabilities,
async request handling, and comprehensive monitoring.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from ..core.config import settings
from ..core.database import get_db
from ..core.cache_manager import CacheManager
from .model_serving import ModelServer
from .confidence_scoring import ConfidenceScorer
from ..schemas.ml_predictions import PredictionRequest, PredictionResponse, BatchPredictionRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
model_server: Optional[ModelServer] = None
cache_manager: Optional[CacheManager] = None
confidence_scorer: Optional[ConfidenceScorer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with model loading and cleanup."""
    global model_server, cache_manager, confidence_scorer

    try:
        # Initialize services on startup
        logger.info("Initializing ML Inference Service...")

        # Initialize cache manager
        cache_manager = CacheManager()
        await cache_manager.initialize()

        # Initialize model server
        model_server = ModelServer(cache_manager)
        await model_server.initialize()

        # Initialize confidence scorer
        confidence_scorer = ConfidenceScorer()

        logger.info("ML Inference Service initialized successfully")

        yield

    except Exception as e:
        logger.error(f"Failed to initialize ML Inference Service: {e}")
        raise
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down ML Inference Service...")
        if cache_manager:
            await cache_manager.close()
        logger.info("ML Inference Service shutdown complete")


def create_inference_app() -> FastAPI:
    """Create and configure the FastAPI inference application."""

    app = FastAPI(
        title="MLB Prospect ML Inference Service",
        description="Real-time ML predictions for MLB prospects with confidence scoring",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS middleware for cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        # Log slow requests (>400ms)
        if process_time > 0.4:
            logger.warning(f"Slow request: {request.url} took {process_time:.3f}s")

        return response

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"Global exception on {request.url}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

    return app


def get_model_server() -> ModelServer:
    """Dependency to get the global model server instance."""
    if model_server is None:
        raise HTTPException(status_code=503, detail="Model server not initialized")
    return model_server


def get_cache_manager() -> CacheManager:
    """Dependency to get the global cache manager instance."""
    if cache_manager is None:
        raise HTTPException(status_code=503, detail="Cache manager not initialized")
    return cache_manager


def get_confidence_scorer() -> ConfidenceScorer:
    """Dependency to get the global confidence scorer instance."""
    if confidence_scorer is None:
        raise HTTPException(status_code=503, detail="Confidence scorer not initialized")
    return confidence_scorer


# Health check endpoints
app = create_inference_app()


@app.get("/health")
async def health_check():
    """Basic health check endpoint for load balancer monitoring."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "ml-inference"
    }


@app.get("/health/detailed")
async def detailed_health_check(
    model_server: ModelServer = Depends(get_model_server),
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """Detailed health check including service dependencies."""
    checks = {
        "model_server": await model_server.health_check(),
        "cache": await cache_manager.health_check(),
        "timestamp": time.time()
    }

    # Determine overall health
    all_healthy = all(check.get("status") == "healthy" for check in checks.values() if isinstance(check, dict))

    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks
    }


@app.get("/metrics")
async def get_metrics(
    model_server: ModelServer = Depends(get_model_server),
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """Service metrics for monitoring and alerting."""
    return {
        "model_metrics": await model_server.get_metrics(),
        "cache_metrics": await cache_manager.get_metrics(),
        "timestamp": time.time()
    }


# Inference configuration
class InferenceConfig:
    """Configuration for ML inference service."""

    # Performance settings
    MAX_CONCURRENT_REQUESTS = 100
    REQUEST_TIMEOUT = 0.5  # 500ms max response time
    BATCH_SIZE_LIMIT = 1000

    # Cache settings
    MODEL_CACHE_TTL = 3600  # 1 hour
    PREDICTION_CACHE_TTL = 86400  # 24 hours

    # Rate limiting
    RATE_LIMIT_PER_MINUTE = 10

    # Model settings
    MODEL_FALLBACK_ENABLED = True
    MODEL_WARMUP_ON_STARTUP = True


def run_inference_service(host: str = "0.0.0.0", port: int = 8001, workers: int = 1):
    """Run the inference service with uvicorn."""

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        workers=workers,
        loop="asyncio",
        access_log=True,
        log_level="info"
    )

    server = uvicorn.Server(config)

    logger.info(f"Starting ML Inference Service on {host}:{port} with {workers} workers")
    server.run()


if __name__ == "__main__":
    run_inference_service()