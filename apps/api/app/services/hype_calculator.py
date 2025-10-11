"""
HYPE Score Calculation Service
Implements the algorithm for calculating player HYPE scores based on social media and media data
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import logging

from app.models.hype import (
    PlayerHype, SocialMention, MediaArticle,
    HypeHistory, HypeAlert, TrendingTopic
)

logger = logging.getLogger(__name__)


class HypeCalculator:
    """Calculate HYPE scores for players based on multi-dimensional data"""

    # Weight configurations for different data sources
    PLATFORM_WEIGHTS = {
        'twitter': 1.0,      # Highest weight for real-time engagement
        'bluesky': 0.85,     # Growing platform, tech-savvy early adopters
        'reddit': 0.8,       # High weight for in-depth discussions
        'instagram': 0.7,    # Visual content engagement
        'tiktok': 0.9,       # High virality potential
        'facebook': 0.5,     # Lower weight, older demographic
    }

    MEDIA_SOURCE_WEIGHTS = {
        'ESPN': 1.0,
        'MLB.com': 0.9,
        'The Athletic': 0.95,
        'Baseball America': 0.85,
        'FanGraphs': 0.8,
        'local_news': 0.6,
        'blog': 0.4,
    }

    # Sentiment impact multipliers
    SENTIMENT_MULTIPLIERS = {
        'positive': 1.2,
        'neutral': 1.0,
        'negative': 0.8,
    }

    # Time decay factors (how much older data matters)
    TIME_DECAY_HOURS = {
        1: 1.0,      # Last hour: full weight
        6: 0.9,      # Last 6 hours: 90% weight
        24: 0.7,     # Last day: 70% weight
        72: 0.5,     # Last 3 days: 50% weight
        168: 0.3,    # Last week: 30% weight
        720: 0.1,    # Last month: 10% weight
    }

    def __init__(self, db: Session):
        self.db = db

    def calculate_hype_score(self, player_id: str) -> Dict:
        """
        Calculate comprehensive HYPE score for a player
        Returns dict with score components and final score
        """
        try:
            # Get or create player HYPE record
            player_hype = self._get_or_create_player_hype(player_id)

            # Calculate time windows
            now = datetime.utcnow()
            time_windows = self._get_time_windows(now)

            # 1. Social Media Score (40% of total)
            social_score, social_metrics = self._calculate_social_score(
                player_hype.id, time_windows
            )

            # 2. Media Coverage Score (30% of total)
            media_score, media_metrics = self._calculate_media_score(
                player_hype.id, time_windows
            )

            # 3. Virality Score (20% of total)
            virality_score, virality_metrics = self._calculate_virality_score(
                player_hype.id, time_windows
            )

            # 4. Sentiment Score (10% of total)
            sentiment_score, sentiment_metrics = self._calculate_sentiment_score(
                player_hype.id, time_windows
            )

            # Calculate weighted final score
            final_score = (
                social_score * 0.4 +
                media_score * 0.3 +
                virality_score * 0.2 +
                sentiment_score * 0.1
            )

            # Calculate trend (compare with previous score)
            trend = self._calculate_trend(player_hype.id, final_score)

            # Update player HYPE record
            self._update_player_hype(
                player_hype,
                final_score,
                trend,
                sentiment_metrics['average'],
                virality_score,
                social_metrics,
                now
            )

            # Check for alerts
            self._check_and_create_alerts(player_hype, final_score, trend)

            # Update trending topics
            self._update_trending_topics(player_hype.id, player_id)

            # Store historical data
            self._store_history(player_hype.id, final_score, sentiment_metrics, social_metrics)

            return {
                'player_id': player_id,
                'hype_score': final_score,
                'trend': trend,
                'components': {
                    'social': social_score,
                    'media': media_score,
                    'virality': virality_score,
                    'sentiment': sentiment_score,
                },
                'metrics': {
                    'social': social_metrics,
                    'media': media_metrics,
                    'virality': virality_metrics,
                    'sentiment': sentiment_metrics,
                }
            }

        except Exception as e:
            logger.error(f"Error calculating HYPE score for {player_id}: {e}")
            raise

    def _get_or_create_player_hype(self, player_id: str) -> PlayerHype:
        """Get existing PlayerHype record or create new one"""
        player_hype = self.db.query(PlayerHype).filter(
            PlayerHype.player_id == player_id
        ).first()

        if not player_hype:
            # Determine player type and name (would integrate with player database)
            player_type = 'prospect' if 'prospect' in player_id else 'mlb'
            player_name = player_id.replace('-', ' ').title()  # Simplified

            player_hype = PlayerHype(
                player_id=player_id,
                player_name=player_name,
                player_type=player_type
            )
            self.db.add(player_hype)
            self.db.commit()

        return player_hype

    def _get_time_windows(self, now: datetime) -> Dict[str, datetime]:
        """Calculate time window boundaries"""
        return {
            '1h': now - timedelta(hours=1),
            '6h': now - timedelta(hours=6),
            '24h': now - timedelta(hours=24),
            '3d': now - timedelta(days=3),
            '7d': now - timedelta(days=7),
            '14d': now - timedelta(days=14),
            '30d': now - timedelta(days=30),
        }

    def _calculate_social_score(
        self, player_hype_id: int, time_windows: Dict
    ) -> Tuple[float, Dict]:
        """Calculate social media engagement score"""

        # Get mentions within different time windows
        mentions_24h = self.db.query(SocialMention).filter(
            SocialMention.player_hype_id == player_hype_id,
            SocialMention.posted_at >= time_windows['24h']
        ).all()

        mentions_7d = self.db.query(SocialMention).filter(
            SocialMention.player_hype_id == player_hype_id,
            SocialMention.posted_at >= time_windows['7d']
        ).all()

        mentions_14d = self.db.query(SocialMention).filter(
            SocialMention.player_hype_id == player_hype_id,
            SocialMention.posted_at >= time_windows['14d']
        ).all()

        # Calculate weighted engagement
        total_engagement = 0
        platform_breakdown = {}

        for mention in mentions_24h:
            platform_weight = self.PLATFORM_WEIGHTS.get(mention.platform, 0.5)
            sentiment_multiplier = self.SENTIMENT_MULTIPLIERS.get(
                mention.sentiment or 'neutral', 1.0
            )

            # Calculate time decay
            hours_old = (datetime.utcnow() - mention.posted_at).total_seconds() / 3600
            time_decay = self._get_time_decay(hours_old)

            # Calculate engagement score for this mention
            engagement = (
                (mention.likes * 1.0 +
                 mention.shares * 2.0 +
                 mention.comments * 1.5) *
                platform_weight *
                sentiment_multiplier *
                time_decay
            )

            # Account for author influence
            if mention.author_followers > 10000:
                engagement *= 1.5
            elif mention.author_followers > 100000:
                engagement *= 2.0

            total_engagement += engagement

            # Track platform breakdown
            if mention.platform not in platform_breakdown:
                platform_breakdown[mention.platform] = 0
            platform_breakdown[mention.platform] += engagement

        # Normalize to 0-100 scale
        # Using logarithmic scale to handle wide range of values
        if total_engagement > 0:
            social_score = min(100, 20 * np.log10(total_engagement + 1))
        else:
            social_score = 0

        metrics = {
            'total_mentions_24h': len(mentions_24h),
            'total_mentions_7d': len(mentions_7d),
            'total_mentions_14d': len(mentions_14d),
            'total_engagement': total_engagement,
            'platform_breakdown': platform_breakdown,
        }

        return social_score, metrics

    def _calculate_media_score(
        self, player_hype_id: int, time_windows: Dict
    ) -> Tuple[float, Dict]:
        """Calculate media coverage score"""

        # Use 14d window for more stable media coverage tracking
        articles = self.db.query(MediaArticle).filter(
            MediaArticle.player_hype_id == player_hype_id,
            MediaArticle.published_at >= time_windows['14d']
        ).all()

        total_coverage = 0
        source_breakdown = {}

        for article in articles:
            source_weight = self.MEDIA_SOURCE_WEIGHTS.get(article.source, 0.5)
            sentiment_multiplier = self.SENTIMENT_MULTIPLIERS.get(
                article.sentiment or 'neutral', 1.0
            )

            # Calculate time decay
            hours_old = (datetime.utcnow() - article.published_at).total_seconds() / 3600
            time_decay = self._get_time_decay(hours_old)

            # Calculate coverage score
            coverage = (
                (article.prominence_score or 1.0) *
                source_weight *
                sentiment_multiplier *
                time_decay *
                10  # Base multiplier for media articles
            )

            total_coverage += coverage

            # Track source breakdown
            if article.source not in source_breakdown:
                source_breakdown[article.source] = 0
            source_breakdown[article.source] += 1

        # Normalize to 0-100 scale
        if total_coverage > 0:
            media_score = min(100, total_coverage)
        else:
            media_score = 0

        metrics = {
            'total_articles': len(articles),
            'total_coverage': total_coverage,
            'source_breakdown': source_breakdown,
        }

        return media_score, metrics

    def _calculate_virality_score(
        self, player_hype_id: int, time_windows: Dict
    ) -> Tuple[float, Dict]:
        """Calculate virality score based on growth rate and spread"""

        # Get mention counts in different periods
        mentions_1h = self.db.query(func.count(SocialMention.id)).filter(
            SocialMention.player_hype_id == player_hype_id,
            SocialMention.posted_at >= time_windows['1h']
        ).scalar() or 0

        mentions_6h = self.db.query(func.count(SocialMention.id)).filter(
            SocialMention.player_hype_id == player_hype_id,
            SocialMention.posted_at >= time_windows['6h']
        ).scalar() or 0

        mentions_24h = self.db.query(func.count(SocialMention.id)).filter(
            SocialMention.player_hype_id == player_hype_id,
            SocialMention.posted_at >= time_windows['24h']
        ).scalar() or 0

        # Calculate growth rates
        growth_rate_6h = (mentions_1h / max(mentions_6h / 6, 1)) if mentions_6h > 0 else 0
        growth_rate_24h = (mentions_6h / max(mentions_24h / 4, 1)) if mentions_24h > 0 else 0

        # Get unique platforms count (spread indicator)
        unique_platforms = self.db.query(
            func.count(func.distinct(SocialMention.platform))
        ).filter(
            SocialMention.player_hype_id == player_hype_id,
            SocialMention.posted_at >= time_windows['24h']
        ).scalar() or 0

        # Calculate virality score
        virality_score = min(100, (
            growth_rate_6h * 30 +
            growth_rate_24h * 20 +
            unique_platforms * 10 +
            min(50, mentions_1h)  # Cap direct mention impact
        ))

        metrics = {
            'mentions_1h': mentions_1h,
            'mentions_6h': mentions_6h,
            'mentions_24h': mentions_24h,
            'growth_rate_6h': growth_rate_6h,
            'growth_rate_24h': growth_rate_24h,
            'unique_platforms': unique_platforms,
        }

        return virality_score, metrics

    def _calculate_sentiment_score(
        self, player_hype_id: int, time_windows: Dict
    ) -> Tuple[float, Dict]:
        """Calculate overall sentiment score"""

        # Get sentiment distribution from social mentions
        social_sentiments = self.db.query(
            SocialMention.sentiment,
            func.count(SocialMention.id).label('count')
        ).filter(
            SocialMention.player_hype_id == player_hype_id,
            SocialMention.posted_at >= time_windows['24h']
        ).group_by(SocialMention.sentiment).all()

        # Get sentiment distribution from media
        media_sentiments = self.db.query(
            MediaArticle.sentiment,
            func.count(MediaArticle.id).label('count')
        ).filter(
            MediaArticle.player_hype_id == player_hype_id,
            MediaArticle.published_at >= time_windows['7d']
        ).group_by(MediaArticle.sentiment).all()

        # Calculate weighted sentiment
        total_positive = 0
        total_negative = 0
        total_neutral = 0

        for sentiment, count in social_sentiments:
            if sentiment == 'positive':
                total_positive += count
            elif sentiment == 'negative':
                total_negative += count
            else:
                total_neutral += count

        # Media sentiments have higher weight
        for sentiment, count in media_sentiments:
            if sentiment == 'positive':
                total_positive += count * 3
            elif sentiment == 'negative':
                total_negative += count * 3
            else:
                total_neutral += count * 2

        total = total_positive + total_negative + total_neutral

        if total > 0:
            # Calculate sentiment ratio (-1 to 1)
            sentiment_ratio = (total_positive - total_negative) / total

            # Convert to 0-100 scale
            sentiment_score = (sentiment_ratio + 1) * 50
        else:
            sentiment_score = 50  # Neutral if no data

        metrics = {
            'positive': total_positive,
            'negative': total_negative,
            'neutral': total_neutral,
            'average': sentiment_ratio if total > 0 else 0,
        }

        return sentiment_score, metrics

    def _calculate_trend(self, player_hype_id: int, current_score: float) -> float:
        """Calculate trend by comparing with previous score"""

        # Get most recent historical score
        recent_history = self.db.query(HypeHistory).filter(
            HypeHistory.player_hype_id == player_hype_id
        ).order_by(desc(HypeHistory.period_end)).first()

        if recent_history:
            # Calculate percentage change
            if recent_history.hype_score > 0:
                trend = ((current_score - recent_history.hype_score) /
                        recent_history.hype_score) * 100
            else:
                trend = 100 if current_score > 0 else 0
        else:
            trend = 0

        return round(trend, 2)

    def _get_time_decay(self, hours_old: float) -> float:
        """Get time decay factor based on age in hours"""
        for threshold, decay in sorted(self.TIME_DECAY_HOURS.items()):
            if hours_old <= threshold:
                return decay
        return 0.05  # Very old data gets minimal weight

    def _update_player_hype(
        self,
        player_hype: PlayerHype,
        score: float,
        trend: float,
        sentiment: float,
        virality: float,
        social_metrics: Dict,
        now: datetime
    ):
        """Update PlayerHype record with calculated values"""
        # Convert to Python float to avoid numpy type issues with PostgreSQL
        player_hype.hype_score = float(round(score, 2))
        player_hype.hype_trend = float(round(trend, 2))
        player_hype.sentiment_score = float(round(sentiment, 3))
        player_hype.virality_score = float(round(virality, 2))
        player_hype.total_mentions_24h = int(social_metrics.get('total_mentions_24h', 0))
        player_hype.total_mentions_7d = int(social_metrics.get('total_mentions_7d', 0))
        player_hype.total_mentions_14d = int(social_metrics.get('total_mentions_14d', 0))
        player_hype.engagement_rate = float(self._calculate_engagement_rate(social_metrics))
        player_hype.last_calculated = now
        player_hype.updated_at = now

        self.db.commit()

    def _calculate_engagement_rate(self, social_metrics: Dict) -> float:
        """Calculate engagement rate from social metrics"""
        total_mentions = social_metrics.get('total_mentions_24h', 0)
        total_engagement = social_metrics.get('total_engagement', 0)

        if total_mentions > 0:
            return round((total_engagement / total_mentions) * 100, 2)
        return 0

    def _check_and_create_alerts(
        self, player_hype: PlayerHype, current_score: float, trend: float
    ):
        """Check for significant changes and create alerts"""

        alerts_to_create = []

        # Check for surge (>25% increase)
        if trend > 25:
            alerts_to_create.append({
                'alert_type': 'surge',
                'severity': 'high' if trend > 50 else 'medium',
                'title': f'HYPE surge detected for {player_hype.player_name}',
                'description': f'HYPE score increased by {trend:.1f}% in the last period',
                'change_percentage': float(trend),
            })

        # Check for crash (>25% decrease)
        elif trend < -25:
            alerts_to_create.append({
                'alert_type': 'crash',
                'severity': 'high' if trend < -50 else 'medium',
                'title': f'HYPE crash detected for {player_hype.player_name}',
                'description': f'HYPE score decreased by {abs(trend):.1f}% in the last period',
                'change_percentage': float(trend),
            })

        # Check for high virality
        if player_hype.virality_score > 80:
            alerts_to_create.append({
                'alert_type': 'viral',
                'severity': 'medium',
                'title': f'{player_hype.player_name} is going viral',
                'description': f'Virality score reached {player_hype.virality_score:.1f}',
                'change_percentage': 0,
            })

        # Create alerts
        for alert_data in alerts_to_create:
            # Check if similar alert already exists and is active
            existing_alert = self.db.query(HypeAlert).filter(
                HypeAlert.player_id == player_hype.player_id,
                HypeAlert.alert_type == alert_data['alert_type'],
                HypeAlert.is_active == True,
                HypeAlert.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).first()

            if not existing_alert:
                alert = HypeAlert(
                    player_id=player_hype.player_id,
                    hype_score_before=float(current_score - (current_score * trend / 100)),
                    hype_score_after=float(current_score),
                    expires_at=datetime.utcnow() + timedelta(days=7),
                    **alert_data
                )
                self.db.add(alert)

        self.db.commit()

    def _update_trending_topics(self, player_hype_id: int, player_id: str):
        """Extract and update trending topics from recent mentions"""

        # Get recent mentions
        recent_mentions = self.db.query(SocialMention).filter(
            SocialMention.player_hype_id == player_hype_id,
            SocialMention.posted_at >= datetime.utcnow() - timedelta(hours=24)
        ).all()

        # Extract hashtags and keywords
        topic_counts = {}
        for mention in recent_mentions:
            if mention.hashtags:
                for hashtag in mention.hashtags:
                    if hashtag not in topic_counts:
                        topic_counts[hashtag] = {'count': 0, 'sentiment': []}
                    topic_counts[hashtag]['count'] += 1
                    if mention.sentiment:
                        sentiment_value = 1 if mention.sentiment == 'positive' else (
                            -1 if mention.sentiment == 'negative' else 0
                        )
                        topic_counts[hashtag]['sentiment'].append(sentiment_value)

        # Update or create trending topics
        for topic, data in sorted(
            topic_counts.items(), key=lambda x: x[1]['count'], reverse=True
        )[:10]:  # Top 10 topics
            trending_topic = self.db.query(TrendingTopic).filter(
                TrendingTopic.player_id == player_id,
                TrendingTopic.topic == topic
            ).first()

            avg_sentiment = (
                sum(data['sentiment']) / len(data['sentiment'])
                if data['sentiment'] else 0
            )

            if trending_topic:
                trending_topic.mention_count = data['count']
                trending_topic.sentiment_average = avg_sentiment
                trending_topic.last_updated = datetime.utcnow()
            else:
                trending_topic = TrendingTopic(
                    player_id=player_id,
                    topic=topic,
                    topic_type='hashtag',
                    mention_count=data['count'],
                    sentiment_average=avg_sentiment,
                    started_trending=datetime.utcnow()
                )
                self.db.add(trending_topic)

        self.db.commit()

    def _store_history(
        self,
        player_hype_id: int,
        score: float,
        sentiment_metrics: Dict,
        social_metrics: Dict
    ):
        """Store historical HYPE data"""

        now = datetime.utcnow()
        period_start = now - timedelta(hours=1)

        # Convert to Python native types to avoid numpy type issues with PostgreSQL
        history = HypeHistory(
            player_hype_id=player_hype_id,
            hype_score=float(score),
            sentiment_score=float(sentiment_metrics['average']),
            virality_score=int(0),
            total_mentions=int(social_metrics.get('total_mentions_24h', 0)),
            period_start=period_start,
            period_end=now,
            granularity='hourly'
        )
        self.db.add(history)
        self.db.commit()