from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api_v1.api import api_router
from app.core.config import settings
from app.core.rate_limiter import setup_rate_limiter
from app.middleware.security_middleware import add_security_middleware

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

# CORS MUST be added FIRST - before rate limiting and security middleware
# This ensures OPTIONS preflight requests are handled correctly
cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["X-Total-Count"],
)

# Setup rate limiting (after CORS)
app = setup_rate_limiter(app)

# Add security middleware (after CORS)
app = add_security_middleware(app)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "A Fine Wine Dynasty API", "version": settings.VERSION}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api"}