#!/usr/bin/env python3
"""
MVP Historical Data Collection Script
Collects 5 years of historical data (2020-2024) for rapid ML model training.

This hybrid approach allows:
- Fast path to working model (2-3 weeks)
- ~10,000 prospect records
- Validation of full pipeline
- Parallel expansion to 15 years
"""

import sys
import os
import asyncio
import logging
import argparse
from datetime import datetime
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, get_db
from app.services.mlb_api_service import MLBAPIClient
from app.services.fangraphs_service import FangraphsService
from app.services.data_integration_service import DataIntegrationService
from app.ml.target_variable_creator import TargetVariableCreator, MultiDefinitionEvaluator
from app.models.prospect import Prospect
from app.models.prospect_stats import ProspectStats

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'mvp_data_collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class MVPDataCollectionPipeline:
    """Orchestrates MVP historical data collection (2020-2024)."""

    def __init__(self, start_year: int = 2020, end_year: int = 2024):
        self.start_year = start_year
        self.end_year = end_year
        self.collected_prospects = []
        self.labeled_prospects = []
        self.metrics = {
            'start_time': datetime.utcnow(),
            'years_processed': 0,
            'prospects_collected': 0,
            'prospects_labeled': 0,
            'success_rate': 0.0
        }

    async def run_full_pipeline(self, create_labels: bool = True, test_definitions: bool = False):
        """
        Execute complete MVP data collection pipeline.

        Args:
            create_labels: Whether to create MLB success labels
            test_definitions: Test all success definitions to find best
        """
        logger.info(f"=" * 80)
        logger.info(f"MVP HISTORICAL DATA COLLECTION PIPELINE")
        logger.info(f"Years: {self.start_year} - {self.end_year}")
        logger.info(f"Create Labels: {create_labels}")
        logger.info(f"Test Definitions: {test_definitions}")
        logger.info(f"=" * 80)

        try:
            # Step 1: Collect historical prospect data
            await self.collect_historical_prospects()

            # Step 2: Label prospects with MLB outcomes
            if create_labels:
                if test_definitions:
                    await self.test_success_definitions()
                else:
                    await self.label_prospects()

            # Step 3: Generate summary report
            self.generate_summary_report()

            logger.info("✅ MVP data collection pipeline completed successfully!")

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {str(e)}")
            raise

    async def collect_historical_prospects(self):
        """Collect historical prospect data from all sources."""
        logger.info(f"\n{'='*80}\nSTEP 1: Collecting Historical Prospect Data\n{'='*80}")

        for year in range(self.start_year, self.end_year + 1):
            logger.info(f"\n>>> Processing year {year}")

            try:
                # Collect from MLB API
                mlb_prospects = await self._collect_mlb_prospects(year)
                logger.info(f"Collected {len(mlb_prospects)} prospects from MLB API")

                # Collect from Fangraphs (top 100 only to respect rate limits)
                fg_prospects = await self._collect_fangraphs_prospects(year, limit=100)
                logger.info(f"Collected {len(fg_prospects)} prospects from Fangraphs")

                # Merge data
                merged = await self._merge_prospect_data(mlb_prospects, fg_prospects, year)
                logger.info(f"Merged to {len(merged)} unique prospects for {year}")

                self.collected_prospects.extend(merged)
                self.metrics['years_processed'] += 1

            except Exception as e:
                logger.error(f"Error processing year {year}: {str(e)}")
                continue

        self.metrics['prospects_collected'] = len(self.collected_prospects)
        logger.info(f"\n✅ Total prospects collected: {self.metrics['prospects_collected']}")

    async def _collect_mlb_prospects(self, year: int) -> list:
        """Collect prospects from MLB API for a specific year."""
        prospects = []

        async with MLBAPIClient() as client:
            try:
                # Get all minor league players for the year
                # Note: MLB API doesn't have a direct "prospects" endpoint
                # We'll get top minor league performers as proxy
                logger.info(f"Fetching MLB data for {year}...")

                # This is a simplified approach - in production you'd query
                # multiple minor league levels and teams
                data = await client.get_prospects_data(sport_id=11)

                if data and 'people' in data:
                    for person in data['people']:
                        prospect = {
                            'mlb_id': str(person.get('id')),
                            'name': person.get('fullName'),
                            'position': person.get('primaryPosition', {}).get('abbreviation'),
                            'organization': person.get('currentTeam', {}).get('name'),
                            'birth_date': person.get('birthDate'),
                            'year': year,
                            'source': 'mlb_api'
                        }
                        prospects.append(prospect)

            except Exception as e:
                logger.error(f"MLB API error for {year}: {str(e)}")

        return prospects

    async def _collect_fangraphs_prospects(self, year: int, limit: int = 100) -> list:
        """Collect top prospects from Fangraphs for a specific year."""
        prospects = []

        async with FangraphsService() as service:
            try:
                # Get top prospects list
                top_list = await service.get_top_prospects_list(year=year, limit=limit)

                # Get detailed data for each (respecting 1 req/sec rate limit)
                for prospect_info in top_list[:limit]:
                    name = prospect_info.get('name')

                    if name:
                        detailed = await service.get_prospect_data(name)

                        if detailed:
                            prospect = {
                                'mlb_id': None,  # Will match later
                                'name': name,
                                'position': prospect_info.get('position'),
                                'organization': prospect_info.get('organization'),
                                'rank': prospect_info.get('rank'),
                                'eta': prospect_info.get('eta'),
                                'scouting_grades': detailed.get('scouting_grades', {}),
                                'year': year,
                                'source': 'fangraphs'
                            }
                            prospects.append(prospect)

            except Exception as e:
                logger.error(f"Fangraphs error for {year}: {str(e)}")

        return prospects

    async def _merge_prospect_data(self, mlb_data: list, fg_data: list, year: int) -> list:
        """Merge MLB and Fangraphs data, deduplicating by name."""
        merged = {}

        # Add MLB prospects
        for p in mlb_data:
            key = p['name'].lower() if p.get('name') else None
            if key:
                merged[key] = p

        # Merge Fangraphs data
        for p in fg_data:
            key = p['name'].lower() if p.get('name') else None
            if key:
                if key in merged:
                    # Merge scouting grades from Fangraphs
                    merged[key]['scouting_grades'] = p.get('scouting_grades', {})
                    merged[key]['fangraphs_rank'] = p.get('rank')
                else:
                    merged[key] = p

        # Convert back to list and add year
        result = []
        for prospect in merged.values():
            prospect['prospect_year'] = year
            result.append(prospect)

        return result

    async def label_prospects(self):
        """Label all collected prospects with MLB success outcomes."""
        logger.info(f"\n{'='*80}\nSTEP 2: Labeling Prospects with MLB Outcomes\n{'='*80}")

        # Prepare prospect list for labeling
        prospects_to_label = [
            (p['mlb_id'], p['prospect_year'])
            for p in self.collected_prospects
            if p.get('mlb_id')
        ]

        logger.info(f"Labeling {len(prospects_to_label)} prospects with known MLB IDs...")

        # Create labeler with strict definition (PRD default)
        labeler = TargetVariableCreator(success_definition='strict')

        # Batch label prospects
        async with get_db() as db:
            results = await labeler.batch_label_prospects(prospects_to_label, db)

            self.labeled_prospects = results['results']
            self.metrics['prospects_labeled'] = results['successfully_labeled']
            self.metrics['success_rate'] = results['success_rate']

            # Analyze distribution
            distribution = labeler.analyze_success_distribution(results['results'])

            logger.info(f"\n{'='*40}")
            logger.info(f"LABELING RESULTS:")
            logger.info(f"Total labeled: {distribution['total_prospects']}")
            logger.info(f"Successes: {distribution['successful']} ({distribution['success_rate']:.1%})")
            logger.info(f"Failures: {distribution['failed']}")
            logger.info(f"Unknown: {distribution['unknown']}")
            logger.info(f"Balanced dataset: {distribution['balanced_dataset']}")
            logger.info(f"{'='*40}\n")

    async def test_success_definitions(self):
        """Test all success definitions to find optimal threshold."""
        logger.info(f"\n{'='*80}\nSTEP 2: Testing Success Definitions\n{'='*80}")

        # Prepare prospect list
        prospects_to_test = [
            (p['mlb_id'], p['prospect_year'])
            for p in self.collected_prospects
            if p.get('mlb_id')
        ][:100]  # Test on first 100 for speed

        logger.info(f"Testing definitions on {len(prospects_to_test)} prospects...")

        evaluator = MultiDefinitionEvaluator()

        async with get_db() as db:
            results = await evaluator.evaluate_all_definitions(prospects_to_test, db)

            logger.info(f"\n{'='*60}")
            logger.info("SUCCESS DEFINITION COMPARISON:")
            logger.info(f"{'='*60}")

            for def_name, data in results['definitions_tested'].items():
                dist = data['distribution']
                logger.info(f"\n{def_name.upper()}:")
                logger.info(f"  Success rate: {dist['success_rate']:.1%}")
                logger.info(f"  Balanced: {dist['balanced_dataset']}")
                logger.info(f"  Avg PA (successful): {dist['average_pa_successful']:.0f}")
                logger.info(f"  Avg IP (successful): {dist['average_ip_successful']:.1f}")

            logger.info(f"\n{'='*60}")
            logger.info(f"RECOMMENDATION: {results['recommendation']}")
            logger.info(f"{'='*60}\n")

    def generate_summary_report(self):
        """Generate final summary report."""
        logger.info(f"\n{'='*80}\nFINAL SUMMARY REPORT\n{'='*80}")

        duration = (datetime.utcnow() - self.metrics['start_time']).total_seconds() / 60

        logger.info(f"Pipeline Duration: {duration:.1f} minutes")
        logger.info(f"Years Processed: {self.metrics['years_processed']}")
        logger.info(f"Prospects Collected: {self.metrics['prospects_collected']}")
        logger.info(f"Prospects Labeled: {self.metrics['prospects_labeled']}")
        logger.info(f"MLB Success Rate: {self.metrics['success_rate']:.1%}")

        # Save results to JSON
        output_file = f"mvp_collection_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        summary = {
            'pipeline_info': {
                'start_year': self.start_year,
                'end_year': self.end_year,
                'completion_time': datetime.utcnow().isoformat(),
                'duration_minutes': duration
            },
            'metrics': self.metrics,
            'prospects_sample': self.collected_prospects[:10],  # First 10 as sample
            'labeled_sample': self.labeled_prospects[:10] if self.labeled_prospects else []
        }

        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"\n✅ Results saved to: {output_file}")
        logger.info(f"{'='*80}\n")


async def main():
    """Main entry point for MVP data collection."""
    parser = argparse.ArgumentParser(description='MVP Historical Data Collection')
    parser.add_argument('--start-year', type=int, default=2020, help='Start year (default: 2020)')
    parser.add_argument('--end-year', type=int, default=2024, help='End year (default: 2024)')
    parser.add_argument('--no-labels', action='store_true', help='Skip labeling step')
    parser.add_argument('--test-definitions', action='store_true', help='Test all success definitions')

    args = parser.parse_args()

    pipeline = MVPDataCollectionPipeline(
        start_year=args.start_year,
        end_year=args.end_year
    )

    await pipeline.run_full_pipeline(
        create_labels=not args.no_labels,
        test_definitions=args.test_definitions
    )


if __name__ == '__main__':
    asyncio.run(main())
