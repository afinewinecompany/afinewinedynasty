"""
Fantrax API Client Service

Handles all interactions with the Fantrax API including league data fetching,
roster synchronization, and caching strategies.
"""

from typing import Optional, Dict, Any, List
import httpx
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import User
from app.services.fantrax_oauth_service import FantraxOAuthService
from app.core.security import decrypt_value
from app.core.cache_manager import CacheManager
import logging
import json
import asyncio

# Initialize cache manager instance
cache_manager = CacheManager()

logger = logging.getLogger(__name__)


class FantraxAPIService:
    """
    Service for interacting with Fantrax API

    Manages API calls, token refresh, rate limiting, and caching
    for all Fantrax data operations.
    """

    API_BASE_URL = "https://www.fantrax.com/api/v2"

    # Cache TTL configurations (in seconds)
    CACHE_TTL = {
        "leagues": 86400,      # 24 hours for league data
        "roster": 3600,        # 1 hour for roster data
        "settings": 86400,     # 24 hours for league settings
        "transactions": 900,   # 15 minutes for recent transactions
    }

    def __init__(self, db: AsyncSession, user_id: int):
        """
        Initialize Fantrax API Service

        @param db - Database session for user data access
        @param user_id - User ID for token retrieval

        @since 1.0.0
        """
        self.db = db
        self.user_id = user_id
        self._access_token = None
        self._token_expires_at = None

    async def _get_access_token(self) -> Optional[str]:
        """
        Get valid access token, refreshing if necessary

        @returns Valid access token or None if unable to obtain

        @performance
        - Token refresh: 300-500ms when needed
        - Cached token: <1ms

        @since 1.0.0
        """
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at:
                return self._access_token

        # Get user's refresh token
        stmt = select(User).where(User.id == self.user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.fantrax_refresh_token:
            logger.error(f"No Fantrax refresh token for user {self.user_id}")
            return None

        # Refresh the access token
        token_response = await FantraxOAuthService.refresh_access_token(
            user.fantrax_refresh_token
        )

        if not token_response:
            logger.error(f"Failed to refresh access token for user {self.user_id}")
            return None

        # Cache the new access token
        self._access_token = token_response["access_token"]
        expires_in = token_response.get("expires_in", 3600)
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)

        # Update refresh token if a new one was provided
        if "refresh_token" in token_response:
            await FantraxOAuthService.store_tokens(
                self.db,
                self.user_id,
                user.fantrax_user_id,
                token_response["refresh_token"]
            )

        return self._access_token

    async def _make_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Make authenticated API request to Fantrax

        @param method - HTTP method (GET, POST, etc.)
        @param endpoint - API endpoint path
        @param params - Query parameters
        @param json_data - JSON body data
        @param retry_count - Current retry attempt

        @returns API response data or None on failure

        @performance
        - Typical response: 200-800ms
        - With retry: up to 3 seconds

        @since 1.0.0
        """
        access_token = await self._get_access_token()
        if not access_token:
            return None

        url = f"{self.API_BASE_URL}/{endpoint}"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_data
                )

                # Handle rate limiting
                if response.status_code == 429:
                    if retry_count < 3:
                        retry_after = int(response.headers.get("Retry-After", 5))
                        logger.warning(f"Rate limited, retrying after {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        return await self._make_api_request(
                            method, endpoint, params, json_data, retry_count + 1
                        )
                    logger.error("Max retries exceeded for rate limiting")
                    return None

                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as e:
                logger.error(f"API request failed: {str(e)}")
                return None

    async def get_user_leagues(self) -> List[Dict[str, Any]]:
        """
        Get all leagues for the authenticated user

        @returns List of league information dictionaries

        @performance
        - Response time: 200-500ms with caching
        - Cache TTL: 24 hours

        @since 1.0.0
        """
        # Check cache first
        cache_key = f"fantrax:leagues:{self.user_id}"
        cached_leagues = await cache_manager.get(cache_key)
        if cached_leagues:
            return json.loads(cached_leagues)

        # Fetch from API
        response = await self._make_api_request("GET", "leagues")
        if not response:
            return []

        leagues = response.get("leagues", [])

        # Process and enrich league data
        processed_leagues = []
        for league in leagues:
            processed_league = {
                "league_id": league["id"],
                "name": league["name"],
                "type": league.get("league_type", "unknown"),
                "team_count": league.get("team_count", 0),
                "roster_size": league.get("roster_size", 0),
                "scoring_type": league.get("scoring_type", "unknown"),
                "is_active": league.get("is_active", True),
                "season": league.get("season", datetime.now().year),
                "my_team_id": league.get("my_team_id"),
                "my_team_name": league.get("my_team_name")
            }

            # Get last sync time from database if available
            # This would require a separate table for tracking syncs
            processed_league["last_sync"] = None

            processed_leagues.append(processed_league)

        # Cache the results
        await cache_manager.set(
            cache_key,
            json.dumps(processed_leagues),
            ttl=self.CACHE_TTL["leagues"]
        )

        return processed_leagues

    async def get_league_settings(self, league_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed league settings and configuration

        @param league_id - Fantrax league ID

        @returns League settings dictionary

        @performance
        - Response time: 300-600ms
        - Cache TTL: 24 hours

        @since 1.0.0
        """
        # Check cache
        cache_key = f"fantrax:settings:{self.user_id}:{league_id}"
        cached_settings = await cache_manager.get(cache_key)
        if cached_settings:
            return json.loads(cached_settings)

        # Fetch from API
        response = await self._make_api_request(
            "GET",
            f"leagues/{league_id}/settings"
        )

        if not response:
            return None

        settings = {
            "roster_positions": response.get("roster_positions", []),
            "scoring_system": response.get("scoring_system", {}),
            "trade_settings": response.get("trade_settings", {}),
            "waiver_settings": response.get("waiver_settings", {}),
            "keeper_rules": response.get("keeper_rules", {}),
            "contract_settings": response.get("contract_settings", {}),
            "minor_league_slots": response.get("minor_league_slots", 0),
            "injured_list_slots": response.get("injured_list_slots", 0)
        }

        # Cache the results
        await cache_manager.set(
            cache_key,
            json.dumps(settings),
            ttl=self.CACHE_TTL["settings"]
        )

        return settings

    async def sync_roster(
        self,
        league_id: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Sync roster data for a specific league

        @param league_id - Fantrax league ID
        @param force_refresh - Force sync even if recently synced

        @returns Sync result with success status and player count

        @performance
        - Response time: 2-5 seconds for 40-player roster
        - Multiple API calls for complete roster data

        @since 1.0.0
        """
        # Check if we need to sync (unless forced)
        if not force_refresh:
            cache_key = f"fantrax:roster:{self.user_id}:{league_id}"
            cached_roster = await cache_manager.get(cache_key)
            if cached_roster:
                roster = json.loads(cached_roster)
                return {
                    "success": True,
                    "players_count": len(roster.get("players", [])),
                    "from_cache": True
                }

        # Fetch roster from API
        response = await self._make_api_request(
            "GET",
            f"leagues/{league_id}/roster"
        )

        if not response:
            return {
                "success": False,
                "error": "Failed to fetch roster from Fantrax"
            }

        # Process roster data
        players = []
        for player in response.get("players", []):
            processed_player = {
                "player_id": player["id"],
                "name": player["name"],
                "positions": player.get("positions", []),
                "team": player.get("team", "FA"),
                "age": player.get("age"),
                "contract_years": player.get("contract_years"),
                "contract_value": player.get("contract_value"),
                "status": player.get("status", "active"),
                "minor_league_eligible": player.get("minor_league_eligible", False),
                "stats_current": player.get("current_stats", {}),
                "stats_projected": player.get("projected_stats", {})
            }
            players.append(processed_player)

        roster_data = {
            "league_id": league_id,
            "team_id": response.get("team_id"),
            "team_name": response.get("team_name"),
            "players": players,
            "last_updated": datetime.utcnow().isoformat()
        }

        # Cache the roster data
        cache_key = f"fantrax:roster:{self.user_id}:{league_id}"
        await cache_manager.set(
            cache_key,
            json.dumps(roster_data),
            ttl=self.CACHE_TTL["roster"]
        )

        # Store in database for persistence
        # This would require the FantraxRoster model implementation
        await self._store_roster_in_db(league_id, roster_data)

        return {
            "success": True,
            "players_count": len(players),
            "from_cache": False
        }

    async def get_roster(self, league_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached roster for a league

        @param league_id - Fantrax league ID

        @returns Roster data or None if not found

        @performance
        - Response time: <100ms (from cache)

        @since 1.0.0
        """
        cache_key = f"fantrax:roster:{self.user_id}:{league_id}"
        cached_roster = await cache_manager.get(cache_key)

        if cached_roster:
            return json.loads(cached_roster)

        # Try to load from database if not in cache
        # This would require database query implementation
        return None

    async def get_player_details(
        self,
        player_id: str,
        league_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific player

        @param player_id - Fantrax player ID
        @param league_id - League context for player data

        @returns Detailed player information

        @performance
        - Response time: 200-400ms
        - Cached for 1 hour

        @since 1.0.0
        """
        cache_key = f"fantrax:player:{player_id}:{league_id}"
        cached_player = await cache_manager.get(cache_key)

        if cached_player:
            return json.loads(cached_player)

        # Fetch from API
        response = await self._make_api_request(
            "GET",
            f"players/{player_id}",
            params={"league_id": league_id}
        )

        if response:
            # Cache the result
            await cache_manager.set(
                cache_key,
                json.dumps(response),
                ttl=self.CACHE_TTL["roster"]
            )

        return response

    async def get_recent_transactions(
        self,
        league_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get recent transactions for a league

        @param league_id - Fantrax league ID
        @param limit - Number of transactions to retrieve

        @returns List of recent transactions

        @performance
        - Response time: 300-600ms
        - Cache TTL: 15 minutes

        @since 1.0.0
        """
        cache_key = f"fantrax:transactions:{league_id}:{limit}"
        cached_transactions = await cache_manager.get(cache_key)

        if cached_transactions:
            return json.loads(cached_transactions)

        # Fetch from API
        response = await self._make_api_request(
            "GET",
            f"leagues/{league_id}/transactions",
            params={"limit": limit}
        )

        if response:
            transactions = response.get("transactions", [])

            # Cache the results
            await cache_manager.set(
                cache_key,
                json.dumps(transactions),
                ttl=self.CACHE_TTL["transactions"]
            )

            return transactions

        return []

    async def _store_roster_in_db(
        self,
        league_id: str,
        roster_data: Dict[str, Any]
    ) -> None:
        """
        Store roster data in database for persistence with transaction handling

        @param league_id - League ID
        @param roster_data - Roster data to store

        @throws ValueError When league not found or invalid roster data
        @throws Exception When database transaction fails

        @since 1.0.0
        """
        from app.db.models import FantraxLeague, FantraxRoster, FantraxSyncHistory
        from datetime import datetime

        start_time = datetime.now()

        try:
            # Begin transaction - fetch league
            stmt = select(FantraxLeague).where(
                FantraxLeague.league_id == league_id,
                FantraxLeague.user_id == self.user_id
            )
            result = await self.db.execute(stmt)
            fantrax_league = result.scalar_one_or_none()

            if not fantrax_league:
                raise ValueError(f"League {league_id} not found for user {self.user_id}")

            # Delete existing roster data for this league
            delete_stmt = select(FantraxRoster).where(
                FantraxRoster.league_id == fantrax_league.id
            )
            existing_rosters = await self.db.execute(delete_stmt)
            for roster in existing_rosters.scalars():
                await self.db.delete(roster)

            # Insert new roster data
            players_synced = 0
            for player in roster_data.get('players', []):
                roster_entry = FantraxRoster(
                    league_id=fantrax_league.id,
                    player_id=player.get('id', ''),
                    player_name=player.get('name', ''),
                    positions=player.get('positions', []),
                    contract_years=player.get('contract_years'),
                    contract_value=player.get('contract_value'),
                    age=player.get('age'),
                    team=player.get('team', 'FA'),
                    status=player.get('status', 'active'),
                    minor_league_eligible=player.get('minor_league_eligible', False),
                    synced_at=datetime.now()
                )
                self.db.add(roster_entry)
                players_synced += 1

            # Update league last_sync timestamp
            fantrax_league.last_sync = datetime.now()

            # Record sync history
            sync_duration = int((datetime.now() - start_time).total_seconds() * 1000)
            sync_record = FantraxSyncHistory(
                league_id=fantrax_league.id,
                sync_type='roster',
                players_synced=players_synced,
                success=True,
                sync_duration_ms=sync_duration,
                synced_at=datetime.now()
            )
            self.db.add(sync_record)

            # Commit transaction
            await self.db.commit()
            logger.info(f"Successfully stored {players_synced} players for league {league_id}")

        except ValueError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()

            # Record failed sync
            try:
                stmt = select(FantraxLeague).where(
                    FantraxLeague.league_id == league_id,
                    FantraxLeague.user_id == self.user_id
                )
                result = await self.db.execute(stmt)
                fantrax_league = result.scalar_one_or_none()

                if fantrax_league:
                    sync_duration = int((datetime.now() - start_time).total_seconds() * 1000)
                    sync_record = FantraxSyncHistory(
                        league_id=fantrax_league.id,
                        sync_type='roster',
                        players_synced=0,
                        success=False,
                        error_message=str(e)[:255],
                        sync_duration_ms=sync_duration,
                        synced_at=datetime.now()
                    )
                    self.db.add(sync_record)
                    await self.db.commit()
            except:
                pass  # Don't fail if we can't record the error

            logger.error(f"Failed to store roster for league {league_id}: {str(e)}")
            raise Exception(f"Database error storing roster: {str(e)}")