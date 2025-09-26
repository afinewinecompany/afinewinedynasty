"""Unit tests for data integration and processing."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from app.services.data_integration_service import DataIntegrationService
from app.services.duplicate_detection_service import DuplicateDetectionService, DuplicateMatch


class TestDataIntegrationService:
    """Test data integration service functionality."""

    @pytest.fixture
    def integration_service(self):
        return DataIntegrationService()

    def test_name_normalization(self, integration_service):
        """Test name normalization for matching."""
        assert integration_service.normalize_name("Jackson Holliday") == "jackson holliday"
        assert integration_service.normalize_name("José Ramírez") == "jos ramrez"
        assert integration_service.normalize_name("O'Neill Jr.") == "oneill jr"

    def test_name_similarity_calculation(self, integration_service):
        """Test name similarity scoring."""
        # Exact match
        score = integration_service.calculate_name_similarity("Jackson Holliday", "Jackson Holliday")
        assert score == 1.0

        # Similar names
        score = integration_service.calculate_name_similarity("Jackson Holliday", "Jackson Holiday")
        assert score > 0.9

        # Different names
        score = integration_service.calculate_name_similarity("Jackson Holliday", "Paul Skenes")
        assert score < 0.3

    def test_prospect_matching(self, integration_service):
        """Test prospect matching logic."""
        prospect1 = {
            'mlb_id': '123',
            'name': 'Jackson Holliday',
            'position': 'SS',
            'organization': 'Baltimore Orioles'
        }

        prospect2 = {
            'mlb_id': '123',
            'name': 'J. Holliday',
            'position': 'SS',
            'organization': 'BAL'
        }

        # Should match on MLB ID
        assert integration_service.match_prospects(prospect1, prospect2) is True

        # Test without MLB ID
        prospect3 = {
            'name': 'Jackson Holiday',  # Slightly different spelling
            'position': 'SS',
            'organization': 'Baltimore Orioles'
        }

        prospect4 = {
            'name': 'Jackson Holliday',
            'position': 'SS',
            'organization': 'Baltimore Orioles'
        }

        # Should match on name similarity and org
        assert integration_service.match_prospects(prospect3, prospect4, threshold=0.85) is True

    @pytest.mark.asyncio
    async def test_merge_prospect_data(self, integration_service):
        """Test merging prospect data from multiple sources."""
        mlb_data = [
            {
                'mlb_id': '123',
                'name': 'Jackson Holliday',
                'position': 'SS',
                'organization': 'Baltimore Orioles',
                'age': 20
            }
        ]

        fangraphs_data = [
            {
                'name': 'Jackson Holliday',
                'position': 'SS',
                'organization': 'BAL',
                'scouting_grades': {
                    'hit': 60,
                    'power': 55,
                    'speed': 55
                },
                'rankings': {
                    'overall': 1
                }
            }
        ]

        merged = await integration_service.merge_prospect_data(
            mlb_data=mlb_data,
            fangraphs_data=fangraphs_data,
            precedence_order=['mlb', 'fangraphs']
        )

        assert len(merged) == 1
        assert merged[0]['mlb_id'] == '123'
        assert merged[0]['name'] == 'Jackson Holliday'
        assert 'scouting_grades' in merged[0]
        assert merged[0]['scouting_grades']['hit'] == 60
        assert 'fangraphs_rankings' in merged[0]

    def test_merge_scouting_grades(self, integration_service):
        """Test merging of scouting grades from multiple sources."""
        grades1 = {
            'hit': 55,
            'power': 60,
            'source': 'mlb'
        }

        grades2 = {
            'hit': 60,
            'speed': 50,
            'field': 45,
            'source': 'fangraphs'
        }

        merged = integration_service.merge_scouting_grades(
            grades1, grades2, precedence=['mlb', 'fangraphs']
        )

        # MLB takes precedence for 'hit'
        assert merged['hit'] == 55
        # Fangraphs values for unique fields
        assert merged['speed'] == 50
        assert merged['field'] == 45
        # MLB value preserved
        assert merged['power'] == 60

    def test_standardize_grade_scale(self, integration_service):
        """Test grade scale standardization."""
        # Already in 20-80 scale
        assert integration_service.standardize_grade_scale(55, 'raw', '20-80') == 55

        # Convert from 2-8 scale
        assert integration_service.standardize_grade_scale(5.5, '2-8', '20-80') == 55

        # Convert from 0-100 scale
        assert integration_service.standardize_grade_scale(58.33, '0-100', '20-80') == 55

        # Invalid grade
        assert integration_service.standardize_grade_scale(None, 'raw', '20-80') is None

    @pytest.mark.asyncio
    async def test_validate_merged_data(self, integration_service):
        """Test validation of merged data."""
        data = [
            {
                'name': 'Valid Player',
                'position': 'SS',
                'organization': 'Baltimore Orioles',
                'age': 20,
                'scouting_grades': {'hit': 55}
            },
            {
                'name': '',  # Invalid - missing name
                'position': 'SS',
                'organization': 'Baltimore Orioles'
            },
            {
                'name': 'Invalid Grade',
                'position': 'SS',
                'organization': 'Baltimore Orioles',
                'scouting_grades': {'hit': 90}  # Invalid - outside 20-80 range
            }
        ]

        valid, invalid = await integration_service.validate_merged_data(data)

        assert len(valid) == 1
        assert valid[0]['name'] == 'Valid Player'

        assert len(invalid) == 2
        assert any('Missing prospect name' in err for err in invalid[0]['errors'])
        assert any('Invalid grade' in str(err) for err in invalid[1]['errors'])


class TestDuplicateDetection:
    """Test duplicate detection functionality."""

    @pytest.fixture
    def duplicate_service(self):
        return DuplicateDetectionService()

    def test_position_matching(self, duplicate_service):
        """Test position matching logic."""
        assert duplicate_service._positions_match('SS', 'SS') is True
        assert duplicate_service._positions_match('SS', 'SHORTSTOP') is False
        assert duplicate_service._positions_match('RHP', 'P') is True
        assert duplicate_service._positions_match('LF', 'OF') is True
        assert duplicate_service._positions_match('1B', '2B') is False

    @pytest.mark.asyncio
    async def test_cross_source_duplicate_detection(self, duplicate_service):
        """Test detection of duplicates across data sources."""
        mock_session = AsyncMock()

        # Mock MLB prospects
        mlb_prospect = Mock(
            id=1,
            name="Jackson Holliday",
            organization="Baltimore Orioles",
            position="SS",
            mlb_id="123",
            last_fangraphs_update=None
        )

        # Mock Fangraphs prospect (potential duplicate)
        fg_prospect = Mock(
            id=2,
            name="Jackson Holiday",  # Slightly different
            organization="BAL",
            position="SS",
            mlb_id=None,
            last_fangraphs_update=datetime.utcnow()
        )

        # Setup mock query results
        mlb_result = Mock()
        mlb_result.scalars.return_value.all.return_value = [mlb_prospect]

        fg_result = Mock()
        fg_result.scalars.return_value.all.return_value = [fg_prospect]

        mock_session.execute.side_effect = [mlb_result, fg_result]

        # Detect duplicates
        duplicates = await duplicate_service.detect_cross_source_duplicates(
            mock_session,
            source_precedence=['mlb', 'fangraphs']
        )

        assert len(duplicates) == 1
        assert duplicates[0].match_type == 'cross_source'
        assert duplicates[0].confidence_score > 0.8
        assert duplicates[0].prospect1_id == 1  # MLB takes precedence
        assert duplicates[0].prospect2_id == 2


class TestDataMappingStandardization:
    """Test data mapping and standardization."""

    @pytest.fixture
    def integration_service(self):
        return DataIntegrationService()

    def test_position_standardization(self, integration_service):
        """Test position string standardization."""
        # Pitcher variations
        assert integration_service.standardize_position("RHP") == "RHP"
        assert integration_service.standardize_position("RHSP") == "RHP"
        assert integration_service.standardize_position("right handed pitcher") == "right handed pitcher"

        # Infield positions
        assert integration_service.standardize_position("SHORTSTOP") == "SS"
        assert integration_service.standardize_position("SS") == "SS"
        assert integration_service.standardize_position("2B") == "2B"
        assert integration_service.standardize_position("SECOND BASE") == "2B"

        # Outfield positions
        assert integration_service.standardize_position("CF") == "CF"
        assert integration_service.standardize_position("CENTER FIELD") == "CF"
        assert integration_service.standardize_position("OUTFIELD") == "OF"

    def test_organization_standardization(self, integration_service):
        """Test organization name standardization."""
        # Team abbreviations
        assert integration_service.standardize_organization("BAL") == "Baltimore Orioles"
        assert integration_service.standardize_organization("NYY") == "New York Yankees"
        assert integration_service.standardize_organization("TB") == "Tampa Bay Rays"
        assert integration_service.standardize_organization("TBR") == "Tampa Bay Rays"

        # Full names
        assert integration_service.standardize_organization("ORIOLES") == "Baltimore Orioles"
        assert integration_service.standardize_organization("RED SOX") == "Boston Red Sox"

        # Unknown organization
        assert integration_service.standardize_organization("") == "Unknown"
        assert integration_service.standardize_organization(None) == "Unknown"

    @pytest.mark.asyncio
    async def test_conflict_resolution(self, integration_service):
        """Test conflict resolution in merged data."""
        data = {
            'name': 'Test Player',
            'sources': ['mlb', 'fangraphs'],
            'mlb_position': 'SS',
            'fangraphs_position': '2B',
            'mlb_age': 20,
            'fangraphs_age': 21
        }

        resolved = await integration_service.resolve_conflicts(
            data,
            precedence_order=['mlb', 'fangraphs']
        )

        # MLB should take precedence
        assert resolved['position'] == 'SS'
        assert resolved['age'] == 20