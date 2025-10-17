"""
HYPE Feature Models - Track media and social interactions for players
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Text, Boolean, UniqueConstraint
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
    total_mentions_14d = Column(Integer, default=0)
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
    search_trends = relationship("SearchTrend", back_populates="player_hype")


class SocialMention(Base):
    """Track individual social media mentions"""
    __tablename__ = 'social_mentions'
    __table_args__ = (
        # Composite unique constraint: same post can mention multiple players
        # but each player can only have the post once
        UniqueConstraint('post_id', 'player_hype_id', name='uq_social_mention_player'),
    )

    id = Column(Integer, primary_key=True, index=True)
    player_hype_id = Column(Integer, ForeignKey('player_hype.id'))

    # Source information
    platform = Column(String, nullable=False)  # twitter, reddit, instagram, tiktok
    post_id = Column(String, nullable=False)  # Removed unique=True, now uses composite constraint
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
    __table_args__ = (
        # Composite unique constraint: same article can be linked to multiple players
        # but each player can only have the article once
        UniqueConstraint('url', 'player_hype_id', name='uq_media_article_player'),
    )

    id = Column(Integer, primary_key=True, index=True)
    player_hype_id = Column(Integer, ForeignKey('player_hype.id'))

    # Article information
    source = Column(String, nullable=False)  # ESPN, MLB.com, etc.
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)  # Removed unique=True, now uses composite constraint
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


class SearchTrend(Base):
    """Track Google Trends search interest data for players"""
    __tablename__ = 'search_trends'

    id = Column(Integer, primary_key=True, index=True)
    player_hype_id = Column(Integer, ForeignKey('player_hype.id'))

    # Search metrics
    search_interest = Column(Float, nullable=False)  # 0-100 score from Google Trends
    search_interest_avg_7d = Column(Float, default=0.0)  # 7-day average
    search_interest_avg_30d = Column(Float, default=0.0)  # 30-day average
    search_growth_rate = Column(Float, default=0.0)  # Percentage change

    # Geographic data
    region = Column(String, default='US')  # Geographic region
    regional_interest = Column(JSON)  # Regional breakdown (state/country level)

    # Related data
    related_queries = Column(JSON)  # Top related search queries
    rising_queries = Column(JSON)  # Breakout/rising search queries

    # Metadata
    collected_at = Column(DateTime, default=datetime.utcnow)
    data_period_start = Column(DateTime)  # Start of the trend data period
    data_period_end = Column(DateTime)  # End of the trend data period

    # Relationships
    player_hype = relationship("PlayerHype", back_populates="search_trends")