"""
Support System Endpoints

Handles support tickets and feature requests with priority routing for premium users.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from app.api.deps import get_current_user, subscription_tier_required
from app.db.database import get_db
from app.db.models import User
from app.db.models_support import SupportTicket, FeatureRequest
from app.services.support_service import SupportService
from app.core.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateTicketRequest(BaseModel):
    """Request model for creating support ticket."""
    subject: str = Field(..., min_length=1, max_length=200, description="Ticket subject")
    description: str = Field(..., min_length=10, description="Detailed description")
    category: str = Field(..., description="Category: technical, billing, feature_request, general, security, payment_issue, bug_report")


class TicketMessageRequest(BaseModel):
    """Request model for adding ticket message."""
    message: str = Field(..., min_length=1, description="Message content")


class ResolveTicketRequest(BaseModel):
    """Request model for resolving ticket."""
    resolution_notes: str = Field(..., description="Resolution details")


class CreateFeatureRequest(BaseModel):
    """Request model for creating feature request."""
    title: str = Field(..., min_length=1, max_length=200, description="Feature title")
    description: str = Field(..., min_length=10, description="Detailed description")
    category: str = Field(..., description="Category: ui, data, ml, integration, performance")


class TicketResponse(BaseModel):
    """Response model for support ticket."""
    id: int
    subject: str
    description: str
    status: str
    priority: str
    category: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    response_time_minutes: Optional[int] = None
    messages_count: int = 0


class FeatureRequestResponse(BaseModel):
    """Response model for feature request."""
    id: int
    title: str
    description: str
    category: str
    status: str
    priority: Optional[str]
    vote_count: int
    created_at: datetime
    updated_at: datetime
    planned_release: Optional[str]
    user_voted: bool = False


@router.post("/tickets", response_model=TicketResponse)
@limiter.limit("10/hour")
async def create_support_ticket(
    request: CreateTicketRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TicketResponse:
    """
    Create a new support ticket.

    Features:
    - Auto-prioritization based on user tier
    - Premium users get high priority
    - Email confirmation sent
    - Support team notified for urgent tickets
    """
    # Get user from database
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Validate category
    valid_categories = ["technical", "billing", "feature_request", "general", "security", "payment_issue", "bug_report"]
    if request.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )

    try:
        ticket = await SupportService.create_support_ticket(
            db=db,
            user_id=user.id,
            subject=request.subject,
            description=request.description,
            category=request.category
        )

        return TicketResponse(
            id=ticket.id,
            subject=ticket.subject,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            category=ticket.category,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            resolved_at=ticket.resolved_at,
            response_time_minutes=ticket.response_time_minutes,
            messages_count=len(ticket.messages) if hasattr(ticket, "messages") else 0
        )

    except Exception as e:
        logger.error(f"Failed to create ticket: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create support ticket"
        )


@router.get("/tickets", response_model=List[TicketResponse])
@limiter.limit("100/minute")
async def get_user_tickets(
    status: Optional[str] = Query(None, description="Filter by status: open, in_progress, resolved, closed"),
    limit: int = Query(50, ge=1, le=100, description="Maximum tickets to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[TicketResponse]:
    """
    Get user's support tickets.

    Returns:
        List of support tickets for the current user
    """
    # Get user from database
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    tickets = await SupportService.get_user_tickets(
        db=db,
        user_id=user.id,
        status=status,
        limit=limit
    )

    return [
        TicketResponse(
            id=ticket.id,
            subject=ticket.subject,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            category=ticket.category,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            resolved_at=ticket.resolved_at,
            response_time_minutes=ticket.response_time_minutes,
            messages_count=len(ticket.messages) if hasattr(ticket, "messages") else 0
        )
        for ticket in tickets
    ]


@router.post("/tickets/{ticket_id}/messages")
@limiter.limit("50/hour")
async def add_ticket_message(
    ticket_id: int,
    request: TicketMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Add a message to a support ticket.

    Args:
        ticket_id: Support ticket ID
        request: Message content

    Returns:
        Success message
    """
    # Get user from database
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        await SupportService.add_ticket_message(
            db=db,
            ticket_id=ticket_id,
            user_id=user.id,
            message=request.message,
            is_support_response=False
        )

        return {"message": "Message added successfully"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to add message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add message"
        )


@router.post("/feature-requests", response_model=FeatureRequestResponse)
@limiter.limit("5/day")
@subscription_tier_required("premium")
async def create_feature_request(
    request: CreateFeatureRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FeatureRequestResponse:
    """
    Create a feature request (Premium only).

    Features:
    - Premium users only
    - Automatically vote for own request
    - Categorized for better organization
    """
    # Get user from database
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Validate category
    valid_categories = ["ui", "data", "ml", "integration", "performance"]
    if request.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )

    try:
        feature_request = await SupportService.create_feature_request(
            db=db,
            user_id=user.id,
            title=request.title,
            description=request.description,
            category=request.category
        )

        return FeatureRequestResponse(
            id=feature_request.id,
            title=feature_request.title,
            description=feature_request.description,
            category=feature_request.category,
            status=feature_request.status,
            priority=feature_request.priority,
            vote_count=feature_request.vote_count,
            created_at=feature_request.created_at,
            updated_at=feature_request.updated_at,
            planned_release=feature_request.planned_release,
            user_voted=True  # Creator always votes for their request
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create feature request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create feature request"
        )


@router.post("/feature-requests/{request_id}/vote")
@limiter.limit("50/day")
@subscription_tier_required("premium")
async def vote_for_feature(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Vote for a feature request (Premium only).

    Features:
    - Premium users only
    - One vote per user per feature
    - Updates vote count

    Returns:
        Vote status and current count
    """
    # Get user from database
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        success = await SupportService.vote_for_feature(
            db=db,
            user_id=user.id,
            feature_request_id=request_id
        )

        if not success:
            return {
                "voted": False,
                "message": "You have already voted for this feature"
            }

        # Get updated vote count
        from app.db.models_support import FeatureRequest
        feature_query = select(FeatureRequest).where(FeatureRequest.id == request_id)
        feature_result = await db.execute(feature_query)
        feature = feature_result.scalar_one_or_none()

        return {
            "voted": True,
            "message": "Vote added successfully",
            "current_votes": feature.vote_count if feature else 0
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to vote: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to vote for feature"
        )


@router.get("/feature-requests", response_model=List[FeatureRequestResponse])
@limiter.limit("100/minute")
async def get_feature_requests(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    sort_by: str = Query("votes", regex="^(votes|created|updated)$", description="Sort field"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[FeatureRequestResponse]:
    """
    Get feature requests with optional filtering.

    Features:
    - View all feature requests
    - Filter by category and status
    - Sort by votes, creation date, or update date
    """
    # Get user to check votes
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    feature_requests = await SupportService.get_feature_requests(
        db=db,
        category=category,
        status=status,
        sort_by=sort_by,
        limit=limit
    )

    # Check which features user has voted for
    user_voted_ids = set()
    if user:
        from app.db.models_support import FeatureVote
        votes_query = select(FeatureVote.feature_request_id).where(
            FeatureVote.user_id == user.id
        )
        votes_result = await db.execute(votes_query)
        user_voted_ids = {row for row in votes_result.scalars()}

    return [
        FeatureRequestResponse(
            id=fr.id,
            title=fr.title,
            description=fr.description,
            category=fr.category,
            status=fr.status,
            priority=fr.priority,
            vote_count=fr.vote_count,
            created_at=fr.created_at,
            updated_at=fr.updated_at,
            planned_release=fr.planned_release,
            user_voted=fr.id in user_voted_ids
        )
        for fr in feature_requests
    ]


@router.get("/support/metrics")
@limiter.limit("10/minute")
async def get_support_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get support system metrics.

    Features:
    - Total tickets and resolution rates
    - Average response times
    - Tickets by priority
    """
    # Verify user is admin or premium
    from sqlalchemy import select
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or user.subscription_tier not in ["premium", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Metrics access requires premium subscription"
        )

    metrics = await SupportService.get_support_metrics(
        db=db,
        days=days
    )

    return metrics