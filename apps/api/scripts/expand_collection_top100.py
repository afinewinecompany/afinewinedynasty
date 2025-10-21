"""
Expand collection to all top 100 prospects
Automated script to continue where we left off
"""

import time
from datetime import datetime
from sqlalchemy import create_engine, text
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(f'expand_collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(DB_URL)

# Remaining top 100 prospects to collect
REMAINING_TOP_100 = [
    # Ranks 11-20
    {'rank': 11, 'name': 'Max Clark', 'mlb_id': 703601},
    {'rank': 12, 'name': 'Aidan Miller', 'mlb_id': 805795},
    {'rank': 13, 'name': 'Nolan McLean', 'mlb_id': 690997},
    {'rank': 14, 'name': 'Sal Stewart', 'mlb_id': 701398},
    {'rank': 15, 'name': 'Eduardo Quintero', 'mlb_id': 808234},
    {'rank': 16, 'name': 'Rainiel Rodriguez', 'mlb_id': 823787},
    {'rank': 17, 'name': 'Jett Williams', 'mlb_id': 805802},
    {'rank': 18, 'name': 'Luis Pena', 'mlb_id': 650656},
    {'rank': 19, 'name': 'Edward Florentino', 'mlb_id': 821273},
    {'rank': 20, 'name': 'Payton Tolle', 'mlb_id': 801139},

    # Ranks 21-30
    {'rank': 21, 'name': 'Bubba Chandler', 'mlb_id': 696149},
    {'rank': 22, 'name': 'Trey Yesavage', 'mlb_id': 702056},
    {'rank': 23, 'name': 'Jonah Tong', 'mlb_id': 804636},
    {'rank': 24, 'name': 'Joshua Baez', 'mlb_id': 695491},
    {'rank': 25, 'name': 'Carter Jensen', 'mlb_id': 695600},
    {'rank': 26, 'name': 'Thomas White', 'mlb_id': 806258},
    {'rank': 27, 'name': 'Connelly Early', 'mlb_id': 813349},
    {'rank': 28, 'name': 'Travis Bazzana', 'mlb_id': 683953},
    {'rank': 29, 'name': 'Bryce Rainer', 'mlb_id': 800614},
    {'rank': 30, 'name': 'Lazaro Montes', 'mlb_id': 807718},
]

def check_existing_data(player_id):
    """Check what data already exists for a player"""

    with engine.connect() as conn:
        # Check PBP data
        result = conn.execute(text("""
            SELECT COUNT(*) FROM milb_plate_appearances
            WHERE mlb_player_id = :player_id
            AND season IN (2024, 2025)
        """), {'player_id': player_id})
        pbp_count = result.scalar()

        # Check pitch data
        result = conn.execute(text("""
            SELECT COUNT(*) FROM milb_batter_pitches
            WHERE mlb_batter_id = :player_id
            AND season IN (2024, 2025)
        """), {'player_id': player_id})
        pitch_count = result.scalar()

        return pbp_count, pitch_count

def prioritize_collection():
    """Determine which prospects need collection most urgently"""

    needs_full = []  # No data at all
    needs_pitch = []  # Has PBP but no pitches
    complete = []  # Has both

    for prospect in REMAINING_TOP_100:
        pbp, pitch = check_existing_data(prospect['mlb_id'])

        if pbp == 0 and pitch == 0:
            needs_full.append(prospect)
        elif pbp > 0 and pitch == 0:
            needs_pitch.append(prospect)
        else:
            complete.append(prospect)

    return needs_full, needs_pitch, complete

def main():
    print("=" * 70)
    print("EXPANDING COLLECTION TO TOP 100 PROSPECTS")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    # Analyze current state
    needs_full, needs_pitch, complete = prioritize_collection()

    print(f"\n=== COLLECTION NEEDS ===")
    print(f"Need full collection: {len(needs_full)} prospects")
    print(f"Need pitch data only: {len(needs_pitch)} prospects")
    print(f"Already complete: {len(complete)} prospects")

    # Priority 1: Collect full data for those with nothing
    if needs_full:
        print(f"\n=== PRIORITY 1: FULL COLLECTION NEEDED ===")
        for p in needs_full[:5]:
            print(f"  Rank #{p['rank']}: {p['name']}")

    # Priority 2: Add pitch data for those with PBP
    if needs_pitch:
        print(f"\n=== PRIORITY 2: PITCH DATA NEEDED ===")
        for p in needs_pitch[:5]:
            print(f"  Rank #{p['rank']}: {p['name']}")

    # Show completion
    if complete:
        print(f"\n=== ALREADY COMPLETE ===")
        for p in complete[:5]:
            print(f"  Rank #{p['rank']}: {p['name']}")

    # Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)

    if needs_full:
        print(f"\n1. Run full collection for {len(needs_full)} prospects:")
        print("   python collect_milb_pbp_data.py --seasons 2024 2025")

    if needs_pitch:
        print(f"\n2. Run pitch collection for {len(needs_pitch)} prospects:")
        print("   python collect_pitch_fixed.py")

    print("\n3. Set up automated daily collection:")
    print("   - Use Windows Task Scheduler or cron")
    print("   - Run at 3 AM daily to catch new games")

    # Save priority lists
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if needs_full:
        with open(f'needs_full_collection_{timestamp}.txt', 'w') as f:
            for p in needs_full:
                f.write(f"{p['mlb_id']},  # Rank #{p['rank']}: {p['name']}\n")
        print(f"\nSaved: needs_full_collection_{timestamp}.txt")

    if needs_pitch:
        with open(f'needs_pitch_collection_{timestamp}.txt', 'w') as f:
            for p in needs_pitch:
                f.write(f"{p['mlb_id']},  # Rank #{p['rank']}: {p['name']}\n")
        print(f"\nSaved: needs_pitch_collection_{timestamp}.txt")

if __name__ == "__main__":
    main()