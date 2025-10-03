"""Support system database models."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Boolean, DateTime, String, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class SupportTicket(Base):
    """Support ticket records with priority for premium users."""
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)  # open, in_progress, resolved, closed
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)  # low, medium, high, urgent
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # technical, billing, feature_request, general
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Support agent name/email
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    response_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="support_tickets")
    messages: Mapped[List["TicketMessage"]] = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")


class TicketMessage(Base):
    """Messages within support tickets."""
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("support_tickets.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_support_response: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    ticket: Mapped["SupportTicket"] = relationship("SupportTicket", back_populates="messages")
    user: Mapped["User"] = relationship("User", back_populates="ticket_messages")


class FeatureRequest(Base):
    """Feature requests with voting system for premium users."""
    __tablename__ = "feature_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # ui, data, ml, integration, performance
    status: Mapped[str] = mapped_column(String(50), default="submitted", nullable=False)  # submitted, reviewing, planned, in_progress, implemented, declined
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # low, medium, high (set by admin)
    vote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    implementation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    planned_release: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Version or date

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="feature_requests")
    votes: Mapped[List["FeatureVote"]] = relationship("FeatureVote", back_populates="feature_request", cascade="all, delete-orphan")


class FeatureVote(Base):
    """Votes on feature requests (premium users only)."""
    __tablename__ = "feature_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    feature_request_id: Mapped[int] = mapped_column(Integer, ForeignKey("feature_requests.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # Unique constraint to prevent duplicate votes
    __table_args__ = (
        UniqueConstraint('feature_request_id', 'user_id', name='unique_feature_vote'),
    )

    # Relationships
    feature_request: Mapped["FeatureRequest"] = relationship("FeatureRequest", back_populates="votes")
    user: Mapped["User"] = relationship("User", back_populates="feature_votes")