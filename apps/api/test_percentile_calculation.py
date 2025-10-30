"""
Test and fix percentile calculations for pitch data
"""
import psycopg2
import numpy as np

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def calculate_percentiles_from_peers():
    """Calculate actual percentiles by comparing to peer group"""

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    print("="*80)
    print("CALCULATING TRUE PERCENTILES FROM PEER DATA")
    print("="*80)

    # Get all hitters' pitch metrics for 2025 season
    print("\n1. Gathering all hitter metrics for comparison...")
    cursor.execute("""
        WITH hitter_metrics AS (
            SELECT
                mlb_batter_id,
                level,
                COUNT(*) as pitches_seen,

                -- Contact Rate
                COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

                -- Whiff Rate
                COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                -- Chase Rate
                COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                -- Zone Contact
                COUNT(*) FILTER (WHERE contact = TRUE AND zone <= 9) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND zone <= 9), 0) as zone_contact

            FROM milb_batter_pitches
            WHERE season = 2025
                AND level IN ('AAA', 'AA', 'A+', 'A')
            GROUP BY mlb_batter_id, level
            HAVING COUNT(*) >= 50  -- Min sample size
        )
        SELECT level,
               COUNT(*) as num_hitters,

               -- Contact Rate percentiles
               PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY contact_rate) as contact_p10,
               PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY contact_rate) as contact_p25,
               PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY contact_rate) as contact_p50,
               PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY contact_rate) as contact_p75,
               PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY contact_rate) as contact_p90,

               -- Whiff Rate percentiles
               PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY whiff_rate) as whiff_p10,
               PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY whiff_rate) as whiff_p25,
               PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY whiff_rate) as whiff_p50,
               PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY whiff_rate) as whiff_p75,
               PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY whiff_rate) as whiff_p90,

               -- Chase Rate percentiles
               PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY chase_rate) as chase_p10,
               PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY chase_rate) as chase_p25,
               PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY chase_rate) as chase_p50,
               PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY chase_rate) as chase_p75,
               PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY chase_rate) as chase_p90

        FROM hitter_metrics
        GROUP BY level
        ORDER BY level
    """)

    level_percentiles = {}
    for row in cursor.fetchall():
        level = row[0]
        level_percentiles[level] = {
            'num_hitters': row[1],
            'contact_rate': {'p10': row[2], 'p25': row[3], 'p50': row[4], 'p75': row[5], 'p90': row[6]},
            'whiff_rate': {'p10': row[7], 'p25': row[8], 'p50': row[9], 'p75': row[10], 'p90': row[11]},
            'chase_rate': {'p10': row[12], 'p25': row[13], 'p50': row[14], 'p75': row[15], 'p90': row[16]}
        }

        print(f"\n{level}: {row[1]} hitters")
        print(f"  Contact Rate: p10={row[2]:.1f}%, p50={row[4]:.1f}%, p90={row[6]:.1f}%")
        print(f"  Whiff Rate:   p10={row[7]:.1f}%, p50={row[9]:.1f}%, p90={row[11]:.1f}%")
        if row[12] is not None:
            print(f"  Chase Rate:   p10={row[12]:.1f}%, p50={row[14]:.1f}%, p90={row[16]:.1f}%")
        else:
            print(f"  Chase Rate:   (insufficient data)")

    # Now test specific players and calculate their true percentiles
    print("\n" + "="*80)
    print("CALCULATING PERCENTILES FOR SPECIFIC PROSPECTS")
    print("="*80)

    test_players = [
        (805811, 'Bryce Eldridge', 'AAA'),
        (804606, 'Konnor Griffin', 'AA'),
        (701350, 'Roman Anthony', 'AA'),
        (692225, 'Kristian Campbell', 'AA')
    ]

    for mlb_id, name, primary_level in test_players:
        print(f"\n{name} (ID: {mlb_id}):")

        # Get this player's metrics
        cursor.execute("""
            SELECT
                COUNT(*) as pitches_seen,

                COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

                COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate

            FROM milb_batter_pitches
            WHERE mlb_batter_id = %s
                AND season = 2025
        """, (mlb_id,))

        result = cursor.fetchone()
        if not result or result[0] < 50:
            print("  Insufficient data")
            continue

        pitches, contact_rate, whiff_rate, chase_rate = result

        print(f"  Raw Metrics ({pitches} pitches):")
        print(f"    Contact: {contact_rate:.1f}%")
        print(f"    Whiff:   {whiff_rate:.1f}%")
        print(f"    Chase:   {chase_rate:.1f}%")

        # Calculate percentiles using the right level
        if primary_level in level_percentiles:
            percs = level_percentiles[primary_level]

            # Contact rate (higher is better)
            contact_pct = calculate_percentile(contact_rate, percs['contact_rate'], higher_is_better=True)

            # Whiff rate (lower is better)
            whiff_pct = calculate_percentile(whiff_rate, percs['whiff_rate'], higher_is_better=False)

            # Chase rate (lower is better)
            chase_pct = calculate_percentile(chase_rate, percs['chase_rate'], higher_is_better=False)

            print(f"  Percentiles vs {primary_level} peers:")
            print(f"    Contact: {contact_pct:.0f}th percentile")
            print(f"    Whiff:   {whiff_pct:.0f}th percentile")
            print(f"    Chase:   {chase_pct:.0f}th percentile")

            # Weighted composite (simplified)
            composite = (contact_pct * 0.40 + whiff_pct * 0.35 + chase_pct * 0.25)
            print(f"  Composite: {composite:.0f}th percentile")

            # Convert to modifier
            if composite >= 90:
                modifier = 10.0
            elif composite >= 75:
                modifier = 5.0
            elif composite >= 60:
                modifier = 2.0
            elif composite >= 40:
                modifier = 0.0
            elif composite >= 25:
                modifier = -5.0
            else:
                modifier = -10.0

            print(f"  Ranking Modifier: {modifier:+.0f}")

    conn.close()

def calculate_percentile(value, thresholds, higher_is_better=True):
    """Calculate what percentile a value falls into"""
    if value is None:
        return 50.0

    p10, p25, p50, p75, p90 = thresholds['p10'], thresholds['p25'], thresholds['p50'], thresholds['p75'], thresholds['p90']

    if higher_is_better:
        # Higher value = better percentile
        if value >= p90:
            return 95.0
        elif value >= p75:
            return 75 + (value - p75) / (p90 - p75) * 15
        elif value >= p50:
            return 50 + (value - p50) / (p75 - p50) * 25
        elif value >= p25:
            return 25 + (value - p25) / (p50 - p25) * 25
        elif value >= p10:
            return 10 + (value - p10) / (p25 - p10) * 15
        else:
            return 5.0
    else:
        # Lower value = better percentile (invert)
        if value <= p10:
            return 95.0
        elif value <= p25:
            return 75 + (p25 - value) / (p25 - p10) * 15
        elif value <= p50:
            return 50 + (p50 - value) / (p50 - p25) * 25
        elif value <= p75:
            return 25 + (p75 - value) / (p75 - p50) * 25
        elif value <= p90:
            return 10 + (p90 - value) / (p90 - p75) * 15
        else:
            return 5.0

if __name__ == "__main__":
    calculate_percentiles_from_peers()