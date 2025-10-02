from datetime import datetime, date
from typing import Optional
from sqlalchemy import Boolean, DateTime, String, Integer, Text, ForeignKey, CheckConstraint, Float, Date, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # OAuth fields
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    profile_picture: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Privacy and consent fields
    privacy_policy_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    privacy_policy_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    data_processing_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_processing_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    marketing_emails_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Subscription management
    subscription_tier: Mapped[str] = mapped_column(String(20), default='free', nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    fantrax_user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    fantrax_refresh_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # User preferences (JSONB)
    preferences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default={})

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationship to sessions
    sessions: Mapped[list["UserSession"]] = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    # Subscription relationships
    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="user", uselist=False)
    payment_methods: Mapped[list["PaymentMethod"]] = relationship("PaymentMethod", back_populates="user", cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "subscription_tier IN ('free', 'premium')",
            name='valid_subscription_tier'
        ),
    )


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


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mlb_id: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[str] = mapped_column(String(10), nullable=False)
    organization: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    eta_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    stats: Mapped[list["ProspectStats"]] = relationship("ProspectStats", back_populates="prospect", cascade="all, delete-orphan")
    scouting_grades: Mapped[list["ScoutingGrades"]] = relationship("ScoutingGrades", back_populates="prospect", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "position IN ('C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'SP', 'RP')",
            name='valid_position'
        ),
        CheckConstraint("age > 0 AND age < 50", name='valid_age'),
        CheckConstraint("eta_year >= 2024 AND eta_year <= 2035", name='valid_eta_year'),
    )


class ProspectStats(Base):
    __tablename__ = "prospect_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prospect_id: Mapped[int] = mapped_column(Integer, ForeignKey("prospects.id"), nullable=False)
    date_recorded: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)

    # Hitting statistics
    games_played: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    at_bats: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hits: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    home_runs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rbi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stolen_bases: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    walks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    strikeouts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    batting_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    on_base_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    slugging_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Pitching statistics
    innings_pitched: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    earned_runs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    era: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    whip: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    strikeouts_per_nine: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    walks_per_nine: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Performance metrics
    woba: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wrc_plus: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    prospect: Mapped["Prospect"] = relationship("Prospect", back_populates="stats")

    __table_args__ = (
        CheckConstraint("season >= 2020 AND season <= 2035", name='valid_season'),
        CheckConstraint("games_played >= 0", name='valid_games_played'),
        CheckConstraint("at_bats >= 0", name='valid_at_bats'),
        CheckConstraint("hits >= 0", name='valid_hits'),
        CheckConstraint("batting_avg >= 0.0 AND batting_avg <= 1.0", name='valid_batting_avg'),
        CheckConstraint("era >= 0.0", name='valid_era'),
    )


class ScoutingGrades(Base):
    __tablename__ = "scouting_grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prospect_id: Mapped[int] = mapped_column(Integer, ForeignKey("prospects.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Overall grade
    overall: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Hitting grades (for position players)
    hit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    run: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    field: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    throw: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Pitching grades (for pitchers)
    fastball: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    curveball: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slider: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    changeup: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    control: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Future Value (common scale)
    future_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Risk assessment
    risk: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    prospect: Mapped["Prospect"] = relationship("Prospect", back_populates="scouting_grades")

    __table_args__ = (
        CheckConstraint(
            "source IN ('Fangraphs', 'MLB Pipeline', 'Baseball America', 'Baseball Prospectus')",
            name='valid_source'
        ),
        CheckConstraint("overall >= 20 AND overall <= 80", name='valid_overall'),
        CheckConstraint("hit >= 20 AND hit <= 80", name='valid_hit'),
        CheckConstraint("power >= 20 AND power <= 80", name='valid_power'),
        CheckConstraint("run >= 20 AND run <= 80", name='valid_run'),
        CheckConstraint("field >= 20 AND field <= 80", name='valid_field'),
        CheckConstraint("throw >= 20 AND throw <= 80", name='valid_throw'),
        CheckConstraint("future_value >= 20 AND future_value <= 80", name='valid_future_value'),
        CheckConstraint(
            "risk IN ('Safe', 'Moderate', 'High', 'Extreme')",
            name='valid_risk'
        ),
    )


class MLPrediction(Base):
    """Placeholder table for future ML prediction features"""
    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prospect_id: Mapped[int] = mapped_column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prediction_value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    prospect: Mapped["Prospect"] = relationship("Prospect")

    __table_args__ = (
        CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0", name='valid_confidence_score'),
        CheckConstraint(
            "prediction_type IN ('career_war', 'debut_probability', 'success_rating')",
            name='valid_prediction_type'
        ),
    )


class UserSavedSearch(Base):
    """User saved search criteria storage."""
    __tablename__ = "user_saved_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    search_name: Mapped[str] = mapped_column(String(100), nullable=False)
    search_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    last_used: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")


class UserSearchHistory(Base):
    """User search history tracking."""
    __tablename__ = "user_search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    search_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    search_criteria: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    results_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    searched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")


class UserProspectView(Base):
    """User prospect view tracking."""
    __tablename__ = "user_prospect_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    prospect_id: Mapped[int] = mapped_column(Integer, ForeignKey("prospects.id"), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    view_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # seconds

    # Relationships
    user: Mapped["User"] = relationship("User")
    prospect: Mapped["Prospect"] = relationship("Prospect")


class UserPushSubscription(Base):
    __tablename__ = "user_push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    p256dh_key: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_key: Mapped[str] = mapped_column(String(255), nullable=False)
    device_info: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")


class Subscription(Base):
    """User subscription data synchronized from Stripe."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # active, past_due, unpaid, canceled, trialing
    plan_id: Mapped[str] = mapped_column(String(100), nullable=False)  # free, premium
    current_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscription")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="subscription", cascade="all, delete-orphan")
    events: Mapped[list["SubscriptionEvent"]] = relationship("SubscriptionEvent", back_populates="subscription", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'past_due', 'unpaid', 'canceled', 'trialing', 'incomplete')",
            name='valid_subscription_status'
        ),
        CheckConstraint(
            "plan_id IN ('free', 'premium')",
            name='valid_plan_id'
        ),
    )


class PaymentMethod(Base):
    """User payment methods from Stripe."""
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    stripe_payment_method_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    card_brand: Mapped[str] = mapped_column(String(50), nullable=False)  # visa, mastercard, amex
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    exp_month: Mapped[int] = mapped_column(Integer, nullable=False)
    exp_year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="payment_methods")


class Invoice(Base):
    """Stripe invoice records."""
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    stripe_invoice_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    subscription_id: Mapped[int] = mapped_column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    amount_paid: Mapped[int] = mapped_column(Integer, nullable=False)  # Amount in cents
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # paid, open, uncollectible, void
    billing_reason: Mapped[str] = mapped_column(String(100), nullable=False)  # subscription_create, subscription_cycle, etc.
    invoice_pdf: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # Stripe PDF URL
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="invoices")
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="invoices")


class SubscriptionEvent(Base):
    """Audit trail for subscription events."""
    __tablename__ = "subscription_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subscription_id: Mapped[int] = mapped_column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)  # created, updated, canceled, payment_failed, etc.
    stripe_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # Additional event data
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="events")


class PaymentAuditLog(Base):
    """PCI-compliant payment method audit log."""
    __tablename__ = "payment_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # added, updated, removed, failed
    payment_method_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)  # Last 4 digits only
    card_brand: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")