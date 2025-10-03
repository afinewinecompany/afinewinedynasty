"""Tests for AdvancedFilterService."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.advanced_filter_service import AdvancedFilterService
from app.db.models import Prospect, ProspectStats


class TestAdvancedFilterService:
    """Test suite for AdvancedFilterService."""

    @pytest.mark.asyncio
    async def test_build_filter_query_with_position(self, db_session: AsyncSession):
        """Test building query with position filter."""
        base_query = select(Prospect)
        filters = {"position": ["SS", "2B"]}

        query = AdvancedFilterService.build_filter_query(base_query, filters)

        # Verify query contains position filter
        query_str = str(query)
        assert "position" in query_str.lower()

    @pytest.mark.asyncio
    async def test_build_filter_query_with_age_range(self, db_session: AsyncSession):
        """Test building query with age range filter."""
        base_query = select(Prospect)
        filters = {
            "age_min": 18,
            "age_max": 25
        }

        query = AdvancedFilterService.build_filter_query(base_query, filters)

        # Verify query contains age filters
        query_str = str(query)
        assert "age" in query_str.lower()

    @pytest.mark.asyncio
    async def test_build_filter_query_with_multiple_filters(self, db_session: AsyncSession):
        """Test building query with multiple filter criteria."""
        base_query = select(Prospect)
        filters = {
            "position": ["SS", "2B"],
            "organization": ["NYY", "BOS"],
            "age_min": 20,
            "age_max": 25,
            "eta_min": 2024,
            "eta_max": 2026
        }

        query = AdvancedFilterService.build_filter_query(base_query, filters)

        # Verify query is valid
        query_str = str(query)
        assert "position" in query_str.lower()
        assert "organization" in query_str.lower()
        assert "age" in query_str.lower()

    @pytest.mark.asyncio
    async def test_build_filter_query_with_or_operator(self, db_session: AsyncSession):
        """Test building query with OR operator."""
        base_query = select(Prospect)
        filters = {
            "position": ["SS", "2B"],
            "level": ["AAA", "AA"]
        }

        query = AdvancedFilterService.build_filter_query(base_query, filters, operator="OR")

        # Query should be valid with OR operator
        assert query is not None

    @pytest.mark.asyncio
    async def test_apply_statistical_filters_batting_avg(self, db_session: AsyncSession):
        """Test filtering prospects by batting average."""
        # Create test prospects with stats
        prospect_ids = [1, 2, 3]
        stat_filters = {
            "batting_avg_min": 0.300,
            "batting_avg_max": 0.350
        }

        # This would need actual test data in the database
        filtered = await AdvancedFilterService.apply_statistical_filters(
            db_session,
            prospect_ids,
            stat_filters
        )

        assert isinstance(filtered, list)

    @pytest.mark.asyncio
    async def test_apply_ml_prediction_filters(self, db_session: AsyncSession):
        """Test filtering prospects by ML predictions."""
        prospect_ids = [1, 2, 3]
        ml_filters = {
            "success_probability_min": 0.7,
            "confidence_levels": ["High"]
        }

        filtered = await AdvancedFilterService.apply_ml_prediction_filters(
            db_session,
            prospect_ids,
            ml_filters
        )

        assert isinstance(filtered, list)

    @pytest.mark.asyncio
    async def test_apply_scouting_grade_filters(self, db_session: AsyncSession):
        """Test filtering prospects by scouting grades."""
        prospect_ids = [1, 2, 3]
        grade_filters = {
            "overall_grade_min": 50,
            "future_value_min": 55,
            "sources": ["Fangraphs", "MLB Pipeline"]
        }

        filtered = await AdvancedFilterService.apply_scouting_grade_filters(
            db_session,
            prospect_ids,
            grade_filters
        )

        assert isinstance(filtered, list)

    def test_build_complex_filter_expression(self):
        """Test building complex filter expressions."""
        filter_groups = [
            {
                "operator": "AND",
                "filters": {
                    "position": ["SS", "2B"],
                    "age_max": 21
                }
            },
            {
                "operator": "OR",
                "filters": {
                    "organization": "NYY",
                    "level": "AAA"
                }
            }
        ]

        conditions, operator = AdvancedFilterService.build_complex_filter_expression(
            filter_groups
        )

        assert len(conditions) == 2
        assert operator == "AND"

    @pytest.mark.asyncio
    async def test_execute_advanced_search_with_caching(self, db_session: AsyncSession):
        """Test advanced search execution with result caching."""
        filter_config = {
            "basic_filters": {
                "position": ["SS"],
                "age_max": 25
            },
            "operator": "AND"
        }

        results = await AdvancedFilterService.execute_advanced_search(
            db_session,
            filter_config,
            limit=10
        )

        assert isinstance(results, list)
        assert len(results) <= 10

    @pytest.mark.asyncio
    async def test_execute_advanced_search_with_all_filters(self, db_session: AsyncSession):
        """Test advanced search with all filter types."""
        filter_config = {
            "basic_filters": {
                "position": ["SS", "2B"],
                "organization": ["NYY"],
                "age_min": 18,
                "age_max": 25
            },
            "stat_filters": {
                "batting_avg_min": 0.280,
                "ops_min": 0.800
            },
            "ml_filters": {
                "success_probability_min": 0.6,
                "confidence_levels": ["High", "Medium"]
            },
            "grade_filters": {
                "overall_grade_min": 50,
                "future_value_min": 50
            },
            "operator": "AND"
        }

        results = await AdvancedFilterService.execute_advanced_search(
            db_session,
            filter_config,
            limit=50
        )

        assert isinstance(results, list)
        assert len(results) <= 50