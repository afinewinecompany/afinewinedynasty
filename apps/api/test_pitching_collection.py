"""
Quick test script to verify pitching data collection works for a known pitcher.

Tests with a professional MiLB pitcher (not college).
"""

import asyncio
import aiohttp
from datetime import datetime


async def test_pitcher_data():
    """Test fetching pitching data for a professional MiLB pitcher."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"
    # Using Paul Skenes (ID 809261) - professional MiLB/MLB pitcher
    player_id = 809261
    season = 2024
    sport_id = 11  # AAA level

    async with aiohttp.ClientSession() as session:
        # Test hitting data (should exist but minimal for pitchers)
        hitting_url = f"{BASE_URL}/people/{player_id}/stats?stats=gameLog&season={season}&group=hitting&sportId={sport_id}"
        print(f"\nFetching HITTING data:")
        print(f"URL: {hitting_url}")

        async with session.get(hitting_url) as response:
            if response.status == 200:
                data = await response.json()
                stats = data.get('stats', [])
                if stats:
                    splits = stats[0].get('splits', [])
                    print(f"[OK] Found {len(splits)} hitting game logs")
                    if splits:
                        sample = splits[0]
                        print(f"  Sample game: {sample.get('date')}")
                        print(f"  Stats: {sample.get('stat', {})}")
                else:
                    print("[OK] No hitting stats found (expected for pitcher)")
            else:
                print(f"[ERROR] HTTP {response.status}")

        # Test pitching data (should have substantial data)
        pitching_url = f"{BASE_URL}/people/{player_id}/stats?stats=gameLog&season={season}&group=pitching&sportId={sport_id}"
        print(f"\nFetching PITCHING data:")
        print(f"URL: {pitching_url}")

        async with session.get(pitching_url) as response:
            if response.status == 200:
                data = await response.json()
                stats = data.get('stats', [])
                if stats:
                    splits = stats[0].get('splits', [])
                    print(f"[OK] Found {len(splits)} pitching game logs")
                    if splits:
                        sample = splits[0]
                        stat = sample.get('stat', {})
                        print(f"  Sample game: {sample.get('date')}")
                        print(f"  IP: {stat.get('inningsPitched', 0)}, ERA: {stat.get('era', 0)}, "
                              f"K: {stat.get('strikeOuts', 0)}, BB: {stat.get('baseOnBalls', 0)}")

                        # Show all available pitching stat fields
                        print(f"\n  All pitching fields available:")
                        for key, value in stat.items():
                            if value is not None and value != 0:
                                print(f"    {key}: {value}")
                else:
                    print("[ERROR] No pitching stats found")
            else:
                print(f"[ERROR] HTTP {response.status}")

        # Test at different levels
        print(f"\n\nTesting across all MiLB levels:")
        sport_ids = {
            11: "AAA",
            12: "AA",
            13: "A+",
            14: "A",
            15: "Rookie",
            16: "Rookie+"
        }

        for sid, level_name in sport_ids.items():
            url = f"{BASE_URL}/people/{player_id}/stats?stats=gameLog&season={season}&group=pitching&sportId={sid}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    stats = data.get('stats', [])
                    if stats:
                        splits = stats[0].get('splits', [])
                        if splits:
                            total_ip = sum(float(s.get('stat', {}).get('inningsPitched', 0)) for s in splits)
                            print(f"  {level_name:8s}: {len(splits):2d} games, {total_ip:.1f} IP")


if __name__ == "__main__":
    print("="*80)
    print("Testing Pitching Data Collection")
    print("Player: Paul Skenes (ID 809261) - Professional MiLB/MLB Pitcher")
    print("="*80)
    asyncio.run(test_pitcher_data())
    print("\n" + "="*80)
    print("Test Complete!")
    print("="*80)
