"""
Explore all available pitch data and metrics for Jesus Made
"""
import psycopg2
import json

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def explore_jesus_made_data():
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    print("="*80)
    print("EXPLORING PITCH DATA FOR JESUS MADE")
    print("="*80)

    # First, find Jesus Made's MLB ID (or search for similar names)
    cursor.execute("""
        SELECT mlb_player_id, name, position, organization
        FROM prospects
        WHERE name ILIKE '%made%' OR name ILIKE '%jesus%'
        ORDER BY name
        LIMIT 10
    """)

    prospects = cursor.fetchall()
    if not prospects:
        print("Jesus Made not found in prospects table")
        return

    for mlb_id, name, position, org in prospects:
        print(f"\nFound: {name} ({mlb_id}) - {position} - {org}")

    # Look for Jesus Made specifically
    mlb_id = None
    name = None
    for id, n, pos, org in prospects:
        if 'Made' in n and ('Jesus' in n or 'Jesús' in n or 'Jes�s' in n):
            mlb_id = id
            name = n
            break

    # If not found, use first match
    if not mlb_id:
        mlb_id = prospects[0][0]
        name = prospects[0][1]

    print(f"\nAnalyzing data for: {name} (ID: {mlb_id})")
    print("-"*80)

    # Check if we have pitch data
    cursor.execute("""
        SELECT COUNT(*) as total_pitches,
               COUNT(DISTINCT game_pk) as games,
               MIN(game_date) as first_date,
               MAX(game_date) as last_date,
               array_agg(DISTINCT level) as levels
        FROM milb_batter_pitches
        WHERE mlb_batter_id = %s AND season = 2025
    """, (int(mlb_id),))

    result = cursor.fetchone()
    if result[0] == 0:
        print("No pitch data found for 2025")
        return

    total_pitches, games, first_date, last_date, levels = result
    print(f"\nBasic Stats:")
    print(f"  Total Pitches: {total_pitches}")
    print(f"  Games: {games}")
    print(f"  Date Range: {first_date} to {last_date}")
    print(f"  Levels: {levels}")

    # Now let's see what columns have actual data
    print("\n" + "="*80)
    print("AVAILABLE DATA FIELDS (non-null counts)")
    print("="*80)

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            -- Pitch characteristics
            COUNT(pitch_type) as has_pitch_type,
            COUNT(start_speed) as has_velocity,
            COUNT(spin_rate) as has_spin,
            COUNT(pfx_x) as has_horizontal_break,
            COUNT(pfx_z) as has_vertical_break,

            -- Location data
            COUNT(plate_x) as has_plate_x,
            COUNT(plate_z) as has_plate_z,
            COUNT(zone) as has_zone,

            -- Swing/contact data
            COUNT(CASE WHEN swing IS NOT NULL THEN 1 END) as has_swing,
            COUNT(CASE WHEN contact IS NOT NULL THEN 1 END) as has_contact,
            COUNT(CASE WHEN swing_and_miss IS NOT NULL THEN 1 END) as has_whiff,
            COUNT(CASE WHEN foul IS NOT NULL THEN 1 END) as has_foul,

            -- Results
            COUNT(pitch_call) as has_pitch_call,
            COUNT(pitch_result) as has_pitch_result,
            COUNT(CASE WHEN is_strike IS NOT NULL THEN 1 END) as has_is_strike,

            -- Batted ball data
            COUNT(launch_speed) as has_exit_velo,
            COUNT(launch_angle) as has_launch_angle,
            COUNT(total_distance) as has_distance,
            COUNT(trajectory) as has_trajectory,
            COUNT(hardness) as has_hardness,

            -- Count state
            COUNT(balls) as has_balls,
            COUNT(strikes) as has_strikes,
            COUNT(outs) as has_outs

        FROM milb_batter_pitches
        WHERE mlb_batter_id = %s AND season = 2025
    """, (int(mlb_id),))

    columns = cursor.description
    result = cursor.fetchone()

    for i, (col, val) in enumerate(zip(columns[1:], result[1:]), 1):
        pct = (val / result[0] * 100) if result[0] > 0 else 0
        if val > 0:
            print(f"  {col.name:20s}: {val:6d} ({pct:5.1f}%)")

    # Calculate comprehensive metrics
    print("\n" + "="*80)
    print("COMPREHENSIVE METRICS WE CAN CALCULATE")
    print("="*80)

    cursor.execute("""
        WITH pitch_data AS (
            SELECT * FROM milb_batter_pitches
            WHERE mlb_batter_id = %s AND season = 2025
        )
        SELECT
            -- Basic rates
            COUNT(*) FILTER (WHERE swing = TRUE) * 100.0 / NULLIF(COUNT(*), 0) as swing_rate,
            COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,
            COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,
            COUNT(*) FILTER (WHERE foul = TRUE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as foul_rate,

            -- Zone metrics
            COUNT(*) FILTER (WHERE zone <= 9) * 100.0 / NULLIF(COUNT(*), 0) as zone_rate,
            COUNT(*) FILTER (WHERE swing = TRUE AND zone <= 9) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE zone <= 9), 0) as zone_swing_rate,
            COUNT(*) FILTER (WHERE contact = TRUE AND zone <= 9) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND zone <= 9), 0) as zone_contact_rate,
            COUNT(*) FILTER (WHERE swing_and_miss = TRUE AND zone <= 9) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND zone <= 9), 0) as zone_whiff_rate,

            -- Chase metrics (out of zone)
            COUNT(*) FILTER (WHERE zone > 9) * 100.0 / NULLIF(COUNT(*), 0) as ball_rate,
            COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,
            COUNT(*) FILTER (WHERE contact = TRUE AND zone > 9) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9), 0) as chase_contact_rate,

            -- Strike/Ball outcomes
            COUNT(*) FILTER (WHERE is_strike = TRUE) * 100.0 / NULLIF(COUNT(*), 0) as strike_rate,
            COUNT(*) FILTER (WHERE pitch_call = 'B') * 100.0 / NULLIF(COUNT(*), 0) as ball_rate_called,
            COUNT(*) FILTER (WHERE pitch_call = 'S' AND swing = FALSE) * 100.0 / NULLIF(COUNT(*), 0) as called_strike_rate,
            COUNT(*) FILTER (WHERE pitch_result = 'Swinging Strike') * 100.0 / NULLIF(COUNT(*), 0) as swinging_strike_rate,

            -- Count leverage
            COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE strikes = 2), 0) as two_strike_swing_rate,
            COUNT(*) FILTER (WHERE contact = TRUE AND strikes = 2) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2), 0) as two_strike_contact_rate,
            COUNT(*) FILTER (WHERE swing = TRUE AND balls = 0 AND strikes = 0) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE balls = 0 AND strikes = 0), 0) as first_pitch_swing_rate,

            -- Pitch type breakdown (if available)
            COUNT(*) FILTER (WHERE pitch_type IN ('FF', 'FT', 'FC', 'FS', 'SI')) * 100.0 / NULLIF(COUNT(*), 0) as fastball_pct,
            COUNT(*) FILTER (WHERE pitch_type IN ('SL', 'CU', 'KC', 'SC', 'SV')) * 100.0 / NULLIF(COUNT(*), 0) as breaking_pct,
            COUNT(*) FILTER (WHERE pitch_type IN ('CH', 'EP', 'FO', 'KN')) * 100.0 / NULLIF(COUNT(*), 0) as offspeed_pct,

            -- Velocity metrics (if available)
            AVG(start_speed) as avg_velocity_seen,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY start_speed) as velo_90th_percentile,

            -- Batted ball (if available - likely NULL)
            AVG(launch_speed) as avg_exit_velo,
            AVG(launch_angle) as avg_launch_angle,
            COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate

        FROM pitch_data
    """, (int(mlb_id),))

    columns = cursor.description
    result = cursor.fetchone()

    print("\nMetrics Available:")
    for col, val in zip(columns, result):
        if val is not None and val != 0:
            if 'rate' in col.name or 'pct' in col.name:
                print(f"  {col.name:30s}: {val:6.2f}%")
            else:
                print(f"  {col.name:30s}: {val:6.2f}")

    # Check specific pitch types seen
    print("\n" + "="*80)
    print("PITCH TYPES FACED")
    print("="*80)

    cursor.execute("""
        SELECT pitch_type, pitch_type_description, COUNT(*) as count,
               COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as pct
        FROM milb_batter_pitches
        WHERE mlb_batter_id = %s AND season = 2025
            AND pitch_type IS NOT NULL
        GROUP BY pitch_type, pitch_type_description
        ORDER BY count DESC
    """, (int(mlb_id),))

    pitch_types = cursor.fetchall()
    if pitch_types:
        for ptype, desc, count, pct in pitch_types:
            print(f"  {ptype:4s} {desc or '':20s}: {count:5d} ({pct:5.1f}%)")
    else:
        print("  No pitch type data available")

    conn.close()

if __name__ == "__main__":
    explore_jesus_made_data()