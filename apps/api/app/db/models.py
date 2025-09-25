from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # OAuth fields
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    profile_picture: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Privacy and consent fields
    privacy_policy_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    privacy_policy_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    data_processing_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_processing_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    marketing_emails_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # User preferences (JSON stored as text)
    preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationship to sessions
    sessions: Mapped[list["UserSession"]] = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship to user
    user: Mapped["User"] = relationship("User", back_populates="sessions")