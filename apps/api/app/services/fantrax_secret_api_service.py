"""
Fantrax Official API Service using Secret ID

This service uses the official Fantrax REST API (v1.2) which requires
a User Secret ID instead of OAuth authentication.

Users can find their Secret ID on their Fantrax User Profile screen.
"""

from typing import Optional, Dict, Any, List
import httpx
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import User
from app.core.security import encrypt_value, decrypt_value
import logging
import json

logger = logging.getLogger(__name__)


class FantraxSecretAPIService:
    """
    Service for interacting with Fantrax Official REST API using Secret ID

    API Documentation: https://www.fantrax.com/fxea/
    Base URL: https://www.fantrax.com/fxea/general/
    """

    API_BASE_URL = "https://www.fantrax.com/fxea/general"

    def __init__(self, secret_id: str):
        """
        Initialize Fantrax Secret API Service

        Args:
            secret_id: User's Fantrax Secret ID from their profile
        """
        self.secret_id = secret_id

    async def _make_api_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> Optional[Dict[str, Any]]:
        """
        Make API request to Fantrax

        Args:
            endpoint: API endpoint (e.g., 'getLeagues', 'getLeagueInfo')
            params: Query string parameters
            json_data: JSON body for POST requests
            method: HTTP method (GET or POST)

        Returns:
            API response data or None on failure
        """
        url = f"{self.API_BASE_URL}/{endpoint}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method == "POST":
                    response = await client.post(
                        url,
                        json=json_data,
                        params=params
                    )
                else:
                    response = await client.get(
                        url,
                        params=params
                    )

                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as e:
                logger.error(f"Fantrax API request failed: {str(e)}")
                return None

    async def get_leagues(self) -> List[Dict[str, Any]]:
        """
        Retrieve the list of leagues for the user

        API Endpoint: /fxea/general/getLeagues

        Returns:
            List of leagues with:
            - league_id: League ID
            - name: League name
            - teams: List of teams the user owns in this league
        """
        response = await self._make_api_request(
            "getLeagues",
            params={"userSecretId": self.secret_id}
        )

        if not response:
            return []

        # Log the raw response structure for debugging
        logger.info(f"Fantrax API raw response: {json.dumps(response, indent=2)[:500]}")  # Log first 500 chars

        # The API might return leagues directly or wrapped in an object
        # Try different possible response structures
        leagues = []

        if isinstance(response, list):
            # Response is directly a list of leagues
            leagues = response
        elif isinstance(response, dict):
            # Response might have leagues under different keys
            leagues = response.get("leagues", response.get("data", []))

            # If still empty, maybe the response IS the league data
            if not leagues and "leagueId" in response:
                leagues = [response]

        processed_leagues = []

        for league in leagues:
            # Try different possible field names for league ID and name
            league_id = league.get("leagueId") or league.get("id") or league.get("league_id")
            league_name = league.get("leagueName") or league.get("name") or league.get("league_name")

            # Skip if we don't have at least an ID
            if not league_id:
                logger.warning(f"Skipping league with no ID: {league}")
                continue

            processed_league = {
                "league_id": league_id,
                "name": league_name or "Unknown League",
                "sport": league.get("sport", "MLB"),
                "teams": []
            }

            # Extract user's teams in this league
            teams = league.get("teams", league.get("userTeams", []))
            for team in teams:
                team_id = team.get("teamId") or team.get("id") or team.get("team_id")
                team_name = team.get("teamName") or team.get("name") or team.get("team_name")

                if team_id:
                    processed_league["teams"].append({
                        "team_id": team_id,
                        "team_name": team_name or "Unknown Team"
                    })

            processed_leagues.append(processed_league)

        logger.info(f"Processed {len(processed_leagues)} leagues")
        return processed_leagues

    async def get_league_info(self, league_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve detailed information about a specific league

        API Endpoint: /fxea/general/getLeagueInfo

        Args:
            league_id: Fantrax League ID

        Returns:
            League info including:
            - teams: All teams in league
            - matchups: Current matchups
            - players: Players in pool with info
            - settings: League configuration settings
        """
        response = await self._make_api_request(
            "getLeagueInfo",
            params={"leagueId": league_id}
        )

        if not response:
            return None

        return {
            "league_id": league_id,
            "name": response.get("name"),
            "sport": response.get("sport"),
            "teams": response.get("teams", []),
            "matchups": response.get("matchups", []),
            "players": response.get("players", []),
            "settings": response.get("settings", {}),
            "current_period": response.get("currentPeriod"),
            "season": response.get("season")
        }

    async def get_team_rosters(
        self,
        league_id: str,
        period: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve roster data for all teams in a league

        API Endpoint: /fxea/general/getTeamRosters

        Args:
            league_id: Fantrax League ID
            period: Optional lineup period (defaults to current/upcoming)

        Returns:
            Roster data including:
            - rosters: List of all team rosters
            - Each roster includes: players, positions, salaries, contracts
        """
        params = {"leagueId": league_id}
        if period is not None:
            params["period"] = period

        response = await self._make_api_request(
            "getTeamRosters",
            params=params
        )

        if not response:
            return None

        # Log sample roster data to understand structure
        rosters_data = response.get("rosters", [])
        if rosters_data:
            if isinstance(rosters_data, dict):
                # If rosters is a dict keyed by team ID
                first_team_id = list(rosters_data.keys())[0]
                first_roster = rosters_data[first_team_id]
                logger.info(f"Sample roster structure for team {first_team_id}: {json.dumps(first_roster, indent=2)[:1000]}")

                # Check roster items
                roster_items = first_roster.get("rosterItems", first_roster.get("players", []))
                if roster_items and len(roster_items) > 0:
                    logger.info(f"Sample roster item: {json.dumps(roster_items[0], indent=2)[:500]}")
            elif isinstance(rosters_data, list) and len(rosters_data) > 0:
                logger.info(f"Sample roster structure: {json.dumps(rosters_data[0], indent=2)[:1000]}")

        return {
            "league_id": league_id,
            "period": response.get("period"),
            "rosters": rosters_data
        }

    async def get_standings(self, league_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve current standings for a league

        API Endpoint: /fxea/general/getStandings

        Args:
            league_id: Fantrax League ID

        Returns:
            Standings data including:
            - standings: List of teams with rank, points, W-L-T, etc.
        """
        response = await self._make_api_request(
            "getStandings",
            params={"leagueId": league_id}
        )

        if not response:
            return None

        return {
            "league_id": league_id,
            "standings": response.get("standings", [])
        }

    async def get_draft_results(self, league_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve draft results for a league

        API Endpoint: /fxea/general/getDraftResults

        Args:
            league_id: Fantrax League ID

        Returns:
            Draft results including:
            - picks: List of all draft picks with player, team, round, pick number
        """
        response = await self._make_api_request(
            "getDraftResults",
            params={"leagueId": league_id}
        )

        if not response:
            return None

        return {
            "league_id": league_id,
            "draft_results": response.get("picks", [])
        }

    async def get_draft_picks(self, league_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve future and current draft picks for a league

        API Endpoint: /fxea/general/getDraftPicks

        Args:
            league_id: Fantrax League ID

        Returns:
            Draft picks data including future picks ownership
        """
        response = await self._make_api_request(
            "getDraftPicks",
            params={"leagueId": league_id}
        )

        if not response:
            return None

        return {
            "league_id": league_id,
            "draft_picks": response.get("draftPicks", [])
        }

    async def get_player_ids(self, sport: str = "MLB") -> Optional[Dict[str, Any]]:
        """
        Retrieve Fantrax player IDs for all players in a sport

        API Endpoint: /fxea/general/getPlayerIds

        Args:
            sport: Sport code (NFL, MLB, NHL, NBA, etc.)

        Returns:
            Dictionary mapping player names to Fantrax IDs
        """
        response = await self._make_api_request(
            "getPlayerIds",
            params={"sport": sport}
        )

        return response

    async def get_enriched_team_roster(
        self,
        league_id: str,
        team_id: str,
        period: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get team roster enriched with full player information

        Combines data from getTeamRosters (contract/roster info) with
        getLeagueInfo (player names, teams, positions, ages)

        Args:
            league_id: Fantrax League ID
            team_id: Team ID to get roster for
            period: Optional lineup period

        Returns:
            Enriched roster with full player details
        """
        # Fetch roster data (has contracts but maybe not full player info)
        rosters_response = await self.get_team_rosters(league_id, period)
        if not rosters_response:
            logger.error(f"Failed to fetch rosters for league {league_id}")
            return None

        # Fetch league info (has full player pool data)
        league_info = await self.get_league_info(league_id)
        if not league_info:
            logger.warning(f"Failed to fetch league info for player enrichment, league {league_id}")

        # Extract the specific team's roster
        rosters = rosters_response.get("rosters", {})
        if isinstance(rosters, dict):
            team_roster = rosters.get(team_id)
        else:
            # If rosters is a list, find by team_id
            team_roster = next((r for r in rosters if r.get("teamId") == team_id), None)

        if not team_roster:
            logger.error(f"Team {team_id} not found in rosters")
            return None

        # Create player lookup from league info
        player_lookup = {}
        if league_info and "players" in league_info:
            for player in league_info.get("players", []):
                player_id = player.get("id") or player.get("playerId")
                if player_id:
                    player_lookup[player_id] = player

        # Enrich roster items with full player data
        roster_items = team_roster.get("rosterItems", team_roster.get("players", []))
        enriched_items = []

        for item in roster_items:
            # Get player ID from roster item
            player_id = item.get("playerId") or item.get("id") or item.get("player_id")

            # Start with roster item data (has contracts)
            enriched_player = dict(item)

            # Enrich with league player pool data if available
            if player_id and player_id in player_lookup:
                pool_player = player_lookup[player_id]
                # Merge data, preferring pool data for player details
                enriched_player.update({
                    "id": player_id,
                    "name": pool_player.get("name") or pool_player.get("playerName") or enriched_player.get("name"),
                    "mlbTeam": pool_player.get("mlbTeam") or pool_player.get("team") or enriched_player.get("mlbTeam"),
                    "positions": pool_player.get("positions") or pool_player.get("eligiblePositions") or enriched_player.get("positions", []),
                    "age": pool_player.get("age") or enriched_player.get("age"),
                    "status": pool_player.get("status") or pool_player.get("injuryStatus") or enriched_player.get("status"),
                })

            enriched_items.append(enriched_player)

        # Log sample enriched player
        if enriched_items:
            logger.info(f"Sample enriched player: {json.dumps(enriched_items[0], indent=2)[:500]}")

        return {
            "league_id": league_id,
            "team_id": team_id,
            "team_name": team_roster.get("teamName") or team_roster.get("name"),
            "period": rosters_response.get("period"),
            "rosterItems": enriched_items
        }

    async def get_adp(
        self,
        sport: str = "MLB",
        position: Optional[str] = None,
        show_all_positions: bool = False,
        order: str = "ADP"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve ADP (Average Draft Pick) info for players

        API Endpoint: /fxea/general/getAdp

        Args:
            sport: Sport code (NFL, MLB, NHL, NBA, etc.)
            position: Optional position filter (e.g., "QB", "WR")
            show_all_positions: Show all Fantrax positions vs default
            order: Sort order - "ADP" or "Name"

        Returns:
            List of players with ADP information
        """
        params = {
            "sport": sport,
            "order": order
        }

        if position:
            params["position"] = position

        if show_all_positions:
            params["showAllPositions"] = "true"

        response = await self._make_api_request(
            "getAdp",
            params=params
        )

        if not response:
            return None

        return response.get("players", [])


async def store_fantrax_secret_id(
    db: AsyncSession,
    user_id: int,
    secret_id: str
) -> None:
    """
    Store encrypted Fantrax Secret ID for a user

    Args:
        db: Database session
        user_id: User ID
        secret_id: Fantrax Secret ID to encrypt and store
    """
    # Encrypt the secret ID before storing
    encrypted_secret_id = encrypt_value(secret_id)

    # Update user record
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        user.fantrax_secret_id = encrypted_secret_id
        user.fantrax_connected = True
        user.fantrax_connected_at = datetime.utcnow()
        await db.commit()
        logger.info(f"Stored Fantrax Secret ID for user {user_id}")


async def get_fantrax_secret_id(
    db: AsyncSession,
    user_id: int
) -> Optional[str]:
    """
    Retrieve and decrypt Fantrax Secret ID for a user

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Decrypted Secret ID or None if not found
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user and user.fantrax_secret_id:
        try:
            return decrypt_value(user.fantrax_secret_id)
        except Exception as e:
            logger.error(f"Failed to decrypt Fantrax Secret ID: {str(e)}")
            return None

    return None
