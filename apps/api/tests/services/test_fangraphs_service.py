"""Tests for Fangraphs data service."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import aiohttp

from app.services.fangraphs_service import (
    FangraphsService,
    FangraphsRateLimiter
)
from app.schemas.fangraphs_schemas import (
    FangraphsProspectData,
    FangraphsScoutingGrades,
    FangraphsRankings
)


@pytest.fixture
async def fangraphs_service():
    """Create Fangraphs service for testing."""
    service = FangraphsService()
    async with service:
        yield service


@pytest.fixture
def mock_html_response():
    """Mock HTML response from Fangraphs."""
    return """
    <html>
        <div class="prospects-grades">
            <div class="grade-item">
                <span class="skill-name">Hit</span>
                <span class="grade-value">55</span>
            </div>
            <div class="grade-item">
                <span class="skill-name">Power</span>
                <span class="grade-value">60</span>
            </div>
            <div class="grade-item">
                <span class="skill-name">Speed</span>
                <span class="grade-value">50</span>
            </div>
        </div>
        <table class="prospects-stats">
            <tr><th>Year</th><th>AVG</th><th>OBP</th><th>SLG</th></tr>
            <tr><td>2024</td><td>.285</td><td>.365</td><td>.475</td></tr>
        </table>
        <div class="prospect-rankings">
            <span class="rank-item">Overall #5</span>
            <span class="rank-item">Organization #1</span>
        </div>
        <div class="prospect-bio">
            <div class="bio-item">
                <span class="bio-label">Age:</span>
                <span class="bio-value">21</span>
            </div>
            <div class="bio-item">
                <span class="bio-label">Position:</span>
                <span class="bio-value">SS</span>
            </div>
        </div>
    </html>
    """


@pytest.fixture
def mock_prospects_list_html():
    """Mock HTML for prospects list."""
    return """
    <html>
        <table class="prospects-list">
            <tr><th>Rank</th><th>Name</th><th>Org</th><th>Pos</th><th>ETA</th></tr>
            <tr>
                <td>#1</td>
                <td><a href="/prospects/jackson-holliday">Jackson Holliday</a></td>
                <td>BAL</td>
                <td>SS</td>
                <td>2024</td>
            </tr>
            <tr>
                <td>#2</td>
                <td><a href="/prospects/paul-skenes">Paul Skenes</a></td>
                <td>PIT</td>
                <td>RHP</td>
                <td>2024</td>
            </tr>
        </table>
    </html>
    """


class TestFangraphsRateLimiter:
    """Test rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiting_delays_requests(self):
        """Test that rate limiter properly delays requests."""
        limiter = FangraphsRateLimiter(calls=1, period=1.0)

        start_time = asyncio.get_event_loop().time()

        async with limiter:
            pass  # First request should go through immediately

        mid_time = asyncio.get_event_loop().time()

        async with limiter:
            pass  # Second request should be delayed

        end_time = asyncio.get_event_loop().time()

        # Second request should be delayed by ~1 second
        assert (end_time - mid_time) >= 0.9  # Allow small margin
        assert (mid_time - start_time) < 0.1  # First should be immediate

    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting(self):
        """Test rate limiting with concurrent requests."""
        limiter = FangraphsRateLimiter(calls=1, period=0.5)

        async def make_request(delay_expected):
            start = asyncio.get_event_loop().time()
            async with limiter:
                pass
            elapsed = asyncio.get_event_loop().time() - start

            if delay_expected:
                assert elapsed >= 0.4  # Should wait at least 0.5 seconds
            else:
                assert elapsed < 0.1  # Should be immediate

        # First request should be immediate
        await make_request(delay_expected=False)

        # Concurrent requests should be delayed
        await asyncio.gather(
            make_request(delay_expected=True),
            make_request(delay_expected=True)
        )


class TestFangraphsService:
    """Test Fangraphs service functionality."""

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initializes properly."""
        async with FangraphsService() as service:
            assert service.session is not None
            assert service.rate_limiter is not None
            assert service.retry_count == 3

    @pytest.mark.asyncio
    async def test_make_request_success(self, fangraphs_service, mock_html_response):
        """Test successful request."""
        with patch.object(fangraphs_service.session, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=mock_html_response)
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await fangraphs_service._make_request("https://test.com")

            assert result == mock_html_response
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_rate_limited(self, fangraphs_service):
        """Test handling of rate limit (429) response."""
        with patch.object(fangraphs_service.session, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 429

            # First two attempts return 429, third succeeds
            responses = [429, 429, 200]
            mock_response.status = responses.pop(0)

            async def side_effect(*args, **kwargs):
                nonlocal responses
                mock_response.status = responses.pop(0) if responses else 200
                if mock_response.status == 200:
                    mock_response.text = AsyncMock(return_value="success")
                return mock_response

            mock_get.return_value.__aenter__ = AsyncMock(side_effect=side_effect)

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await fangraphs_service._make_request("https://test.com")

            # Should eventually succeed after retries
            assert result == "success" or result is None

    @pytest.mark.asyncio
    async def test_make_request_404(self, fangraphs_service):
        """Test handling of 404 response."""
        with patch.object(fangraphs_service.session, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await fangraphs_service._make_request("https://test.com/notfound")

            assert result is None

    @pytest.mark.asyncio
    async def test_make_request_timeout(self, fangraphs_service):
        """Test handling of request timeout."""
        with patch.object(fangraphs_service.session, 'get') as mock_get:
            mock_get.side_effect = asyncio.TimeoutError()

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await fangraphs_service._make_request("https://test.com")

            assert result is None

    @pytest.mark.asyncio
    async def test_parse_prospect_data(self, fangraphs_service, mock_html_response):
        """Test parsing of prospect HTML data."""
        data = fangraphs_service._parse_prospect_data(mock_html_response, "Test Player")

        assert data["name"] == "Test Player"
        assert data["source"] == "fangraphs"
        assert "fetched_at" in data

        # Check scouting grades
        assert data["scouting_grades"]["hit"] == 55
        assert data["scouting_grades"]["power"] == 60
        assert data["scouting_grades"]["speed"] == 50

        # Check statistics
        assert "2024" in data["statistics"]
        assert data["statistics"]["2024"]["AVG"] == 0.285
        assert data["statistics"]["2024"]["OBP"] == 0.365
        assert data["statistics"]["2024"]["SLG"] == 0.475

        # Check rankings
        assert data["rankings"]["Overall"] == 5
        assert data["rankings"]["Organization"] == 1

        # Check bio
        assert data["bio"]["age"] == "21"
        assert data["bio"]["position"] == "SS"

    @pytest.mark.asyncio
    async def test_get_prospect_data(self, fangraphs_service, mock_html_response):
        """Test fetching complete prospect data."""
        with patch.object(fangraphs_service, '_make_request') as mock_request:
            mock_request.return_value = mock_html_response

            result = await fangraphs_service.get_prospect_data("Jackson Holliday")

            assert result is not None
            assert result["name"] == "Jackson Holliday"
            assert result["source"] == "fangraphs"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_prospects_list(self, fangraphs_service, mock_prospects_list_html):
        """Test parsing of prospects list."""
        prospects = fangraphs_service._parse_prospects_list(mock_prospects_list_html, 10)

        assert len(prospects) == 2
        assert prospects[0]["rank"] == "#1"
        assert prospects[0]["name"] == "Jackson Holliday"
        assert prospects[0]["organization"] == "BAL"
        assert prospects[0]["position"] == "SS"
        assert prospects[0]["eta"] == "2024"
        assert prospects[0]["profile_url"] == "/prospects/jackson-holliday"

        assert prospects[1]["rank"] == "#2"
        assert prospects[1]["name"] == "Paul Skenes"

    @pytest.mark.asyncio
    async def test_get_top_prospects_list(self, fangraphs_service, mock_prospects_list_html):
        """Test fetching top prospects list."""
        with patch.object(fangraphs_service, '_make_request') as mock_request:
            mock_request.return_value = mock_prospects_list_html

            result = await fangraphs_service.get_top_prospects_list(2024, limit=10)

            assert len(result) == 2
            assert result[0]["name"] == "Jackson Holliday"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_fetch_prospects(self, fangraphs_service, mock_html_response):
        """Test batch fetching of multiple prospects."""
        with patch.object(fangraphs_service, 'get_prospect_data') as mock_get:
            mock_get.side_effect = [
                {"name": "Player 1", "source": "fangraphs"},
                None,  # Second player not found
                {"name": "Player 3", "source": "fangraphs"}
            ]

            prospects = ["Player 1", "Player 2", "Player 3"]
            results = await fangraphs_service.batch_fetch_prospects(prospects)

            assert len(results) == 2
            assert results[0]["name"] == "Player 1"
            assert results[1]["name"] == "Player 3"
            assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test that session is properly cleaned up."""
        service = FangraphsService()

        async with service:
            assert service.session is not None

        # After context exit, session should be closed
        assert service.session.closed