import psycopg2
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def audit_pitching_prospects():
    """Audit all prospects to find pitchers and check their pitching data coverage"""

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    logging.info("\n" + "="*80)
    logging.info("PITCHING PROSPECTS AUDIT")
    logging.info("="*80)

    # Check if there's a position field in prospects table
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'prospects'
        AND column_name IN ('position', 'primary_position', 'pos')
    """)
    position_columns = [row[0] for row in cur.fetchall()]

    if position_columns:
        logging.info(f"\nFound position column(s): {', '.join(position_columns)}")
        position_col = position_columns[0]

        # Count pitchers
        cur.execute(f"""
            SELECT COUNT(*)
            FROM prospects
            WHERE {position_col} IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
            AND mlb_player_id IS NOT NULL
        """)
        pitcher_count = cur.fetchone()[0]
        logging.info(f"\nTotal pitchers with MLB player ID: {pitcher_count}")

        # Get top-ranked pitchers
        cur.execute(f"""
            SELECT p.mlb_player_id, p.name, p.{position_col}, pr.v7_rank, p.organization
            FROM prospects p
            LEFT JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id
            WHERE p.{position_col} IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
            AND p.mlb_player_id IS NOT NULL
            ORDER BY COALESCE(pr.v7_rank, 999)
            LIMIT 50
        """)
        top_pitchers = cur.fetchall()

        logging.info(f"\n{'Rank':<8} {'Name':<30} {'Pos':<6} {'Org':<6}")
        logging.info("-" * 60)
        for mlb_id, name, pos, rank, org in top_pitchers:
            rank_str = str(rank) if rank else "N/A"
            logging.info(f"{rank_str:<8} {name:<30} {pos:<6} {org or 'N/A':<6}")

    else:
        logging.info("\nNo position column found - checking all prospects")

        # Get all prospects with rankings to manually identify pitchers
        cur.execute("""
            SELECT p.mlb_player_id, p.name, pr.v7_rank, p.organization
            FROM prospects p
            LEFT JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id
            WHERE p.mlb_player_id IS NOT NULL
            ORDER BY COALESCE(pr.v7_rank, 999)
            LIMIT 50
        """)
        all_prospects = cur.fetchall()

        logging.info(f"\nTop 50 Prospects (need manual position identification):")
        logging.info(f"{'Rank':<8} {'Name':<30} {'Org':<6}")
        logging.info("-" * 50)
        for mlb_id, name, rank, org in all_prospects:
            rank_str = str(rank) if rank else "N/A"
            logging.info(f"{rank_str:<8} {name:<30} {org or 'N/A':<6}")

    # Check for pitching-related tables
    logging.info("\n" + "="*80)
    logging.info("CHECKING FOR PITCHING DATA TABLES")
    logging.info("="*80)

    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE '%pitch%'
        ORDER BY table_name
    """)
    pitching_tables = [row[0] for row in cur.fetchall()]

    if pitching_tables:
        logging.info(f"\nFound pitching-related tables:")
        for table in pitching_tables:
            logging.info(f"  - {table}")

            # Get table structure
            cur.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            logging.info(f"    Columns: {', '.join([col[0] for col in columns[:10]])}...")

            # Count rows
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cur.fetchone()[0]
            logging.info(f"    Row count: {row_count:,}")
    else:
        logging.info("\nNo pitching-specific tables found!")
        logging.info("We need to create tables for:")
        logging.info("  - milb_pitcher_appearances (game logs)")
        logging.info("  - milb_pitcher_pitches (pitch-by-pitch data)")

    # Check if milb_batter_pitches has pitcher data
    logging.info("\n" + "="*80)
    logging.info("CHECKING EXISTING PITCH DATA")
    logging.info("="*80)

    cur.execute("""
        SELECT COUNT(DISTINCT mlb_pitcher_id)
        FROM milb_batter_pitches
        WHERE season = 2025
    """)
    unique_pitchers = cur.fetchone()[0]
    logging.info(f"\nUnique pitchers in milb_batter_pitches (2025): {unique_pitchers}")

    cur.execute("""
        SELECT COUNT(*)
        FROM milb_batter_pitches
        WHERE season = 2025
    """)
    total_pitches = cur.fetchone()[0]
    logging.info(f"Total pitches recorded (2025): {total_pitches:,}")

    # Sample some pitcher IDs to check if they're in our prospects
    cur.execute("""
        SELECT mbp.mlb_pitcher_id, COUNT(*) as pitch_count
        FROM milb_batter_pitches mbp
        WHERE mbp.season = 2025
        GROUP BY mbp.mlb_pitcher_id
        ORDER BY pitch_count DESC
        LIMIT 20
    """)
    top_pitch_counts = cur.fetchall()

    logging.info(f"\nTop 20 pitchers by pitch count (2025):")
    logging.info(f"{'Pitcher ID':<15} {'Pitches':<10} {'In Prospects?'}")
    logging.info("-" * 45)

    for pitcher_id, pitch_count in top_pitch_counts:
        cur.execute("""
            SELECT name FROM prospects WHERE mlb_player_id::INTEGER = %s
        """, (pitcher_id,))
        result = cur.fetchone()
        in_prospects = result[0] if result else "No"
        logging.info(f"{pitcher_id:<15} {pitch_count:<10} {in_prospects}")

    conn.close()

    logging.info("\n" + "="*80)
    logging.info("AUDIT COMPLETE")
    logging.info("="*80)

if __name__ == "__main__":
    audit_pitching_prospects()
