import psycopg2
import logging
import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def investigate_missing_data():
    """Investigate why so many prospects have no 2025 MiLB data"""

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    logging.info("\n" + "="*80)
    logging.info("INVESTIGATING MISSING 2025 DATA")
    logging.info("="*80)

    # Get sample of prospects with no data
    cur.execute("""
        SELECT p.mlb_player_id, p.name, p.position, p.organization, pr.v7_rank
        FROM prospects p
        LEFT JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id
        WHERE p.mlb_player_id IS NOT NULL
        AND NOT EXISTS(
            SELECT 1 FROM milb_plate_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
            AND mpa.season = 2025
        )
        AND NOT EXISTS(
            SELECT 1 FROM milb_batter_pitches mbp
            WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER
            AND mbp.season = 2025
        )
        ORDER BY COALESCE(pr.v7_rank, 999)
        LIMIT 50
    """)

    missing_prospects = cur.fetchall()

    logging.info(f"\nTop 50 prospects with NO 2025 MiLB data:")
    logging.info(f"{'Rank':<8} {'Name':<30} {'Pos':<6} {'Org':<6}")
    logging.info("-" * 60)

    for mlb_id, name, pos, org, rank in missing_prospects:
        rank_str = f"#{rank}" if rank else "N/A"
        logging.info(f"{rank_str:<8} {name:<30} {pos or 'N/A':<6} {org or 'N/A':<6}")

    # Let's manually check a few via API to see what's happening
    logging.info("\n" + "="*80)
    logging.info("MANUAL API CHECKS - Sample Prospects")
    logging.info("="*80)

    sample_prospects = missing_prospects[:10]

    for mlb_id, name, pos, org, rank in sample_prospects:
        logging.info(f"\nChecking {name} (ID: {mlb_id})...")

        # Check hitting stats
        url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"

        for sport_id in [11, 12, 13, 14]:  # AAA, AA, High-A, Single-A
            params = {
                'stats': 'gameLog',
                'season': 2025,
                'sportId': sport_id,
                'group': 'hitting'
            }

            try:
                response = requests.get(url, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if 'stats' in data and data['stats']:
                        for stat in data['stats']:
                            if 'splits' in stat and stat['splits']:
                                games = stat['splits']
                                sport_names = {11: 'AAA', 12: 'AA', 13: 'High-A', 14: 'Single-A'}
                                logging.info(f"  -> FOUND {len(games)} games at {sport_names[sport_id]}!")
                                # Check first game details
                                if games:
                                    first_game = games[0]
                                    logging.info(f"     First game: {first_game.get('date')}")
                                    logging.info(f"     Team: {first_game.get('team', {}).get('name', 'Unknown')}")
                                break
            except Exception as e:
                logging.error(f"  Error checking {name}: {e}")

        # Check if they might be in MLB instead
        params = {
            'stats': 'gameLog',
            'season': 2025,
            'sportId': 1,  # MLB
            'group': 'hitting'
        }

        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'stats' in data and data['stats']:
                    for stat in data['stats']:
                        if 'splits' in stat and stat['splits']:
                            mlb_games = stat['splits']
                            logging.info(f"  -> PROMOTED TO MLB! {len(mlb_games)} games in 2025")
                            break
        except Exception as e:
            pass

    # Check how many prospects might be in MLB
    logging.info("\n" + "="*80)
    logging.info("CHECKING MLB PROMOTIONS")
    logging.info("="*80)

    # Check if there's an MLB stats table
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE '%mlb%'
        AND table_name NOT LIKE '%milb%'
        ORDER BY table_name
    """)

    mlb_tables = [row[0] for row in cur.fetchall()]
    logging.info(f"\nFound MLB tables: {mlb_tables}")

    # Check roster years
    logging.info("\n" + "="*80)
    logging.info("PROSPECT ROSTER YEARS")
    logging.info("="*80)

    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE EXISTS(
                SELECT 1 FROM milb_plate_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
                AND mpa.season = 2023
            )) as had_2023_data,
            COUNT(*) FILTER (WHERE EXISTS(
                SELECT 1 FROM milb_plate_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
                AND mpa.season = 2024
            )) as had_2024_data,
            COUNT(*) FILTER (WHERE EXISTS(
                SELECT 1 FROM milb_plate_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
                AND mpa.season = 2025
            )) as had_2025_data,
            COUNT(*) as total_prospects
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
    """)

    year_stats = cur.fetchone()
    logging.info(f"\nProspects with data by year:")
    logging.info(f"  2023: {year_stats[0]} ({year_stats[0]/year_stats[3]*100:.1f}%)")
    logging.info(f"  2024: {year_stats[1]} ({year_stats[1]/year_stats[3]*100:.1f}%)")
    logging.info(f"  2025: {year_stats[2]} ({year_stats[2]/year_stats[3]*100:.1f}%)")
    logging.info(f"  Total prospects: {year_stats[3]}")

    # Check if there are prospects with NO data across ALL years
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND NOT EXISTS(
            SELECT 1 FROM milb_plate_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
        )
    """)
    never_played = cur.fetchone()[0]
    logging.info(f"\nProspects with ZERO MiLB data (any year): {never_played}")

    conn.close()

if __name__ == "__main__":
    investigate_missing_data()
