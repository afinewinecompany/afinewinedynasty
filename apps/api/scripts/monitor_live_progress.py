"""
Monitor live collection progress
Shows real-time stats on what's being collected
"""

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(DB_URL)

def monitor_progress():
    print("=" * 70)
    print("LIVE COLLECTION MONITORING")
    print(f"Time: {datetime.now()}")
    print("=" * 70)

    with engine.connect() as conn:
        # Check last 10 minutes of activity
        cutoff = datetime.now() - timedelta(minutes=10)

        # Recent PBP additions
        result = conn.execute(text("""
            SELECT
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(DISTINCT game_pk) as games,
                COUNT(*) as records,
                MIN(created_at) as first_record,
                MAX(created_at) as last_record
            FROM milb_plate_appearances
            WHERE created_at > :cutoff
        """), {'cutoff': cutoff})

        row = result.fetchone()
        print("\n=== LAST 10 MINUTES - PLAY-BY-PLAY ===")
        if row[2] > 0:
            print(f"Players collected: {row[0]}")
            print(f"Games processed: {row[1]}")
            print(f"Records added: {row[2]}")
            print(f"Time span: {row[3]} to {row[4]}")
        else:
            print("No recent PBP activity")

        # Recent pitch additions
        result = conn.execute(text("""
            SELECT
                COUNT(DISTINCT mlb_batter_id) as batters,
                COUNT(DISTINCT game_pk) as games,
                COUNT(*) as pitches,
                MAX(created_at) as last_record
            FROM milb_batter_pitches
            WHERE created_at > :cutoff
        """), {'cutoff': cutoff})

        row = result.fetchone()
        print("\n=== LAST 10 MINUTES - PITCHES ===")
        if row[2] > 0:
            print(f"Batters collected: {row[0]}")
            print(f"Games with pitches: {row[1]}")
            print(f"Pitches added: {row[2]}")
            print(f"Last record: {row[3]}")
        else:
            print("No recent pitch activity")

        # Check specific prospects progress
        print("\n=== TOP 30 CURRENT STATUS ===")

        key_prospects = [
            (690997, 'Nolan McLean', 13),
            (801139, 'Payton Tolle', 20),
            (696149, 'Bubba Chandler', 21),
            (695600, 'Carter Jensen', 25),
            (701807, 'Carson Benge', 31),
            (691725, 'Andrew Painter', 37),
        ]

        for mlb_id, name, rank in key_prospects:
            result = conn.execute(text("""
                SELECT
                    COUNT(DISTINCT pa.game_pk) as pbp_games,
                    COUNT(DISTINCT bp.game_pk) as pitch_games,
                    MAX(pa.created_at) as last_pbp,
                    MAX(bp.created_at) as last_pitch
                FROM prospects p
                LEFT JOIN milb_plate_appearances pa ON p.mlb_player_id::text = pa.mlb_player_id::text
                    AND pa.season IN (2024, 2025)
                LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::text = bp.mlb_batter_id::text
                    AND bp.season IN (2024, 2025)
                WHERE p.mlb_player_id = :player_id
                GROUP BY p.mlb_player_id
            """), {'player_id': str(mlb_id)})

            row = result.fetchone()
            if row:
                status = "✓ COMPLETE" if row[0] and row[1] else "→ IN PROGRESS" if row[0] or row[1] else "○ PENDING"
                print(f"Rank #{rank:2}: {name:20} - PBP:{row[0] or 0:3} Pitch:{row[1] or 0:3} {status}")

        # Overall totals today
        result = conn.execute(text("""
            SELECT
                'PBP' as type,
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as records
            FROM milb_plate_appearances
            WHERE created_at::date = CURRENT_DATE
            UNION ALL
            SELECT
                'Pitch' as type,
                COUNT(DISTINCT mlb_batter_id) as players,
                COUNT(*) as records
            FROM milb_batter_pitches
            WHERE created_at::date = CURRENT_DATE
        """))

        print("\n=== TODAY'S TOTALS ===")
        for row in result:
            print(f"{row[0]}: {row[1]} players, {row[2]:,} records")

        # Collection rate
        result = conn.execute(text("""
            SELECT
                COUNT(*) as records_last_minute
            FROM milb_plate_appearances
            WHERE created_at > NOW() - INTERVAL '1 minute'
        """))

        rate = result.scalar()
        print(f"\nCollection rate: {rate} records/minute")

if __name__ == "__main__":
    monitor_progress()