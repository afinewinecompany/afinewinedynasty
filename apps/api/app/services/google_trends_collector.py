"""
Google Trends Data Collection Service
Collects search interest data from Google Trends for players
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class GoogleTrendsCollector:
    """Collect Google Trends data for players"""

    def __init__(self, db: Session):
        self.db = db
        self.pytrends = None
        self._init_pytrends()

    def _init_pytrends(self):
        """Initialize pytrends client with error handling"""
        try:
            from pytrends.request import TrendReq

            # Initialize with US locale and timezone
            # Note: Using simple initialization to avoid compatibility issues
            self.pytrends = TrendReq(
                hl='en-US',
                tz=360  # US Central Time
            )
            logger.info("Google Trends client initialized successfully")
        except ImportError:
            logger.error("pytrends library not installed. Install with: pip install pytrends")
            self.pytrends = None
        except Exception as e:
            logger.error(f"Failed to initialize Google Trends client: {e}")
            self.pytrends = None

    def collect_player_trends(
        self,
        player_name: str,
        player_hype_id: int,
        timeframe: str = 'today 7-d',
        geo: str = 'US'
    ) -> Dict:
        """
        Collect Google Trends data for a specific player

        Args:
            player_name: Full name of the player to search
            player_hype_id: ID of the PlayerHype record
            timeframe: Google Trends timeframe (default: 'today 7-d')
                Options: 'now 1-H', 'now 4-H', 'today 1-d', 'today 7-d',
                        'today 1-m', 'today 3-m', 'today 12-m', 'today 5-y', 'all'
            geo: Geographic region (default: 'US')

        Returns:
            Dict with trends data including search interest, related queries, etc.
        """
        if not self.pytrends:
            logger.error("Google Trends client not initialized")
            return self._empty_result()

        try:
            # Build payload for Google Trends
            # For baseball players, we might want to add context like "baseball"
            search_term = f"{player_name} baseball"

            self.pytrends.build_payload(
                kw_list=[search_term],
                timeframe=timeframe,
                geo=geo,
                gprop=''  # Web search (empty string for web, 'news' for news, etc.)
            )

            # Get interest over time
            interest_over_time_df = self.pytrends.interest_over_time()

            # Get interest by region (US states)
            interest_by_region_df = self.pytrends.interest_by_region(
                resolution='REGION',  # US states
                inc_low_vol=True
            )

            # Get related queries
            related_queries_dict = self.pytrends.related_queries()

            # Process the data
            result = self._process_trends_data(
                player_name=player_name,
                player_hype_id=player_hype_id,
                interest_over_time=interest_over_time_df,
                interest_by_region=interest_by_region_df,
                related_queries=related_queries_dict,
                timeframe=timeframe,
                geo=geo
            )

            logger.info(f"Successfully collected Google Trends data for {player_name}")
            return result

        except Exception as e:
            logger.error(f"Error collecting Google Trends for {player_name}: {e}")
            return self._empty_result()

    def _process_trends_data(
        self,
        player_name: str,
        player_hype_id: int,
        interest_over_time,
        interest_by_region,
        related_queries,
        timeframe: str,
        geo: str
    ) -> Dict:
        """Process raw Google Trends data into structured format"""

        from app.models.hype import SearchTrend

        # Calculate metrics from interest over time
        if interest_over_time is not None and not interest_over_time.empty:
            # Remove the 'isPartial' column if it exists
            search_term = f"{player_name} baseball"
            if 'isPartial' in interest_over_time.columns:
                interest_over_time = interest_over_time.drop('isPartial', axis=1)

            # Get the search interest values
            interest_values = interest_over_time[search_term] if search_term in interest_over_time.columns else []

            current_interest = float(interest_values.iloc[-1]) if len(interest_values) > 0 else 0.0
            avg_7d_interest = float(interest_values.tail(7).mean()) if len(interest_values) >= 7 else current_interest
            avg_30d_interest = float(interest_values.mean()) if len(interest_values) > 0 else current_interest

            # Calculate growth rate (compare last value to average)
            if avg_7d_interest > 0:
                growth_rate = ((current_interest - avg_7d_interest) / avg_7d_interest) * 100
            else:
                growth_rate = 0.0

            period_start = interest_over_time.index[0].to_pydatetime() if len(interest_over_time) > 0 else datetime.utcnow() - timedelta(days=7)
            period_end = interest_over_time.index[-1].to_pydatetime() if len(interest_over_time) > 0 else datetime.utcnow()
        else:
            current_interest = 0.0
            avg_7d_interest = 0.0
            avg_30d_interest = 0.0
            growth_rate = 0.0
            period_start = datetime.utcnow() - timedelta(days=7)
            period_end = datetime.utcnow()

        # Process regional interest
        regional_data = {}
        if interest_by_region is not None and not interest_by_region.empty:
            # Convert to dict, taking top 10 regions
            search_term = f"{player_name} baseball"
            if search_term in interest_by_region.columns:
                regional_data = interest_by_region[search_term].nlargest(10).to_dict()

        # Process related queries
        related_top = []
        rising_top = []

        if related_queries and search_term in related_queries:
            queries_data = related_queries[search_term]

            # Top related queries
            if queries_data.get('top') is not None and not queries_data['top'].empty:
                top_df = queries_data['top'].head(10)
                related_top = [
                    {'query': row['query'], 'value': int(row['value'])}
                    for _, row in top_df.iterrows()
                ]

            # Rising queries (breakout searches)
            if queries_data.get('rising') is not None and not queries_data['rising'].empty:
                rising_df = queries_data['rising'].head(10)
                rising_top = [
                    {
                        'query': row['query'],
                        'value': str(row['value'])  # Can be 'Breakout' or a number
                    }
                    for _, row in rising_df.iterrows()
                ]

        # Create or update SearchTrend record
        search_trend = SearchTrend(
            player_hype_id=player_hype_id,
            search_interest=current_interest,
            search_interest_avg_7d=avg_7d_interest,
            search_interest_avg_30d=avg_30d_interest,
            search_growth_rate=growth_rate,
            region=geo,
            regional_interest=regional_data,
            related_queries=related_top,
            rising_queries=rising_top,
            collected_at=datetime.utcnow(),
            data_period_start=period_start,
            data_period_end=period_end
        )

        self.db.add(search_trend)
        self.db.commit()

        return {
            'player_name': player_name,
            'search_interest': current_interest,
            'search_interest_avg_7d': avg_7d_interest,
            'search_interest_avg_30d': avg_30d_interest,
            'search_growth_rate': growth_rate,
            'regional_interest': regional_data,
            'related_queries': related_top,
            'rising_queries': rising_top,
            'data_period_start': period_start,
            'data_period_end': period_end
        }

    def _empty_result(self) -> Dict:
        """Return empty result structure for error cases"""
        return {
            'player_name': '',
            'search_interest': 0.0,
            'search_interest_avg_7d': 0.0,
            'search_interest_avg_30d': 0.0,
            'search_growth_rate': 0.0,
            'regional_interest': {},
            'related_queries': [],
            'rising_queries': [],
            'data_period_start': datetime.utcnow() - timedelta(days=7),
            'data_period_end': datetime.utcnow()
        }

    def collect_batch_trends(
        self,
        player_list: List[Tuple[str, int]],
        delay_seconds: int = 2
    ) -> List[Dict]:
        """
        Collect trends for multiple players with rate limiting

        Args:
            player_list: List of (player_name, player_hype_id) tuples
            delay_seconds: Delay between requests to avoid rate limiting

        Returns:
            List of results for each player
        """
        import time

        results = []

        for idx, (player_name, player_hype_id) in enumerate(player_list):
            logger.info(f"Collecting trends for {player_name} ({idx + 1}/{len(player_list)})")

            result = self.collect_player_trends(player_name, player_hype_id)
            results.append(result)

            # Rate limiting: wait between requests
            if idx < len(player_list) - 1:  # Don't wait after the last request
                time.sleep(delay_seconds)

        return results

    def get_latest_trends(self, player_hype_id: int) -> Optional[Dict]:
        """
        Get the most recent Google Trends data for a player

        Args:
            player_hype_id: ID of the PlayerHype record

        Returns:
            Dict with latest trends data or None if not found
        """
        from app.models.hype import SearchTrend
        from sqlalchemy import desc

        latest_trend = self.db.query(SearchTrend).filter(
            SearchTrend.player_hype_id == player_hype_id
        ).order_by(desc(SearchTrend.collected_at)).first()

        if not latest_trend:
            return None

        return {
            'search_interest': latest_trend.search_interest,
            'search_interest_avg_7d': latest_trend.search_interest_avg_7d,
            'search_interest_avg_30d': latest_trend.search_interest_avg_30d,
            'search_growth_rate': latest_trend.search_growth_rate,
            'regional_interest': latest_trend.regional_interest,
            'related_queries': latest_trend.related_queries,
            'rising_queries': latest_trend.rising_queries,
            'collected_at': latest_trend.collected_at,
            'data_period_start': latest_trend.data_period_start,
            'data_period_end': latest_trend.data_period_end
        }
