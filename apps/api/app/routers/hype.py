"""
HYPE Feature API Routes
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel

from app.db.database import get_db
from app.models.hype import (
    PlayerHype, SocialMention, MediaArticle,
    HypeHistory, HypeAlert, TrendingTopic
)
from app.core.auth import get_current_user


router = APIRouter(prefix="/api/hype", tags=["hype"])


# Pydantic models
class HypeScoreResponse(BaseModel):
    player_id: str
    player_name: str
    player_type: str
    hype_score: float
    hype_trend: float
    sentiment_score: float
    virality_score: float
    total_mentions_24h: int
    total_mentions_7d: int
    engagement_rate: float
    last_calculated: datetime
    trending_topics: List[Dict[str, Any]]
    recent_alerts: List[Dict[str, Any]]


class HypeHistoryResponse(BaseModel):
    timestamp: datetime
    hype_score: float
    sentiment_score: float
    total_mentions: int


class SocialFeedItem(BaseModel):
    id: int
    platform: str
    author_handle: str
    content: str
    url: str
    likes: int
    shares: int
    sentiment: str
    posted_at: datetime


class MediaFeedItem(BaseModel):
    id: int
    source: str
    title: str
    url: str
    summary: str
    sentiment: str
    published_at: datetime


class HypeLeaderboardItem(BaseModel):
    rank: int
    player_id: str
    player_name: str
    hype_score: float
    change_24h: float
    change_7d: float
    sentiment: str


@router.get("/player/{player_id}", response_model=HypeScoreResponse)
async def get_player_hype(
    player_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get current HYPE data for a specific player"""

    player_hype = db.query(PlayerHype).filter(
        PlayerHype.player_id == player_id
    ).first()

    if not player_hype:
        raise HTTPException(status_code=404, detail="Player HYPE data not found")

    # Get trending topics
    trending_topics = db.query(TrendingTopic).filter(
        TrendingTopic.player_id == player_id,
        TrendingTopic.is_active == True
    ).order_by(desc(TrendingTopic.mention_count)).limit(5).all()

    # Get recent alerts
    recent_alerts = db.query(HypeAlert).filter(
        HypeAlert.player_id == player_id,
        HypeAlert.is_active == True
    ).order_by(desc(HypeAlert.created_at)).limit(3).all()

    return HypeScoreResponse(
        player_id=player_hype.player_id,
        player_name=player_hype.player_name,
        player_type=player_hype.player_type,
        hype_score=player_hype.hype_score,
        hype_trend=player_hype.hype_trend,
        sentiment_score=player_hype.sentiment_score,
        virality_score=player_hype.virality_score,
        total_mentions_24h=player_hype.total_mentions_24h,
        total_mentions_7d=player_hype.total_mentions_7d,
        engagement_rate=player_hype.engagement_rate,
        last_calculated=player_hype.last_calculated,
        trending_topics=[{
            "topic": t.topic,
            "type": t.topic_type,
            "mentions": t.mention_count,
            "sentiment": t.sentiment_average
        } for t in trending_topics],
        recent_alerts=[{
            "type": a.alert_type,
            "severity": a.severity,
            "title": a.title,
            "change": a.change_percentage,
            "created_at": a.created_at
        } for a in recent_alerts]
    )


@router.get("/player/{player_id}/history", response_model=List[HypeHistoryResponse])
async def get_hype_history(
    player_id: str,
    period: str = Query("7d", regex="^(24h|7d|30d|3m|1y)$"),
    granularity: str = Query("daily", regex="^(hourly|daily|weekly)$"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get historical HYPE data for a player"""

    # Calculate date range
    end_date = datetime.utcnow()
    if period == "24h":
        start_date = end_date - timedelta(days=1)
    elif period == "7d":
        start_date = end_date - timedelta(days=7)
    elif period == "30d":
        start_date = end_date - timedelta(days=30)
    elif period == "3m":
        start_date = end_date - timedelta(days=90)
    else:  # 1y
        start_date = end_date - timedelta(days=365)

    # Get history
    history = db.query(HypeHistory).filter(
        HypeHistory.player_hype_id == db.query(PlayerHype.id).filter(
            PlayerHype.player_id == player_id
        ).scalar_subquery(),
        HypeHistory.period_start >= start_date,
        HypeHistory.granularity == granularity
    ).order_by(HypeHistory.period_start).all()

    return [
        HypeHistoryResponse(
            timestamp=h.period_start,
            hype_score=h.hype_score,
            sentiment_score=h.sentiment_score,
            total_mentions=h.total_mentions
        ) for h in history
    ]


@router.get("/player/{player_id}/social-feed", response_model=List[SocialFeedItem])
async def get_social_feed(
    player_id: str,
    platform: Optional[str] = None,
    sentiment: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get recent social media mentions for a player"""

    query = db.query(SocialMention).join(PlayerHype).filter(
        PlayerHype.player_id == player_id
    )

    if platform:
        query = query.filter(SocialMention.platform == platform)

    if sentiment:
        query = query.filter(SocialMention.sentiment == sentiment)

    mentions = query.order_by(
        desc(SocialMention.posted_at)
    ).limit(limit).offset(offset).all()

    return [
        SocialFeedItem(
            id=m.id,
            platform=m.platform,
            author_handle=m.author_handle,
            content=m.content,
            url=m.url,
            likes=m.likes,
            shares=m.shares,
            sentiment=m.sentiment,
            posted_at=m.posted_at
        ) for m in mentions
    ]


@router.get("/player/{player_id}/media-feed", response_model=List[MediaFeedItem])
async def get_media_feed(
    player_id: str,
    source: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get recent media articles for a player"""

    query = db.query(MediaArticle).join(PlayerHype).filter(
        PlayerHype.player_id == player_id
    )

    if source:
        query = query.filter(MediaArticle.source == source)

    articles = query.order_by(
        desc(MediaArticle.published_at)
    ).limit(limit).offset(offset).all()

    return [
        MediaFeedItem(
            id=a.id,
            source=a.source,
            title=a.title,
            url=a.url,
            summary=a.summary,
            sentiment=a.sentiment,
            published_at=a.published_at
        ) for a in articles
    ]


@router.get("/leaderboard", response_model=List[HypeLeaderboardItem])
async def get_hype_leaderboard(
    player_type: Optional[str] = None,
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get HYPE leaderboard"""

    query = db.query(PlayerHype)

    if player_type:
        query = query.filter(PlayerHype.player_type == player_type)

    players = query.order_by(desc(PlayerHype.hype_score)).limit(limit).all()

    leaderboard = []
    for idx, player in enumerate(players, 1):
        # Calculate 24h and 7d changes (simplified - in production, query historical data)
        change_24h = player.hype_trend * 2.5  # Simplified calculation
        change_7d = player.hype_trend * 10  # Simplified calculation

        sentiment = "positive" if player.sentiment_score > 0.2 else (
            "negative" if player.sentiment_score < -0.2 else "neutral"
        )

        leaderboard.append(HypeLeaderboardItem(
            rank=idx,
            player_id=player.player_id,
            player_name=player.player_name,
            hype_score=player.hype_score,
            change_24h=change_24h,
            change_7d=change_7d,
            sentiment=sentiment
        ))

    return leaderboard


@router.get("/trending-players", response_model=List[Dict[str, Any]])
async def get_trending_players(
    timeframe: str = Query("24h", regex="^(1h|6h|24h|7d)$"),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get currently trending players based on HYPE momentum"""

    # Get players with highest positive trend
    trending = db.query(PlayerHype).filter(
        PlayerHype.hype_trend > 0
    ).order_by(desc(PlayerHype.hype_trend)).limit(limit).all()

    return [{
        "player_id": p.player_id,
        "player_name": p.player_name,
        "player_type": p.player_type,
        "hype_score": p.hype_score,
        "trend": p.hype_trend,
        "virality": p.virality_score,
        "mentions_24h": p.total_mentions_24h
    } for p in trending]


@router.post("/player/{player_id}/refresh")
async def refresh_player_hype(
    player_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Trigger a refresh of HYPE data for a specific player"""

    player_hype = db.query(PlayerHype).filter(
        PlayerHype.player_id == player_id
    ).first()

    if not player_hype:
        # Create new entry
        player_hype = PlayerHype(
            player_id=player_id,
            player_name="Unknown",  # Will be updated by background task
            player_type="unknown"
        )
        db.add(player_hype)
        db.commit()

    # Add background task to fetch and calculate HYPE data
    # This would integrate with social media APIs
    background_tasks.add_task(calculate_hype_score, player_id, db)

    return {"message": "HYPE refresh initiated", "player_id": player_id}


@router.get("/alerts/active", response_model=List[Dict[str, Any]])
async def get_active_alerts(
    severity: Optional[str] = None,
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get active HYPE alerts"""

    query = db.query(HypeAlert).filter(
        HypeAlert.is_active == True,
        HypeAlert.acknowledged == False
    )

    if severity:
        query = query.filter(HypeAlert.severity == severity)

    alerts = query.order_by(desc(HypeAlert.created_at)).limit(limit).all()

    return [{
        "id": a.id,
        "player_id": a.player_id,
        "type": a.alert_type,
        "severity": a.severity,
        "title": a.title,
        "description": a.description,
        "change_percentage": a.change_percentage,
        "created_at": a.created_at
    } for a in alerts]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Acknowledge a HYPE alert"""

    alert = db.query(HypeAlert).filter(HypeAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    db.commit()

    return {"message": "Alert acknowledged", "alert_id": alert_id}


# Background task placeholder
async def calculate_hype_score(player_id: str, db: Session):
    """
    Calculate HYPE score for a player
    This would integrate with various APIs:
    - Twitter/X API
    - Reddit API
    - News aggregation APIs
    - Sports data APIs
    """
    # Placeholder for actual implementation
    pass