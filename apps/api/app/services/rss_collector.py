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

        # Configure RSS feed sources - comprehensive list
        self.feeds = {
            # Primary feeds
            'rotowire': 'https://www.rotowire.com/rss/news.php?sport=MLB',
            'mlb_news': 'https://www.mlb.com/feeds/news/rss.xml',
            'mlb_pipeline': 'https://www.mlb.com/feeds/prospects/rss.xml',
            'mlb_trade_rumors': 'https://www.mlbtraderumors.com/feed',

            # Analytics sites
            'fangraphs': 'https://www.fangraphs.com/feed/',
            'fangraphs_blogs': 'https://blogs.fangraphs.com/feed',
            'razzball': 'https://razzball.com/feed/',
            'baseball_prospectus': 'https://www.baseballprospectus.com/feed/',

            # Team blogs - SB Nation
            'red_leg_nation': 'https://www.redlegnation.com/feed/',
            'brew_crew_ball': 'https://www.brewcrewball.com/rss/current.xml',
            'federal_baseball': 'https://www.federalbaseball.com/rss/current.xml',
            'purple_row': 'https://www.purplerow.com/rss/current.xml',
            'gaslamp_ball': 'https://www.gaslampball.com/rss/current.xml',
            'south_side_sox': 'https://www.southsidesox.com/rss/current.xml',
            'royals_review': 'https://www.royalsreview.com/rss/current',

            # Team blogs - Independent
            'dodgers_digest': 'https://dodgersdigest.com/feed/',
            'twins_daily': 'https://twinsdaily.com/rss/2-community-blogs.xml/',
            'blue_jays_nation': 'https://bluejaysnation.com/feed',
            'surviving_grady': 'https://survivinggrady.com/feed',
            'steel_city_pirates': 'https://steelcitypirates.com/feed/',

            # Other sources
            'espn_mlb': 'http://www.espn.com/espn/rss/mlb/news',
            'ba_prospects': 'https://www.baseballamerica.com/feed/',
            'athletic_mlb': 'https://theathletic.com/mlb?rss',
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

                    # Commit each article individually to handle unique constraint violations
                    try:
                        self.db.commit()
                        processed_count += 1
                    except Exception as commit_error:
                        self.db.rollback()
                        # Skip if duplicate URL (same article for multiple players with unique constraint)
                        if 'duplicate key' in str(commit_error).lower() or 'unique constraint' in str(commit_error).lower():
                            logger.debug(f"Article already exists: {article['url']}")
                        else:
                            logger.error(f"Error committing article: {commit_error}")

            except Exception as e:
                logger.error(f"Error processing article: {e}")
                self.db.rollback()
                continue

        return processed_count

    def _format_source_name(self, source: str) -> str:
        """Format source name for display"""
        source_names = {
            'rotowire': 'Rotowire',
            'mlb_news': 'MLB.com',
            'mlb_pipeline': 'MLB Pipeline',
            'mlb_trade_rumors': 'MLB Trade Rumors',
            'espn_mlb': 'ESPN',
            'ba_prospects': 'Baseball America',
            'fangraphs': 'FanGraphs',
            'fangraphs_blogs': 'FanGraphs Blogs',
            'razzball': 'Razzball',
            'baseball_prospectus': 'Baseball Prospectus',
            'athletic_mlb': 'The Athletic',

            # Team blogs
            'red_leg_nation': 'Red Leg Nation (Reds)',
            'brew_crew_ball': 'Brew Crew Ball (Brewers)',
            'federal_baseball': 'Federal Baseball (Nationals)',
            'purple_row': 'Purple Row (Rockies)',
            'gaslamp_ball': 'Gaslamp Ball (Padres)',
            'south_side_sox': 'South Side Sox (White Sox)',
            'royals_review': 'Royals Review',
            'dodgers_digest': 'Dodgers Digest',
            'twins_daily': 'Twins Daily',
            'blue_jays_nation': 'Blue Jays Nation',
            'surviving_grady': 'Surviving Grady (Red Sox)',
            'steel_city_pirates': 'Steel City Pirates',
        }

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