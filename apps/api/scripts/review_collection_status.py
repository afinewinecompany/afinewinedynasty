import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print('\n' + '='*90)
print('COMPREHENSIVE DATA COLLECTION STATUS REVIEW')
print('='*90)
print(f'Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('='*90)

# 1. TOTAL PROSPECTS
print('\n[PROSPECT OVERVIEW]')
print('-'*90)

cur.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER') THEN 1 END) as pitchers,
        COUNT(CASE WHEN position NOT IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER') THEN 1 END) as batters
    FROM prospects
    WHERE mlb_player_id IS NOT NULL
""")
total, pitchers, batters = cur.fetchone()
print(f'Total Prospects:    {total:,}')
print(f'  Pitchers:         {pitchers:,}')
print(f'  Batters:          {batters:,}')

# 2. BATTER DATA - 2025
print('\n[BATTER DATA - 2025 SEASON]')
print('-'*90)

cur.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_plate_appearances
    WHERE season = 2025
""")
batters_with_pa = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_plate_appearances
    WHERE season = 2025
""")
total_pa_2025 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT mlb_batter_id)
    FROM milb_batter_pitches
    WHERE season = 2025
""")
batters_with_pitches = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_batter_pitches
    WHERE season = 2025
""")
total_pitches_2025 = cur.fetchone()[0]

print(f'Batters with Plate Appearances: {batters_with_pa:,} / {batters:,} ({100*batters_with_pa/batters:.1f}%)')
print(f'Total Plate Appearances:        {total_pa_2025:,}')
print(f'Batters with Pitch Data:        {batters_with_pitches:,} / {batters:,} ({100*batters_with_pitches/batters:.1f}%)')
print(f'Total Pitches (as batter):      {total_pitches_2025:,}')

# 3. BATTER DATA - 2024
print('\n[BATTER DATA - 2024 SEASON]')
print('-'*90)

cur.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_plate_appearances
    WHERE season = 2024
""")
batters_with_pa_2024 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_plate_appearances
    WHERE season = 2024
""")
total_pa_2024 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT mlb_batter_id)
    FROM milb_batter_pitches
    WHERE season = 2024
""")
batters_with_pitches_2024 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_batter_pitches
    WHERE season = 2024
""")
total_pitches_2024 = cur.fetchone()[0]

print(f'Batters with Plate Appearances: {batters_with_pa_2024:,} / {batters:,} ({100*batters_with_pa_2024/batters:.1f}%)')
print(f'Total Plate Appearances:        {total_pa_2024:,}')
print(f'Batters with Pitch Data:        {batters_with_pitches_2024:,} / {batters:,} ({100*batters_with_pitches_2024/batters:.1f}%)')
print(f'Total Pitches (as batter):      {total_pitches_2024:,}')

# 4. PITCHER DATA - 2025
print('\n[PITCHER DATA - 2025 SEASON]')
print('-'*90)

cur.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_pitcher_appearances
    WHERE season = 2025
""")
pitchers_with_app = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_pitcher_appearances
    WHERE season = 2025
""")
total_appearances_2025 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT mlb_pitcher_id)
    FROM milb_pitcher_pitches
    WHERE season = 2025
""")
pitchers_with_pitches = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_pitcher_pitches
    WHERE season = 2025
""")
total_pitcher_pitches_2025 = cur.fetchone()[0]

print(f'Pitchers with Appearances:      {pitchers_with_app:,} / {pitchers:,} ({100*pitchers_with_app/pitchers:.1f}%)')
print(f'Total Pitcher Appearances:      {total_appearances_2025:,}')
print(f'Pitchers with Pitch Data:       {pitchers_with_pitches:,} / {pitchers:,} ({100*pitchers_with_pitches/pitchers:.1f}%)')
print(f'Total Pitches (as pitcher):     {total_pitcher_pitches_2025:,}')

# 5. PITCHER DATA - 2024
print('\n[PITCHER DATA - 2024 SEASON]')
print('-'*90)

cur.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_pitcher_appearances
    WHERE season = 2024
""")
pitchers_with_app_2024 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_pitcher_appearances
    WHERE season = 2024
""")
total_appearances_2024 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT mlb_pitcher_id)
    FROM milb_pitcher_pitches
    WHERE season = 2024
""")
pitchers_with_pitches_2024 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_pitcher_pitches
    WHERE season = 2024
""")
total_pitcher_pitches_2024 = cur.fetchone()[0]

print(f'Pitchers with Appearances:      {pitchers_with_app_2024:,} / {pitchers:,} ({100*pitchers_with_app_2024/pitchers:.1f}%)')
print(f'Total Pitcher Appearances:      {total_appearances_2024:,}')
print(f'Pitchers with Pitch Data:       {pitchers_with_pitches_2024:,} / {pitchers:,} ({100*pitchers_with_pitches_2024/pitchers:.1f}%)')
print(f'Total Pitches (as pitcher):     {total_pitcher_pitches_2024:,}')

# 6. RECENT ACTIVITY
print('\n[RECENT ACTIVITY - Last 30 minutes]')
print('-'*90)

cur.execute("""
    SELECT
        COUNT(DISTINCT mlb_batter_id) as batters,
        COUNT(*) as pitches
    FROM milb_batter_pitches
    WHERE created_at > NOW() - INTERVAL '30 minutes'
""")
recent_batters, recent_batter_pitches = cur.fetchone()

cur.execute("""
    SELECT
        COUNT(DISTINCT mlb_pitcher_id) as pitchers,
        COUNT(*) as pitches
    FROM milb_pitcher_pitches
    WHERE created_at > NOW() - INTERVAL '30 minutes'
""")
recent_pitchers, recent_pitcher_pitches = cur.fetchone()

print(f'Batter Data Collected:')
print(f'  New batters:                  {recent_batters:,}')
print(f'  New pitches (as batter):      {recent_batter_pitches:,}')
print(f'\nPitcher Data Collected:')
print(f'  New pitchers:                 {recent_pitchers:,}')
print(f'  New pitches (as pitcher):     {recent_pitcher_pitches:,}')

# 7. COVERAGE GAPS
print('\n[COVERAGE GAPS]')
print('-'*90)

cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.position NOT IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND p.mlb_player_id IS NOT NULL
        AND NOT EXISTS(
            SELECT 1 FROM milb_batter_pitches mp
            WHERE mp.mlb_batter_id = p.mlb_player_id::INTEGER
            AND mp.season = 2025
        )
""")
batters_missing_2025 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.position NOT IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND p.mlb_player_id IS NOT NULL
        AND NOT EXISTS(
            SELECT 1 FROM milb_batter_pitches mp
            WHERE mp.mlb_batter_id = p.mlb_player_id::INTEGER
            AND mp.season = 2024
        )
""")
batters_missing_2024 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND p.mlb_player_id IS NOT NULL
        AND NOT EXISTS(
            SELECT 1 FROM milb_pitcher_pitches mpp
            WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER
            AND mpp.season = 2025
        )
""")
pitchers_missing_2025 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND p.mlb_player_id IS NOT NULL
        AND NOT EXISTS(
            SELECT 1 FROM milb_pitcher_pitches mpp
            WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER
            AND mpp.season = 2024
        )
""")
pitchers_missing_2024 = cur.fetchone()[0]

print(f'Batters missing 2025 data:      {batters_missing_2025:,} / {batters:,} ({100*batters_missing_2025/batters:.1f}%)')
print(f'Batters missing 2024 data:      {batters_missing_2024:,} / {batters:,} ({100*batters_missing_2024/batters:.1f}%)')
print(f'Pitchers missing 2025 data:     {pitchers_missing_2025:,} / {pitchers:,} ({100*pitchers_missing_2025/pitchers:.1f}%)')
print(f'Pitchers missing 2024 data:     {pitchers_missing_2024:,} / {pitchers:,} ({100*pitchers_missing_2024/pitchers:.1f}%)')

# 8. OVERALL TOTALS
print('\n[OVERALL DATABASE TOTALS]')
print('-'*90)

total_all_pitches = total_pitches_2025 + total_pitches_2024 + total_pitcher_pitches_2025 + total_pitcher_pitches_2024
total_all_pa = total_pa_2025 + total_pa_2024 + total_appearances_2025 + total_appearances_2024

print(f'Total Pitches (all types):      {total_all_pitches:,}')
print(f'Total Appearances/PAs:          {total_all_pa:,}')

print('\n' + '='*90)

conn.close()
