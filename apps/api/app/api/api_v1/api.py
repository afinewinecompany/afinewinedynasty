from fastapi import APIRouter

from app.api.api_v1.endpoints import health, auth, prospects, users, admin, ml_predictions, monitoring, search, discovery, notifications, subscriptions, webhooks, fantrax, recommendations

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(prospects.router, prefix="/prospects", tags=["prospects"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(discovery.router, prefix="/discovery", tags=["discovery"])
api_router.include_router(ml_predictions.router, prefix="/ml", tags=["ml-predictions"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(fantrax.router, prefix="/integrations/fantrax", tags=["fantrax"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])