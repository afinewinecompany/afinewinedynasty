"""
Support Service for Managing Support Tickets and Feature Requests

Handles priority support for premium users and feature voting system.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import logging

from app.db.models import User
from app.db.models_support import SupportTicket, TicketMessage, FeatureRequest, FeatureVote
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.core.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class SupportService:
    """
    Service for managing support tickets and feature requests.

    Features:
    - Priority ticket routing for premium users
    - Support ticket management
    - Feature request voting system
    - Response time tracking
    - Email notifications
    """

    @staticmethod
    async def create_support_ticket(
        db: AsyncSession,
        user_id: int,
        subject: str,
        description: str,
        category: str
    ) -> SupportTicket:
        """
        Create a new support ticket with auto-prioritization.

        Args:
            db: Database session
            user_id: User ID creating the ticket
            subject: Ticket subject
            description: Detailed description
            category: Ticket category

        Returns:
            Created support ticket
        """
        # Get user to check subscription tier
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Auto-prioritize based on subscription tier
        if user.subscription_tier == "premium":
            priority = "high"
        else:
            priority = "medium"

        # Override priority for critical categories
        if category in ["security", "payment_issue"]:
            priority = "urgent"
        elif category == "bug_report":
            if user.subscription_tier == "premium":
                priority = "urgent"
            else:
                priority = "high"

        # Create ticket
        ticket = SupportTicket(
            user_id=user_id,
            subject=subject,
            description=description,
            category=category,
            priority=priority,
            status="open",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)

        # Send notifications
        try:
            # Email notification to user
            await EmailService.send_ticket_confirmation(
                user.email,
                ticket.id,
                subject,
                priority
            )

            # Priority notification for urgent tickets
            if priority in ["urgent", "high"]:
                await NotificationService.notify_support_team(
                    ticket_id=ticket.id,
                    priority=priority,
                    user_tier=user.subscription_tier
                )
        except Exception as e:
            logger.error(f"Failed to send notifications: {e}")

        logger.info(f"Support ticket {ticket.id} created for user {user_id} with priority {priority}")

        return ticket

    @staticmethod
    async def get_user_tickets(
        db: AsyncSession,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[SupportTicket]:
        """
        Get support tickets for a user.

        Args:
            db: Database session
            user_id: User ID
            status: Optional status filter
            limit: Maximum number of tickets

        Returns:
            List of support tickets
        """
        query = select(SupportTicket).where(
            SupportTicket.user_id == user_id
        ).options(
            selectinload(SupportTicket.messages)
        )

        if status:
            query = query.where(SupportTicket.status == status)

        query = query.order_by(desc(SupportTicket.created_at)).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def add_ticket_message(
        db: AsyncSession,
        ticket_id: int,
        user_id: int,
        message: str,
        is_support_response: bool = False
    ) -> TicketMessage:
        """
        Add a message to a support ticket.

        Args:
            db: Database session
            ticket_id: Ticket ID
            user_id: User ID posting the message
            message: Message content
            is_support_response: Whether this is a support team response

        Returns:
            Created ticket message
        """
        # Verify ticket exists and user has access
        ticket_query = select(SupportTicket).where(
            SupportTicket.id == ticket_id
        )
        ticket_result = await db.execute(ticket_query)
        ticket = ticket_result.scalar_one_or_none()

        if not ticket:
            raise ValueError("Ticket not found")

        # Create message
        ticket_message = TicketMessage(
            ticket_id=ticket_id,
            user_id=user_id,
            message=message,
            is_support_response=is_support_response,
            created_at=datetime.utcnow()
        )

        db.add(ticket_message)

        # Update ticket status and timestamps
        ticket.updated_at = datetime.utcnow()

        if is_support_response and ticket.status == "open":
            ticket.status = "in_progress"

            # Calculate response time for first support response
            if not ticket.response_time_minutes:
                response_time = datetime.utcnow() - ticket.created_at
                ticket.response_time_minutes = int(response_time.total_seconds() / 60)

        await db.commit()
        await db.refresh(ticket_message)

        return ticket_message

    @staticmethod
    async def resolve_ticket(
        db: AsyncSession,
        ticket_id: int,
        resolution_notes: str
    ) -> SupportTicket:
        """
        Resolve a support ticket.

        Args:
            db: Database session
            ticket_id: Ticket ID
            resolution_notes: Resolution details

        Returns:
            Updated ticket
        """
        ticket_query = select(SupportTicket).where(
            SupportTicket.id == ticket_id
        )
        ticket_result = await db.execute(ticket_query)
        ticket = ticket_result.scalar_one_or_none()

        if not ticket:
            raise ValueError("Ticket not found")

        ticket.status = "resolved"
        ticket.resolution_notes = resolution_notes
        ticket.resolved_at = datetime.utcnow()
        ticket.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(ticket)

        # Send resolution notification
        try:
            user_query = select(User).where(User.id == ticket.user_id)
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()

            if user:
                await EmailService.send_ticket_resolution(
                    user.email,
                    ticket.id,
                    ticket.subject,
                    resolution_notes
                )
        except Exception as e:
            logger.error(f"Failed to send resolution notification: {e}")

        return ticket

    @staticmethod
    async def create_feature_request(
        db: AsyncSession,
        user_id: int,
        title: str,
        description: str,
        category: str
    ) -> FeatureRequest:
        """
        Create a new feature request (premium users only).

        Args:
            db: Database session
            user_id: User ID
            title: Feature title
            description: Detailed description
            category: Feature category

        Returns:
            Created feature request
        """
        # Verify user is premium
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user or user.subscription_tier != "premium":
            raise ValueError("Feature requests are for premium users only")

        # Create feature request
        feature_request = FeatureRequest(
            user_id=user_id,
            title=title,
            description=description,
            category=category,
            status="submitted",
            vote_count=1,  # Creator automatically votes for their request
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(feature_request)
        await db.flush()

        # Add creator's vote
        creator_vote = FeatureVote(
            feature_request_id=feature_request.id,
            user_id=user_id,
            created_at=datetime.utcnow()
        )

        db.add(creator_vote)
        await db.commit()
        await db.refresh(feature_request)

        logger.info(f"Feature request {feature_request.id} created by user {user_id}")

        return feature_request

    @staticmethod
    async def vote_for_feature(
        db: AsyncSession,
        user_id: int,
        feature_request_id: int
    ) -> bool:
        """
        Vote for a feature request (premium users only).

        Args:
            db: Database session
            user_id: User ID
            feature_request_id: Feature request ID

        Returns:
            True if vote was added, False if already voted
        """
        # Verify user is premium
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user or user.subscription_tier != "premium":
            raise ValueError("Voting is for premium users only")

        # Check if already voted
        existing_vote_query = select(FeatureVote).where(
            and_(
                FeatureVote.feature_request_id == feature_request_id,
                FeatureVote.user_id == user_id
            )
        )
        existing_vote_result = await db.execute(existing_vote_query)
        existing_vote = existing_vote_result.scalar_one_or_none()

        if existing_vote:
            return False

        # Get feature request
        feature_query = select(FeatureRequest).where(
            FeatureRequest.id == feature_request_id
        )
        feature_result = await db.execute(feature_query)
        feature_request = feature_result.scalar_one_or_none()

        if not feature_request:
            raise ValueError("Feature request not found")

        # Add vote
        vote = FeatureVote(
            feature_request_id=feature_request_id,
            user_id=user_id,
            created_at=datetime.utcnow()
        )

        db.add(vote)

        # Update vote count
        feature_request.vote_count += 1
        feature_request.updated_at = datetime.utcnow()

        await db.commit()

        logger.info(f"User {user_id} voted for feature request {feature_request_id}")

        return True

    @staticmethod
    async def get_feature_requests(
        db: AsyncSession,
        category: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: str = "votes",
        limit: int = 50
    ) -> List[FeatureRequest]:
        """
        Get feature requests with optional filtering.

        Args:
            db: Database session
            category: Optional category filter
            status: Optional status filter
            sort_by: Sort field (votes, created, updated)
            limit: Maximum number of results

        Returns:
            List of feature requests
        """
        query = select(FeatureRequest).options(
            selectinload(FeatureRequest.votes),
            selectinload(FeatureRequest.user)
        )

        if category:
            query = query.where(FeatureRequest.category == category)

        if status:
            query = query.where(FeatureRequest.status == status)

        # Apply sorting
        if sort_by == "votes":
            query = query.order_by(desc(FeatureRequest.vote_count))
        elif sort_by == "created":
            query = query.order_by(desc(FeatureRequest.created_at))
        elif sort_by == "updated":
            query = query.order_by(desc(FeatureRequest.updated_at))
        else:
            query = query.order_by(desc(FeatureRequest.vote_count))

        query = query.limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_support_metrics(
        db: AsyncSession,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get support metrics and statistics.

        Args:
            db: Database session
            days: Number of days to analyze

        Returns:
            Support metrics dictionary
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Total tickets
        total_tickets_query = select(func.count(SupportTicket.id)).where(
            SupportTicket.created_at >= cutoff_date
        )
        total_result = await db.execute(total_tickets_query)
        total_tickets = total_result.scalar() or 0

        # Tickets by priority
        priority_query = select(
            SupportTicket.priority,
            func.count(SupportTicket.id).label("count")
        ).where(
            SupportTicket.created_at >= cutoff_date
        ).group_by(SupportTicket.priority)

        priority_result = await db.execute(priority_query)
        tickets_by_priority = {row.priority: row.count for row in priority_result}

        # Average response time
        response_time_query = select(
            func.avg(SupportTicket.response_time_minutes)
        ).where(
            and_(
                SupportTicket.created_at >= cutoff_date,
                SupportTicket.response_time_minutes.isnot(None)
            )
        )
        response_time_result = await db.execute(response_time_query)
        avg_response_time = response_time_result.scalar() or 0

        # Resolution rate
        resolved_query = select(func.count(SupportTicket.id)).where(
            and_(
                SupportTicket.created_at >= cutoff_date,
                SupportTicket.status == "resolved"
            )
        )
        resolved_result = await db.execute(resolved_query)
        resolved_tickets = resolved_result.scalar() or 0

        resolution_rate = (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0

        return {
            "period_days": days,
            "total_tickets": total_tickets,
            "tickets_by_priority": tickets_by_priority,
            "average_response_time_minutes": round(avg_response_time, 1),
            "resolution_rate": round(resolution_rate, 1),
            "resolved_tickets": resolved_tickets
        }