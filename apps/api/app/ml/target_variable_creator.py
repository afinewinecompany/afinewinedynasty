"""
Target Variable Creator for ML Model Training
Creates binary labels for prospect MLB success based on career outcomes.

Success Criteria:
- Primary: >500 PA (plate appearances) OR >100 IP (innings pitched) within 4 years
- Alternative definitions available for testing
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.db.models import Prospect, ProspectStats
from app.services.mlb_api_service import MLBAPIClient

logger = logging.getLogger(__name__)


class TargetVariableCreator:
    """Create MLB success labels for historical prospects."""

    # Success definitions for testing different criteria
    SUCCESS_DEFINITIONS = {
        'strict': {
            'min_pa': 500,
            'min_ip': 100,
            'years_window': 4,
            'description': 'Standard definition from PRD'
        },
        'moderate': {
            'min_pa': 200,
            'min_ip': 50,
            'years_window': 4,
            'description': 'More lenient for broader success'
        },
        'loose': {
            'min_pa': 100,
            'min_ip': 25,
            'years_window': 5,
            'description': 'Very lenient, larger window'
        }
    }

    def __init__(self, success_definition: str = 'strict'):
        """
        Initialize target variable creator.

        Args:
            success_definition: Which success criteria to use ('strict', 'moderate', 'loose')
        """
        if success_definition not in self.SUCCESS_DEFINITIONS:
            raise ValueError(f"Invalid success definition: {success_definition}")

        self.definition = self.SUCCESS_DEFINITIONS[success_definition]
        self.success_definition_name = success_definition
        logger.info(f"Target variable creator initialized with '{success_definition}' definition")

    async def label_prospect_success(
        self,
        mlb_id: str,
        prospect_year: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Determine if a prospect achieved MLB success.

        Args:
            mlb_id: MLB player ID
            prospect_year: Year when player was considered a prospect
            db: Database session

        Returns:
            Dictionary with success label and supporting metrics
        """
        logger.debug(f"Labeling prospect {mlb_id} from year {prospect_year}")

        # Get MLB career stats within the evaluation window
        career_stats = await self._get_mlb_career_stats(
            mlb_id=mlb_id,
            start_year=prospect_year,
            end_year=prospect_year + self.definition['years_window']
        )

        if not career_stats:
            return {
                'mlb_success': False,
                'total_pa': 0,
                'total_ip': 0.0,
                'years_in_mlb': 0,
                'reached_mlb': False,
                'evaluation_window': f"{prospect_year}-{prospect_year + self.definition['years_window']}",
                'definition_used': self.success_definition_name
            }

        # Calculate totals
        total_pa = sum(stat.get('plate_appearances', 0) for stat in career_stats)
        total_ip = sum(stat.get('innings_pitched', 0.0) for stat in career_stats)
        years_in_mlb = len(set(stat.get('season') for stat in career_stats))

        # Determine success
        success = (
            total_pa >= self.definition['min_pa'] or
            total_ip >= self.definition['min_ip']
        )

        result = {
            'mlb_success': success,
            'total_pa': total_pa,
            'total_ip': total_ip,
            'years_in_mlb': years_in_mlb,
            'reached_mlb': True,
            'evaluation_window': f"{prospect_year}-{prospect_year + self.definition['years_window']}",
            'definition_used': self.success_definition_name,
            'success_reason': self._get_success_reason(total_pa, total_ip, success)
        }

        logger.debug(f"Prospect {mlb_id}: success={success}, PA={total_pa}, IP={total_ip}")
        return result

    def _get_success_reason(self, pa: int, ip: float, success: bool) -> str:
        """Determine why prospect succeeded or failed."""
        if not success:
            return "Did not meet minimum MLB playing time requirements"

        reasons = []
        if pa >= self.definition['min_pa']:
            reasons.append(f"Position player: {pa} PA")
        if ip >= self.definition['min_ip']:
            reasons.append(f"Pitcher: {ip:.1f} IP")

        return " AND ".join(reasons) if len(reasons) > 1 else reasons[0]

    async def _get_mlb_career_stats(
        self,
        mlb_id: str,
        start_year: int,
        end_year: int
    ) -> List[Dict[str, Any]]:
        """
        Get MLB career statistics for a prospect within evaluation window.

        Args:
            mlb_id: MLB player ID
            start_year: First year to include
            end_year: Last year to include

        Returns:
            List of season statistics
        """
        stats = []

        async with MLBAPIClient() as client:
            for year in range(start_year, end_year + 1):
                try:
                    # Fetch season stats from MLB API
                    season_stats = await client.get_player_stats(
                        player_id=int(mlb_id),
                        season=year
                    )

                    if season_stats and 'stats' in season_stats:
                        # Parse hitting and pitching stats
                        for stat_group in season_stats['stats']:
                            if stat_group.get('type', {}).get('displayName') == 'season':
                                splits = stat_group.get('splits', [])

                                for split in splits:
                                    stat_data = split.get('stat', {})
                                    league = split.get('league', {})

                                    # Only count MLB stats (league ID 103 or 104)
                                    league_id = league.get('id')
                                    if league_id not in [103, 104]:  # AL=103, NL=104
                                        continue

                                    stats.append({
                                        'season': year,
                                        'plate_appearances': stat_data.get('plateAppearances', 0),
                                        'innings_pitched': float(stat_data.get('inningsPitched', 0)),
                                        'games': stat_data.get('gamesPlayed', 0),
                                        'league_id': league_id
                                    })

                except Exception as e:
                    logger.warning(f"Could not fetch stats for {mlb_id} in {year}: {str(e)}")
                    continue

        return stats

    async def batch_label_prospects(
        self,
        prospects: List[Tuple[str, int]],
        db: Session
    ) -> Dict[str, Any]:
        """
        Label multiple prospects in batch.

        Args:
            prospects: List of (mlb_id, prospect_year) tuples
            db: Database session

        Returns:
            Dictionary with labeled results and statistics
        """
        logger.info(f"Batch labeling {len(prospects)} prospects")

        results = []
        successes = 0
        failures = 0
        errors = 0

        for mlb_id, prospect_year in prospects:
            try:
                label_result = await self.label_prospect_success(
                    mlb_id=mlb_id,
                    prospect_year=prospect_year,
                    db=db
                )

                results.append({
                    'mlb_id': mlb_id,
                    'prospect_year': prospect_year,
                    **label_result
                })

                if label_result['mlb_success']:
                    successes += 1
                else:
                    failures += 1

            except Exception as e:
                logger.error(f"Error labeling prospect {mlb_id}: {str(e)}")
                errors += 1
                results.append({
                    'mlb_id': mlb_id,
                    'prospect_year': prospect_year,
                    'mlb_success': None,
                    'error': str(e)
                })

        success_rate = successes / (successes + failures) if (successes + failures) > 0 else 0

        summary = {
            'total_prospects': len(prospects),
            'successfully_labeled': successes + failures,
            'successes': successes,
            'failures': failures,
            'errors': errors,
            'success_rate': success_rate,
            'definition_used': self.success_definition_name,
            'results': results
        }

        logger.info(
            f"Batch labeling complete: {successes} successes, {failures} failures, "
            f"{errors} errors (success rate: {success_rate:.1%})"
        )

        return summary

    def analyze_success_distribution(self, labeled_results: List[Dict]) -> Dict[str, Any]:
        """
        Analyze the distribution of success labels for validation.

        Args:
            labeled_results: List of labeled prospect dictionaries

        Returns:
            Distribution analysis
        """
        total = len(labeled_results)
        successes = sum(1 for r in labeled_results if r.get('mlb_success') is True)
        failures = sum(1 for r in labeled_results if r.get('mlb_success') is False)
        unknown = sum(1 for r in labeled_results if r.get('mlb_success') is None)

        # Calculate statistics for successful prospects
        successful_prospects = [r for r in labeled_results if r.get('mlb_success')]

        avg_pa = (
            sum(r.get('total_pa', 0) for r in successful_prospects) / len(successful_prospects)
            if successful_prospects else 0
        )

        avg_ip = (
            sum(r.get('total_ip', 0) for r in successful_prospects) / len(successful_prospects)
            if successful_prospects else 0
        )

        return {
            'total_prospects': total,
            'successful': successes,
            'failed': failures,
            'unknown': unknown,
            'success_rate': successes / (successes + failures) if (successes + failures) > 0 else 0,
            'average_pa_successful': avg_pa,
            'average_ip_successful': avg_ip,
            'definition': self.definition,
            'balanced_dataset': 0.30 <= (successes / total) <= 0.70 if total > 0 else False
        }


class MultiDefinitionEvaluator:
    """Test multiple success definitions to find optimal threshold."""

    async def evaluate_all_definitions(
        self,
        prospects: List[Tuple[str, int]],
        db: Session
    ) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate all success definitions and compare results.

        Args:
            prospects: List of (mlb_id, prospect_year) tuples
            db: Database session

        Returns:
            Comparison of all definitions
        """
        logger.info("Evaluating all success definitions")

        results = {}

        for def_name in TargetVariableCreator.SUCCESS_DEFINITIONS.keys():
            logger.info(f"Testing definition: {def_name}")

            creator = TargetVariableCreator(success_definition=def_name)
            batch_results = await creator.batch_label_prospects(prospects, db)

            results[def_name] = {
                'summary': batch_results,
                'distribution': creator.analyze_success_distribution(batch_results['results'])
            }

        # Recommend best definition
        best_def = self._recommend_best_definition(results)

        return {
            'definitions_tested': results,
            'recommendation': best_def
        }

    def _recommend_best_definition(self, results: Dict) -> str:
        """Recommend best success definition based on balance and realism."""

        # Prefer definitions with 30-50% success rate (balanced dataset)
        scores = {}

        for def_name, data in results.items():
            success_rate = data['distribution']['success_rate']
            balanced = data['distribution']['balanced_dataset']

            # Score based on how close to 40% (ideal balance)
            balance_score = 1.0 - abs(success_rate - 0.40)

            scores[def_name] = {
                'balance_score': balance_score,
                'success_rate': success_rate,
                'balanced': balanced
            }

        # Return definition with best balance
        best = max(scores.items(), key=lambda x: x[1]['balance_score'])

        logger.info(f"Recommended definition: {best[0]} (success rate: {best[1]['success_rate']:.1%})")
        return best[0]
