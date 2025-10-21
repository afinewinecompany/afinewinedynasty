"""Test the composite rankings API endpoint."""

import asyncio
import httpx

API_BASE_URL = "http://localhost:8000"


async def test_composite_rankings_endpoint():
    """Test the /v1/prospects/composite-rankings endpoint."""

    print("\n" + "=" * 80)
    print("TESTING COMPOSITE RANKINGS API ENDPOINT")
    print("=" * 80 + "\n")

    async with httpx.AsyncClient() as client:
        # Test 1: Get first page (default)
        print("[TEST 1] GET /v1/prospects/composite-rankings (page 1, default)")
        print("-" * 80)

        try:
            response = await client.get(
                f"{API_BASE_URL}/v1/prospects/composite-rankings",
                params={"page": 1, "page_size": 10}
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                print(f"Total prospects: {data['total']}")
                print(f"Page: {data['page']}/{data['total_pages']}")
                print(f"Showing: {len(data['prospects'])} prospects")
                print(f"Generated at: {data['generated_at']}")
                print()

                # Display top 5
                print("Top 5 Prospects:")
                print(f"{'Rank':<5} {'Name':<25} {'Pos':<5} {'FV':<6} {'Comp':<6} {'Adj':<6} {'Tier'}")
                print("-" * 80)

                for p in data['prospects'][:5]:
                    print(f"#{p['rank']:<4} {p['name'][:24]:<25} {p['position']:<5} "
                          f"{p['base_fv']:<6.1f} {p['composite_score']:<6.1f} "
                          f"{p['total_adjustment']:+5.1f}  {p['tier_label']}")

                print()
            else:
                print(f"[ERROR] {response.status_code}: {response.text}")
                print()

        except Exception as e:
            print(f"[ERROR] {e}\n")

        # Test 2: Filter by position (SS)
        print("[TEST 2] Filter by position: SS")
        print("-" * 80)

        try:
            response = await client.get(
                f"{API_BASE_URL}/v1/prospects/composite-rankings",
                params={"position": "SS", "page_size": 5}
            )

            if response.status_code == 200:
                data = response.json()
                print(f"Found {data['total']} shortstops")
                print()

                for p in data['prospects']:
                    print(f"#{p['rank']} {p['name']} - FV: {p['base_fv']}, Composite: {p['composite_score']}")

                print()
            else:
                print(f"[ERROR] {response.status_code}\n")

        except Exception as e:
            print(f"[ERROR] {e}\n")

        # Test 3: Check response model completeness
        print("[TEST 3] Response Model Validation")
        print("-" * 80)

        try:
            response = await client.get(
                f"{API_BASE_URL}/v1/prospects/composite-rankings",
                params={"page_size": 1}
            )

            if response.status_code == 200:
                data = response.json()
                prospect = data['prospects'][0]

                required_fields = [
                    'rank', 'prospect_id', 'name', 'position', 'composite_score',
                    'base_fv', 'performance_modifier', 'trend_adjustment',
                    'age_adjustment', 'total_adjustment', 'tool_grades', 'tier'
                ]

                missing = [f for f in required_fields if f not in prospect]

                if missing:
                    print(f"[WARN] Missing fields: {missing}")
                else:
                    print("[OK] All required fields present")

                print()
                print("Sample prospect structure:")
                print(f"  Rank: {prospect['rank']}")
                print(f"  Name: {prospect['name']}")
                print(f"  Base FV: {prospect['base_fv']}")
                print(f"  Composite: {prospect['composite_score']}")
                print(f"  Adjustments:")
                print(f"    Performance: {prospect['performance_modifier']:+.1f}")
                print(f"    Trend: {prospect['trend_adjustment']:+.1f}")
                print(f"    Age: {prospect['age_adjustment']:+.1f}")
                print(f"    Total: {prospect['total_adjustment']:+.1f}")
                print(f"  Tier: {prospect['tier']} - {prospect['tier_label']}")
                print()

        except Exception as e:
            print(f"[ERROR] {e}\n")

    print("=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print("\nMake sure the API server is running on http://localhost:8000")
    print("Run: uvicorn app.main:app --reload\n")

    try:
        asyncio.run(test_composite_rankings_endpoint())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
