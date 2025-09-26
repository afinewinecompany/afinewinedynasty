"""
Tests for database models and schema validation.
"""

import pytest
from datetime import date, datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction


@pytest.mark.asyncio
async def test_prospect_creation(async_session):
    """Test creating a prospect with valid data."""
    prospect = Prospect(
        mlb_id="TEST001",
        name="Test Player",
        position="SS",
        organization="Test Team",
        level="AA",
        age=21,
        eta_year=2025
    )

    async_session.add(prospect)
    await async_session.commit()

    assert prospect.id is not None
    assert prospect.mlb_id == "TEST001"
    assert prospect.name == "Test Player"
    assert prospect.position == "SS"


@pytest.mark.asyncio
async def test_prospect_unique_mlb_id(async_session):
    """Test that MLB ID must be unique."""
    prospect1 = Prospect(
        mlb_id="UNIQUE001",
        name="Player One",
        position="CF",
        organization="Team A",
        age=20,
        eta_year=2026
    )

    prospect2 = Prospect(
        mlb_id="UNIQUE001",  # Same MLB ID
        name="Player Two",
        position="1B",
        organization="Team B",
        age=22,
        eta_year=2025
    )

    async_session.add(prospect1)
    await async_session.commit()

    async_session.add(prospect2)
    with pytest.raises(IntegrityError):
        await async_session.commit()


@pytest.mark.asyncio
async def test_prospect_stats_creation(async_session):
    """Test creating prospect statistics."""
    # First create a prospect
    prospect = Prospect(
        mlb_id="STATS001",
        name="Stats Player",
        position="3B",
        organization="Stats Team",
        age=23,
        eta_year=2025
    )
    async_session.add(prospect)
    await async_session.commit()

    # Create stats
    stats = ProspectStats(
        prospect_id=prospect.id,
        date_recorded=date(2024, 5, 15),
        season=2024,
        games_played=50,
        at_bats=180,
        hits=52,
        home_runs=8,
        rbi=25,
        batting_avg=0.289,
        on_base_pct=0.340,
        slugging_pct=0.450
    )

    async_session.add(stats)
    await async_session.commit()

    assert stats.id is not None
    assert stats.prospect_id == prospect.id
    assert stats.season == 2024
    assert stats.batting_avg == 0.289


@pytest.mark.asyncio
async def test_scouting_grades_creation(async_session):
    """Test creating scouting grades."""
    # First create a prospect
    prospect = Prospect(
        mlb_id="GRADE001",
        name="Grade Player",
        position="SP",
        organization="Grade Team",
        age=22,
        eta_year=2026
    )
    async_session.add(prospect)
    await async_session.commit()

    # Create scouting grades
    grades = ScoutingGrades(
        prospect_id=prospect.id,
        source="Fangraphs",
        overall=55,
        fastball=60,
        curveball=50,
        changeup=45,
        control=55,
        future_value=55,
        risk="Moderate"
    )

    async_session.add(grades)
    await async_session.commit()

    assert grades.id is not None
    assert grades.prospect_id == prospect.id
    assert grades.source == "Fangraphs"
    assert grades.overall == 55


@pytest.mark.asyncio
async def test_ml_prediction_creation(async_session):
    """Test creating ML predictions."""
    # First create a prospect
    prospect = Prospect(
        mlb_id="ML001",
        name="ML Player",
        position="CF",
        organization="ML Team",
        age=20,
        eta_year=2027
    )
    async_session.add(prospect)
    await async_session.commit()

    # Create ML prediction
    prediction = MLPrediction(
        prospect_id=prospect.id,
        model_version="v1.0",
        prediction_type="career_war",
        prediction_value=3.5,
        confidence_score=0.85
    )

    async_session.add(prediction)
    await async_session.commit()

    assert prediction.id is not None
    assert prediction.prospect_id == prospect.id
    assert prediction.model_version == "v1.0"
    assert prediction.prediction_value == 3.5


@pytest.mark.asyncio
async def test_prospect_relationships(async_session):
    """Test relationships between prospect and related tables."""
    # Create a prospect
    prospect = Prospect(
        mlb_id="REL001",
        name="Relationship Player",
        position="2B",
        organization="Rel Team",
        age=21,
        eta_year=2026
    )
    async_session.add(prospect)
    await async_session.commit()

    # Create stats and grades
    stats = ProspectStats(
        prospect_id=prospect.id,
        date_recorded=date(2024, 6, 1),
        season=2024,
        games_played=30,
        at_bats=120,
        hits=36,
        batting_avg=0.300
    )

    grades = ScoutingGrades(
        prospect_id=prospect.id,
        source="MLB Pipeline",
        overall=50,
        hit=55,
        power=45,
        run=60,
        field=55,
        throw=50
    )

    async_session.add_all([stats, grades])
    await async_session.commit()

    # Refresh prospect to load relationships
    await async_session.refresh(prospect)

    # Test relationships (note: these would work with proper session management)
    assert len(prospect.stats) >= 1
    assert len(prospect.scouting_grades) >= 1


@pytest.mark.asyncio
async def test_query_performance_under_100ms(async_session):
    """Test that common query patterns execute in under 100ms."""
    import time

    # Create test data
    prospects = []
    for i in range(100):
        prospect = Prospect(
            mlb_id=f"PERF{i:03d}",
            name=f"Performance Player {i}",
            position="SS" if i % 2 == 0 else "CF",
            organization=f"Team {i % 5}",
            age=20 + (i % 5),
            eta_year=2025 + (i % 3)
        )
        prospects.append(prospect)

    async_session.add_all(prospects)
    await async_session.commit()

    # Test 1: Query by organization
    start_time = time.time()
    result = await async_session.execute(
        select(Prospect).where(Prospect.organization == "Team 1")
    )
    prospects_team1 = result.scalars().all()
    duration = (time.time() - start_time) * 1000  # Convert to ms
    assert duration < 100, f"Query by organization took {duration}ms, expected <100ms"

    # Test 2: Query by position and ETA year
    start_time = time.time()
    result = await async_session.execute(
        select(Prospect)
        .where(Prospect.position == "SS")
        .where(Prospect.eta_year == 2025)
    )
    shortstops_2025 = result.scalars().all()
    duration = (time.time() - start_time) * 1000
    assert duration < 100, f"Query by position and ETA took {duration}ms, expected <100ms"

    # Test 3: Query with pagination
    start_time = time.time()
    result = await async_session.execute(
        select(Prospect)
        .order_by(Prospect.name)
        .limit(20)
        .offset(40)
    )
    paginated = result.scalars().all()
    duration = (time.time() - start_time) * 1000
    assert duration < 100, f"Paginated query took {duration}ms, expected <100ms"

    # Test 4: Join query with stats
    start_time = time.time()
    result = await async_session.execute(
        select(Prospect)
        .join(ProspectStats)
        .where(ProspectStats.season == 2024)
        .distinct()
    )
    prospects_with_2024_stats = result.scalars().all()
    duration = (time.time() - start_time) * 1000
    assert duration < 100, f"Join query took {duration}ms, expected <100ms"


@pytest.mark.asyncio
async def test_statistical_field_boundaries(async_session):
    """Test boundary conditions for statistical validation constraints."""
    # Create a prospect for testing
    prospect = Prospect(
        mlb_id="BOUND001",
        name="Boundary Player",
        position="CF",
        organization="Test Team",
        age=20,
        eta_year=2025
    )
    async_session.add(prospect)
    await async_session.commit()

    # Test 1: Batting average boundaries (0.000 to 1.000)
    stats_low = ProspectStats(
        prospect_id=prospect.id,
        date_recorded=date(2024, 5, 1),
        season=2024,
        games_played=1,
        at_bats=100,
        hits=0,
        batting_avg=0.000  # Minimum boundary
    )
    async_session.add(stats_low)
    await async_session.commit()
    assert stats_low.batting_avg == 0.000

    stats_high = ProspectStats(
        prospect_id=prospect.id,
        date_recorded=date(2024, 5, 2),
        season=2024,
        games_played=1,
        at_bats=100,
        hits=100,
        batting_avg=1.000  # Maximum boundary
    )
    async_session.add(stats_high)
    await async_session.commit()
    assert stats_high.batting_avg == 1.000

    # Test 2: ERA boundaries (0.00 to very high)
    pitcher_stats = ProspectStats(
        prospect_id=prospect.id,
        date_recorded=date(2024, 5, 3),
        season=2024,
        innings_pitched=9.0,
        earned_runs=0,
        era=0.00  # Perfect ERA
    )
    async_session.add(pitcher_stats)
    await async_session.commit()
    assert pitcher_stats.era == 0.00

    high_era_stats = ProspectStats(
        prospect_id=prospect.id,
        date_recorded=date(2024, 5, 4),
        season=2024,
        innings_pitched=1.0,
        earned_runs=99,
        era=891.00  # Very high ERA
    )
    async_session.add(high_era_stats)
    await async_session.commit()
    assert high_era_stats.era == 891.00

    # Test 3: Scouting grades boundaries (20 to 80 scale)
    grades_min = ScoutingGrades(
        prospect_id=prospect.id,
        source="Test Source Min",
        overall=20,  # Minimum scouting grade
        hit=20,
        power=20
    )
    async_session.add(grades_min)
    await async_session.commit()
    assert grades_min.overall == 20

    grades_max = ScoutingGrades(
        prospect_id=prospect.id,
        source="Test Source Max",
        overall=80,  # Maximum scouting grade
        hit=80,
        power=80
    )
    async_session.add(grades_max)
    await async_session.commit()
    assert grades_max.overall == 80

    # Test 4: Percentage fields (0.0 to 1.0)
    stats_pct = ProspectStats(
        prospect_id=prospect.id,
        date_recorded=date(2024, 5, 5),
        season=2024,
        games_played=100,
        on_base_pct=0.000,  # Minimum OBP
        slugging_pct=1.000   # Maximum theoretical SLG (all at-bats are home runs)
    )
    async_session.add(stats_pct)
    await async_session.commit()
    assert stats_pct.on_base_pct == 0.000
    assert stats_pct.slugging_pct == 1.000

    # Test 5: Count fields should not be negative
    stats_counts = ProspectStats(
        prospect_id=prospect.id,
        date_recorded=date(2024, 5, 6),
        season=2024,
        games_played=0,  # Zero games
        at_bats=0,        # Zero at bats
        hits=0,           # Zero hits
        home_runs=0,      # Zero home runs
        rbi=0,            # Zero RBIs
        stolen_bases=0    # Zero stolen bases
    )
    async_session.add(stats_counts)
    await async_session.commit()
    assert stats_counts.games_played == 0
    assert stats_counts.at_bats == 0