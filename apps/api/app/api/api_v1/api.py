from fastapi import APIRouter

from app.api.api_v1.endpoints import health, auth, prospects, users

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(prospects.router, prefix="/prospects", tags=["prospects"])