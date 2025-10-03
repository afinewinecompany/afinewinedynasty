"""
Unit tests for FantraxAPIService

Tests API client functionality including league data fetching, roster sync,
caching, rate limiting, and error handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.fantrax_api_service import FantraxAPIService
from app.db.models import User, FantraxLeague, FantraxRoster, FantraxSyncHistory


@pytest.fixture
def mock_db():
    """Create mock database session"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_user():
    """Create mock user with Fantrax credentials"""
    user = Mock(spec=User)
    user.id = 1
    user.fantrax_user_id = "test_fantrax_user"
    user.fantrax_refresh_token = "encrypted_refresh_token"
    return user


@pytest.fixture
def fantrax_service(mock_db):
    """Create FantraxAPIService instance"""
    return FantraxAPIService(db=mock_db, user_id=1)


class TestFantraxAPIServiceInitialization:
    """Test service initialization and configuration"""

    def test_initialization(self, fantrax_service):
        """Service initializes with correct configuration"""
        assert fantrax_service.user_id == 1
        assert fantrax_service.API_BASE_URL == "https://www.fantrax.com/api/v2"
        assert fantrax_service.CACHE_TTL["leagues"] == 86400
        assert fantrax_service.CACHE_TTL["roster"] == 3600


class TestGetUserLeagues:
    """Test fetching user's Fantrax leagues"""

    @pytest.mark.asyncio
    async def test_get_user_leagues_success(self, fantrax_service, mock_db):
        """Successfully fetch user leagues from API"""
        mock_response = {
            "leagues": [
                {
                    "id": "league123",
                    "name": "Test Dynasty League",
                    "type": "dynasty",
                    "settings": {"roster_size": 40}
                }
            ]
        }

        with patch.object(fantrax_service, '_make_fantrax_request', new=AsyncMock(return_value=mock_response)):
            leagues = await fantrax_service.get_user_leagues()

            assert len(leagues) == 1
            assert leagues[0]["id"] == "league123"
            assert leagues[0]["name"] == "Test Dynasty League"

    @pytest.mark.asyncio
    async def test_get_user_leagues_from_cache(self, fantrax_service):
        """Fetch leagues from cache when available"""
        cached_data = [{"id": "cached_league", "name": "Cached League"}]

        with patch('app.services.fantrax_api_service.cache_manager.get', new=AsyncMock(return_value=cached_data)):
            leagues = await fantrax_service.get_user_leagues()

            assert leagues == cached_data

    @pytest.mark.asyncio
    async def test_get_user_leagues_api_error(self, fantrax_service):
        """Handle API errors gracefully"""
        with patch.object(fantrax_service, '_make_fantrax_request', side_effect=Exception("API Error")):
            leagues = await fantrax_service.get_user_leagues()

            assert leagues == []


class TestSyncRoster:
    """Test roster synchronization functionality"""

    @pytest.mark.asyncio
    async def test_sync_roster_success(self, fantrax_service, mock_db):
        """Successfully sync roster from Fantrax API"""
        mock_roster = {
            "players": [
                {
                    "id": "player123",
                    "name": "Test Player",
                    "positions": ["OF"],
                    "age": 22,
                    "team": "BAL",
                    "status": "active"
                }
            ]
        }

        with patch.object(fantrax_service, 'get_roster', new=AsyncMock(return_value=mock_roster)):
            with patch.object(fantrax_service, '_store_roster_in_db', new=AsyncMock()) as mock_store:
                result = await fantrax_service.sync_roster("league123")

                assert result["success"] is True
                assert result["players_synced"] == 1
                mock_store.assert_called_once_with("league123", mock_roster)

    @pytest.mark.asyncio
    async def test_sync_roster_empty(self, fantrax_service):
        """Handle empty roster sync"""
        mock_roster = {"players": []}

        with patch.object(fantrax_service, 'get_roster', new=AsyncMock(return_value=mock_roster)):
            with patch.object(fantrax_service, '_store_roster_in_db', new=AsyncMock()) as mock_store:
                result = await fantrax_service.sync_roster("league123")

                assert result["success"] is True
                assert result["players_synced"] == 0


class TestGetRoster:
    """Test roster data retrieval"""

    @pytest.mark.asyncio
    async def test_get_roster_from_api(self, fantrax_service):
        """Fetch roster from Fantrax API"""
        mock_response = {
            "roster": {
                "players": [
                    {"id": "p1", "name": "Player 1", "positions": ["C", "1B"]}
                ]
            }
        }

        with patch.object(fantrax_service, '_make_fantrax_request', new=AsyncMock(return_value=mock_response)):
            roster = await fantrax_service.get_roster("league123")

            assert "players" in roster
            assert len(roster["players"]) == 1

    @pytest.mark.asyncio
    async def test_get_roster_caching(self, fantrax_service):
        """Roster data is properly cached"""
        cached_roster = {"players": [{"id": "cached"}]}

        with patch('app.services.fantrax_api_service.cache_manager.get', new=AsyncMock(return_value=cached_roster)):
            roster = await fantrax_service.get_roster("league123")

            assert roster == cached_roster


class TestGetLeagueSettings:
    """Test league settings retrieval"""

    @pytest.mark.asyncio
    async def test_get_league_settings_success(self, fantrax_service):
        """Fetch league settings from API"""
        mock_settings = {
            "league_id": "league123",
            "roster_size": 40,
            "scoring": {"HR": 4, "RBI": 1}
        }

        with patch.object(fantrax_service, '_make_fantrax_request', new=AsyncMock(return_value=mock_settings)):
            settings = await fantrax_service.get_league_settings("league123")

            assert settings["league_id"] == "league123"
            assert settings["roster_size"] == 40


class TestStoreRosterInDb:
    """Test database roster storage with transaction handling"""

    @pytest.mark.asyncio
    async def test_store_roster_success(self, fantrax_service, mock_db):
        """Successfully store roster in database"""
        roster_data = {
            "players": [
                {
                    "id": "p1",
                    "name": "Test Player",
                    "positions": ["OF"],
                    "age": 25,
                    "team": "BAL",
                    "status": "active"
                }
            ]
        }

        # Mock league lookup
        mock_league = Mock(spec=FantraxLeague)
        mock_league.id = 1
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_league
        mock_db.execute.return_value = mock_result

        # Mock existing rosters (empty)
        mock_empty_result = Mock()
        mock_empty_result.scalars.return_value = []

        # Configure side effects for different execute calls
        mock_db.execute.side_effect = [mock_result, mock_empty_result]

        await fantrax_service._store_roster_in_db("league123", roster_data)

        # Verify commit was called
        mock_db.commit.assert_called()
        # Verify roster entry was added
        assert mock_db.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_store_roster_league_not_found(self, fantrax_service, mock_db):
        """Raise error when league not found"""
        roster_data = {"players": []}

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="League .* not found"):
            await fantrax_service._store_roster_in_db("invalid_league", roster_data)

        # Verify rollback was called
        mock_db.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_store_roster_transaction_failure(self, fantrax_service, mock_db):
        """Handle transaction failures with rollback"""
        roster_data = {"players": [{"id": "p1", "name": "Test"}]}

        # Mock league found
        mock_league = Mock(spec=FantraxLeague)
        mock_league.id = 1
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_league

        # Make commit raise exception
        mock_db.commit.side_effect = Exception("Database error")
        mock_db.execute.return_value = mock_result

        with pytest.raises(Exception, match="Database error"):
            await fantrax_service._store_roster_in_db("league123", roster_data)

        # Verify rollback was called
        assert mock_db.rollback.call_count >= 1


class TestMakeFantraxRequest:
    """Test API request handling with rate limiting and retries"""

    @pytest.mark.asyncio
    async def test_make_request_success(self, fantrax_service):
        """Successful API request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}

        with patch('httpx.AsyncClient.get', new=AsyncMock(return_value=mock_response)):
            result = await fantrax_service._make_fantrax_request("/test/endpoint")

            assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_make_request_rate_limited_retry(self, fantrax_service):
        """Retry on rate limit response"""
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"data": "success"}

        with patch('httpx.AsyncClient.get', new=AsyncMock(side_effect=[rate_limit_response, success_response])):
            with patch('asyncio.sleep', new=AsyncMock()):
                result = await fantrax_service._make_fantrax_request("/test/endpoint")

                assert result == {"data": "success"}

    @pytest.mark.asyncio
    async def test_make_request_token_refresh(self, fantrax_service):
        """Refresh token on 401 unauthorized"""
        unauthorized_response = Mock()
        unauthorized_response.status_code = 401

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"data": "success"}

        with patch('httpx.AsyncClient.get', new=AsyncMock(side_effect=[unauthorized_response, success_response])):
            with patch.object(fantrax_service, '_refresh_access_token', new=AsyncMock()):
                result = await fantrax_service._make_fantrax_request("/test/endpoint")

                assert result == {"data": "success"}


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_network_timeout(self, fantrax_service):
        """Handle network timeout gracefully"""
        with patch('httpx.AsyncClient.get', side_effect=httpx.TimeoutException("Timeout")):
            with pytest.raises(Exception, match="Timeout"):
                await fantrax_service._make_fantrax_request("/test")

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, fantrax_service):
        """Handle invalid JSON response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch('httpx.AsyncClient.get', new=AsyncMock(return_value=mock_response)):
            with pytest.raises(ValueError):
                await fantrax_service._make_fantrax_request("/test")
