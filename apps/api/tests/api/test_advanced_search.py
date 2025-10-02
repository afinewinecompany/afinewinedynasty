"""Tests for advanced search API endpoints."""

import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timedelta
import json

from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction, User, UserSavedSearch
from app.core.security import create_access_token


class TestAdvancedSearchEndpoints:
    """Test suite for advanced search API endpoints."""

    @pytest.fixture
    async def test_prospects(self, db_session):
        """Create test prospects with varied data for search testing."""
        prospects = []

        # Create diverse prospects for comprehensive testing
        prospect_data = [
            {
                "mlb_id": "search001",
                "name": "Test Player One",
                "position": "SS",
                "organization": "Test Organization A",
                "level": "AA",
                "age": 20,
                "eta_year": 2025
            },
            {
                "mlb_id": "search002",
                "name": "Test Player Two",
                "position": "SP",
                "organization": "Test Organization B",
                "level": "AAA",
                "age": 22,
                "eta_year": 2024
            },
            {
                "mlb_id": "search003",
                "name": "Test Player Three",
                "position": "CF",
                "organization": "Test Organization A",
                "level": "A+",
                "age": 19,
                "eta_year": 2026
            }
        ]

        for data in prospect_data:
            prospect = Prospect(**data)
            db_session.add(prospect)
            await db_session.flush()
            prospects.append(prospect)

            # Add stats for each prospect
            stats = ProspectStats(
                prospect_id=prospect.id,
                date_recorded=datetime.now().date(),
                season=2024,
                games_played=100,
                at_bats=400,
                hits=120,
                batting_avg=0.300,
                on_base_pct=0.350,
                slugging_pct=0.450,
                era=3.50 if prospect.position in ['SP', 'RP'] else None,
                whip=1.20 if prospect.position in ['SP', 'RP'] else None,
                woba=0.340
            )
            db_session.add(stats)

            # Add scouting grades
            grade = ScoutingGrades(
                prospect_id=prospect.id,
                source="Test Scout",
                overall=55,
                hit=50 if prospect.position not in ['SP', 'RP'] else None,
                power=45 if prospect.position not in ['SP', 'RP'] else None,
                future_value=55,
                risk="Moderate"
            )
            db_session.add(grade)

            # Add ML predictions
            prediction = MLPrediction(
                prospect_id=prospect.id,
                model_version="test_v1",
                prediction_type="success_rating",
                prediction_value=0.75,
                confidence_score=0.85
            )
            db_session.add(prediction)

        await db_session.commit()
        return prospects

    @pytest.fixture
    async def auth_headers(self, test_user):
        """Create authentication headers for API requests."""
        access_token = create_access_token(subject=test_user.email)
        return {"Authorization": f"Bearer {access_token}"}

    async def test_advanced_search_basic_criteria(self, client: AsyncClient, auth_headers, test_prospects):
        """Test advanced search with basic prospect criteria."""
        search_data = {
            "positions": ["SS", "CF"],
            "min_age": 19,
            "max_age": 21,
            "page": 1,
            "size": 10
        }

        response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "prospects" in data
        assert "total_count" in data
        assert "page" in data
        assert "search_metadata" in data

        # Should find prospects matching criteria
        assert data["total_count"] >= 1
        assert len(data["prospects"]) <= 10

        # Verify prospects match criteria
        for prospect in data["prospects"]:
            assert prospect["position"] in ["SS", "CF"]
            assert 19 <= prospect["age"] <= 21

    async def test_advanced_search_statistical_criteria(self, client: AsyncClient, auth_headers, test_prospects):
        """Test advanced search with statistical performance criteria."""
        search_data = {
            "min_batting_avg": 0.250,
            "max_batting_avg": 0.350,
            "min_on_base_pct": 0.300,
            "page": 1,
            "size": 10
        }

        response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total_count"] >= 0
        assert "search_metadata" in data
        assert data["search_metadata"]["applied_filters"]["statistical"] is True

    async def test_advanced_search_scouting_criteria(self, client: AsyncClient, auth_headers, test_prospects):
        """Test advanced search with scouting grade criteria."""
        search_data = {
            "min_overall_grade": 50,
            "max_overall_grade": 60,
            "scouting_sources": ["Test Scout"],
            "risk_levels": ["Moderate"],
            "page": 1,
            "size": 10
        }

        response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total_count"] >= 0
        assert data["search_metadata"]["applied_filters"]["scouting"] is True

    async def test_advanced_search_ml_criteria(self, client: AsyncClient, auth_headers, test_prospects):
        """Test advanced search with ML prediction criteria."""
        search_data = {
            "min_success_probability": 0.70,
            "min_confidence_score": 0.80,
            "prediction_types": ["success_rating"],
            "page": 1,
            "size": 10
        }

        response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total_count"] >= 0
        assert data["search_metadata"]["applied_filters"]["ml_predictions"] is True

    async def test_advanced_search_text_query(self, client: AsyncClient, auth_headers, test_prospects):
        """Test advanced search with text search query."""
        search_data = {
            "search_query": "Test Player",
            "page": 1,
            "size": 10
        }

        response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total_count"] >= 1
        assert data["search_metadata"]["applied_filters"]["text_search"] is True

    async def test_advanced_search_pagination(self, client: AsyncClient, auth_headers, test_prospects):
        """Test advanced search pagination functionality."""
        # First page
        search_data = {"page": 1, "size": 2}
        response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["page"] == 1
        assert data["size"] == 2
        assert len(data["prospects"]) <= 2

        if data["total_count"] > 2:
            assert data["has_next"] is True
        assert data["has_prev"] is False

    async def test_advanced_search_sorting(self, client: AsyncClient, auth_headers, test_prospects):
        """Test advanced search sorting options."""
        sort_options = ["name", "age", "eta_year", "organization"]

        for sort_by in sort_options:
            search_data = {"sort_by": sort_by, "page": 1, "size": 10}
            response = await client.post(
                "/api/search/advanced",
                json=search_data,
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "prospects" in data

    async def test_advanced_search_validation_errors(self, client: AsyncClient, auth_headers):
        """Test advanced search input validation."""
        # Invalid batting average
        search_data = {"min_batting_avg": 1.5}
        response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Invalid age range
        search_data = {"min_age": 40}
        response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Invalid grade range
        search_data = {"min_overall_grade": 15}
        response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_search_criteria_options(self, client: AsyncClient, auth_headers):
        """Test getting search criteria options."""
        response = await client.get(
            "/api/search/criteria/options",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "positions" in data
        assert "scouting_sources" in data
        assert "risk_levels" in data
        assert "prediction_types" in data
        assert "levels" in data
        assert "sort_options" in data
        assert "grade_range" in data
        assert "age_range" in data
        assert "eta_range" in data

        # Verify expected positions
        assert "SS" in data["positions"]
        assert "SP" in data["positions"]
        assert "CF" in data["positions"]

    async def test_advanced_search_unauthorized(self, client: AsyncClient):
        """Test advanced search without authentication."""
        search_data = {"positions": ["SS"]}
        response = await client.post(
            "/api/search/advanced",
            json=search_data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestSavedSearchEndpoints:
    """Test suite for saved search functionality."""

    @pytest.fixture
    async def auth_headers(self, test_user):
        """Create authentication headers for API requests."""
        access_token = create_access_token(subject=test_user.email)
        return {"Authorization": f"Bearer {access_token}"}

    async def test_create_saved_search(self, client: AsyncClient, auth_headers, test_user):
        """Test creating a saved search."""
        search_data = {
            "search_name": "My Test Search",
            "search_criteria": {
                "statistical": {"min_batting_avg": 0.300},
                "basic": {"positions": ["SS", "CF"]},
                "scouting": {"min_overall_grade": 50},
                "ml": {"min_success_probability": 0.70}
            }
        }

        response = await client.post(
            "/api/search/saved",
            json=search_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["search_name"] == "My Test Search"
        assert data["search_criteria"] == search_data["search_criteria"]
        assert "id" in data
        assert "created_at" in data
        assert "last_used" in data

    async def test_create_duplicate_saved_search_name(self, client: AsyncClient, auth_headers, db_session, test_user):
        """Test creating saved search with duplicate name fails."""
        # Create first saved search
        saved_search = UserSavedSearch(
            user_id=test_user.id,
            search_name="Duplicate Name",
            search_criteria={"test": "data"}
        )
        db_session.add(saved_search)
        await db_session.commit()

        # Try to create another with same name
        search_data = {
            "search_name": "Duplicate Name",
            "search_criteria": {"different": "data"}
        }

        response = await client.post(
            "/api/search/saved",
            json=search_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_get_saved_searches(self, client: AsyncClient, auth_headers, db_session, test_user):
        """Test getting user's saved searches."""
        # Create test saved searches
        for i in range(3):
            saved_search = UserSavedSearch(
                user_id=test_user.id,
                search_name=f"Test Search {i+1}",
                search_criteria={"test": f"data_{i+1}"}
            )
            db_session.add(saved_search)

        await db_session.commit()

        response = await client.get(
            "/api/search/saved",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 3
        assert all("search_name" in item for item in data)
        assert all("search_criteria" in item for item in data)

    async def test_get_saved_search_by_id(self, client: AsyncClient, auth_headers, db_session, test_user):
        """Test getting a specific saved search by ID."""
        saved_search = UserSavedSearch(
            user_id=test_user.id,
            search_name="Specific Search",
            search_criteria={"specific": "data"}
        )
        db_session.add(saved_search)
        await db_session.commit()
        await db_session.refresh(saved_search)

        response = await client.get(
            f"/api/search/saved/{saved_search.id}",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == saved_search.id
        assert data["search_name"] == "Specific Search"
        assert data["search_criteria"] == {"specific": "data"}

    async def test_update_saved_search(self, client: AsyncClient, auth_headers, db_session, test_user):
        """Test updating a saved search."""
        saved_search = UserSavedSearch(
            user_id=test_user.id,
            search_name="Original Name",
            search_criteria={"original": "data"}
        )
        db_session.add(saved_search)
        await db_session.commit()
        await db_session.refresh(saved_search)

        update_data = {
            "search_name": "Updated Name",
            "search_criteria": {"updated": "data"}
        }

        response = await client.put(
            f"/api/search/saved/{saved_search.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["search_name"] == "Updated Name"
        assert data["search_criteria"] == {"updated": "data"}

    async def test_delete_saved_search(self, client: AsyncClient, auth_headers, db_session, test_user):
        """Test deleting a saved search."""
        saved_search = UserSavedSearch(
            user_id=test_user.id,
            search_name="To Delete",
            search_criteria={"delete": "me"}
        )
        db_session.add(saved_search)
        await db_session.commit()
        await db_session.refresh(saved_search)

        response = await client.delete(
            f"/api/search/saved/{saved_search.id}",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Saved search deleted successfully"

        # Verify it's actually deleted
        get_response = await client.get(
            f"/api/search/saved/{saved_search.id}",
            headers=auth_headers
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_saved_search_access_control(self, client: AsyncClient, db_session):
        """Test that users can only access their own saved searches."""
        # Create two users
        user1 = User(
            email="user1@test.com",
            hashed_password="hashedpass1",
            full_name="User One"
        )
        user2 = User(
            email="user2@test.com",
            hashed_password="hashedpass2",
            full_name="User Two"
        )
        db_session.add_all([user1, user2])
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)

        # Create saved search for user1
        saved_search = UserSavedSearch(
            user_id=user1.id,
            search_name="User1 Search",
            search_criteria={"user1": "data"}
        )
        db_session.add(saved_search)
        await db_session.commit()
        await db_session.refresh(saved_search)

        # Try to access with user2's token
        user2_token = create_access_token(subject=user2.email)
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        response = await client.get(
            f"/api/search/saved/{saved_search.id}",
            headers=user2_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSearchHistoryEndpoints:
    """Test suite for search history functionality."""

    @pytest.fixture
    async def auth_headers(self, test_user):
        """Create authentication headers for API requests."""
        access_token = create_access_token(subject=test_user.email)
        return {"Authorization": f"Bearer {access_token}"}

    async def test_get_search_history(self, client: AsyncClient, auth_headers):
        """Test getting user's search history."""
        response = await client.get(
            "/api/search/history",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    async def test_get_recently_viewed_prospects(self, client: AsyncClient, auth_headers):
        """Test getting user's recently viewed prospects."""
        response = await client.get(
            "/api/search/recently-viewed",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    async def test_track_prospect_view(self, client: AsyncClient, auth_headers, test_prospects):
        """Test tracking a prospect view."""
        prospect_id = test_prospects[0].id

        response = await client.post(
            "/api/search/track-view",
            params={"prospect_id": prospect_id, "view_duration": 30},
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Prospect view tracked successfully"