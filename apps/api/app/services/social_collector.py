"""
Social Media Data Collector Service
Integrates with various social media APIs to collect player mentions
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib
import json
import logging
import os
from sqlalchemy.orm import Session

from app.models.hype import SocialMention, PlayerHype

logger = logging.getLogger(__name__)


class SocialMediaCollector:
    """Collect and process social media data from multiple platforms"""

    def __init__(self, db: Session):
        self.db = db
        self.sentiment_analyzer = SentimentAnalyzer()

        # API configurations (would be in environment variables)
        self.twitter_bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        self.reddit_secret = os.getenv('REDDIT_SECRET')
        self.bluesky_handle = os.getenv('BLUESKY_HANDLE')  # e.g., username.bsky.social
        self.bluesky_password = os.getenv('BLUESKY_APP_PASSWORD')

        # Rate limiting configurations
        self.rate_limits = {
            'twitter': {'calls': 300, 'window': 900},  # 300 calls per 15 min
            'reddit': {'calls': 60, 'window': 60},     # 60 calls per minute
            'bluesky': {'calls': 100, 'window': 300},  # 100 calls per 5 min (estimated)
        }

    async def collect_all_platforms(self, player_name: str, player_id: str) -> Dict:
        """Collect data from all available platforms"""
        tasks = [
            self.collect_twitter_data(player_name, player_id),
            self.collect_reddit_data(player_name, player_id),
            self.collect_bluesky_data(player_name, player_id),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        platform_results = {}
        platforms = ['twitter', 'reddit', 'bluesky']

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error collecting from {platforms[i]}: {result}")
                platform_results[platforms[i]] = {'error': str(result)}
            else:
                platform_results[platforms[i]] = result

        return platform_results

    async def collect_twitter_data(self, player_name: str, player_id: str) -> Dict:
        """Collect Twitter/X mentions for a player"""
        if not self.twitter_bearer_token:
            return {'status': 'skipped', 'reason': 'No Twitter API token'}

        try:
            # Twitter API v2 endpoint
            search_url = "https://api.twitter.com/2/tweets/search/recent"

            # Build query
            query = f'"{player_name}" (baseball OR MLB OR prospect OR "home run" OR strikeout)'

            params = {
                'query': query,
                'max_results': 100,
                'tweet.fields': 'created_at,author_id,public_metrics,entities',
                'expansions': 'author_id',
                'user.fields': 'public_metrics'
            }

            headers = {
                'Authorization': f'Bearer {self.twitter_bearer_token}'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Twitter API error: {response.status}")
                        return {'status': 'error', 'code': response.status}

                    data = await response.json()

                    # Process tweets
                    processed_tweets = await self._process_twitter_data(data, player_id)

                    return {
                        'status': 'success',
                        'count': len(processed_tweets),
                        'tweets': processed_tweets
                    }

        except Exception as e:
            logger.error(f"Twitter collection error: {e}")
            return {'status': 'error', 'message': str(e)}

    async def _process_twitter_data(self, twitter_response: Dict, player_id: str) -> List[Dict]:
        """Process and store Twitter data"""
        processed = []

        if 'data' not in twitter_response:
            return processed

        # Get player HYPE record
        player_hype = self.db.query(PlayerHype).filter(
            PlayerHype.player_id == player_id
        ).first()

        if not player_hype:
            return processed

        # Create user lookup
        users = {}
        if 'includes' in twitter_response and 'users' in twitter_response['includes']:
            for user in twitter_response['includes']['users']:
                users[user['id']] = user

        for tweet in twitter_response['data']:
            try:
                # Generate unique ID for deduplication
                post_id = f"twitter_{tweet['id']}"

                # Check if already exists
                existing = self.db.query(SocialMention).filter(
                    SocialMention.post_id == post_id
                ).first()

                if existing:
                    continue

                # Get author info
                author = users.get(tweet.get('author_id', ''), {})

                # Extract hashtags
                hashtags = []
                if 'entities' in tweet and 'hashtags' in tweet['entities']:
                    hashtags = [tag['tag'] for tag in tweet['entities']['hashtags']]

                # Analyze sentiment
                sentiment_result = await self.sentiment_analyzer.analyze(tweet['text'])

                # Create mention record
                mention = SocialMention(
                    player_hype_id=player_hype.id,
                    platform='twitter',
                    post_id=post_id,
                    author_handle=author.get('username', 'unknown'),
                    author_followers=author.get('public_metrics', {}).get('followers_count', 0),
                    content=tweet['text'],
                    url=f"https://twitter.com/i/status/{tweet['id']}",
                    hashtags=hashtags,
                    likes=tweet.get('public_metrics', {}).get('like_count', 0),
                    shares=tweet.get('public_metrics', {}).get('retweet_count', 0),
                    comments=tweet.get('public_metrics', {}).get('reply_count', 0),
                    sentiment=sentiment_result['sentiment'],
                    sentiment_confidence=sentiment_result['confidence'],
                    keywords=sentiment_result.get('keywords', []),
                    posted_at=datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00')),
                    collected_at=datetime.utcnow()
                )

                self.db.add(mention)
                processed.append({
                    'id': post_id,
                    'text': tweet['text'],
                    'sentiment': sentiment_result['sentiment']
                })

            except Exception as e:
                logger.error(f"Error processing tweet {tweet.get('id')}: {e}")
                continue

        self.db.commit()
        return processed

    async def collect_reddit_data(self, player_name: str, player_id: str) -> Dict:
        """Collect Reddit mentions for a player"""
        if not self.reddit_client_id or not self.reddit_secret:
            return {'status': 'skipped', 'reason': 'No Reddit API credentials'}

        try:
            # Get Reddit access token
            token = await self._get_reddit_token()
            if not token:
                return {'status': 'error', 'message': 'Failed to get Reddit token'}

            # Search relevant subreddits
            subreddits = ['baseball', 'mlb', 'fantasybaseball', 'baseballcards']
            all_posts = []

            for subreddit in subreddits:
                posts = await self._search_reddit_subreddit(
                    token, subreddit, player_name, player_id
                )
                all_posts.extend(posts)

            return {
                'status': 'success',
                'count': len(all_posts),
                'posts': all_posts
            }

        except Exception as e:
            logger.error(f"Reddit collection error: {e}")
            return {'status': 'error', 'message': str(e)}

    async def _get_reddit_token(self) -> Optional[str]:
        """Get Reddit API access token"""
        try:
            auth_url = "https://www.reddit.com/api/v1/access_token"

            auth = aiohttp.BasicAuth(self.reddit_client_id, self.reddit_secret)
            data = {'grant_type': 'client_credentials'}
            headers = {'User-Agent': 'AFineWineDynasty/1.0'}

            async with aiohttp.ClientSession() as session:
                async with session.post(auth_url, auth=auth, data=data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('access_token')
                    return None

        except Exception as e:
            logger.error(f"Reddit auth error: {e}")
            return None

    async def _search_reddit_subreddit(
        self, token: str, subreddit: str, player_name: str, player_id: str
    ) -> List[Dict]:
        """Search a specific subreddit for player mentions"""
        try:
            search_url = f"https://oauth.reddit.com/r/{subreddit}/search.json"

            headers = {
                'Authorization': f'Bearer {token}',
                'User-Agent': 'AFineWineDynasty/1.0'
            }

            params = {
                'q': player_name,
                'sort': 'new',
                'limit': 25,
                't': 'week'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, params=params) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    return await self._process_reddit_data(data, player_id, subreddit)

        except Exception as e:
            logger.error(f"Reddit search error for r/{subreddit}: {e}")
            return []

    async def _process_reddit_data(
        self, reddit_response: Dict, player_id: str, subreddit: str
    ) -> List[Dict]:
        """Process and store Reddit data"""
        processed = []

        if 'data' not in reddit_response or 'children' not in reddit_response['data']:
            return processed

        # Get player HYPE record
        player_hype = self.db.query(PlayerHype).filter(
            PlayerHype.player_id == player_id
        ).first()

        if not player_hype:
            return processed

        for post in reddit_response['data']['children']:
            try:
                post_data = post['data']

                # Generate unique ID
                post_id = f"reddit_{post_data['id']}"

                # Check if already exists
                existing = self.db.query(SocialMention).filter(
                    SocialMention.post_id == post_id
                ).first()

                if existing:
                    continue

                # Combine title and selftext for sentiment analysis
                content = f"{post_data['title']} {post_data.get('selftext', '')}"

                # Analyze sentiment
                sentiment_result = await self.sentiment_analyzer.analyze(content)

                # Create mention record
                mention = SocialMention(
                    player_hype_id=player_hype.id,
                    platform='reddit',
                    post_id=post_id,
                    author_handle=post_data.get('author', 'deleted'),
                    author_followers=0,  # Reddit doesn't expose follower count
                    content=content[:2000],  # Truncate if too long
                    url=f"https://reddit.com{post_data['permalink']}",
                    hashtags=[subreddit],  # Use subreddit as a tag
                    likes=post_data.get('ups', 0),
                    shares=0,  # Reddit doesn't have shares
                    comments=post_data.get('num_comments', 0),
                    sentiment=sentiment_result['sentiment'],
                    sentiment_confidence=sentiment_result['confidence'],
                    keywords=sentiment_result.get('keywords', []),
                    posted_at=datetime.fromtimestamp(post_data['created_utc']),
                    collected_at=datetime.utcnow()
                )

                self.db.add(mention)
                processed.append({
                    'id': post_id,
                    'title': post_data['title'],
                    'subreddit': subreddit,
                    'sentiment': sentiment_result['sentiment']
                })

            except Exception as e:
                logger.error(f"Error processing Reddit post {post.get('id')}: {e}")
                continue

        self.db.commit()
        return processed

    async def collect_bluesky_data(self, player_name: str, player_id: str) -> Dict:
        """Collect Bluesky posts for a player using the official AT Protocol SDK"""

        # Check if Bluesky credentials are available
        if not self.bluesky_handle or not self.bluesky_password:
            logger.info("Bluesky credentials not configured, skipping")
            return {'status': 'skipped', 'reason': 'No credentials configured'}

        try:
            # Use the official AT Protocol SDK
            from atproto import Client as AtProtoClient

            # Create client
            client = AtProtoClient()

            # Execute in a thread pool to avoid blocking async loop
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            executor = ThreadPoolExecutor(max_workers=1)
            loop = asyncio.get_event_loop()

            # Authenticate first
            try:
                await loop.run_in_executor(
                    executor,
                    lambda: client.login(self.bluesky_handle, self.bluesky_password)
                )
                logger.info(f"Successfully authenticated to Bluesky as {self.bluesky_handle}")
            except Exception as auth_error:
                logger.error(f"Bluesky authentication failed: {auth_error}")
                return {'status': 'error', 'message': f'Authentication failed: {auth_error}'}

            # Search for posts about the player
            query = f'{player_name} baseball'

            # Run the synchronous SDK call in an executor
            response = await loop.run_in_executor(
                executor,
                lambda: client.app.bsky.feed.search_posts(
                    {'q': query, 'limit': 50}
                )
            )

            # Convert SDK response to dictionary format for processing
            posts_data = []
            for post in response.posts:
                posts_data.append({
                    'uri': post.uri,
                    'cid': post.cid,
                    'author': {
                        'handle': post.author.handle,
                        'followersCount': getattr(post.author, 'followers_count', 0)
                    },
                    'record': {
                        'text': post.record.text,
                        'createdAt': post.record.created_at,
                        'facets': getattr(post.record, 'facets', [])
                    },
                    'likeCount': getattr(post, 'like_count', 0),
                    'repostCount': getattr(post, 'repost_count', 0),
                    'replyCount': getattr(post, 'reply_count', 0),
                    'quoteCount': getattr(post, 'quote_count', 0)
                })

            # Process posts
            processed_posts = await self._process_bluesky_data(
                {'posts': posts_data},
                player_id
            )

            return {
                'status': 'success',
                'count': len(processed_posts),
                'posts': processed_posts
            }

        except Exception as e:
            logger.error(f"Bluesky collection error: {e}")
            return {'status': 'error', 'message': str(e)}

    async def _process_bluesky_data(self, bluesky_response: Dict, player_id: str) -> List[Dict]:
        """Process and store Bluesky data"""
        processed = []

        if 'posts' not in bluesky_response:
            return processed

        # Get player HYPE record
        player_hype = self.db.query(PlayerHype).filter(
            PlayerHype.player_id == player_id
        ).first()

        if not player_hype:
            return processed

        for post in bluesky_response.get('posts', []):
            try:
                # Generate unique ID for deduplication
                post_uri = post.get('uri', '')
                post_id = f"bluesky_{post_uri.split('/')[-1] if post_uri else post.get('cid', '')}"

                # Check if already exists
                existing = self.db.query(SocialMention).filter(
                    SocialMention.post_id == post_id
                ).first()

                if existing:
                    continue

                # Extract post content
                record = post.get('record', {})
                content = record.get('text', '')

                # Extract author info
                author = post.get('author', {})
                author_handle = author.get('handle', 'unknown')
                author_followers = author.get('followersCount', 0)

                # Extract engagement metrics
                like_count = post.get('likeCount', 0)
                reply_count = post.get('replyCount', 0)
                repost_count = post.get('repostCount', 0)
                quote_count = post.get('quoteCount', 0)

                # Extract hashtags from facets (Bluesky's way of storing rich text)
                hashtags = []
                facets = record.get('facets', [])
                for facet in facets:
                    for feature in facet.get('features', []):
                        if feature.get('$type') == 'app.bsky.richtext.facet#tag':
                            hashtags.append(feature.get('tag', ''))

                # Analyze sentiment
                sentiment_result = await self.sentiment_analyzer.analyze(content)

                # Create mention record
                mention = SocialMention(
                    player_hype_id=player_hype.id,
                    platform='bluesky',
                    post_id=post_id,
                    author_handle=author_handle,
                    author_followers=author_followers,
                    content=content,
                    url=f"https://bsky.app/profile/{author_handle}/post/{post_uri.split('/')[-1] if post_uri else ''}",
                    hashtags=hashtags,
                    likes=like_count,
                    shares=repost_count + quote_count,  # Combine reposts and quotes
                    comments=reply_count,
                    sentiment=sentiment_result['sentiment'],
                    sentiment_confidence=sentiment_result['confidence'],
                    keywords=sentiment_result.get('keywords', []),
                    posted_at=datetime.fromisoformat(record.get('createdAt', '').replace('Z', '+00:00')) if record.get('createdAt') else datetime.utcnow(),
                    collected_at=datetime.utcnow()
                )

                self.db.add(mention)
                processed.append({
                    'id': post_id,
                    'text': content,
                    'author': author_handle,
                    'sentiment': sentiment_result['sentiment']
                })

            except Exception as e:
                logger.error(f"Error processing Bluesky post: {e}")
                continue

        self.db.commit()
        return processed


class SentimentAnalyzer:
    """Analyze sentiment of text using NLP"""

    def __init__(self):
        # In production, would use a proper NLP model like TextBlob, VADER, or transformers
        self.positive_words = {
            'great', 'amazing', 'excellent', 'fantastic', 'incredible', 'awesome',
            'outstanding', 'brilliant', 'superb', 'stellar', 'phenomenal', 'elite',
            'dominant', 'impressive', 'clutch', 'mvp', 'goat', 'beast', 'stud'
        }

        self.negative_words = {
            'terrible', 'awful', 'horrible', 'bad', 'poor', 'disappointing',
            'struggling', 'slump', 'bust', 'overrated', 'injury', 'benched',
            'demoted', 'failed', 'strike out', 'error', 'loss', 'weak'
        }

        self.baseball_positive = {
            'home run', 'homer', 'grand slam', 'triple', 'double', 'rbi',
            'perfect game', 'no-hitter', 'strikeout', 'save', 'win', 'clutch hit',
            'walk-off', 'cycle', 'gold glove', 'all-star', 'rookie of the year'
        }

        self.baseball_negative = {
            'strikeout', 'error', 'wild pitch', 'balk', 'ejected', 'suspended',
            'injured', 'disabled list', 'tommy john', 'slump', 'losing streak'
        }

    async def analyze(self, text: str) -> Dict:
        """Analyze sentiment of text"""
        text_lower = text.lower()

        # Count positive and negative indicators
        positive_score = 0
        negative_score = 0

        # Check individual words
        words = text_lower.split()
        for word in words:
            if word in self.positive_words:
                positive_score += 1
            elif word in self.negative_words:
                negative_score += 1

        # Check phrases
        for phrase in self.baseball_positive:
            if phrase in text_lower:
                positive_score += 2

        for phrase in self.baseball_negative:
            if phrase in text_lower:
                negative_score += 2

        # Determine sentiment
        if positive_score > negative_score + 2:
            sentiment = 'positive'
        elif negative_score > positive_score + 2:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        # Calculate confidence (simplified)
        total_indicators = positive_score + negative_score
        if total_indicators > 0:
            confidence = min(0.9, total_indicators * 0.15)
        else:
            confidence = 0.5

        # Extract keywords (simplified)
        keywords = []
        for phrase in self.baseball_positive:
            if phrase in text_lower:
                keywords.append(phrase)
        for phrase in self.baseball_negative:
            if phrase in text_lower:
                keywords.append(phrase)

        return {
            'sentiment': sentiment,
            'confidence': confidence,
            'positive_score': positive_score,
            'negative_score': negative_score,
            'keywords': keywords[:5]  # Limit to top 5
        }