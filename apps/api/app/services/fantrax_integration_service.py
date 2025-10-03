"""
Fantrax Integration Service using FantraxAPI Library

Handles all Fantrax operations using the unofficial FantraxAPI Python library
with cookie-based authentication for private leagues.
"""

import pickle
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from requests import Session

from fantraxapi import FantraxAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.fantrax_cookie_service import FantraxCookieService

logger = logging.getLogger(__name__)


class FantraxIntegrationService:
    """
    Service for interacting with Fantrax using the FantraxAPI library

    Uses cookie-based authentication for private league access.
    """

    def __init__(self, db: AsyncSession, user_id: int):
        """
        Initialize Fantrax Integration Service

        @param db - Database session for user data access
        @param user_id - User ID for cookie retrieval

        @since 1.0.0
        """
        self.db = db
        self.user_id = user_id
        self._session: Optional[Session] = None

    async def _get_authenticated_session(self) -> Optional[Session]:
        """
        Get authenticated requests session with user's cookies

        @returns Authenticated Session or None if no cookies available

        @since 1.0.0
        """
        if self._session:
            return self._session

        # Retrieve user's cookies
        cookies = await FantraxCookieService.get_user_cookies(self.db, self.user_id)
        if not cookies:
            logger.error(f"No Fantrax cookies found for user {self.user_id}")
            return None

        # Create session with cookies
        session = Session()
        for cookie in cookies:
            session.cookies.set(cookie["name"], cookie["value"])

        self._session = session
        return session

    async def get_user_leagues(self) -> List[Dict[str, Any]]:
        """
        Get all leagues for the authenticated user

        Note: This requires determining the user's team IDs first.
        The FantraxAPI library requires a specific league_id to initialize.

        @returns List of league information dictionaries

        @since 1.0.0
        """
        # Note: FantraxAPI doesn't have a direct "get all leagues" method
        # Users will need to manually add their league IDs
        logger.warning("FantraxAPI requires league_id to initialize - user must provide league IDs")
        return []

    async def connect_league(self, league_id: str) -> Dict[str, Any]:
        """
        Connect to a specific Fantrax league

        @param league_id - Fantrax league ID

        @returns Connection result with league info

        @since 1.0.0
        """
        try:
            session = await self._get_authenticated_session()
            if not session:
                return {
                    "success": False,
                    "error": "User not authenticated with Fantrax. Please connect your account first."
                }

            # Initialize FantraxAPI with league ID
            api = FantraxAPI(league_id, session=session)

            # Get league information
            teams = api.teams
            scoring_periods = api.scoring_periods()

            league_info = {
                "league_id": league_id,
                "teams": [
                    {
                        "team_id": team.id,
                        "name": team.name,
                        "logo": getattr(team, 'logo', None),
                    }
                    for team in teams
                ],
                "team_count": len(teams),
                "scoring_periods": len(scoring_periods),
                "connected_at": datetime.utcnow().isoformat()
            }

            return {
                "success": True,
                "league_info": league_info
            }

        except Exception as e:
            logger.error(f"Failed to connect to league {league_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def sync_roster(
        self,
        league_id: str,
        team_id: str
    ) -> Dict[str, Any]:
        """
        Sync roster data for a specific team in a league

        @param league_id - Fantrax league ID
        @param team_id - Team ID within the league

        @returns Sync result with success status and player count

        @since 1.0.0
        """
        try:
            session = await self._get_authenticated_session()
            if not session:
                return {
                    "success": False,
                    "error": "User not authenticated with Fantrax"
                }

            # Initialize FantraxAPI
            api = FantraxAPI(league_id, session=session)

            # Get roster information
            roster = api.roster_info(team_id)

            # Process roster data
            players = []
            if hasattr(roster, 'players') and roster.players:
                for player in roster.players:
                    player_data = {
                        "player_id": getattr(player, 'id', None),
                        "name": getattr(player, 'name', ''),
                        "positions": getattr(player, 'positions', []),
                        "team": getattr(player, 'team', ''),
                        "status": getattr(player, 'status', 'active'),
                        # Add more fields as available from the player object
                    }
                    players.append(player_data)

            return {
                "success": True,
                "players_count": len(players),
                "players": players,
                "team_id": team_id,
                "league_id": league_id,
                "synced_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to sync roster for team {team_id} in league {league_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_standings(
        self,
        league_id: str,
        week: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get league standings

        @param league_id - Fantrax league ID
        @param week - Optional week number (None for current week)

        @returns Standings data

        @since 1.0.0
        """
        try:
            session = await self._get_authenticated_session()
            if not session:
                return {
                    "success": False,
                    "error": "User not authenticated with Fantrax"
                }

            # Initialize FantraxAPI
            api = FantraxAPI(league_id, session=session)

            # Get standings
            standings = api.standings(week=week)

            # Process standings data
            standings_data = {
                "week": week,
                "teams": []
            }

            if hasattr(standings, 'teams') and standings.teams:
                for team in standings.teams:
                    team_data = {
                        "team_id": getattr(team, 'id', None),
                        "name": getattr(team, 'name', ''),
                        "wins": getattr(team, 'wins', 0),
                        "losses": getattr(team, 'losses', 0),
                        "ties": getattr(team, 'ties', 0),
                        "points": getattr(team, 'points', 0),
                        # Add more fields as available
                    }
                    standings_data["teams"].append(team_data)

            return {
                "success": True,
                "standings": standings_data
            }

        except Exception as e:
            logger.error(f"Failed to get standings for league {league_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_transactions(
        self,
        league_id: str,
        count: int = 100
    ) -> Dict[str, Any]:
        """
        Get recent transactions for a league

        @param league_id - Fantrax league ID
        @param count - Number of transactions to retrieve

        @returns List of recent transactions

        @since 1.0.0
        """
        try:
            session = await self._get_authenticated_session()
            if not session:
                return {
                    "success": False,
                    "error": "User not authenticated with Fantrax"
                }

            # Initialize FantraxAPI
            api = FantraxAPI(league_id, session=session)

            # Get transactions
            transactions = api.transactions(count=count)

            # Process transactions data
            transactions_data = []
            for transaction in transactions:
                transaction_data = {
                    "type": getattr(transaction, 'type', ''),
                    "player": getattr(transaction, 'player', ''),
                    "from_team": getattr(transaction, 'from_team', ''),
                    "to_team": getattr(transaction, 'to_team', ''),
                    "timestamp": getattr(transaction, 'timestamp', None),
                    # Add more fields as available
                }
                transactions_data.append(transaction_data)

            return {
                "success": True,
                "transactions": transactions_data,
                "count": len(transactions_data)
            }

        except Exception as e:
            logger.error(f"Failed to get transactions for league {league_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_trade_block(self, league_id: str) -> Dict[str, Any]:
        """
        Get trade block for a league

        @param league_id - Fantrax league ID

        @returns List of players on trade block

        @since 1.0.0
        """
        try:
            session = await self._get_authenticated_session()
            if not session:
                return {
                    "success": False,
                    "error": "User not authenticated with Fantrax"
                }

            # Initialize FantraxAPI
            api = FantraxAPI(league_id, session=session)

            # Get trade block
            trade_block = api.trade_block()

            # Process trade block data
            trade_block_data = []
            for item in trade_block:
                item_data = {
                    "player": getattr(item, 'player', ''),
                    "team": getattr(item, 'team', ''),
                    # Add more fields as available
                }
                trade_block_data.append(item_data)

            return {
                "success": True,
                "trade_block": trade_block_data,
                "count": len(trade_block_data)
            }

        except Exception as e:
            logger.error(f"Failed to get trade block for league {league_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
