import psycopg2
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def check_pitcher_coverage():
    """Check how many pitching prospects have data in milb_pitcher_pitches"""

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    logging.info("\n" + "="*80)
    logging.info("PITCHER PROSPECT DATA COVERAGE")
    logging.info("="*80)

    # Total pitchers
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects
        WHERE position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND mlb_player_id IS NOT NULL
    """)
    total_pitchers = cur.fetchone()[0]
    logging.info(f"\nTotal pitching prospects with MLB ID: {total_pitchers}")

    # Pitchers with data in milb_pitcher_pitches for 2025
    cur.execute("""
        SELECT COUNT(DISTINCT p.mlb_player_id)
        FROM prospects p
        INNER JOIN milb_pitcher_pitches mpp ON mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER
        WHERE p.position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND p.mlb_player_id IS NOT NULL
        AND mpp.season = 2025
    """)
    pitchers_with_2025_data = cur.fetchone()[0]
    logging.info(f"Pitchers with 2025 pitch data: {pitchers_with_2025_data}")

    # Coverage percentage
    coverage_pct = (pitchers_with_2025_data / total_pitchers * 100) if total_pitchers > 0 else 0
    logging.info(f"Coverage: {coverage_pct:.1f}%")

    # Top-ranked pitchers
    logging.info("\n" + "="*80)
    logging.info("TOP-RANKED PITCHING PROSPECTS - DATA STATUS")
    logging.info("="*80)

    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            pr.v7_rank,
            p.organization,
            EXISTS(
                SELECT 1 FROM milb_pitcher_pitches mpp
                WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER
                AND mpp.season = 2025
            ) as has_2025_pitches,
            (
                SELECT COUNT(*)
                FROM milb_pitcher_pitches mpp
                WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER
                AND mpp.season = 2025
            ) as pitch_count
        FROM prospects p
        LEFT JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id
        WHERE p.position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND p.mlb_player_id IS NOT NULL
        ORDER BY COALESCE(pr.v7_rank, 999), p.name
        LIMIT 50
    """)

    top_pitchers = cur.fetchall()

    logging.info(f"\n{'Rank':<8} {'Name':<30} {'Org':<6} {'Has 2025?':<12} {'Pitches':<10}")
    logging.info("-" * 76)

    pitchers_with_data = 0
    pitchers_without_data = []

    for mlb_id, name, rank, org, has_data, pitch_count in top_pitchers:
        rank_str = str(rank) if rank else "N/A"
        org_str = org or "N/A"
        has_str = "YES" if has_data else "NO"
        pitch_str = str(pitch_count) if pitch_count > 0 else "-"

        logging.info(f"{rank_str:<8} {name:<30} {org_str:<6} {has_str:<12} {pitch_str:<10}")

        if has_data:
            pitchers_with_data += 1
        else:
            pitchers_without_data.append((mlb_id, name, rank))

    # Summary
    logging.info("\n" + "="*80)
    logging.info("SUMMARY - TOP 50 PITCHERS")
    logging.info("="*80)
    logging.info(f"With 2025 data: {pitchers_with_data}")
    logging.info(f"Missing 2025 data: {len(pitchers_without_data)}")

    if pitchers_without_data:
        logging.info(f"\nPitchers needing data collection ({len(pitchers_without_data)}):")
        for mlb_id, name, rank in pitchers_without_data[:20]:
            rank_str = f"#{rank}" if rank else "Unranked"
            logging.info(f"  {rank_str:<10} {name:<30} (ID: {mlb_id})")

    # Check if there's a pitcher game log table
    logging.info("\n" + "="*80)
    logging.info("CHECKING FOR PITCHER GAME LOG TABLE")
    logging.info("="*80)

    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND (table_name LIKE '%pitcher%' AND table_name LIKE '%appearance%'
             OR table_name LIKE '%pitcher%' AND table_name LIKE '%game%')
        ORDER BY table_name
    """)

    game_log_tables = [row[0] for row in cur.fetchall()]

    if game_log_tables:
        logging.info(f"Found potential game log tables:")
        for table in game_log_tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            logging.info(f"  - {table}: {count:,} rows")
    else:
        logging.info("No pitcher game log table found!")
        logging.info("Need to create: milb_pitcher_appearances")

    conn.close()

if __name__ == "__main__":
    check_pitcher_coverage()
