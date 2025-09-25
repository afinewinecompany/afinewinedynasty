from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis.asyncio as redis
from fastapi import Request
from app.core.config import settings


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


# Create limiter instance with Redis backend
limiter = Limiter(
    key_func=get_client_ip,
    storage_uri=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    strategy="moving-window"
)


def setup_rate_limiter(app):
    """Setup rate limiter middleware and exception handlers"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    return app