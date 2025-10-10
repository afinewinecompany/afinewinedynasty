"""
HYPE Feature Models - Track media and social interactions for players
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base


class PlayerHype(Base):
    """Core HYPE tracking model for players"""
    __tablename__ = 'player_hype'

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(String, index=True, nullable=False)  # Can be prospect_id or MLB player ID
    player_name = Column(String, nullable=False)
    player_type = Column(String, nullable=False)  # 'prospect' or 'mlb'

    # Core HYPE metrics
    hype_score = Column(Float, default=0.0)  # 0-100 score
    hype_trend = Column(Float, default=0.0)  # -100 to +100 (momentum)
    sentiment_score = Column(Float, default=0.0)  # -1 to 1
    virality_score = Column(Float, default=0.0)  # 0-100

    # Volume metrics
    total_mentions_24h = Column(Integer, default=0)
    total_mentions_7d = Column(Integer, default=0)
    total_mentions_30d = Column(Integer, default=0)

    # Engagement metrics
    total_likes = Column(Integer, default=0)
    total_shares = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)

    # Metadata
    last_calculated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    social_mentions = relationship("SocialMention", back_populates="player_hype")
    media_articles = relationship("MediaArticle", back_populates="player_hype")
    hype_history = relationship("HypeHistory", back_populates="player_hype")


class SocialMention(Base):
    """Track individual social media mentions"""
    __tablename__ = 'social_mentions'

    id = Column(Integer, primary_key=True, index=True)
    player_hype_id = Column(Integer, ForeignKey('player_hype.id'))

    # Source information
    platform = Column(String, nullable=False)  # twitter, reddit, instagram, tiktok
    post_id = Column(String, unique=True, nullable=False)
    author_handle = Column(String)
    author_followers = Column(Integer, default=0)

    # Content
    content = Column(Text)
    url = Column(String)
    media_urls = Column(JSON)  # Array of image/video URLs
    hashtags = Column(JSON)  # Array of hashtags

    # Metrics
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    views = Column(Integer, default=0)

    # Sentiment analysis
    sentiment = Column(String)  # positive, negative, neutral
    sentiment_confidence = Column(Float)
    keywords = Column(JSON)  # Extracted keywords

    # Timestamps
    posted_at = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    player_hype = relationship("PlayerHype", back_populates="social_mentions")


class MediaArticle(Base):
    """Track media articles and news coverage"""
    __tablename__ = 'media_articles'

    id = Column(Integer, primary_key=True, index=True)
    player_hype_id = Column(Integer, ForeignKey('player_hype.id'))

    # Article information
    source = Column(String, nullable=False)  # ESPN, MLB.com, etc.
    title = Column(String, nullable=False)
    url = Column(String, unique=True, nullable=False)
    author = Column(String)

    # Content analysis
    summary = Column(Text)
    sentiment = Column(String)  # positive, negative, neutral
    sentiment_confidence = Column(Float)
    prominence_score = Column(Float)  # How prominently featured is the player

    # Metadata
    published_at = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    player_hype = relationship("PlayerHype", back_populates="media_articles")


class HypeHistory(Base):
    """Historical tracking of HYPE scores"""
    __tablename__ = 'hype_history'

    id = Column(Integer, primary_key=True, index=True)
    player_hype_id = Column(Integer, ForeignKey('player_hype.id'))

    # Snapshot data
    hype_score = Column(Float, nullable=False)
    sentiment_score = Column(Float, nullable=False)
    virality_score = Column(Float, nullable=False)
    total_mentions = Column(Integer, nullable=False)

    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    granularity = Column(String, nullable=False)  # hourly, daily, weekly

    # Relationships
    player_hype = relationship("PlayerHype", back_populates="hype_history")


class HypeAlert(Base):
    """Alerts for significant HYPE changes"""
    __tablename__ = 'hype_alerts'

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(String, index=True, nullable=False)

    # Alert details
    alert_type = Column(String, nullable=False)  # surge, crash, trending, viral
    severity = Column(String, nullable=False)  # low, medium, high, critical
    title = Column(String, nullable=False)
    description = Column(Text)

    # Metrics at time of alert
    hype_score_before = Column(Float)
    hype_score_after = Column(Float)
    change_percentage = Column(Float)

    # Status
    is_active = Column(Boolean, default=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)


class TrendingTopic(Base):
    """Track trending topics related to players"""
    __tablename__ = 'trending_topics'

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(String, index=True, nullable=False)

    # Topic information
    topic = Column(String, nullable=False)
    topic_type = Column(String)  # injury, performance, trade, scandal, achievement

    # Metrics
    mention_count = Column(Integer, default=0)
    engagement_total = Column(Integer, default=0)
    sentiment_average = Column(Float, default=0.0)

    # Time window
    started_trending = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)