"""
Test MLB Expectation Prediction API
===================================

Tests the prediction API with real prospects from the database.
"""

import asyncio
import asyncpg
import subprocess
import json
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def get_test_prospects():
    """Get sample prospects for testing."""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get a mix of hitters and pitchers with Fangraphs data
        query = """
            SELECT DISTINCT
                p.id,
                p.name,
                p.position,
                CASE
                    WHEN p.position IN ('SP', 'RP', 'LHP', 'RHP') THEN 'pitcher'
                    ELSE 'hitter'
                END as player_type
            FROM prospects p
            WHERE p.fg_player_id IS NOT NULL
            AND p.position IS NOT NULL
            ORDER BY p.id
            LIMIT 20
        """

        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    finally:
        await conn.close()


def test_prediction(prospect_id, year):
    """Test prediction for a single prospect."""
    try:
        # Run prediction script
        result = subprocess.run(
            ['python', 'predict_mlb_expectation.py', '--prospect-id', str(prospect_id), '--year', str(year), '--output', 'json'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            prediction = json.loads(result.stdout)
            return {
                'success': True,
                'prediction': prediction
            }
        else:
            return {
                'success': False,
                'error': result.stderr
            }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Timeout'
        }
    except json.JSONDecodeError:
        return {
            'success': False,
            'error': 'Invalid JSON response',
            'output': result.stdout
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


async def main():
    print("="*80)
    print("TESTING MLB EXPECTATION PREDICTION API")
    print("="*80)

    # Get test prospects
    print("\nFetching test prospects from database...")
    prospects = await get_test_prospects()
    print(f"Found {len(prospects)} prospects to test")

    # Test predictions
    year = 2024
    results = {
        'hitters': {'success': 0, 'failed': 0, 'predictions': []},
        'pitchers': {'success': 0, 'failed': 0, 'predictions': []}
    }

    print(f"\nTesting predictions for year {year}...\n")

    for prospect in prospects[:10]:  # Test first 10
        prospect_id = prospect['id']
        name = prospect['name']
        position = prospect['position']
        player_type = prospect['player_type']

        print(f"Testing: {name} ({position}) [ID: {prospect_id}]")

        result = test_prediction(prospect_id, year)

        if result['success']:
            pred = result['prediction']['prediction']
            label = pred['label']
            confidence = max(pred['probabilities'].values())

            print(f"  [OK] Prediction: {label} ({confidence:.1%} confidence)")

            results[player_type + 's']['success'] += 1
            results[player_type + 's']['predictions'].append({
                'id': prospect_id,
                'name': name,
                'position': position,
                'prediction': label,
                'confidence': confidence
            })
        else:
            print(f"  [FAIL] Failed: {result['error'][:100]}")
            results[player_type + 's']['failed'] += 1

        print()

    # Summary
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)

    total_success = results['hitters']['success'] + results['pitchers']['success']
    total_failed = results['hitters']['failed'] + results['pitchers']['failed']
    total = total_success + total_failed

    print(f"\nOverall Results:")
    print(f"  Total tests: {total}")
    print(f"  Successful: {total_success} ({total_success/total*100:.1f}%)")
    print(f"  Failed: {total_failed} ({total_failed/total*100:.1f}%)")

    print(f"\nHitters:")
    print(f"  Success: {results['hitters']['success']}")
    print(f"  Failed: {results['hitters']['failed']}")

    print(f"\nPitchers:")
    print(f"  Success: {results['pitchers']['success']}")
    print(f"  Failed: {results['pitchers']['failed']}")

    # Show sample predictions
    if results['hitters']['predictions']:
        print(f"\nSample Hitter Predictions:")
        for pred in results['hitters']['predictions'][:3]:
            print(f"  {pred['name']} ({pred['position']}): {pred['prediction']} ({pred['confidence']:.1%})")

    if results['pitchers']['predictions']:
        print(f"\nSample Pitcher Predictions:")
        for pred in results['pitchers']['predictions'][:3]:
            print(f"  {pred['name']} ({pred['position']}): {pred['prediction']} ({pred['confidence']:.1%})")

    print("\n" + "="*80)

    if total_success == total:
        print("SUCCESS: All predictions completed successfully!")
    else:
        print(f"WARNING: {total_failed} predictions failed")

    print("="*80)

    return results


if __name__ == "__main__":
    results = asyncio.run(main())
