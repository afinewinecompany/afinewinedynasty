#!/usr/bin/env python3
"""
API Validation Suite for A Fine Wine Dynasty
Tests MLB Stats API, Fantrax API, and FanGraphs scraping capabilities
"""

import requests
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd
from bs4 import BeautifulSoup
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APIValidationSuite:
    def __init__(self):
        self.results = {
            'mlb_api': {},
            'fantrax_api': {},
            'fangraphs_scraping': {},
            'timestamp': datetime.now().isoformat()
        }

        # API Base URLs
        self.mlb_base_url = "http://statsapi.mlb.com/api/v1"
        self.fantrax_base_url = "https://www.fantrax.com/fxea/general"
        self.fangraphs_base_url = "https://www.fangraphs.com"

        # Headers for web scraping
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def test_mlb_stats_api(self) -> Dict[str, Any]:
        """Test MLB Stats API endpoints and capabilities"""
        logger.info("Testing MLB Stats API...")

        results = {
            'available': False,
            'rate_limits': {},
            'data_quality': {},
            'endpoints': {},
            'errors': []
        }

        try:
            # Test 1: Basic connectivity
            logger.info("Testing MLB API connectivity...")
            response = requests.get(f"{self.mlb_base_url}/sports", timeout=10)
            results['available'] = response.status_code == 200
            results['endpoints']['sports'] = {
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'data_count': len(response.json().get('sports', []))
            }

            # Test 2: Minor League Players (Prospects)
            logger.info("Testing minor league prospects endpoint...")
            # Sport ID 11 = Minor League Baseball
            prospects_response = requests.get(f"{self.mlb_base_url}/sports/11/players", timeout=10)
            results['endpoints']['minor_league_players'] = {
                'status_code': prospects_response.status_code,
                'response_time': prospects_response.elapsed.total_seconds(),
                'available': prospects_response.status_code == 200
            }

            if prospects_response.status_code == 200:
                prospect_data = prospects_response.json()
                results['data_quality']['prospect_count'] = len(prospect_data.get('people', []))

                # Analyze data completeness for first 5 prospects
                sample_prospects = prospect_data.get('people', [])[:5]
                if sample_prospects:
                    completeness = self._analyze_prospect_data_completeness(sample_prospects)
                    results['data_quality']['completeness'] = completeness

            # Test 3: Rate limiting analysis
            logger.info("Testing MLB API rate limits...")
            rate_limit_results = self._test_mlb_rate_limits()
            results['rate_limits'] = rate_limit_results

            # Test 4: Prospect search capabilities
            logger.info("Testing prospect search...")
            search_response = requests.get(
                f"{self.mlb_base_url}/people/search",
                params={'names': 'Jackson Holliday'},
                timeout=10
            )
            results['endpoints']['player_search'] = {
                'status_code': search_response.status_code,
                'response_time': search_response.elapsed.total_seconds(),
                'available': search_response.status_code == 200
            }

        except Exception as e:
            results['errors'].append(f"MLB API Error: {str(e)}")
            logger.error(f"MLB API Error: {str(e)}")

        self.results['mlb_api'] = results
        return results

    def test_fantrax_api(self, user_secret_id: Optional[str] = None) -> Dict[str, Any]:
        """Test Fantrax API endpoints and capabilities"""
        logger.info("Testing Fantrax API...")

        results = {
            'available': False,
            'endpoints': {},
            'data_quality': {},
            'authentication': {},
            'errors': []
        }

        try:
            # Test 1: Public endpoints (no auth required)
            logger.info("Testing Fantrax public endpoints...")

            # Player IDs endpoint
            player_ids_response = requests.get(
                f"{self.fantrax_base_url}/getPlayerIds",
                params={'sport': 'MLB'},
                timeout=10
            )
            results['endpoints']['player_ids'] = {
                'status_code': player_ids_response.status_code,
                'response_time': player_ids_response.elapsed.total_seconds(),
                'available': player_ids_response.status_code == 200
            }

            if player_ids_response.status_code == 200:
                player_data = player_ids_response.json()
                results['data_quality']['player_count'] = len(player_data.get('players', []))
                results['available'] = True

            # ADP (Average Draft Position) endpoint
            adp_response = requests.get(
                f"{self.fantrax_base_url}/getAdp",
                params={'sport': 'MLB'},
                timeout=10
            )
            results['endpoints']['adp'] = {
                'status_code': adp_response.status_code,
                'response_time': adp_response.elapsed.total_seconds(),
                'available': adp_response.status_code == 200
            }

            if adp_response.status_code == 200:
                adp_data = adp_response.json()
                results['data_quality']['adp_players'] = len(adp_data.get('players', []))

                # Analyze ADP data completeness
                sample_adp = adp_data.get('players', [])[:5]
                if sample_adp:
                    results['data_quality']['adp_fields'] = list(sample_adp[0].keys()) if sample_adp else []

            # Test 2: Authenticated endpoints (if user_secret_id provided)
            if user_secret_id:
                logger.info("Testing Fantrax authenticated endpoints...")
                leagues_response = requests.get(
                    f"{self.fantrax_base_url}/getLeagues",
                    params={'userSecretId': user_secret_id},
                    timeout=10
                )
                results['authentication']['leagues'] = {
                    'status_code': leagues_response.status_code,
                    'response_time': leagues_response.elapsed.total_seconds(),
                    'available': leagues_response.status_code == 200
                }

                if leagues_response.status_code == 200:
                    leagues_data = leagues_response.json()
                    results['authentication']['user_leagues'] = len(leagues_data.get('leagues', []))
            else:
                results['authentication']['note'] = "No userSecretId provided for testing authenticated endpoints"

        except Exception as e:
            results['errors'].append(f"Fantrax API Error: {str(e)}")
            logger.error(f"Fantrax API Error: {str(e)}")

        self.results['fantrax_api'] = results
        return results

    def test_fangraphs_scraping(self) -> Dict[str, Any]:
        """Test FanGraphs scraping capabilities for prospect data"""
        logger.info("Testing FanGraphs scraping...")

        results = {
            'available': False,
            'scraping_endpoints': {},
            'data_extraction': {},
            'rate_limits': {},
            'legal_compliance': {},
            'errors': []
        }

        try:
            # Test 1: Basic site accessibility
            logger.info("Testing FanGraphs site accessibility...")
            response = requests.get(f"{self.fangraphs_base_url}", headers=self.headers, timeout=10)
            results['available'] = response.status_code == 200
            results['scraping_endpoints']['homepage'] = {
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }

            # Test 2: Prospect pages accessibility
            logger.info("Testing prospect pages...")
            prospect_list_url = f"{self.fangraphs_base_url}/prospects"
            prospect_response = requests.get(prospect_list_url, headers=self.headers, timeout=10)
            results['scraping_endpoints']['prospects_page'] = {
                'status_code': prospect_response.status_code,
                'response_time': prospect_response.elapsed.total_seconds(),
                'available': prospect_response.status_code == 200
            }

            # Test 3: Data extraction capabilities
            if prospect_response.status_code == 200:
                logger.info("Testing data extraction...")
                soup = BeautifulSoup(prospect_response.content, 'html.parser')

                # Look for prospect data tables
                tables = soup.find_all('table')
                results['data_extraction']['tables_found'] = len(tables)

                # Look for prospect rankings
                prospect_links = soup.find_all('a', href=lambda href: href and '/prospects/' in href)
                results['data_extraction']['prospect_links_found'] = len(prospect_links)

                # Check for scouting grades or rankings
                grade_elements = soup.find_all(text=lambda text: text and any(
                    grade in str(text).lower() for grade in ['hit', 'power', 'speed', 'field', 'arm']
                ))
                results['data_extraction']['scouting_elements_found'] = len(grade_elements)

            # Test 4: Rate limiting and politeness
            logger.info("Testing rate limiting behavior...")
            rate_limit_results = self._test_fangraphs_rate_limits()
            results['rate_limits'] = rate_limit_results

            # Test 5: robots.txt compliance
            logger.info("Checking robots.txt...")
            robots_response = requests.get(f"{self.fangraphs_base_url}/robots.txt", headers=self.headers, timeout=10)
            if robots_response.status_code == 200:
                results['legal_compliance']['robots_txt'] = robots_response.text
                results['legal_compliance']['allows_scraping'] = 'Disallow: /' not in robots_response.text

        except Exception as e:
            results['errors'].append(f"FanGraphs Scraping Error: {str(e)}")
            logger.error(f"FanGraphs Scraping Error: {str(e)}")

        self.results['fangraphs_scraping'] = results
        return results

    def _analyze_prospect_data_completeness(self, prospects: List[Dict]) -> Dict[str, Any]:
        """Analyze completeness of prospect data from MLB API"""
        if not prospects:
            return {}

        fields_analysis = {}
        total_prospects = len(prospects)

        # Check common fields
        common_fields = ['id', 'fullName', 'birthDate', 'primaryPosition', 'currentTeam']

        for field in common_fields:
            field_present = sum(1 for prospect in prospects if prospect.get(field) is not None)
            fields_analysis[field] = {
                'present': field_present,
                'percentage': (field_present / total_prospects) * 100
            }

        # Sample prospect for structure analysis
        fields_analysis['sample_prospect_keys'] = list(prospects[0].keys()) if prospects else []

        return fields_analysis

    def _test_mlb_rate_limits(self) -> Dict[str, Any]:
        """Test MLB API rate limits"""
        rate_test = {
            'requests_made': 0,
            'successful_requests': 0,
            'rate_limited': False,
            'average_response_time': 0,
            'errors': []
        }

        response_times = []

        try:
            # Make 10 requests with minimal delay to test rate limits
            for i in range(10):
                start_time = time.time()
                response = requests.get(f"{self.mlb_base_url}/sports", timeout=5)
                end_time = time.time()

                rate_test['requests_made'] += 1
                response_times.append(end_time - start_time)

                if response.status_code == 200:
                    rate_test['successful_requests'] += 1
                elif response.status_code == 429:  # Too Many Requests
                    rate_test['rate_limited'] = True
                    break

                time.sleep(0.5)  # 500ms delay between requests

            if response_times:
                rate_test['average_response_time'] = sum(response_times) / len(response_times)

        except Exception as e:
            rate_test['errors'].append(str(e))

        return rate_test

    def _test_fangraphs_rate_limits(self) -> Dict[str, Any]:
        """Test FanGraphs scraping rate limits and politeness"""
        rate_test = {
            'requests_made': 0,
            'successful_requests': 0,
            'blocked_requests': 0,
            'average_response_time': 0,
            'recommended_delay': 2.0,  # Start with 2 seconds
            'errors': []
        }

        response_times = []

        try:
            # Make 5 requests with 2-second delay (being polite)
            for i in range(5):
                start_time = time.time()
                response = requests.get(f"{self.fangraphs_base_url}", headers=self.headers, timeout=10)
                end_time = time.time()

                rate_test['requests_made'] += 1
                response_times.append(end_time - start_time)

                if response.status_code == 200:
                    rate_test['successful_requests'] += 1
                elif response.status_code in [403, 429, 503]:
                    rate_test['blocked_requests'] += 1

                time.sleep(rate_test['recommended_delay'])  # Be polite

            if response_times:
                rate_test['average_response_time'] = sum(response_times) / len(response_times)

        except Exception as e:
            rate_test['errors'].append(str(e))

        return rate_test

    def generate_report(self) -> str:
        """Generate comprehensive validation report"""
        report = []
        report.append("=" * 80)
        report.append("API VALIDATION SUITE REPORT")
        report.append(f"Generated: {self.results['timestamp']}")
        report.append("=" * 80)

        # MLB API Results
        mlb_results = self.results.get('mlb_api', {})
        report.append("\n🏀 MLB STATS API RESULTS")
        report.append("-" * 40)
        report.append(f"Available: {'✅ YES' if mlb_results.get('available') else '❌ NO'}")

        if mlb_results.get('endpoints'):
            report.append("\nEndpoints Tested:")
            for endpoint, data in mlb_results['endpoints'].items():
                status = "✅ PASS" if data.get('status_code') == 200 else f"❌ FAIL ({data.get('status_code')})"
                report.append(f"  {endpoint}: {status} ({data.get('response_time', 0):.2f}s)")

        if mlb_results.get('data_quality'):
            report.append(f"\nData Quality:")
            dq = mlb_results['data_quality']
            if 'prospect_count' in dq:
                report.append(f"  Prospects found: {dq['prospect_count']}")
            if 'completeness' in dq:
                report.append(f"  Data completeness: {json.dumps(dq['completeness'], indent=4)}")

        # Fantrax API Results
        fantrax_results = self.results.get('fantrax_api', {})
        report.append("\n⚾ FANTRAX API RESULTS")
        report.append("-" * 40)
        report.append(f"Available: {'✅ YES' if fantrax_results.get('available') else '❌ NO'}")

        if fantrax_results.get('endpoints'):
            report.append("\nEndpoints Tested:")
            for endpoint, data in fantrax_results['endpoints'].items():
                status = "✅ PASS" if data.get('status_code') == 200 else f"❌ FAIL ({data.get('status_code')})"
                report.append(f"  {endpoint}: {status} ({data.get('response_time', 0):.2f}s)")

        # FanGraphs Scraping Results
        fg_results = self.results.get('fangraphs_scraping', {})
        report.append("\n📊 FANGRAPHS SCRAPING RESULTS")
        report.append("-" * 40)
        report.append(f"Site Accessible: {'✅ YES' if fg_results.get('available') else '❌ NO'}")

        if fg_results.get('data_extraction'):
            de = fg_results['data_extraction']
            report.append(f"\nData Extraction:")
            report.append(f"  Tables found: {de.get('tables_found', 0)}")
            report.append(f"  Prospect links: {de.get('prospect_links_found', 0)}")
            report.append(f"  Scouting elements: {de.get('scouting_elements_found', 0)}")

        if fg_results.get('legal_compliance'):
            lc = fg_results['legal_compliance']
            report.append(f"\nLegal Compliance:")
            report.append(f"  Allows scraping: {'✅ YES' if lc.get('allows_scraping') else '❌ NO/UNKNOWN'}")

        # Summary and Recommendations
        report.append("\n🎯 SUMMARY & RECOMMENDATIONS")
        report.append("-" * 40)

        if mlb_results.get('available'):
            report.append("✅ MLB API: Ready for integration")
        else:
            report.append("❌ MLB API: Requires investigation")

        if fantrax_results.get('available'):
            report.append("✅ Fantrax API: Ready for integration")
        else:
            report.append("❌ Fantrax API: Requires investigation")

        if fg_results.get('available'):
            report.append("✅ FanGraphs: Scraping possible with proper rate limiting")
        else:
            report.append("❌ FanGraphs: Site accessibility issues")

        # Errors section
        all_errors = []
        for api_name, api_results in self.results.items():
            if isinstance(api_results, dict) and 'errors' in api_results:
                for error in api_results['errors']:
                    all_errors.append(f"{api_name}: {error}")

        if all_errors:
            report.append("\n❌ ERRORS ENCOUNTERED")
            report.append("-" * 40)
            for error in all_errors:
                report.append(f"  {error}")

        return "\n".join(report)

    def save_results(self, filename: str = "api_validation_results.json"):
        """Save results to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Results saved to {filename}")

def main():
    """Main execution function"""
    print("🚀 Starting API Validation Suite for A Fine Wine Dynasty")
    print("=" * 60)

    suite = APIValidationSuite()

    # Test MLB API
    print("\n📊 Testing MLB Stats API...")
    mlb_results = suite.test_mlb_stats_api()

    # Test Fantrax API
    print("\n⚾ Testing Fantrax API...")
    # Note: To test authenticated endpoints, pass your userSecretId here
    fantrax_results = suite.test_fantrax_api()

    # Test FanGraphs scraping
    print("\n📈 Testing FanGraphs scraping...")
    fangraphs_results = suite.test_fangraphs_scraping()

    # Generate and display report
    print("\n" + "=" * 60)
    print(suite.generate_report())

    # Save results
    suite.save_results()

    return suite.results

if __name__ == "__main__":
    main()