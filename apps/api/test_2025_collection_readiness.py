"""Test if 2025 collection can run and what it would collect"""
import asyncio
import aiohttp
import sys
from sqlalchemy import text
from app.db.database import engine

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


async def test_collection():
    print("="*70)
    print("2025 MiLB COLLECTION READINESS TEST")
    print("="*70)
    print()

    # Test API access
    print("1. Testing MLB Stats API Access...")
    print("-" * 50)
    async with aiohttp.ClientSession() as session:
        # Test getting AAA teams for 2025
        url = "https://statsapi.mlb.com/api/v1/teams?sportId=11&season=2025"
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    teams = data.get('teams', [])
                    print("[OK] API accessible")
                    print(f"[OK] Found {len(teams)} AAA teams for 2025")

                    # Filter professional teams
                    pro_teams = [t for t in teams if t.get('parentOrgId')]
                    print(f"[OK] {len(pro_teams)} professional AAA teams")
                else:
                    print(f"[ERROR] API returned status {response.status}")
        except Exception as e:
            print(f"[ERROR] API error: {e}")
    print()

    # Check current database state
    print("2. Current 2025 Database State...")
    print("-" * 50)
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as games,
                MIN(game_date) as first_date,
                MAX(game_date) as last_date
            FROM milb_game_logs
            WHERE season = 2025 AND mlb_player_id IS NOT NULL
        """))
        row = result.fetchone()
        print(f"Current data: {row[0]} players, {row[1]} games")
        print(f"Date range: {row[2]} to {row[3]}")

        # Check for NULL player IDs
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM milb_game_logs WHERE season = 2025 AND mlb_player_id IS NULL
        """))
        null_count = result.fetchone()[0]
        if null_count > 0:
            print(f"[WARNING] {null_count} records with NULL mlb_player_id (deleted data)")
        else:
            print("[OK] No NULL player IDs found")
    print()

    # Check for collection script
    print("3. Collection Script Status...")
    print("-" * 50)
    from pathlib import Path
    script_v1 = Path("scripts/collect_all_milb_gamelog.py")
    script_v2 = Path("scripts/collect_all_milb_gamelog_v2.py")

    if script_v2.exists():
        print(f"[OK] V2 script found: {script_v2}")
        print("  Features: concurrent processing, resume capability, progress tracking")
    elif script_v1.exists():
        print(f"[WARNING] Only V1 script found: {script_v1}")
        print("  Recommend using V2 for better performance")
    else:
        print("[ERROR] No collection script found!")
    print()

    # Check for resume file
    print("4. Resume Capability...")
    print("-" * 50)
    resume_file = Path("resume_2025.json")
    if resume_file.exists():
        import json
        with open(resume_file) as f:
            state = json.load(f)
        print("[OK] Resume file exists")
        print(f"  Processed: {len(state.get('processed', []))} players")
        print(f"  Failed: {len(state.get('failed', []))} players")
        print(f"  Last run: {state.get('timestamp', 'unknown')}")
    else:
        print("[OK] No resume file (fresh start)")
    print()

    # Recommendation
    print("="*70)
    print("RECOMMENDATION")
    print("="*70)

    if row[0] < 100:  # Less than 100 players means incomplete
        print("[WARNING] INCOMPLETE DATA DETECTED")
        print()
        print(f"Current state shows only {row[0]} players with {row[1]} games.")
        print("Normal 2025 season should have ~4,000+ players.")
        print()
        print("NEXT STEPS:")
        print("1. Run the V2 collection script for 2025:")
        print("   cd apps/api")
        print("   python scripts/collect_all_milb_gamelog_v2.py --season 2025 --levels AAA AA A+")
        print()
        print("2. Expected results:")
        print("   - 4,000+ players discovered")
        print("   - 150,000+ game records")
        print("   - 3-6 hours collection time")
        print()
        print("3. Monitor progress:")
        print("   python check_2025_collection_status.py")
    else:
        print("[OK] Data appears complete")
        print(f"  {row[0]} players is within normal range")


if __name__ == "__main__":
    asyncio.run(test_collection())
