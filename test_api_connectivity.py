#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple External API Connectivity Test
Tests if external APIs are reachable and returning data
"""

import urllib.request
import urllib.error
import json
import sys
import io
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def test_mlb_stats_api():
    """Test MLB Stats API connectivity"""
    print("=" * 60)
    print("Testing MLB Stats API")
    print("=" * 60)

    base_url = "https://statsapi.mlb.com/api/v1"
    test_endpoints = [
        ("/sports", "Get sports list"),
        ("/teams?sportId=1", "Get MLB teams"),
    ]

    results = []
    for endpoint, description in test_endpoints:
        url = f"{base_url}{endpoint}"
        print(f"\n Testing: {description}")
        print(f"   URL: {url}")

        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'AFineWineDynasty/1.0',
                    'Accept': 'application/json'
                }
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    print(f"   ✅ SUCCESS - Status: {response.status}")
                    print(f"   Response keys: {list(data.keys())}")
                    results.append({"endpoint": endpoint, "status": "success", "code": 200})
                else:
                    print(f"   ❌ FAILED - Status: {response.status}")
                    results.append({"endpoint": endpoint, "status": "failed", "code": response.status})

        except urllib.error.HTTPError as e:
            print(f"   ❌ HTTP ERROR - Status: {e.code}")
            print(f"   Error: {e.reason}")
            results.append({"endpoint": endpoint, "status": "error", "code": e.code})
        except urllib.error.URLError as e:
            print(f"   ❌ CONNECTION ERROR")
            print(f"   Error: {e.reason}")
            results.append({"endpoint": endpoint, "status": "connection_error", "error": str(e.reason)})
        except Exception as e:
            print(f"   ❌ UNEXPECTED ERROR")
            print(f"   Error: {str(e)}")
            results.append({"endpoint": endpoint, "status": "unexpected_error", "error": str(e)})

    return results

def test_fangraphs_connectivity():
    """Test FanGraphs website connectivity"""
    print("\n" + "=" * 60)
    print("Testing FanGraphs Connectivity")
    print("=" * 60)

    url = "https://www.fangraphs.com"
    print(f"\n Testing: FanGraphs homepage")
    print(f"   URL: {url}")

    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'A Fine Wine Dynasty Bot 1.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                content = response.read().decode('utf-8')
                print(f"   ✅ SUCCESS - Status: {response.status}")
                print(f"   Content length: {len(content)} bytes")
                print(f"   Site is reachable")
                return {"status": "success", "code": 200}
            else:
                print(f"   ❌ FAILED - Status: {response.status}")
                return {"status": "failed", "code": response.status}

    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP ERROR - Status: {e.code}")
        print(f"   Error: {e.reason}")
        return {"status": "error", "code": e.code}
    except urllib.error.URLError as e:
        print(f"   ❌ CONNECTION ERROR")
        print(f"   Error: {e.reason}")
        return {"status": "connection_error", "error": str(e.reason)}
    except Exception as e:
        print(f"   ❌ UNEXPECTED ERROR")
        print(f"   Error: {str(e)}")
        return {"status": "unexpected_error", "error": str(e)}

def test_fantrax_api():
    """Test Fantrax API connectivity (public endpoints)"""
    print("\n" + "=" * 60)
    print("Testing Fantrax API")
    print("=" * 60)

    # Fantrax API v1.2 base URL
    base_url = "https://www.fantrax.com/fxea/general"

    # Test public endpoint that doesn't require auth
    endpoint = "/getPlayerIds"
    url = f"{base_url}{endpoint}"
    params = "?sport=MLB"
    full_url = url + params

    print(f"\n Testing: Get Player IDs (public endpoint)")
    print(f"   URL: {full_url}")

    try:
        req = urllib.request.Request(
            full_url,
            headers={
                'User-Agent': 'AFineWineDynasty/1.0',
                'Accept': 'application/json'
            }
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                try:
                    data = json.loads(response.read().decode('utf-8'))
                    print(f"   ✅ SUCCESS - Status: {response.status}")
                    print(f"   API is responding")
                    print(f"   Response keys: {list(data.keys())}")

                    # Check if we got player data
                    if 'players' in data:
                        print(f"   Player count in response: {len(data.get('players', []))}")

                    return {"status": "success", "code": 200, "has_data": bool(data)}
                except json.JSONDecodeError:
                    # Not JSON, might be HTML
                    print(f"   ⚠️  Response is not JSON (might be HTML)")
                    return {"status": "non_json", "code": 200}
            else:
                print(f"   ❌ FAILED - Status: {response.status}")
                return {"status": "failed", "code": response.status}

    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP ERROR - Status: {e.code}")
        print(f"   Error: {e.reason}")
        print(f"   Note: Fantrax API may require different authentication method")
        return {"status": "error", "code": e.code}
    except urllib.error.URLError as e:
        print(f"   ❌ CONNECTION ERROR")
        print(f"   Error: {e.reason}")
        return {"status": "connection_error", "error": str(e.reason)}
    except Exception as e:
        print(f"   ❌ UNEXPECTED ERROR")
        print(f"   Error: {str(e)}")
        return {"status": "unexpected_error", "error": str(e)}

def generate_report(mlb_results, fangraphs_result, fantrax_result):
    """Generate summary report"""
    print("\n" + "=" * 60)
    print("API CONNECTIVITY SUMMARY REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    print("=" * 60)

    # MLB Stats API
    mlb_success = sum(1 for r in mlb_results if r.get("status") == "success")
    mlb_total = len(mlb_results)
    print(f"\n[*] MLB Stats API: {mlb_success}/{mlb_total} endpoints successful")
    if mlb_success == mlb_total:
        print("   ✅ ALL TESTS PASSED - API is working and returning data")
    elif mlb_success > 0:
        print("   ⚠️  PARTIAL SUCCESS - Some endpoints working")
    else:
        print("   ❌ ALL TESTS FAILED - API not accessible")

    # FanGraphs
    print(f"\n[*] FanGraphs: {fangraphs_result.get('status', 'unknown')}")
    if fangraphs_result.get("status") == "success":
        print("   ✅ Website is accessible for scraping")
        print("   ⚠️  Note: Rate limiting (1 req/sec) is implemented in code")
    else:
        print("   ❌ Website not accessible")

    # Fantrax
    print(f"\n[*] Fantrax API: {fantrax_result.get('status', 'unknown')}")
    if fantrax_result.get("status") == "success":
        print("   ✅ API is accessible and returning data")
    elif fantrax_result.get("code") == 200:
        print("   ⚠️  API responded but format may be different than expected")
    else:
        print("   ❌ API not accessible")
        print("   ⚠️  Note: OAuth endpoints require FANTRAX_CLIENT_ID and FANTRAX_CLIENT_SECRET")

    # Overall Assessment
    print("\n" + "=" * 60)
    print(">> OVERALL ASSESSMENT")
    print("=" * 60)

    working_apis = []
    if mlb_success > 0:
        working_apis.append("MLB Stats API")
    if fangraphs_result.get("status") == "success":
        working_apis.append("FanGraphs")
    if fantrax_result.get("status") in ["success", "non_json"]:
        working_apis.append("Fantrax")

    if len(working_apis) == 3:
        print("✅ ALL EXTERNAL APIS ARE ACCESSIBLE")
        print("\nRecommendations:")
        print("  1. ✅ MLB Stats API is working - can fetch real data")
        print("  2. ✅ FanGraphs is accessible - scraping can work with rate limiting")
        print("  3. ⚠️  Fantrax requires OAuth credentials to be set in .env file:")
        print("        FANTRAX_CLIENT_ID=<your_client_id>")
        print("        FANTRAX_CLIENT_SECRET=<your_client_secret>")
    elif len(working_apis) > 0:
        print(f"⚠️  PARTIAL CONNECTIVITY: {', '.join(working_apis)} accessible")
        print(f"\nNot working: {', '.join(['MLB Stats API', 'FanGraphs', 'Fantrax'] - set(working_apis))}")
    else:
        print("❌ NO EXTERNAL APIS ARE ACCESSIBLE")
        print("\nPossible causes:")
        print("  - Internet connectivity issues")
        print("  - Firewall blocking outbound connections")
        print("  - APIs temporarily down")

    print("\n" + "=" * 60)

def main():
    """Main test runner"""
    print("\n>> External API Connectivity Test")
    print("Testing all external APIs used by the application\n")

    # Run tests
    mlb_results = test_mlb_stats_api()
    fangraphs_result = test_fangraphs_connectivity()
    fantrax_result = test_fantrax_api()

    # Generate report
    generate_report(mlb_results, fangraphs_result, fantrax_result)

    # Return exit code
    all_success = (
        all(r.get("status") == "success" for r in mlb_results) and
        fangraphs_result.get("status") == "success" and
        fantrax_result.get("status") in ["success", "non_json"]
    )

    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())
