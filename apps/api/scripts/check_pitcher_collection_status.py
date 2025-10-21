import psycopg2
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def check_pitcher_status():
    """Check current pitcher data collection status"""

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    logging.info("\n" + "="*80)
    logging.info("PITCHER DATA COLLECTION STATUS")
    logging.info("="*80)

    # Total pitchers
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects
        WHERE position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND mlb_player_id IS NOT NULL
    """)
    total_pitchers = cur.fetchone()[0]
    logging.info(f"\nTotal pitching prospects: {total_pitchers}")

    # Pitchers with 2025 appearances
    cur.execute("""
        SELECT COUNT(DISTINCT mlb_player_id)
        FROM milb_pitcher_appearances
        WHERE season = 2025
    """)
    pitchers_with_appearances = cur.fetchone()[0]

    # Pitchers with 2025 pitches
    cur.execute("""
        SELECT COUNT(DISTINCT mlb_pitcher_id)
        FROM milb_pitcher_pitches
        WHERE season = 2025
    """)
    pitchers_with_pitches = cur.fetchone()[0]

    logging.info(f"\nPitchers with 2025 game appearances: {pitchers_with_appearances}")
    logging.info(f"Pitchers with 2025 pitch data: {pitchers_with_pitches}")

    # Total stats
    cur.execute("""
        SELECT COUNT(*), SUM(innings_pitched)
        FROM milb_pitcher_appearances
        WHERE season = 2025
    """)
    total_games, total_ip = cur.fetchone()

    cur.execute("""
        SELECT COUNT(*)
        FROM milb_pitcher_pitches
        WHERE season = 2025
    """)
    total_pitches = cur.fetchone()[0]

    logging.info(f"\nTotal pitching appearances (2025): {total_games}")
    logging.info(f"Total innings pitched (2025): {total_ip}")
    logging.info(f"Total pitches thrown (2025): {total_pitches:,}")

    # Pitchers still missing data
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND p.mlb_player_id IS NOT NULL
        AND NOT EXISTS(
            SELECT 1 FROM milb_pitcher_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
            AND mpa.season = 2025
        )
    """)
    missing_pitchers = cur.fetchone()[0]

    logging.info(f"\n" + "="*80)
    logging.info(f"Pitchers still missing 2025 data: {missing_pitchers}/{total_pitchers}")
    logging.info(f"Coverage: {(total_pitchers - missing_pitchers)/total_pitchers*100:.1f}%")
    logging.info("="*80)

    # Check if the pitcher collection completed successfully
    cur.execute("""
        SELECT p.mlb_player_id, p.name, p.position
        FROM prospects p
        WHERE p.position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND p.mlb_player_id IS NOT NULL
        AND EXISTS(
            SELECT 1 FROM milb_pitcher_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
            AND mpa.season = 2025
        )
        ORDER BY p.name
        LIMIT 20
    """)

    collected_pitchers = cur.fetchall()
    logging.info(f"\nSample of pitchers WITH 2025 data:")
    for mlb_id, name, pos in collected_pitchers[:10]:
        # Get their stats
        cur.execute("""
            SELECT COUNT(*) as games, SUM(innings_pitched) as ip
            FROM milb_pitcher_appearances
            WHERE mlb_player_id = %s AND season = 2025
        """, (int(mlb_id),))
        games, ip = cur.fetchone()

        cur.execute("""
            SELECT COUNT(*)
            FROM milb_pitcher_pitches
            WHERE mlb_pitcher_id = %s AND season = 2025
        """, (int(mlb_id),))
        pitches = cur.fetchone()[0]

        logging.info(f"  {name:<30} {pos:<4} - {games} games, {ip} IP, {pitches} pitches")

    conn.close()

if __name__ == "__main__":
    check_pitcher_status()
