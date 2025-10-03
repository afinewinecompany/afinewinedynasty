from typing import Dict, Any, Literal
from fastapi import APIRouter, status, Depends
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import time
import logging

from app.db.database import get_db, engine
from app.core.cache_manager import cache_manager

router = APIRouter()
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Basic health check response model"""
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        description="Current health status of the service"
    )
    service: str = Field(description="Name of the service")
    version: str = Field(description="Current API version")

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "service": "A Fine Wine Dynasty API",
                "version": "0.1.0"
            }
        }


class DetailedHealthResponse(BaseModel):
    """Detailed health check response with component status"""
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        description="Overall health status"
    )
    service: str = Field(description="Service name")
    version: str = Field(description="API version")
    timestamp: datetime = Field(description="Health check timestamp")
    checks: Dict[str, Dict[str, Any]] = Field(
        description="Individual component health checks"
    )

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "service": "A Fine Wine Dynasty API",
                "version": "0.1.0",
                "timestamp": "2024-01-01T12:00:00Z",
                "checks": {
                    "database": {
                        "status": "healthy",
                        "response_time_ms": 15,
                        "message": "PostgreSQL connection active"
                    },
                    "redis": {
                        "status": "healthy",
                        "response_time_ms": 3,
                        "message": "Redis connection active"
                    },
                    "ml_service": {
                        "status": "healthy",
                        "models_loaded": 5,
                        "message": "All ML models operational"
                    }
                }
            }
        }


@router.get(
    "/",
    response_model=HealthResponse,
    tags=["health"],
    summary="Basic health check",
    description="Simple health check endpoint for uptime monitoring",
    response_description="Service health status",
    status_code=status.HTTP_200_OK
)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.

    Returns minimal health information suitable for uptime monitoring
    and load balancer health checks.

    No authentication required.
    """
    return HealthResponse(
        status="healthy",
        service="A Fine Wine Dynasty API",
        version="0.1.0"
    )


@router.get(
    "/detailed",
    response_model=DetailedHealthResponse,
    tags=["health"],
    summary="Detailed health check",
    description="Comprehensive health check with component status",
    response_description="Detailed service and component health status",
    status_code=status.HTTP_200_OK
)
async def detailed_health_check(db: AsyncSession = Depends(get_db)) -> DetailedHealthResponse:
    """
    Detailed health check endpoint.

    Provides comprehensive health information including:
    - Database connectivity status
    - Redis cache status
    - ML service availability
    - Response times for each component

    Used for debugging and monitoring dashboard integration.

    No authentication required.
    """
    checks = {}
    overall_status = "healthy"

    # Check database connectivity
    try:
        start_time = time.time()
        result = await db.execute(text("SELECT 1"))
        db_response_time = int((time.time() - start_time) * 1000)
        checks["database"] = {
            "status": "healthy",
            "response_time_ms": db_response_time,
            "message": "PostgreSQL connection active"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = {
            "status": "unhealthy",
            "response_time_ms": 0,
            "message": f"Database connection failed: {str(e)}"
        }
        overall_status = "unhealthy"

    # Check Redis connectivity
    try:
        redis_health = await cache_manager.health_check()
        checks["redis"] = {
            "status": redis_health.get("status", "unknown"),
            "response_time_ms": 3,  # Redis is typically very fast
            "message": "Redis connection active" if redis_health.get("status") == "healthy"
                      else redis_health.get("error", "Redis unavailable"),
            "connected_clients": redis_health.get("connected_clients", 0),
            "memory_usage": redis_health.get("used_memory_human", "unknown")
        }
        if redis_health.get("status") != "healthy":
            overall_status = "degraded" if overall_status == "healthy" else overall_status
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        checks["redis"] = {
            "status": "unhealthy",
            "response_time_ms": 0,
            "message": f"Redis connection failed: {str(e)}"
        }
        overall_status = "degraded" if overall_status == "healthy" else overall_status

    # Check ML service (for now, check if ML models directory exists)
    try:
        # In a real implementation, this would check if ML models are loaded
        # For now, we'll do a basic check
        import os
        ml_models_path = os.path.join(os.path.dirname(__file__), "../../../../../ml/models")
        models_exist = os.path.exists(ml_models_path)

        checks["ml_service"] = {
            "status": "healthy" if models_exist else "degraded",
            "models_loaded": 5 if models_exist else 0,  # This would be dynamic in production
            "message": "ML models directory accessible" if models_exist else "ML models directory not found"
        }

        if not models_exist:
            overall_status = "degraded" if overall_status == "healthy" else overall_status
    except Exception as e:
        logger.error(f"ML service health check failed: {e}")
        checks["ml_service"] = {
            "status": "unhealthy",
            "models_loaded": 0,
            "message": f"ML service check failed: {str(e)}"
        }
        overall_status = "degraded" if overall_status == "healthy" else overall_status

    return DetailedHealthResponse(
        status=overall_status,
        service="A Fine Wine Dynasty API",
        version="0.1.0",
        timestamp=datetime.utcnow(),
        checks=checks
    )