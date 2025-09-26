from fastapi import APIRouter

from app.api.api_v1.endpoints import health, auth, prospects, users, admin, ml_predictions, monitoring

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(prospects.router, prefix="/prospects", tags=["prospects"])
api_router.include_router(ml_predictions.router, prefix="/ml", tags=["ml-predictions"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])