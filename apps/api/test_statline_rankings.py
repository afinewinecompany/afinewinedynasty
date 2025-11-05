"""
Test script for Statline Rankings API

Tests the new Statline ranking endpoint with various parameters.
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Optional, Dict, Any


class StatlineRankingTester:
    """Test client for Statline rankings API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_statline_rankings(
        self,
        level: Optional[str] = None,
        min_pa: int = 100,
        season: int = 2025,
        include_pitch_data: bool = True
    ) -> Dict[str, Any]:
        """Test the statline rankings endpoint."""

        params = {
            "min_pa": min_pa,
            "season": season,
            "include_pitch_data": str(include_pitch_data).lower()
        }

        if level:
            params["level"] = level

        url = f"{self.base_url}/api/v1/prospects/rankings/statline"

        print(f"\nTesting Statline Rankings:")
        print(f"  URL: {url}")
        print(f"  Params: {params}")

        try:
            async with self.session.get(url, params=params) as response:
                print(f"  Status: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    return self._process_results(data)
                else:
                    error_text = await response.text()
                    print(f"  Error: {error_text}")
                    return {"error": error_text, "status": response.status}

        except Exception as e:
            print(f"  Exception: {str(e)}")
            return {"error": str(e)}

    def _process_results(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and display ranking results."""

        rankings = data.get("rankings", [])
        metadata = data.get("metadata", {})

        print(f"\n  === STATLINE RANKINGS RESULTS ===")
        print(f"  Total Players: {metadata.get('total_players', 0)}")
        print(f"  Level: {metadata.get('level', 'all')}")
        print(f"  Season: {metadata.get('season')}")
        print(f"  Min PAs: {metadata.get('min_plate_appearances')}")
        print(f"  Includes Pitch Data: {metadata.get('includes_pitch_data')}")

        if rankings:
            print(f"\n  Top 10 Players:")
            print(f"  {'Rank':<6} {'Name':<25} {'Age':<4} {'Level':<6} {'AVG':<6} {'OBP':<6} {'SLG':<6} {'Score':<6}")
            print(f"  {'-'*6} {'-'*25} {'-'*4} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")

            for player in rankings[:10]:
                name = player.get('name', 'Unknown')[:24]
                age = player.get('age', 0)
                level = player.get('level', 'N/A')
                avg = player.get('batting_avg', 0)
                obp = player.get('on_base_pct', 0)
                slg = player.get('slugging_pct', 0)
                score = player.get('adjusted_percentile', 0)

                print(f"  {player['rank']:<6} {name:<25} {age:<4} {level:<6} "
                      f"{avg:.3f} {obp:.3f} {slg:.3f} {score:>5.0f}%")

                # Show skill scores
                if 'skill_scores' in player and player['skill_scores']:
                    skill_line = "    Skills: "
                    for skill_name, skill_data in player['skill_scores'].items():
                        percentile = skill_data.get('percentile', 0)
                        display_name = skill_data.get('display_name', skill_name)
                        skill_line += f"{display_name}: {percentile:.0f}% | "
                    print(skill_line[:-3])  # Remove trailing separator

                # Show age adjustment
                age_adj = player.get('age_adjustment', 0)
                if abs(age_adj) > 0.01:
                    adj_type = "younger" if age_adj < 0 else "older"
                    print(f"    Age Adjustment: {age_adj:+.3f} ({adj_type} than average)")

        return data

    async def run_comprehensive_tests(self):
        """Run a comprehensive suite of tests."""

        print("\n" + "="*60)
        print("STATLINE RANKINGS COMPREHENSIVE TEST SUITE")
        print("="*60)

        # Test 1: All levels with default parameters
        print("\n1. Testing all levels with default parameters...")
        await self.test_statline_rankings()

        # Test 2: AAA level only
        print("\n2. Testing AAA level only...")
        await self.test_statline_rankings(level="AAA")

        # Test 3: AA level with higher PA threshold
        print("\n3. Testing AA level with 200 PA minimum...")
        await self.test_statline_rankings(level="AA", min_pa=200)

        # Test 4: Without pitch data
        print("\n4. Testing without pitch data...")
        await self.test_statline_rankings(include_pitch_data=False)

        # Test 5: Low-A with minimal PA requirement
        print("\n5. Testing Low-A with 50 PA minimum...")
        await self.test_statline_rankings(level="A", min_pa=50)

        print("\n" + "="*60)
        print("TEST SUITE COMPLETE")
        print("="*60)


async def main():
    """Main test runner."""

    async with StatlineRankingTester() as tester:
        await tester.run_comprehensive_tests()


if __name__ == "__main__":
    print(f"Starting Statline Rankings Test at {datetime.now()}")
    asyncio.run(main())