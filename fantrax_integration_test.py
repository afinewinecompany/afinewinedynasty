#!/usr/bin/env python3
"""
Detailed Fantrax API Integration Test
Based on Fantrax API v1.2 Documentation

This script provides detailed testing of ALL Fantrax API endpoints
and validates integration capabilities for dynasty league features.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FantraxAPITester:
    def __init__(self, user_secret_id: Optional[str] = None):
        self.base_url = "https://www.fantrax.com/fxea/general"
        self.user_secret_id = user_secret_id
        self.session = requests.Session()
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'user_secret_provided': user_secret_id is not None,
            'endpoints': {},
            'integration_assessment': {}
        }

    def test_all_endpoints(self) -> Dict[str, Any]:
        """Test all Fantrax API endpoints from the documentation"""

        logger.info("Starting comprehensive Fantrax API testing...")

        # Public endpoints (no auth required)
        self._test_get_player_ids()
        self._test_get_adp()

        # Authenticated endpoints (require userSecretId)
        if self.user_secret_id:
            self._test_get_leagues()
            self._test_league_endpoints()
        else:
            logger.warning("No userSecretId provided - skipping authenticated endpoints")

        # Assess integration capabilities
        self._assess_integration_capabilities()

        return self.results

    def _test_get_player_ids(self):
        """Test getPlayerIds endpoint"""
        logger.info("Testing getPlayerIds endpoint...")

        endpoint_results = {
            'name': 'getPlayerIds',
            'required_auth': False,
            'tests': {}
        }

        # Test MLB players
        try:
            response = self._make_request('getPlayerIds', {'sport': 'MLB'})
            endpoint_results['tests']['mlb_players'] = self._analyze_response(response)

            if response.status_code == 200:
                data = response.json()
                # Analyze player data structure
                if 'players' in data and data['players']:
                    sample_player = data['players'][0]
                    endpoint_results['data_structure'] = {
                        'player_fields': list(sample_player.keys()),
                        'total_players': len(data['players']),
                        'has_prospect_data': any('prospect' in str(key).lower() or 'minor' in str(key).lower()
                                               for key in sample_player.keys())
                    }

        except Exception as e:
            endpoint_results['tests']['mlb_players'] = {'error': str(e)}

        self.results['endpoints']['getPlayerIds'] = endpoint_results

    def _test_get_adp(self):
        """Test getAdp endpoint with various parameters"""
        logger.info("Testing getAdp endpoint...")

        endpoint_results = {
            'name': 'getAdp',
            'required_auth': False,
            'tests': {}
        }

        test_cases = [
            # Basic MLB ADP
            {'sport': 'MLB'},
            # With position filter
            {'sport': 'MLB', 'position': 'OF'},
            # With pagination
            {'sport': 'MLB', 'start': 1, 'limit': 10},
            # Ordered by name
            {'sport': 'MLB', 'order': 'NAME', 'limit': 5}
        ]

        for i, params in enumerate(test_cases):
            test_name = f"test_case_{i+1}"
            try:
                response = self._make_request('getAdp', params)
                result = self._analyze_response(response)
                result['parameters'] = params

                if response.status_code == 200:
                    data = response.json()
                    if 'players' in data and data['players']:
                        sample_player = data['players'][0]
                        result['sample_data'] = {
                            'fields': list(sample_player.keys()),
                            'has_adp': 'adp' in sample_player,
                            'has_position': 'position' in sample_player,
                            'player_count': len(data['players'])
                        }

                endpoint_results['tests'][test_name] = result

            except Exception as e:
                endpoint_results['tests'][test_name] = {'error': str(e), 'parameters': params}

        self.results['endpoints']['getAdp'] = endpoint_results

    def _test_get_leagues(self):
        """Test getLeagues endpoint (requires authentication)"""
        logger.info("Testing getLeagues endpoint...")

        endpoint_results = {
            'name': 'getLeagues',
            'required_auth': True,
            'tests': {}
        }

        if not self.user_secret_id:
            endpoint_results['tests']['auth_test'] = {'error': 'No userSecretId provided'}
            self.results['endpoints']['getLeagues'] = endpoint_results
            return

        try:
            response = self._make_request('getLeagues', {'userSecretId': self.user_secret_id})
            result = self._analyze_response(response)

            if response.status_code == 200:
                data = response.json()
                if 'leagues' in data:
                    result['league_analysis'] = {
                        'total_leagues': len(data['leagues']),
                        'league_types': [],
                        'dynasty_leagues': 0
                    }

                    # Analyze league types and find dynasty leagues
                    for league in data['leagues'][:5]:  # Sample first 5
                        if 'type' in league:
                            result['league_analysis']['league_types'].append(league['type'])
                        if any(dynasty_indicator in str(league).lower()
                               for dynasty_indicator in ['dynasty', 'keeper', 'multi-year']):
                            result['league_analysis']['dynasty_leagues'] += 1

                    # Store league IDs for further testing
                    if data['leagues']:
                        self.sample_league_id = data['leagues'][0].get('id')
                        result['sample_league_id'] = self.sample_league_id

            endpoint_results['tests']['auth_test'] = result

        except Exception as e:
            endpoint_results['tests']['auth_test'] = {'error': str(e)}

        self.results['endpoints']['getLeagues'] = endpoint_results

    def _test_league_endpoints(self):
        """Test league-specific endpoints if we have a league ID"""
        if not hasattr(self, 'sample_league_id') or not self.sample_league_id:
            logger.warning("No league ID available for testing league endpoints")
            return

        league_id = self.sample_league_id
        logger.info(f"Testing league endpoints with league ID: {league_id}")

        # Test getLeagueInfo
        self._test_league_endpoint('getLeagueInfo', league_id)

        # Test getTeamRosters
        self._test_league_endpoint('getTeamRosters', league_id, {'period': 1})

        # Test getStandings
        self._test_league_endpoint('getStandings', league_id)

        # Test getDraftPicks
        self._test_league_endpoint('getDraftPicks', league_id)

        # Test getDraftResults
        self._test_league_endpoint('getDraftResults', league_id)

    def _test_league_endpoint(self, endpoint_name: str, league_id: str, extra_params: Dict = None):
        """Test a specific league endpoint"""
        logger.info(f"Testing {endpoint_name} endpoint...")

        endpoint_results = {
            'name': endpoint_name,
            'required_auth': True,
            'league_specific': True,
            'tests': {}
        }

        try:
            params = {'leagueId': league_id}
            if extra_params:
                params.update(extra_params)

            response = self._make_request(endpoint_name, params)
            result = self._analyze_response(response)
            result['parameters'] = params

            if response.status_code == 200:
                data = response.json()
                result['data_analysis'] = self._analyze_league_data(data, endpoint_name)

            endpoint_results['tests']['main_test'] = result

        except Exception as e:
            endpoint_results['tests']['main_test'] = {'error': str(e)}

        self.results['endpoints'][endpoint_name] = endpoint_results

    def _make_request(self, endpoint: str, params: Dict = None) -> requests.Response:
        """Make API request to Fantrax endpoint"""
        url = f"{self.base_url}/{endpoint}"

        # Try both GET with query params and POST with JSON body
        try:
            # First try GET request
            response = self.session.get(url, params=params, timeout=10)
            return response
        except:
            # If GET fails, try POST with JSON body
            response = self.session.post(url, json=params, timeout=10)
            return response

    def _analyze_response(self, response: requests.Response) -> Dict[str, Any]:
        """Analyze API response"""
        result = {
            'status_code': response.status_code,
            'response_time': response.elapsed.total_seconds(),
            'success': response.status_code == 200,
            'headers': dict(response.headers),
            'content_length': len(response.content)
        }

        if response.status_code == 200:
            try:
                result['json_data'] = True
                data = response.json()
                result['data_keys'] = list(data.keys()) if isinstance(data, dict) else []
            except:
                result['json_data'] = False
                result['content_preview'] = response.text[:200]
        else:
            result['error_content'] = response.text[:200]

        return result

    def _analyze_league_data(self, data: Dict, endpoint_name: str) -> Dict[str, Any]:
        """Analyze league-specific data structure"""
        analysis = {
            'data_type': type(data).__name__,
            'main_keys': list(data.keys()) if isinstance(data, dict) else []
        }

        # Endpoint-specific analysis
        if endpoint_name == 'getLeagueInfo':
            analysis['league_info'] = {
                'has_teams': 'teams' in data,
                'has_settings': 'settings' in data or 'config' in data,
                'has_players': 'players' in data or 'playerPool' in data
            }

        elif endpoint_name == 'getTeamRosters':
            if 'rosters' in data:
                analysis['roster_info'] = {
                    'team_count': len(data['rosters']),
                    'has_salary_data': any('salary' in str(roster).lower()
                                         for roster in data['rosters'][:3]),
                    'has_contract_data': any('contract' in str(roster).lower()
                                           for roster in data['rosters'][:3])
                }

        elif endpoint_name == 'getStandings':
            if 'standings' in data:
                analysis['standings_info'] = {
                    'team_count': len(data['standings']),
                    'has_wins_losses': any('wins' in str(team).lower() or 'losses' in str(team).lower()
                                         for team in data['standings'][:3])
                }

        return analysis

    def _assess_integration_capabilities(self):
        """Assess Fantrax integration capabilities for dynasty features"""
        logger.info("Assessing integration capabilities...")

        assessment = {
            'dynasty_league_support': False,
            'roster_integration': False,
            'draft_integration': False,
            'player_identification': False,
            'real_time_updates': False,
            'api_reliability': 0,
            'missing_features': [],
            'integration_readiness': 'Unknown'
        }

        # Check if we can get player IDs (essential for integration)
        player_ids_result = self.results['endpoints'].get('getPlayerIds', {})
        if player_ids_result.get('tests', {}).get('mlb_players', {}).get('success'):
            assessment['player_identification'] = True

        # Check if we can get ADP data
        adp_result = self.results['endpoints'].get('getAdp', {})
        if any(test.get('success') for test in adp_result.get('tests', {}).values()):
            assessment['dynasty_league_support'] = True

        # Check authenticated endpoints
        if self.user_secret_id:
            # Check league access
            leagues_result = self.results['endpoints'].get('getLeagues', {})
            if leagues_result.get('tests', {}).get('auth_test', {}).get('success'):
                assessment['roster_integration'] = True

            # Check roster access
            if 'getTeamRosters' in self.results['endpoints']:
                roster_result = self.results['endpoints']['getTeamRosters']
                if roster_result.get('tests', {}).get('main_test', {}).get('success'):
                    assessment['roster_integration'] = True

            # Check draft integration
            if 'getDraftPicks' in self.results['endpoints'] or 'getDraftResults' in self.results['endpoints']:
                assessment['draft_integration'] = True

        # Calculate API reliability based on successful endpoints
        total_tests = 0
        successful_tests = 0

        for endpoint_name, endpoint_data in self.results['endpoints'].items():
            for test_name, test_data in endpoint_data.get('tests', {}).items():
                total_tests += 1
                if test_data.get('success'):
                    successful_tests += 1

        if total_tests > 0:
            assessment['api_reliability'] = (successful_tests / total_tests) * 100

        # Determine integration readiness
        if assessment['player_identification'] and assessment['roster_integration']:
            assessment['integration_readiness'] = 'Ready'
        elif assessment['player_identification']:
            assessment['integration_readiness'] = 'Partial'
        else:
            assessment['integration_readiness'] = 'Not Ready'

        # Identify missing features
        if not assessment['player_identification']:
            assessment['missing_features'].append('Player ID mapping')
        if not assessment['roster_integration']:
            assessment['missing_features'].append('Roster access')
        if not assessment['draft_integration']:
            assessment['missing_features'].append('Draft information')

        self.results['integration_assessment'] = assessment

    def generate_fantrax_report(self) -> str:
        """Generate detailed Fantrax integration report"""
        report = []
        report.append("=" * 80)
        report.append("FANTRAX API INTEGRATION ASSESSMENT REPORT")
        report.append(f"Generated: {self.results['timestamp']}")
        report.append(f"Authentication: {'✅ PROVIDED' if self.results['user_secret_provided'] else '❌ NOT PROVIDED'}")
        report.append("=" * 80)

        # Endpoint Results Summary
        report.append("\n📊 ENDPOINT TESTING RESULTS")
        report.append("-" * 50)

        for endpoint_name, endpoint_data in self.results['endpoints'].items():
            auth_required = "🔐" if endpoint_data.get('required_auth') else "🌐"
            report.append(f"\n{auth_required} {endpoint_name.upper()}")

            for test_name, test_data in endpoint_data.get('tests', {}).items():
                if test_data.get('success'):
                    status = "✅ PASS"
                    details = f"({test_data.get('response_time', 0):.2f}s)"
                else:
                    status = "❌ FAIL"
                    details = f"({test_data.get('status_code', 'Unknown')})"

                report.append(f"  {test_name}: {status} {details}")

        # Integration Assessment
        assessment = self.results.get('integration_assessment', {})
        report.append(f"\n🎯 DYNASTY INTEGRATION READINESS")
        report.append("-" * 50)
        report.append(f"Overall Status: {assessment.get('integration_readiness', 'Unknown')}")
        report.append(f"API Reliability: {assessment.get('api_reliability', 0):.1f}%")

        capabilities = [
            ('Player Identification', assessment.get('player_identification')),
            ('Roster Integration', assessment.get('roster_integration')),
            ('Draft Integration', assessment.get('draft_integration')),
            ('Dynasty League Support', assessment.get('dynasty_league_support'))
        ]

        report.append("\nCapabilities:")
        for capability, supported in capabilities:
            status = "✅ SUPPORTED" if supported else "❌ NOT AVAILABLE"
            report.append(f"  {capability}: {status}")

        if assessment.get('missing_features'):
            report.append(f"\nMissing Features:")
            for feature in assessment['missing_features']:
                report.append(f"  - {feature}")

        # Recommendations
        report.append(f"\n💡 RECOMMENDATIONS")
        report.append("-" * 50)

        if assessment.get('integration_readiness') == 'Ready':
            report.append("✅ Fantrax integration is ready for implementation")
            report.append("✅ All core dynasty features can be supported")
            report.append("✅ Proceed with Story 4.3 development")
        elif assessment.get('integration_readiness') == 'Partial':
            report.append("⚠️ Partial integration possible")
            report.append("⚠️ Consider implementing core features first")
            report.append("⚠️ May need fallback for missing capabilities")
        else:
            report.append("❌ Integration not ready")
            report.append("❌ Consider alternative approaches")
            report.append("❌ Manual CSV import may be required")

        return "\n".join(report)

def main():
    """Main function for Fantrax testing"""
    print("🚀 Fantrax API Integration Tester")
    print("Based on Fantrax API v1.2 Documentation")
    print("=" * 60)

    # Prompt for user secret ID
    print("\n📋 To test authenticated endpoints, you need your Fantrax User Secret ID")
    print("   Find this on your Fantrax User Profile screen")
    print("   Leave blank to test only public endpoints")

    user_secret_id = input("\nEnter your Fantrax User Secret ID (or press Enter to skip): ").strip()
    if not user_secret_id:
        user_secret_id = None

    # Run tests
    tester = FantraxAPITester(user_secret_id)
    results = tester.test_all_endpoints()

    # Display results
    print("\n" + "=" * 60)
    print(tester.generate_fantrax_report())

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fantrax_api_results_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Detailed results saved to: {filename}")

    return results

if __name__ == "__main__":
    main()