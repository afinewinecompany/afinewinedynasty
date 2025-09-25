from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="A Fine Wine Dynasty API",
        version="0.1.0"
    )


@router.get("/detailed")
async def detailed_health_check():
    return {
        "status": "healthy",
        "service": "A Fine Wine Dynasty API",
        "version": "0.1.0",
        "uptime": "N/A",
        "database": "Not configured",
        "redis": "Not configured"
    }