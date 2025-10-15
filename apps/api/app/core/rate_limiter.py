from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis.asyncio as redis
from fastapi import Request
from starlette.requests import Request as StarletteRequest
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


async def get_redis_client():
    """Get async Redis client"""
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )


def get_client_ip(request: Request):
    """Extract client IP from request"""
    return get_remote_address(request)


def is_healthcheck(request: StarletteRequest) -> bool:
    """Check if request is a healthcheck - exempt from rate limiting"""
    path = request.url.path
    # Exempt health endpoints and Railway's internal healthcheck domain
    if path in ["/health", "/api/v1/health"]:
        return True
    if request.headers.get("host", "").startswith("healthcheck.railway.app"):
        return True
    return False


# Create limiter instance with memory backend if Redis is not configured
# In production, Redis should be configured for distributed rate limiting
try:
    # Try to use Redis if REDIS_URL is set or if we're not using default localhost
    if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL and settings.REDIS_URL != "redis://localhost:6379/0":
        storage_uri = settings.REDIS_URL
    elif settings.REDIS_HOST != "localhost":
        storage_uri = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    else:
        # Fall back to in-memory storage for development/when Redis is unavailable
        storage_uri = "memory://"
        logger.warning("Redis not configured, using in-memory rate limiting (not suitable for production)")

    limiter = Limiter(
        key_func=get_client_ip,
        storage_uri=storage_uri,
        strategy="moving-window"
    )
except Exception as e:
    logger.warning(f"Failed to initialize Redis rate limiter: {e}. Using in-memory fallback.")
    limiter = Limiter(
        key_func=get_client_ip,
        storage_uri="memory://",
        strategy="moving-window"
    )


def setup_rate_limiter(app):
    """Setup rate limiter middleware and exception handlers"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add custom middleware to exempt healthcheck endpoints from rate limiting
    @app.middleware("http")
    async def rate_limit_with_healthcheck_exemption(request, call_next):
        # Skip rate limiting for healthcheck endpoints
        if is_healthcheck(request):
            return await call_next(request)

        # Apply rate limiting to all other requests
        # Note: SlowAPIMiddleware processes the request through the limiter
        response = await call_next(request)
        return response

    # Still add SlowAPIMiddleware for decorated endpoints using @limiter.limit()
    app.add_middleware(SlowAPIMiddleware)

    return app