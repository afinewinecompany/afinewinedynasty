from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.api_v1.api import api_router
from app.core.config import settings
from app.core.rate_limiter import setup_rate_limiter
from app.middleware.security_middleware import add_security_middleware
from app.services.hype_scheduler import start_hype_scheduler, stop_hype_scheduler

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
# A Fine Wine Dynasty API

## Overview
A Fine Wine Dynasty is a comprehensive baseball prospect analysis platform that provides:
- Real-time MLB prospect tracking and evaluation
- Advanced ML-powered predictions and analytics
- Historical performance comparisons
- Fantasy baseball integration

## Features
- **Prospect Rankings**: Dynamic rankings based on performance metrics
- **ML Predictions**: Advanced machine learning models for performance forecasting
- **Comparison Tools**: Side-by-side prospect comparisons with radar charts
- **Search & Discovery**: Advanced filtering and breakout detection
- **Subscription Tiers**: Free, Pro ($9.99/mo), and Premium ($19.99/mo) plans

## Authentication
This API uses JWT Bearer token authentication. Include the token in the Authorization header:
```
Authorization: Bearer <your-token>
```

## Rate Limiting
- **Free Tier**: 100 requests per minute
- **Pro Tier**: 500 requests per minute
- **Premium Tier**: 1000 requests per minute

## Support
For support, please contact: support@afinewinedynasty.com
    """,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    terms_of_service="https://afinewinedynasty.com/terms",
    contact={
        "name": "A Fine Wine Dynasty Support",
        "url": "https://afinewinedynasty.com/support",
        "email": "support@afinewinedynasty.com"
    },
    license_info={
        "name": "Proprietary",
        "url": "https://afinewinedynasty.com/license"
    },
    openapi_tags=[
        {"name": "auth", "description": "Authentication operations"},
        {"name": "prospects", "description": "Prospect data and operations"},
        {"name": "predictions", "description": "ML predictions and analytics"},
        {"name": "comparisons", "description": "Prospect comparison tools"},
        {"name": "subscriptions", "description": "Subscription management"},
        {"name": "users", "description": "User profile management"},
        {"name": "search", "description": "Advanced search and discovery"},
        {"name": "health", "description": "Service health checks"}
    ]
)

# Debug: Log CORS configuration at startup
import logging
logger = logging.getLogger(__name__)
logger.info(f"🔧 CORS Configuration:")
logger.info(f"   Raw BACKEND_CORS_ORIGINS: {settings.BACKEND_CORS_ORIGINS}")
cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else ["http://localhost:3000"]
logger.info(f"   Processed cors_origins: {cors_origins}")
logger.info(f"   Total origins: {len(cors_origins)}")

# MIDDLEWARE ORDER (applied in reverse, so last added = first executed):
# 1. Security middleware FIRST (includes TrustedHost for Railway domains)
app = add_security_middleware(app)

# 2. CORS middleware (after host validation, before rate limiting)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["X-Total-Count"],
)

# 3. Rate limiting LAST (after CORS, with healthcheck exemption)
app = setup_rate_limiter(app)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "A Fine Wine Dynasty API", "version": settings.VERSION}


@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "healthy", "service": "api"}


@app.head("/health", include_in_schema=False)
async def health_check_head():
    """HEAD handler for Railway healthchecks"""
    return Response(status_code=200)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""

    # Validate critical environment variables
    logger.info("=" * 60)
    logger.info("🔍 Validating environment configuration...")
    try:
        logger.info(f"   Environment: {settings.ENVIRONMENT}")
        logger.info(f"   CORS Origins: {len(settings.BACKEND_CORS_ORIGINS)} configured")
        if settings.BACKEND_CORS_ORIGINS:
            for origin in settings.BACKEND_CORS_ORIGINS[:5]:  # Show first 5
                logger.info(f"     - {origin}")
        else:
            logger.warning("   ⚠️  No CORS origins configured - all origins blocked!")
        logger.info(f"   Database: {'✅ Configured' if settings.SQLALCHEMY_DATABASE_URI else '❌ Not set'}")
        logger.info(f"   Redis: {'✅ Configured' if settings.REDIS_URL else '❌ Not set'}")
        logger.info(f"   Google OAuth: {'✅ Configured' if settings.GOOGLE_CLIENT_ID else '❌ Not set'}")
        logger.info("✅ Environment validation complete")
    except Exception as e:
        logger.error(f"❌ Environment validation failed: {e}")
        logger.error("   Check Railway environment variables for malformed JSON or missing values")
        # Don't raise - let app start but warn loudly
        pass
    logger.info("=" * 60)
    logger.info("")

    # Start HYPE scheduler
    logger.info("Starting HYPE scheduler...")
    try:
        start_hype_scheduler()
        logger.info("HYPE scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start HYPE scheduler: {e}")
        logger.warning("Continuing startup despite scheduler failure - app will function without HYPE updates")
        # Don't re-raise - allow app to start even if scheduler fails
        # This prevents healthcheck failures when DB tables are missing
        pass


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("Stopping HYPE scheduler...")
    try:
        stop_hype_scheduler()
        logger.info("HYPE scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping HYPE scheduler: {e}")