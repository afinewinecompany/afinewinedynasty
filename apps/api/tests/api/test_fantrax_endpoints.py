"""
Integration tests for Fantrax API endpoints

Tests authentication, authorization, request/response handling, and
error scenarios for all Fantrax integration endpoints.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
from datetime import datetime

from app.main import app
from app.core.security import create_access_token


@pytest.fixture
def auth_headers():
    """Generate authentication headers for premium user"""
    token_data = {
        "sub": "1",
        "subscription_tier": "premium"
    }
    access_token = create_access_token(data=token_data)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def free_user_headers():
    """Generate authentication headers for free user"""
    token_data = {
        "sub": "2",
        "subscription_tier": "free"
    }
    access_token = create_access_token(data=token_data)
    return {"Authorization": f"Bearer {access_token}"}


class TestFantraxAuthEndpoint:
    """Test GET /api/integrations/fantrax/auth"""

    def test_get_auth_url_success(self, auth_headers):
        """Successfully generate Fantrax OAuth URL"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_oauth_service.FantraxOAuthService.get_authorization_url') as mock_get_url:
                mock_get_url.return_value = "https://fantrax.com/oauth?state=abc123"

                response = client.get(
                    "/api/integrations/fantrax/auth",
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert "authorization_url" in data
                assert "fantrax.com" in data["authorization_url"]

    def test_get_auth_url_requires_premium(self, free_user_headers):
        """Reject free users from Fantrax integration"""
        with TestClient(app) as client:
            response = client.get(
                "/api/integrations/fantrax/auth",
                headers=free_user_headers
            )

            assert response.status_code == 403
            assert "premium" in response.json()["detail"].lower()

    def test_get_auth_url_requires_authentication(self):
        """Reject unauthenticated requests"""
        with TestClient(app) as client:
            response = client.get("/api/integrations/fantrax/auth")

            assert response.status_code == 401


class TestFantraxCallbackEndpoint:
    """Test POST /api/integrations/fantrax/callback"""

    def test_callback_success(self, auth_headers):
        """Successfully handle OAuth callback"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_oauth_service.FantraxOAuthService.handle_callback') as mock_callback:
                mock_callback.return_value = {
                    "success": True,
                    "user_id": "fantrax_user_123"
                }

                response = client.post(
                    "/api/integrations/fantrax/callback",
                    headers=auth_headers,
                    json={
                        "code": "auth_code_123",
                        "state": "state_token"
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True

    def test_callback_invalid_state(self, auth_headers):
        """Reject callback with invalid state token"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_oauth_service.FantraxOAuthService.handle_callback') as mock_callback:
                mock_callback.side_effect = ValueError("Invalid state token")

                response = client.post(
                    "/api/integrations/fantrax/callback",
                    headers=auth_headers,
                    json={
                        "code": "auth_code_123",
                        "state": "invalid_state"
                    }
                )

                assert response.status_code == 400

    def test_callback_missing_code(self, auth_headers):
        """Reject callback without authorization code"""
        with TestClient(app) as client:
            response = client.post(
                "/api/integrations/fantrax/callback",
                headers=auth_headers,
                json={"state": "state_token"}
            )

            assert response.status_code == 422  # Validation error


class TestFantraxDisconnectEndpoint:
    """Test POST /api/integrations/fantrax/disconnect"""

    def test_disconnect_success(self, auth_headers):
        """Successfully disconnect Fantrax account"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_oauth_service.FantraxOAuthService.disconnect') as mock_disconnect:
                mock_disconnect.return_value = {"success": True}

                response = client.post(
                    "/api/integrations/fantrax/disconnect",
                    headers=auth_headers
                )

                assert response.status_code == 200
                assert response.json()["success"] is True


class TestGetUserLeaguesEndpoint:
    """Test GET /api/integrations/fantrax/leagues"""

    def test_get_leagues_success(self, auth_headers):
        """Successfully retrieve user's leagues"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_api_service.FantraxAPIService.get_user_leagues') as mock_get_leagues:
                mock_get_leagues.return_value = [
                    {
                        "id": "league123",
                        "name": "Test Dynasty League",
                        "type": "dynasty"
                    }
                ]

                response = client.get(
                    "/api/integrations/fantrax/leagues",
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["name"] == "Test Dynasty League"

    def test_get_leagues_not_connected(self, auth_headers):
        """Handle user not connected to Fantrax"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_api_service.FantraxAPIService.get_user_leagues') as mock_get_leagues:
                mock_get_leagues.side_effect = ValueError("User not connected to Fantrax")

                response = client.get(
                    "/api/integrations/fantrax/leagues",
                    headers=auth_headers
                )

                assert response.status_code == 400


class TestSyncRosterEndpoint:
    """Test POST /api/integrations/fantrax/roster/sync"""

    def test_sync_roster_success(self, auth_headers):
        """Successfully sync league roster"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_api_service.FantraxAPIService.sync_roster') as mock_sync:
                mock_sync.return_value = {
                    "success": True,
                    "players_synced": 35,
                    "sync_duration_ms": 1250
                }

                response = client.post(
                    "/api/integrations/fantrax/roster/sync",
                    headers=auth_headers,
                    json={"league_id": "league123"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["players_synced"] == 35

    def test_sync_roster_rate_limit(self, auth_headers):
        """Respect rate limiting on roster sync"""
        with TestClient(app) as client:
            # Mock rate limiter to reject request
            with patch('app.api.api_v1.endpoints.fantrax.rate_limiter.check_rate_limit') as mock_rate_limit:
                mock_rate_limit.return_value = False

                response = client.post(
                    "/api/integrations/fantrax/roster/sync",
                    headers=auth_headers,
                    json={"league_id": "league123"}
                )

                # Depending on implementation, could be 429 or handled differently
                assert response.status_code in [429, 400]


class TestGetRosterEndpoint:
    """Test GET /api/integrations/fantrax/roster/{league_id}"""

    def test_get_roster_success(self, auth_headers):
        """Successfully retrieve cached roster"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_api_service.FantraxAPIService.get_roster') as mock_get_roster:
                mock_get_roster.return_value = {
                    "players": [
                        {
                            "id": "p1",
                            "name": "Test Player",
                            "positions": ["OF"],
                            "age": 25
                        }
                    ]
                }

                response = client.get(
                    "/api/integrations/fantrax/roster/league123",
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert "players" in data
                assert len(data["players"]) == 1

    def test_get_roster_not_found(self, auth_headers):
        """Handle league not found"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_api_service.FantraxAPIService.get_roster') as mock_get_roster:
                mock_get_roster.side_effect = ValueError("League not found")

                response = client.get(
                    "/api/integrations/fantrax/roster/invalid_league",
                    headers=auth_headers
                )

                assert response.status_code == 404


class TestGetAnalysisEndpoint:
    """Test GET /api/integrations/fantrax/analysis/{league_id}"""

    def test_get_analysis_success(self, auth_headers):
        """Successfully retrieve team analysis"""
        with TestClient(app) as client:
            with patch('app.services.roster_analysis_service.RosterAnalysisService.analyze_team') as mock_analyze:
                mock_analyze.return_value = {
                    "timeline": "rebuilding",
                    "needs": [{"position": "C", "priority": "high"}],
                    "strengths": ["OF", "SS"]
                }

                response = client.get(
                    "/api/integrations/fantrax/analysis/league123",
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert data["timeline"] == "rebuilding"
                assert len(data["needs"]) > 0


class TestGetRecommendationsEndpoint:
    """Test GET /api/integrations/fantrax/recommendations/{league_id}"""

    def test_get_recommendations_success(self, auth_headers):
        """Successfully retrieve personalized recommendations"""
        with TestClient(app) as client:
            with patch('app.services.personalized_recommendation_service.PersonalizedRecommendationService.get_recommendations') as mock_recs:
                mock_recs.return_value = [
                    {
                        "prospect": {
                            "id": "p1",
                            "name": "Elite Prospect",
                            "position": "C"
                        },
                        "fit_score": 92,
                        "reason": "Fills critical catcher need"
                    }
                ]

                response = client.get(
                    "/api/integrations/fantrax/recommendations/league123",
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) > 0
                assert data[0]["fit_score"] == 92

    def test_get_recommendations_with_limit(self, auth_headers):
        """Respect limit query parameter"""
        with TestClient(app) as client:
            with patch('app.services.personalized_recommendation_service.PersonalizedRecommendationService.get_recommendations') as mock_recs:
                mock_recs.return_value = [{"prospect": {"id": f"p{i}"}} for i in range(5)]

                response = client.get(
                    "/api/integrations/fantrax/recommendations/league123?limit=5",
                    headers=auth_headers
                )

                assert response.status_code == 200
                assert len(response.json()) <= 5


class TestTradeAnalysisEndpoint:
    """Test POST /api/integrations/fantrax/trade-analysis"""

    def test_trade_analysis_success(self, auth_headers):
        """Successfully analyze trade"""
        with TestClient(app) as client:
            with patch('app.services.personalized_recommendation_service.PersonalizedRecommendationService.analyze_trade') as mock_analyze:
                mock_analyze.return_value = {
                    "net_value": 15,
                    "fit_improvement": 10,
                    "recommendation": "Accept this trade"
                }

                response = client.post(
                    "/api/integrations/fantrax/trade-analysis",
                    headers=auth_headers,
                    json={
                        "league_id": "league123",
                        "prospects_to_receive": [{"id": "p1", "overall_rating": 90}],
                        "prospects_to_give": [{"id": "p2", "overall_rating": 75}]
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert data["net_value"] == 15
                assert "recommendation" in data

    def test_trade_analysis_missing_prospects(self, auth_headers):
        """Reject trade analysis without prospects"""
        with TestClient(app) as client:
            response = client.post(
                "/api/integrations/fantrax/trade-analysis",
                headers=auth_headers,
                json={"league_id": "league123"}
            )

            assert response.status_code == 422  # Validation error


class TestAuthenticationAndAuthorization:
    """Test authentication and authorization across all endpoints"""

    def test_all_endpoints_require_auth(self):
        """All Fantrax endpoints require authentication"""
        endpoints = [
            ("GET", "/api/integrations/fantrax/auth"),
            ("GET", "/api/integrations/fantrax/leagues"),
            ("GET", "/api/integrations/fantrax/roster/league123"),
            ("GET", "/api/integrations/fantrax/analysis/league123"),
            ("GET", "/api/integrations/fantrax/recommendations/league123"),
        ]

        with TestClient(app) as client:
            for method, endpoint in endpoints:
                response = client.request(method, endpoint)
                assert response.status_code == 401, f"{endpoint} should require authentication"

    def test_all_endpoints_require_premium(self, free_user_headers):
        """All Fantrax endpoints require premium subscription"""
        endpoints = [
            ("GET", "/api/integrations/fantrax/auth"),
            ("GET", "/api/integrations/fantrax/leagues"),
        ]

        with TestClient(app) as client:
            for method, endpoint in endpoints:
                response = client.request(method, endpoint, headers=free_user_headers)
                assert response.status_code == 403, f"{endpoint} should require premium"


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_invalid_league_id_format(self, auth_headers):
        """Handle invalid league ID format"""
        with TestClient(app) as client:
            response = client.get(
                "/api/integrations/fantrax/roster/",
                headers=auth_headers
            )

            # Should be 404 (not found) or 422 (validation error)
            assert response.status_code in [404, 422]

    def test_database_error_handling(self, auth_headers):
        """Gracefully handle database errors"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_api_service.FantraxAPIService.get_user_leagues') as mock_leagues:
                mock_leagues.side_effect = Exception("Database connection error")

                response = client.get(
                    "/api/integrations/fantrax/leagues",
                    headers=auth_headers
                )

                assert response.status_code == 500

    def test_fantrax_api_timeout(self, auth_headers):
        """Handle Fantrax API timeout gracefully"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_api_service.FantraxAPIService.sync_roster') as mock_sync:
                mock_sync.side_effect = TimeoutError("Fantrax API timeout")

                response = client.post(
                    "/api/integrations/fantrax/roster/sync",
                    headers=auth_headers,
                    json={"league_id": "league123"}
                )

                assert response.status_code in [500, 504]  # Internal error or gateway timeout


class TestResponseValidation:
    """Test response schema validation"""

    def test_leagues_response_schema(self, auth_headers):
        """Validate leagues endpoint response schema"""
        with TestClient(app) as client:
            with patch('app.services.fantrax_api_service.FantraxAPIService.get_user_leagues') as mock_leagues:
                mock_leagues.return_value = [
                    {
                        "id": "league123",
                        "name": "Test League",
                        "type": "dynasty",
                        "settings": {}
                    }
                ]

                response = client.get(
                    "/api/integrations/fantrax/leagues",
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                if len(data) > 0:
                    assert "id" in data[0]
                    assert "name" in data[0]

    def test_analysis_response_schema(self, auth_headers):
        """Validate analysis endpoint response schema"""
        with TestClient(app) as client:
            with patch('app.services.roster_analysis_service.RosterAnalysisService.analyze_team') as mock_analyze:
                mock_analyze.return_value = {
                    "timeline": "rebuilding",
                    "needs": [],
                    "strengths": [],
                    "roster_spots": {"available": 5}
                }

                response = client.get(
                    "/api/integrations/fantrax/analysis/league123",
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert "timeline" in data
                assert "needs" in data
