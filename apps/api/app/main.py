from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api_v1.api import api_router
from app.core.config import settings
from app.core.rate_limiter import setup_rate_limiter
from app.middleware.security_middleware import add_security_middleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="A Fine Wine Dynasty - Baseball Prospect Analysis Platform",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Setup rate limiting
app = setup_rate_limiter(app)

# Add security middleware
app = add_security_middleware(app)

# Set CORS with security restrictions
cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["X-Total-Count"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "A Fine Wine Dynasty API", "version": settings.VERSION}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api"}