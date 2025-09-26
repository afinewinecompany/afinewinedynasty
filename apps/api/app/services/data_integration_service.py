"""Data integration service for merging and standardizing prospect data from multiple sources."""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import re
from difflib import SequenceMatcher

from app.schemas.fangraphs_schemas import (
    FangraphsProspectData,
    FangraphsScoutingGrades,
    FangraphsStatistics
)
from app.services.pipeline_monitoring import PipelineMonitor

logger = logging.getLogger(__name__)


class DataIntegrationService:
    """Service for integrating prospect data from multiple sources."""

    # Standardized position mappings
    POSITION_MAPPINGS = {
        # Pitchers
        'RHP': 'RHP', 'LHP': 'LHP', 'P': 'P',
        'SP': 'SP', 'RP': 'RP', 'CL': 'CL',
        'RHSP': 'RHP', 'LHSP': 'LHP',
        'RHRP': 'RHP', 'LHRP': 'LHP',

        # Catchers
        'C': 'C', 'CA': 'C', 'CATCHER': 'C',

        # Infielders
        '1B': '1B', 'FIRST': '1B', 'FIRST BASE': '1B',
        '2B': '2B', 'SECOND': '2B', 'SECOND BASE': '2B',
        '3B': '3B', 'THIRD': '3B', 'THIRD BASE': '3B',
        'SS': 'SS', 'SHORTSTOP': 'SS', 'SHORT': 'SS',
        'INF': 'INF', 'IF': 'INF', 'UTIL': 'UTIL',

        # Outfielders
        'LF': 'LF', 'LEFT': 'LF', 'LEFT FIELD': 'LF',
        'CF': 'CF', 'CENTER': 'CF', 'CENTER FIELD': 'CF',
        'RF': 'RF', 'RIGHT': 'RF', 'RIGHT FIELD': 'RF',
        'OF': 'OF', 'OUTFIELD': 'OF',

        # Other
        'DH': 'DH', 'DESIGNATED HITTER': 'DH',
    }

    # Organization name mappings
    ORGANIZATION_MAPPINGS = {
        # AL East
        'BAL': 'Baltimore Orioles', 'ORIOLES': 'Baltimore Orioles',
        'BOS': 'Boston Red Sox', 'RED SOX': 'Boston Red Sox',
        'NYY': 'New York Yankees', 'YANKEES': 'New York Yankees',
        'TB': 'Tampa Bay Rays', 'TBR': 'Tampa Bay Rays', 'RAYS': 'Tampa Bay Rays',
        'TOR': 'Toronto Blue Jays', 'BLUE JAYS': 'Toronto Blue Jays',

        # AL Central
        'CLE': 'Cleveland Guardians', 'GUARDIANS': 'Cleveland Guardians',
        'CWS': 'Chicago White Sox', 'CHW': 'Chicago White Sox', 'WHITE SOX': 'Chicago White Sox',
        'DET': 'Detroit Tigers', 'TIGERS': 'Detroit Tigers',
        'KC': 'Kansas City Royals', 'KCR': 'Kansas City Royals', 'ROYALS': 'Kansas City Royals',
        'MIN': 'Minnesota Twins', 'TWINS': 'Minnesota Twins',

        # AL West
        'HOU': 'Houston Astros', 'ASTROS': 'Houston Astros',
        'LAA': 'Los Angeles Angels', 'ANGELS': 'Los Angeles Angels',
        'OAK': 'Oakland Athletics', 'ATHLETICS': 'Oakland Athletics', 'A\'S': 'Oakland Athletics',
        'SEA': 'Seattle Mariners', 'MARINERS': 'Seattle Mariners',
        'TEX': 'Texas Rangers', 'RANGERS': 'Texas Rangers',

        # NL East
        'ATL': 'Atlanta Braves', 'BRAVES': 'Atlanta Braves',
        'MIA': 'Miami Marlins', 'MARLINS': 'Miami Marlins',
        'NYM': 'New York Mets', 'METS': 'New York Mets',
        'PHI': 'Philadelphia Phillies', 'PHILLIES': 'Philadelphia Phillies',
        'WAS': 'Washington Nationals', 'WSN': 'Washington Nationals', 'NATIONALS': 'Washington Nationals',

        # NL Central
        'CHC': 'Chicago Cubs', 'CUBS': 'Chicago Cubs',
        'CIN': 'Cincinnati Reds', 'REDS': 'Cincinnati Reds',
        'MIL': 'Milwaukee Brewers', 'BREWERS': 'Milwaukee Brewers',
        'PIT': 'Pittsburgh Pirates', 'PIRATES': 'Pittsburgh Pirates',
        'STL': 'St. Louis Cardinals', 'CARDINALS': 'St. Louis Cardinals',

        # NL West
        'ARI': 'Arizona Diamondbacks', 'AZ': 'Arizona Diamondbacks', 'DIAMONDBACKS': 'Arizona Diamondbacks',
        'COL': 'Colorado Rockies', 'ROCKIES': 'Colorado Rockies',
        'LAD': 'Los Angeles Dodgers', 'DODGERS': 'Los Angeles Dodgers',
        'SD': 'San Diego Padres', 'PADRES': 'San Diego Padres',
        'SF': 'San Francisco Giants', 'SFG': 'San Francisco Giants', 'GIANTS': 'San Francisco Giants',
    }

    def __init__(self):
        self.monitor = PipelineMonitor()

    def standardize_position(self, position: str) -> str:
        """Standardize position strings to consistent format."""
        if not position:
            return "UNKNOWN"

        position_upper = position.upper().strip()
        return self.POSITION_MAPPINGS.get(position_upper, position_upper)

    def standardize_organization(self, org: str) -> str:
        """Standardize organization names to consistent format."""
        if not org:
            return "Unknown"

        org_upper = org.upper().strip()
        return self.ORGANIZATION_MAPPINGS.get(org_upper, org)

    def normalize_name(self, name: str) -> str:
        """Normalize prospect name for matching."""
        if not name:
            return ""

        # Remove special characters and extra spaces
        normalized = re.sub(r'[^\w\s]', '', name)
        normalized = ' '.join(normalized.split())
        return normalized.lower()

    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity score between two names."""
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Check if one name contains the other (for nicknames)
        if norm1 in norm2 or norm2 in norm1:
            return 0.9

        # Use sequence matching for fuzzy comparison
        return SequenceMatcher(None, norm1, norm2).ratio()

    def match_prospects(self, prospect1: Dict, prospect2: Dict, threshold: float = 0.85) -> bool:
        """Determine if two prospect records represent the same person."""
        # If MLB IDs match, they're the same
        if prospect1.get('mlb_id') and prospect2.get('mlb_id'):
            return prospect1['mlb_id'] == prospect2['mlb_id']

        # Match by name and organization
        name_sim = self.calculate_name_similarity(
            prospect1.get('name', ''),
            prospect2.get('name', '')
        )

        if name_sim < threshold:
            return False

        # Additional checks for same organization and position
        org1 = self.standardize_organization(prospect1.get('organization', ''))
        org2 = self.standardize_organization(prospect2.get('organization', ''))

        pos1 = self.standardize_position(prospect1.get('position', ''))
        pos2 = self.standardize_position(prospect2.get('position', ''))

        # If organizations match, lower the name threshold
        if org1 == org2:
            return name_sim >= 0.75

        # If positions also match, further lower the threshold
        if pos1 == pos2:
            return name_sim >= 0.8

        return name_sim >= threshold

    def merge_scouting_grades(self, grades1: Dict, grades2: Dict, precedence: List[str]) -> Dict:
        """Merge scouting grades from multiple sources."""
        merged = {}

        # Get all unique grade types
        all_grades = set(list(grades1.keys()) + list(grades2.keys()))

        for grade_type in all_grades:
            val1 = grades1.get(grade_type)
            val2 = grades2.get(grade_type)

            if val1 is not None and val2 is not None:
                # If both sources have the grade, use precedence
                if grades1.get('source') in precedence:
                    source_idx1 = precedence.index(grades1.get('source', ''))
                else:
                    source_idx1 = 999

                if grades2.get('source') in precedence:
                    source_idx2 = precedence.index(grades2.get('source', ''))
                else:
                    source_idx2 = 999

                merged[grade_type] = val1 if source_idx1 <= source_idx2 else val2
            else:
                # Use whichever value is available
                merged[grade_type] = val1 if val1 is not None else val2

        return merged

    def merge_statistics(self, stats1: Dict, stats2: Dict) -> Dict:
        """Merge statistics from multiple sources."""
        merged = {}

        # Combine all years
        all_years = set(list(stats1.keys()) + list(stats2.keys()))

        for year in all_years:
            year_stats1 = stats1.get(year, {})
            year_stats2 = stats2.get(year, {})

            if year_stats1 and year_stats2:
                # Merge stats for the same year
                merged[year] = {**year_stats2, **year_stats1}  # Stats1 takes precedence
            else:
                merged[year] = year_stats1 or year_stats2

        return merged

    async def merge_prospect_data(
        self,
        mlb_data: List[Dict],
        fangraphs_data: List[Dict],
        precedence_order: List[str] = None
    ) -> List[Dict]:
        """Merge prospect data from MLB API and Fangraphs."""
        if precedence_order is None:
            precedence_order = ['mlb', 'fangraphs']

        merged_prospects = []
        matched_indices = set()

        # Start with MLB data as the base
        for mlb_prospect in mlb_data or []:
            merged = {
                'mlb_id': mlb_prospect.get('mlb_id') or mlb_prospect.get('id'),
                'name': mlb_prospect.get('fullName') or mlb_prospect.get('name'),
                'position': self.standardize_position(mlb_prospect.get('position')),
                'organization': self.standardize_organization(mlb_prospect.get('organization')),
                'level': mlb_prospect.get('level'),
                'age': mlb_prospect.get('age'),
                'eta_year': mlb_prospect.get('eta_year'),
                'source': 'mlb',
                'sources': ['mlb'],
                'last_updated': datetime.utcnow().isoformat()
            }

            # Try to find matching Fangraphs data
            for idx, fg_prospect in enumerate(fangraphs_data or []):
                if idx in matched_indices:
                    continue

                if self.match_prospects(merged, fg_prospect):
                    matched_indices.add(idx)

                    # Merge the data
                    merged['sources'].append('fangraphs')

                    # Merge scouting grades
                    if fg_prospect.get('scouting_grades'):
                        if 'scouting_grades' not in merged:
                            merged['scouting_grades'] = {}

                        merged['scouting_grades'] = self.merge_scouting_grades(
                            merged.get('scouting_grades', {}),
                            fg_prospect['scouting_grades'],
                            precedence_order
                        )

                    # Merge statistics
                    if fg_prospect.get('statistics'):
                        if 'statistics' not in merged:
                            merged['statistics'] = {}

                        merged['statistics'] = self.merge_statistics(
                            merged.get('statistics', {}),
                            fg_prospect['statistics']
                        )

                    # Add Fangraphs-specific data
                    if fg_prospect.get('rankings'):
                        merged['fangraphs_rankings'] = fg_prospect['rankings']

                    if fg_prospect.get('bio'):
                        merged['bio'] = fg_prospect['bio']

                    merged['last_fangraphs_update'] = fg_prospect.get('fetched_at')

                    logger.info(f"Matched {merged['name']} between MLB and Fangraphs")
                    break

            merged_prospects.append(merged)

        # Add unmatched Fangraphs prospects
        for idx, fg_prospect in enumerate(fangraphs_data or []):
            if idx not in matched_indices:
                merged = {
                    'name': fg_prospect.get('name'),
                    'position': self.standardize_position(fg_prospect.get('position')),
                    'organization': self.standardize_organization(fg_prospect.get('organization')),
                    'source': 'fangraphs',
                    'sources': ['fangraphs'],
                    'last_updated': datetime.utcnow().isoformat(),
                    'last_fangraphs_update': fg_prospect.get('fetched_at')
                }

                # Add Fangraphs data
                if fg_prospect.get('scouting_grades'):
                    merged['scouting_grades'] = fg_prospect['scouting_grades']

                if fg_prospect.get('statistics'):
                    merged['statistics'] = fg_prospect['statistics']

                if fg_prospect.get('rankings'):
                    merged['fangraphs_rankings'] = fg_prospect['rankings']

                if fg_prospect.get('bio'):
                    merged['bio'] = fg_prospect['bio']
                    merged['age'] = fg_prospect['bio'].get('age')

                merged_prospects.append(merged)
                logger.info(f"Added Fangraphs-only prospect: {merged['name']}")

        # Log merge statistics
        await self.monitor.record_data_merge(
            source1='mlb',
            source2='fangraphs',
            source1_count=len(mlb_data or []),
            source2_count=len(fangraphs_data or []),
            matched_count=len(matched_indices),
            total_merged=len(merged_prospects)
        )

        logger.info(f"Merged {len(merged_prospects)} total prospects from {len(mlb_data or [])} MLB and {len(fangraphs_data or [])} Fangraphs records")
        return merged_prospects

    async def resolve_conflicts(self, data: Dict, precedence_order: List[str]) -> Dict:
        """Resolve conflicts in merged data based on precedence rules."""
        resolved = data.copy()

        # Identify conflicting fields
        conflicts = []

        for field in ['position', 'organization', 'age', 'level']:
            values = {}

            for source in data.get('sources', []):
                source_value = data.get(f"{source}_{field}")
                if source_value:
                    values[source] = source_value

            if len(set(values.values())) > 1:
                # Conflict detected
                conflicts.append({
                    'field': field,
                    'values': values
                })

                # Resolve based on precedence
                for source in precedence_order:
                    if source in values:
                        resolved[field] = values[source]
                        break

        if conflicts:
            await self.monitor.record_conflict_resolution(
                prospect_name=data.get('name'),
                conflicts=conflicts,
                resolution_method='precedence',
                precedence_order=precedence_order
            )

            logger.info(f"Resolved {len(conflicts)} conflicts for {data.get('name')}")

        return resolved

    def standardize_grade_scale(self, grade: Any, current_scale: str = 'raw', target_scale: str = '20-80') -> Optional[int]:
        """Convert scouting grades to standardized 20-80 scale."""
        if grade is None:
            return None

        try:
            grade_val = float(grade)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert grade to number: {grade}")
            return None

        if target_scale == '20-80':
            if current_scale == 'raw':
                # Already in 20-80 scale
                if 20 <= grade_val <= 80:
                    return round(grade_val / 5) * 5  # Round to nearest 5

            elif current_scale == '2-8':
                # Convert from 2-8 to 20-80
                return int(grade_val * 10)

            elif current_scale == '0-100':
                # Convert from 0-100 to 20-80
                return int(20 + (grade_val * 0.6))

            elif current_scale == '1-10':
                # Convert from 1-10 to 20-80
                return int(20 + ((grade_val - 1) * 60 / 9))

        return None

    async def validate_merged_data(self, data: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Validate merged data and separate valid from invalid records."""
        valid = []
        invalid = []

        for record in data:
            errors = []

            # Required fields
            if not record.get('name'):
                errors.append("Missing prospect name")

            if not record.get('position'):
                errors.append("Missing position")

            if not record.get('organization'):
                errors.append("Missing organization")

            # Validate scouting grades if present
            if record.get('scouting_grades'):
                for grade_name, grade_value in record['scouting_grades'].items():
                    if isinstance(grade_value, (int, float)):
                        if grade_value < 20 or grade_value > 80:
                            errors.append(f"Invalid grade {grade_name}: {grade_value}")

            # Validate age if present
            if record.get('age'):
                try:
                    age = int(record['age'])
                    if age < 15 or age > 50:
                        errors.append(f"Invalid age: {age}")
                except (ValueError, TypeError):
                    errors.append(f"Invalid age format: {record['age']}")

            if errors:
                invalid.append({
                    'record': record,
                    'errors': errors
                })
                logger.warning(f"Invalid record for {record.get('name')}: {errors}")
            else:
                valid.append(record)

        await self.monitor.record_validation_results(
            total_records=len(data),
            valid_count=len(valid),
            invalid_count=len(invalid)
        )

        return valid, invalid