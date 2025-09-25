from fastapi import HTTPException, Request, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.core.config import settings
import logging


# Configure logging for security events
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size"""

    def __init__(self, app: ASGIApp, max_request_size: int = 1024 * 1024):  # 1MB default
        super().__init__(app)
        self.max_request_size = max_request_size

    async def dispatch(self, request: Request, call_next):
        if request.headers.get("content-length"):
            content_length = int(request.headers["content-length"])
            if content_length > self.max_request_size:
                security_logger.warning(
                    f"Request too large: {content_length} bytes from {request.client.host}"
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request too large"}
                )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log security-relevant requests"""

    async def dispatch(self, request: Request, call_next):
        # Log authentication attempts
        if "/auth/" in str(request.url):
            security_logger.info(
                f"Auth request: {request.method} {request.url.path} from {request.client.host}"
            )

        response = await call_next(request)

        # Log failed authentication attempts
        if "/auth/" in str(request.url) and response.status_code in [401, 403, 429]:
            security_logger.warning(
                f"Failed auth attempt: {response.status_code} from {request.client.host} to {request.url.path}"
            )

        return response


def add_security_middleware(app):
    """Add security middleware to FastAPI app"""
    # Request size limiting
    app.add_middleware(RequestSizeLimitMiddleware, max_request_size=2 * 1024 * 1024)  # 2MB limit

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Security logging
    app.add_middleware(SecurityLoggingMiddleware)

    # Trusted host middleware - use specific hosts in production
    allowed_hosts = settings.ALLOWED_HOSTS if settings.ALLOWED_HOSTS else ["*"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    return app