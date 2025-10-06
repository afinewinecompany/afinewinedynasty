"""
Integration tests for lineup endpoints
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, UserLineup, LineupProspect, Prospect
from app.core.security import create_access_token


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        is_active=True,
        privacy_policy_accepted=True,
        data_processing_accepted=True,
        preferences={}
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_token(test_user):
    """Create auth token for test user"""
    return create_access_token(subject=test_user.email)


@pytest.fixture
async def test_prospect(db_session: AsyncSession):
    """Create a test prospect"""
    prospect = Prospect(
        mlb_id="TEST001",
        name="Test Prospect",
        position="SS",
        organization="Test Org",
        age=22,
        eta_year=2025
    )
    db_session.add(prospect)
    await db_session.commit()
    await db_session.refresh(prospect)
    return prospect


class TestLineupCRUD:
    """Test lineup CRUD operations"""

    async def test_create_lineup_success(
        self,
        async_client: AsyncClient,
        test_user_token: str
    ):
        """Test creating a lineup"""
        response = await async_client.post(
            "/api/v1/lineups",
            json={
                "name": "My Test Lineup",
                "description": "A test lineup",
                "lineup_type": "custom"
            },
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Test Lineup"
        assert data["description"] == "A test lineup"
        assert data["lineup_type"] == "custom"
        assert data["prospect_count"] == 0
        assert "id" in data

    async def test_create_lineup_unauthorized(self, async_client: AsyncClient):
        """Test creating lineup without auth fails"""
        response = await async_client.post(
            "/api/v1/lineups",
            json={"name": "Test Lineup", "lineup_type": "custom"}
        )

        assert response.status_code == 401

    async def test_create_lineup_invalid_type(
        self,
        async_client: AsyncClient,
        test_user_token: str
    ):
        """Test creating lineup with invalid type fails"""
        response = await async_client.post(
            "/api/v1/lineups",
            json={
                "name": "Test Lineup",
                "lineup_type": "invalid_type"
            },
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 422  # Validation error

    async def test_get_lineups_empty(
        self,
        async_client: AsyncClient,
        test_user_token: str
    ):
        """Test getting lineups when user has none"""
        response = await async_client.get(
            "/api/v1/lineups",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["lineups"] == []
        assert data["total"] == 0

    async def test_get_lineups_with_data(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        db_session: AsyncSession
    ):
        """Test getting lineups when user has some"""
        # Create test lineups
        lineup1 = UserLineup(
            user_id=test_user.id,
            name="Lineup 1",
            lineup_type="custom",
            settings={}
        )
        lineup2 = UserLineup(
            user_id=test_user.id,
            name="Lineup 2",
            lineup_type="watchlist",
            settings={}
        )
        db_session.add_all([lineup1, lineup2])
        await db_session.commit()

        response = await async_client.get(
            "/api/v1/lineups",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["lineups"]) == 2
        assert data["total"] == 2

    async def test_get_lineup_by_id_success(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        db_session: AsyncSession
    ):
        """Test getting a specific lineup by ID"""
        # Create test lineup
        lineup = UserLineup(
            user_id=test_user.id,
            name="Test Lineup",
            description="Test description",
            lineup_type="custom",
            settings={}
        )
        db_session.add(lineup)
        await db_session.commit()
        await db_session.refresh(lineup)

        response = await async_client.get(
            f"/api/v1/lineups/{lineup.id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == lineup.id
        assert data["name"] == "Test Lineup"
        assert data["prospects"] == []

    async def test_get_lineup_not_found(
        self,
        async_client: AsyncClient,
        test_user_token: str
    ):
        """Test getting non-existent lineup returns 404"""
        response = await async_client.get(
            "/api/v1/lineups/99999",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 404

    async def test_update_lineup_success(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        db_session: AsyncSession
    ):
        """Test updating a lineup"""
        # Create test lineup
        lineup = UserLineup(
            user_id=test_user.id,
            name="Original Name",
            lineup_type="custom",
            settings={}
        )
        db_session.add(lineup)
        await db_session.commit()
        await db_session.refresh(lineup)

        response = await async_client.put(
            f"/api/v1/lineups/{lineup.id}",
            json={"name": "Updated Name", "description": "New description"},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New description"

    async def test_delete_lineup_success(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        db_session: AsyncSession
    ):
        """Test deleting a lineup"""
        # Create test lineup
        lineup = UserLineup(
            user_id=test_user.id,
            name="To Delete",
            lineup_type="custom",
            settings={}
        )
        db_session.add(lineup)
        await db_session.commit()
        await db_session.refresh(lineup)
        lineup_id = lineup.id

        response = await async_client.delete(
            f"/api/v1/lineups/{lineup_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 204

        # Verify deletion
        stmt = select(UserLineup).where(UserLineup.id == lineup_id)
        result = await db_session.execute(stmt)
        deleted_lineup = result.scalar_one_or_none()
        assert deleted_lineup is None


class TestLineupProspects:
    """Test lineup prospect management"""

    async def test_add_prospect_to_lineup_success(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        test_prospect: Prospect,
        db_session: AsyncSession
    ):
        """Test adding a prospect to a lineup"""
        # Create test lineup
        lineup = UserLineup(
            user_id=test_user.id,
            name="Test Lineup",
            lineup_type="custom",
            settings={}
        )
        db_session.add(lineup)
        await db_session.commit()
        await db_session.refresh(lineup)

        response = await async_client.post(
            f"/api/v1/lineups/{lineup.id}/prospects",
            json={
                "prospect_id": test_prospect.id,
                "position": "SS",
                "rank": 1,
                "notes": "Top prospect"
            },
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["prospect_id"] == test_prospect.id
        assert data["position"] == "SS"
        assert data["rank"] == 1
        assert data["notes"] == "Top prospect"
        assert data["prospect_name"] == "Test Prospect"

    async def test_add_prospect_duplicate_fails(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        test_prospect: Prospect,
        db_session: AsyncSession
    ):
        """Test adding same prospect twice fails"""
        # Create test lineup with prospect
        lineup = UserLineup(
            user_id=test_user.id,
            name="Test Lineup",
            lineup_type="custom",
            settings={}
        )
        db_session.add(lineup)
        await db_session.flush()

        lineup_prospect = LineupProspect(
            lineup_id=lineup.id,
            prospect_id=test_prospect.id
        )
        db_session.add(lineup_prospect)
        await db_session.commit()

        # Try to add again
        response = await async_client.post(
            f"/api/v1/lineups/{lineup.id}/prospects",
            json={"prospect_id": test_prospect.id},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 400
        assert "already in lineup" in response.json()["detail"].lower()

    async def test_update_prospect_in_lineup(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        test_prospect: Prospect,
        db_session: AsyncSession
    ):
        """Test updating prospect details in lineup"""
        # Create test lineup with prospect
        lineup = UserLineup(
            user_id=test_user.id,
            name="Test Lineup",
            lineup_type="custom",
            settings={}
        )
        db_session.add(lineup)
        await db_session.flush()

        lineup_prospect = LineupProspect(
            lineup_id=lineup.id,
            prospect_id=test_prospect.id,
            notes="Original notes"
        )
        db_session.add(lineup_prospect)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/lineups/{lineup.id}/prospects/{test_prospect.id}",
            json={"notes": "Updated notes", "rank": 5},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated notes"
        assert data["rank"] == 5

    async def test_remove_prospect_from_lineup(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        test_prospect: Prospect,
        db_session: AsyncSession
    ):
        """Test removing a prospect from lineup"""
        # Create test lineup with prospect
        lineup = UserLineup(
            user_id=test_user.id,
            name="Test Lineup",
            lineup_type="custom",
            settings={}
        )
        db_session.add(lineup)
        await db_session.flush()

        lineup_prospect = LineupProspect(
            lineup_id=lineup.id,
            prospect_id=test_prospect.id
        )
        db_session.add(lineup_prospect)
        await db_session.commit()

        response = await async_client.delete(
            f"/api/v1/lineups/{lineup.id}/prospects/{test_prospect.id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 204

        # Verify removal
        stmt = select(LineupProspect).where(
            LineupProspect.lineup_id == lineup.id,
            LineupProspect.prospect_id == test_prospect.id
        )
        result = await db_session.execute(stmt)
        removed = result.scalar_one_or_none()
        assert removed is None

    async def test_bulk_add_prospects(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        db_session: AsyncSession
    ):
        """Test bulk adding multiple prospects"""
        # Create test lineup
        lineup = UserLineup(
            user_id=test_user.id,
            name="Test Lineup",
            lineup_type="custom",
            settings={}
        )
        db_session.add(lineup)
        await db_session.flush()

        # Create multiple prospects
        prospects = []
        for i in range(3):
            prospect = Prospect(
                mlb_id=f"BULK{i:03d}",
                name=f"Bulk Prospect {i}",
                position="SS",
                organization="Test Org",
                age=22
            )
            db_session.add(prospect)
            prospects.append(prospect)

        await db_session.commit()
        for p in prospects:
            await db_session.refresh(p)

        prospect_ids = [p.id for p in prospects]

        response = await async_client.post(
            f"/api/v1/lineups/{lineup.id}/prospects/bulk",
            json={"prospect_ids": prospect_ids},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] == 3
        assert data["skipped_count"] == 0
        assert len(data["errors"]) == 0


class TestLineupAuthorization:
    """Test lineup authorization and access control"""

    async def test_cannot_access_other_user_lineup(
        self,
        async_client: AsyncClient,
        test_user: User,
        test_user_token: str,
        db_session: AsyncSession
    ):
        """Test user cannot access another user's lineup"""
        # Create another user
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            full_name="Other User",
            is_active=True,
            privacy_policy_accepted=True,
            data_processing_accepted=True,
            preferences={}
        )
        db_session.add(other_user)
        await db_session.flush()

        # Create lineup for other user
        other_lineup = UserLineup(
            user_id=other_user.id,
            name="Other User's Lineup",
            lineup_type="custom",
            settings={}
        )
        db_session.add(other_lineup)
        await db_session.commit()
        await db_session.refresh(other_lineup)

        # Try to access with test_user's token
        response = await async_client.get(
            f"/api/v1/lineups/{other_lineup.id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 404  # Should not reveal existence

    async def test_cannot_modify_other_user_lineup(
        self,
        async_client: AsyncClient,
        test_user_token: str,
        db_session: AsyncSession
    ):
        """Test user cannot modify another user's lineup"""
        # Create another user
        other_user = User(
            email="other2@example.com",
            hashed_password="hashed",
            full_name="Other User 2",
            is_active=True,
            privacy_policy_accepted=True,
            data_processing_accepted=True,
            preferences={}
        )
        db_session.add(other_user)
        await db_session.flush()

        # Create lineup for other user
        other_lineup = UserLineup(
            user_id=other_user.id,
            name="Protected Lineup",
            lineup_type="custom",
            settings={}
        )
        db_session.add(other_lineup)
        await db_session.commit()
        await db_session.refresh(other_lineup)

        # Try to modify
        response = await async_client.put(
            f"/api/v1/lineups/{other_lineup.id}",
            json={"name": "Hacked Name"},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 404

    async def test_cannot_delete_other_user_lineup(
        self,
        async_client: AsyncClient,
        test_user_token: str,
        db_session: AsyncSession
    ):
        """Test user cannot delete another user's lineup"""
        # Create another user
        other_user = User(
            email="other3@example.com",
            hashed_password="hashed",
            full_name="Other User 3",
            is_active=True,
            privacy_policy_accepted=True,
            data_processing_accepted=True,
            preferences={}
        )
        db_session.add(other_user)
        await db_session.flush()

        # Create lineup for other user
        other_lineup = UserLineup(
            user_id=other_user.id,
            name="Protected Lineup",
            lineup_type="custom",
            settings={}
        )
        db_session.add(other_lineup)
        await db_session.commit()
        await db_session.refresh(other_lineup)
        lineup_id = other_lineup.id

        # Try to delete
        response = await async_client.delete(
            f"/api/v1/lineups/{lineup_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 404

        # Verify lineup still exists
        stmt = select(UserLineup).where(UserLineup.id == lineup_id)
        result = await db_session.execute(stmt)
        lineup = result.scalar_one_or_none()
        assert lineup is not None
