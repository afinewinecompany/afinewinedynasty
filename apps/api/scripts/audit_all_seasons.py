import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print('\n' + '='*100)
print('COMPLETE HISTORICAL DATA AUDIT - SEASONS 2021-2025')
print('='*100)
print(f'Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('='*100)

# Get total prospects
cur.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER') THEN 1 END) as pitchers,
        COUNT(CASE WHEN position NOT IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER') THEN 1 END) as batters
    FROM prospects
    WHERE mlb_player_id IS NOT NULL
""")
total, pitchers, batters = cur.fetchone()

print(f'\nTotal Prospects: {total:,} ({pitchers:,} pitchers, {batters:,} batters)')
print('='*100)

seasons = [2021, 2022, 2023, 2024, 2025]

# BATTER DATA SUMMARY
print('\n' + '='*100)
print('BATTER DATA COVERAGE BY SEASON')
print('='*100)
print(f'{"Season":>6} | {"Batters w/ PA":>15} | {"Coverage":>10} | {"Total PAs":>12} | {"Batters w/ Pitches":>18} | {"Coverage":>10} | {"Total Pitches":>15}')
print('-'*100)

batter_summary = {}
for season in seasons:
    # Plate Appearances
    cur.execute("""
        SELECT COUNT(DISTINCT mlb_player_id)
        FROM milb_plate_appearances
        WHERE season = %s
    """, (season,))
    batters_with_pa = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*)
        FROM milb_plate_appearances
        WHERE season = %s
    """, (season,))
    total_pa = cur.fetchone()[0] or 0

    # Pitch Data
    cur.execute("""
        SELECT COUNT(DISTINCT mlb_batter_id)
        FROM milb_batter_pitches
        WHERE season = %s
    """, (season,))
    batters_with_pitches = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*)
        FROM milb_batter_pitches
        WHERE season = %s
    """, (season,))
    total_pitches = cur.fetchone()[0] or 0

    batter_summary[season] = {
        'pa_count': batters_with_pa,
        'pa_total': total_pa,
        'pitch_count': batters_with_pitches,
        'pitch_total': total_pitches
    }

    pa_pct = (batters_with_pa / batters * 100) if batters > 0 else 0
    pitch_pct = (batters_with_pitches / batters * 100) if batters > 0 else 0

    print(f'{season:>6} | {batters_with_pa:>15,} | {pa_pct:>9.1f}% | {total_pa:>12,} | {batters_with_pitches:>18,} | {pitch_pct:>9.1f}% | {total_pitches:>15,}')

# PITCHER DATA SUMMARY
print('\n' + '='*100)
print('PITCHER DATA COVERAGE BY SEASON')
print('='*100)
print(f'{"Season":>6} | {"Pitchers w/ App":>16} | {"Coverage":>10} | {"Total Apps":>12} | {"Pitchers w/ Pitches":>19} | {"Coverage":>10} | {"Total Pitches":>15}')
print('-'*100)

pitcher_summary = {}
for season in seasons:
    # Appearances
    cur.execute("""
        SELECT COUNT(DISTINCT mlb_player_id)
        FROM milb_pitcher_appearances
        WHERE season = %s
    """, (season,))
    pitchers_with_app = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*)
        FROM milb_pitcher_appearances
        WHERE season = %s
    """, (season,))
    total_app = cur.fetchone()[0] or 0

    # Pitch Data
    cur.execute("""
        SELECT COUNT(DISTINCT mlb_pitcher_id)
        FROM milb_pitcher_pitches
        WHERE season = %s
    """, (season,))
    pitchers_with_pitches = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*)
        FROM milb_pitcher_pitches
        WHERE season = %s
    """, (season,))
    total_pitches = cur.fetchone()[0] or 0

    pitcher_summary[season] = {
        'app_count': pitchers_with_app,
        'app_total': total_app,
        'pitch_count': pitchers_with_pitches,
        'pitch_total': total_pitches
    }

    app_pct = (pitchers_with_app / pitchers * 100) if pitchers > 0 else 0
    pitch_pct = (pitchers_with_pitches / pitchers * 100) if pitchers > 0 else 0

    print(f'{season:>6} | {pitchers_with_app:>16,} | {app_pct:>9.1f}% | {total_app:>12,} | {pitchers_with_pitches:>19,} | {pitch_pct:>9.1f}% | {total_pitches:>15,}')

# DETAILED GAPS ANALYSIS
print('\n' + '='*100)
print('COVERAGE GAPS ANALYSIS')
print('='*100)

for season in seasons:
    print(f'\n--- {season} Season ---')

    # Batters missing PA data
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.position NOT IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
            AND p.mlb_player_id IS NOT NULL
            AND NOT EXISTS(
                SELECT 1 FROM milb_plate_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
                AND mpa.season = %s
            )
    """, (season,))
    batters_missing_pa = cur.fetchone()[0]

    # Batters missing pitch data
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.position NOT IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
            AND p.mlb_player_id IS NOT NULL
            AND NOT EXISTS(
                SELECT 1 FROM milb_batter_pitches mbp
                WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER
                AND mbp.season = %s
            )
    """, (season,))
    batters_missing_pitches = cur.fetchone()[0]

    # Pitchers missing appearance data
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
            AND p.mlb_player_id IS NOT NULL
            AND NOT EXISTS(
                SELECT 1 FROM milb_pitcher_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
                AND mpa.season = %s
            )
    """, (season,))
    pitchers_missing_app = cur.fetchone()[0]

    # Pitchers missing pitch data
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
            AND p.mlb_player_id IS NOT NULL
            AND NOT EXISTS(
                SELECT 1 FROM milb_pitcher_pitches mpp
                WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER
                AND mpp.season = %s
            )
    """, (season,))
    pitchers_missing_pitches = cur.fetchone()[0]

    ba_pa_pct = (batters_missing_pa / batters * 100) if batters > 0 else 0
    ba_pi_pct = (batters_missing_pitches / batters * 100) if batters > 0 else 0
    pi_ap_pct = (pitchers_missing_app / pitchers * 100) if pitchers > 0 else 0
    pi_pi_pct = (pitchers_missing_pitches / pitchers * 100) if pitchers > 0 else 0

    print(f'  Batters missing PA data:       {batters_missing_pa:>4,} / {batters:,} ({ba_pa_pct:>5.1f}%)')
    print(f'  Batters missing pitch data:    {batters_missing_pitches:>4,} / {batters:,} ({ba_pi_pct:>5.1f}%)')
    print(f'  Pitchers missing appearances:  {pitchers_missing_app:>4,} / {pitchers:,} ({pi_ap_pct:>5.1f}%)')
    print(f'  Pitchers missing pitch data:   {pitchers_missing_pitches:>4,} / {pitchers:,} ({pi_pi_pct:>5.1f}%)')

# OVERALL TOTALS
print('\n' + '='*100)
print('OVERALL DATABASE TOTALS (2021-2025)')
print('='*100)

total_batter_pa = sum(s['pa_total'] for s in batter_summary.values())
total_batter_pitches = sum(s['pitch_total'] for s in batter_summary.values())
total_pitcher_app = sum(s['app_total'] for s in pitcher_summary.values())
total_pitcher_pitches = sum(s['pitch_total'] for s in pitcher_summary.values())
total_all_pitches = total_batter_pitches + total_pitcher_pitches
total_all_events = total_batter_pa + total_pitcher_app

print(f'Total Plate Appearances:        {total_batter_pa:>15,}')
print(f'Total Batter Pitches:           {total_batter_pitches:>15,}')
print(f'Total Pitcher Appearances:      {total_pitcher_app:>15,}')
print(f'Total Pitcher Pitches:          {total_pitcher_pitches:>15,}')
print(f'Total All Pitches:              {total_all_pitches:>15,}')
print(f'Total All Events:               {total_all_events:>15,}')

# PRIORITY RECOMMENDATIONS
print('\n' + '='*100)
print('RECOMMENDATIONS FOR DATA COLLECTION')
print('='*100)

print('\nHIGH PRIORITY GAPS (pitch-by-pitch data):')
for season in seasons:
    pitcher_gap = pitcher_summary[season]['app_count'] - pitcher_summary[season]['pitch_count']
    batter_gap_pct = ((batters - batter_summary[season]['pitch_count']) / batters * 100) if batters > 0 else 0
    pitcher_gap_pct = ((pitchers - pitcher_summary[season]['pitch_count']) / pitchers * 100) if pitchers > 0 else 0

    if pitcher_gap_pct > 20 or batter_gap_pct > 30:
        print(f'\n  {season}:')
        if batter_gap_pct > 30:
            missing = batters - batter_summary[season]['pitch_count']
            print(f'    - Batter pitch data: {missing:,} batters missing ({batter_gap_pct:.1f}% gap)')
        if pitcher_gap_pct > 20:
            missing = pitchers - pitcher_summary[season]['pitch_count']
            print(f'    - Pitcher pitch data: {missing:,} pitchers missing ({pitcher_gap_pct:.1f}% gap)')

print('\n' + '='*100)

conn.close()
