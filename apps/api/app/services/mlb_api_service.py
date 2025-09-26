import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)


class MLBStatsAPIError(Exception):
    """Custom exception for MLB Stats API errors."""
    pass


class RateLimitExceededError(MLBStatsAPIError):
    """Exception raised when API rate limit is exceeded."""
    pass


class MLBAPIClient:
    """MLB Stats API client with rate limiting and error handling."""

    def __init__(self):
        self.base_url = settings.MLB_STATS_API_BASE_URL
        self.request_delay = settings.MLB_STATS_API_REQUEST_DELAY
        self.daily_limit = settings.MLB_STATS_API_RATE_LIMIT
        self.request_count = 0
        self.last_reset = datetime.now()
        self.session: Optional[ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        timeout = ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": "AFineWineDynasty/1.0",
                "Accept": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def _reset_daily_counter(self):
        """Reset daily request counter if new day."""
        now = datetime.now()
        if now.date() > self.last_reset.date():
            self.request_count = 0
            self.last_reset = now
            logger.info("Daily MLB API request counter reset")

    def _check_rate_limit(self):
        """Check if rate limit would be exceeded."""
        self._reset_daily_counter()
        if self.request_count >= self.daily_limit:
            raise RateLimitExceededError(
                f"Daily rate limit of {self.daily_limit} requests exceeded"
            )

    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request with rate limiting and error handling."""
        self._check_rate_limit()

        if not self.session:
            raise MLBStatsAPIError("Session not initialized. Use async context manager.")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            # Add request delay to avoid overwhelming API
            if self.request_count > 0:
                await asyncio.sleep(self.request_delay)

            logger.debug(f"MLB API request: {url} with params: {params}")

            async with self.session.get(url, params=params) as response:
                self.request_count += 1

                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"MLB API response received: {len(str(data))} bytes")
                    return data
                elif response.status == 429:
                    raise RateLimitExceededError(f"API rate limit exceeded: {response.status}")
                else:
                    error_text = await response.text()
                    raise MLBStatsAPIError(
                        f"MLB API request failed with status {response.status}: {error_text}"
                    )

        except aiohttp.ClientError as e:
            raise MLBStatsAPIError(f"Network error during MLB API request: {str(e)}")
        except json.JSONDecodeError as e:
            raise MLBStatsAPIError(f"Invalid JSON response from MLB API: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry_error_callback=lambda retry_state: logger.warning(
            f"MLB API retry attempt {retry_state.attempt_number}"
        )
    )
    async def get_prospects_data(self, sport_id: int = 11) -> Dict[str, Any]:
        """
        Get prospects data from MLB API.

        Args:
            sport_id: Sport ID (11 for baseball)

        Returns:
            Dict containing prospects data
        """
        params = {
            "sportId": sport_id,
            "fields": "people,id,fullName,primaryPosition,currentTeam,birthDate,height,weight,mlbDebutDate"
        }

        return await self._make_request("people", params)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def get_player_stats(self, player_id: int, season: Optional[int] = None) -> Dict[str, Any]:
        """
        Get player statistics from MLB API.

        Args:
            player_id: MLB player ID
            season: Season year (current year if None)

        Returns:
            Dict containing player statistics
        """
        if season is None:
            season = datetime.now().year

        params = {
            "season": season,
            "stats": "season",
            "group": "hitting,pitching"
        }

        return await self._make_request(f"people/{player_id}/stats", params)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def get_teams_data(self, sport_ids: str = "11") -> Dict[str, Any]:
        """
        Get teams data from MLB API.

        Args:
            sport_ids: Comma-separated sport IDs

        Returns:
            Dict containing teams data
        """
        params = {
            "sportIds": sport_ids,
            "fields": "teams,id,name,abbreviation,teamName,locationName,league,division"
        }

        return await self._make_request("teams", params)

    async def get_minor_league_levels(self) -> Dict[str, Any]:
        """Get minor league levels data."""
        params = {
            "fields": "leagues,id,name,abbreviation,sport,hasWildcard"
        }

        return await self._make_request("league", params)

    def get_request_stats(self) -> Dict[str, Any]:
        """Get current request statistics."""
        return {
            "requests_made_today": self.request_count,
            "daily_limit": self.daily_limit,
            "requests_remaining": max(0, self.daily_limit - self.request_count),
            "last_reset": self.last_reset.isoformat()
        }


# Singleton instance for dependency injection
mlb_api_client = MLBAPIClient()