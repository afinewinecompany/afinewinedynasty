from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import logging

from app.api import deps
from app.db.database import get_db
from app.services.data_ingestion_service import DataIngestionService
from app.db.models import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/data-refresh")
async def trigger_manual_data_refresh(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Manually trigger data refresh for development and testing.
    Requires admin privileges.
    """
    # Check if user has admin privileges (assuming subscription_tier == "admin" indicates admin)
    if not current_user.subscription_tier or current_user.subscription_tier != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    try:
        ingestion_service = DataIngestionService(db)

        # Execute manual data ingestion
        await ingestion_service.ingest_daily_data()

        logger.info(f"Manual data refresh triggered by user {current_user.id}")

        return {
            "status": "success",
            "message": "Data refresh completed successfully",
            "triggered_by": current_user.email
        }

    except Exception as e:
        logger.error(f"Manual data refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data refresh failed: {str(e)}"
        )


@router.post("/data-refresh/{prospect_id}")
async def trigger_prospect_data_refresh(
    prospect_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Manually trigger data refresh for a specific prospect.
    Requires admin privileges.
    """
    # Check if user has admin privileges
    if not current_user.subscription_tier or current_user.subscription_tier != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    try:
        ingestion_service = DataIngestionService(db)

        # Execute prospect-specific data refresh
        success = await ingestion_service.refresh_prospect_data(prospect_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prospect {prospect_id} not found or refresh failed"
            )

        logger.info(f"Prospect {prospect_id} data refresh triggered by user {current_user.id}")

        return {
            "status": "success",
            "message": f"Data refresh for prospect {prospect_id} completed successfully",
            "prospect_id": prospect_id,
            "triggered_by": current_user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prospect {prospect_id} data refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prospect data refresh failed: {str(e)}"
        )