"""
RSS Feed Collector for MLB News and Player Mentions
Collects articles from various MLB news sources
"""

import asyncio
import aiohttp
import feedparser
from datetime import datetime
from typing import Dict, List, Optional
import logging
import re
from sqlalchemy.orm import Session

from app.models.hype import MediaArticle, PlayerHype, SocialMention
from app.db.models import Prospect

logger = logging.getLogger(__name__)


class RSSCollector:
    """Collect MLB news from RSS feeds"""

    def __init__(self, db: Session):
        self.db = db

        # Configure RSS feed sources - start with core feeds
        self.feeds = {
            # Primary feeds
            'rotowire': 'https://www.rotowire.com/rss/news.php?sport=MLB',
            'mlb_news': 'https://www.mlb.com/feeds/news/rss.xml',
            'mlb_pipeline': 'https://www.mlb.com/feeds/prospects/rss.xml',

            # Add The Athletic team feeds selectively (ones that work)
            'athletic_mlb': 'https://theathletic.com/mlb?rss',

            # ESPN and others
            'espn_mlb': 'http://www.espn.com/espn/rss/mlb/news',
            'ba_prospects': 'https://www.baseballamerica.com/feed/',
            'fangraphs': 'https://www.fangraphs.com/feed/',
        }

    async def collect_all_feeds(self) -> Dict:
        """Collect articles from all RSS feeds"""
        all_articles = []

        for source, url in self.feeds.items():
            try:
                articles = await self.fetch_feed(source, url)
                all_articles.extend(articles)
                logger.info(f"Collected {len(articles)} articles from {source}")
            except Exception as e:
                logger.error(f"Error fetching {source}: {e}")

        # Process articles for player mentions
        processed_count = await self.process_articles_for_players(all_articles)

        return {
            'status': 'success',
            'total_articles': len(all_articles),
            'processed_for_players': processed_count
        }

    async def fetch_feed(self, source: str, url: str) -> List[Dict]:
        """Fetch and parse RSS feed"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)  # Reduce timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Feed {source} returned status {response.status}")
                        return []

                    content = await response.text()

            # Parse feed with feedparser
            feed = feedparser.parse(content)

            articles = []
            for entry in feed.entries[:50]:  # Limit to recent 50 entries
                article = {
                    'source': source,
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'summary': entry.get('summary', entry.get('description', '')),
                    'published': self._parse_published_date(entry),
                    'author': entry.get('author', ''),
                    'tags': [tag.term for tag in entry.get('tags', [])]
                }
                articles.append(article)

            return articles

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {source}")
            return []
        except Exception as e:
            logger.error(f"Error fetching {source}: {e}")
            return []

    def _parse_published_date(self, entry) -> datetime:
        """Parse various date formats from RSS feeds"""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            import time
            return datetime.fromtimestamp(time.mktime(entry.published_parsed))
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            import time
            return datetime.fromtimestamp(time.mktime(entry.updated_parsed))
        else:
            return datetime.utcnow()

    async def process_articles_for_players(self, articles: List[Dict]) -> int:
        """Process articles and extract player mentions"""

        # Get all prospects to search for
        prospects = self.db.query(Prospect).all()
        player_hypes = self.db.query(PlayerHype).all()

        # Create player name lookup (including variations)
        player_names = {}

        for prospect in prospects:
            name = prospect.name
            player_names[name.lower()] = f"prospect_{prospect.mlb_id}"
            # Add last name only for common references
            last_name = name.split()[-1] if ' ' in name else name
            if len(last_name) > 4:  # Avoid short common names
                player_names[last_name.lower()] = f"prospect_{prospect.mlb_id}"

        for player_hype in player_hypes:
            name = player_hype.player_name
            player_names[name.lower()] = player_hype.player_id
            last_name = name.split()[-1] if ' ' in name else name
            if len(last_name) > 4:
                player_names[last_name.lower()] = player_hype.player_id

        processed_count = 0

        for article in articles:
            try:
                # Combine title and summary for searching
                full_text = f"{article['title']} {article['summary']}".lower()

                # Find all player mentions
                mentioned_players = []
                for player_name, player_id in player_names.items():
                    if player_name in full_text:
                        mentioned_players.append((player_name, player_id))

                # Create entries for each mentioned player
                for player_name, player_id in mentioned_players:
                    # Get player hype record
                    player_hype = self.db.query(PlayerHype).filter(
                        PlayerHype.player_id == player_id
                    ).first()

                    if not player_hype:
                        continue

                    # Check if article already exists
                    existing = self.db.query(MediaArticle).filter(
                        MediaArticle.url == article['url'],
                        MediaArticle.player_hype_id == player_hype.id
                    ).first()

                    if existing:
                        continue

                    # Determine sentiment based on keywords
                    sentiment = self._analyze_article_sentiment(article['title'], article['summary'])

                    # Create media article entry
                    media_article = MediaArticle(
                        player_hype_id=player_hype.id,
                        source=self._format_source_name(article['source']),
                        title=article['title'][:500],  # Limit length
                        url=article['url'],
                        author=article['author'] or 'Staff',
                        summary=article['summary'][:2000],  # Limit length
                        sentiment=sentiment['sentiment'],
                        sentiment_confidence=sentiment['confidence'],
                        prominence_score=self._calculate_prominence(player_name, full_text),
                        published_at=article['published'],
                        collected_at=datetime.utcnow()
                    )

                    self.db.add(media_article)

                    # Also create a social mention for unified display
                    social_mention = SocialMention(
                        player_hype_id=player_hype.id,
                        platform='news',  # Use 'news' as platform for RSS feeds
                        post_id=f"rss_{article['source']}_{hash(article['url'])}",
                        author_handle=self._format_source_name(article['source']),
                        author_followers=0,
                        content=f"{article['title']}\n\n{article['summary'][:500]}",
                        url=article['url'],
                        hashtags=[],
                        likes=0,
                        shares=0,
                        comments=0,
                        sentiment=sentiment['sentiment'],
                        sentiment_confidence=sentiment['confidence'],
                        keywords=[player_name],
                        posted_at=article['published'],
                        collected_at=datetime.utcnow()
                    )

                    self.db.add(social_mention)
                    processed_count += 1

            except Exception as e:
                logger.error(f"Error processing article: {e}")
                continue

        self.db.commit()
        return processed_count

    def _format_source_name(self, source: str) -> str:
        """Format source name for display"""
        source_names = {
            'rotowire': 'Rotowire',
            'athletic_national': 'The Athletic',
            'mlb_news': 'MLB.com',
            'mlb_pipeline': 'MLB Pipeline',
            'espn_mlb': 'ESPN',
            'ba_prospects': 'Baseball America',
            'fangraphs': 'FanGraphs',
        }

        # Handle team-specific Athletic feeds
        if source.startswith('athletic_'):
            if source == 'athletic_national':
                return 'The Athletic'
            else:
                team = source.replace('athletic_', '').replace('_', ' ').title()
                return f'The Athletic ({team})'

        return source_names.get(source, source.replace('_', ' ').title())

    def _analyze_article_sentiment(self, title: str, summary: str) -> Dict:
        """Analyze sentiment of article about player"""
        text = f"{title} {summary}".lower()

        positive_keywords = [
            'breakout', 'impressive', 'dominant', 'excellent', 'outstanding',
            'promising', 'rising', 'stellar', 'strong', 'success',
            'promoted', 'call-up', 'debut', 'all-star', 'award',
            'leads', 'wins', 'saves', 'homers', 'streak'
        ]

        negative_keywords = [
            'injured', 'injury', 'struggling', 'slump', 'demoted',
            'optioned', 'benched', 'surgery', 'setback', 'disappointing',
            'concerns', 'issues', 'problems', 'suspended', 'poor'
        ]

        positive_count = sum(1 for word in positive_keywords if word in text)
        negative_count = sum(1 for word in negative_keywords if word in text)

        if positive_count > negative_count + 1:
            return {'sentiment': 'positive', 'confidence': min(0.9, positive_count * 0.2)}
        elif negative_count > positive_count + 1:
            return {'sentiment': 'negative', 'confidence': min(0.9, negative_count * 0.2)}
        else:
            return {'sentiment': 'neutral', 'confidence': 0.5}

    def _calculate_prominence(self, player_name: str, text: str) -> float:
        """Calculate how prominently the player is featured"""
        # Count mentions
        mentions = text.lower().count(player_name.lower())

        # Check if in title
        in_title = 1.0 if player_name.lower() in text[:100].lower() else 0.0

        # Calculate score (0-10)
        score = min(10.0, (mentions * 2) + (in_title * 5))
        return score


async def collect_rss_feeds(db: Session):
    """Main function to collect RSS feeds"""
    collector = RSSCollector(db)
    results = await collector.collect_all_feeds()
    return results