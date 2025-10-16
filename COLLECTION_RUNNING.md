# 🚀 Full Pitch Collection - NOW RUNNING

## Status: COLLECTION IN PROGRESS

Full pitch-by-pitch data collection is running for **ALL seasons (2021-2025)** and **ALL MiLB players**.

---

## What's Collecting

### Seasons: 2021, 2022, 2023, 2024, 2025 (All concurrent)
- **Players per season:** ~3,000-5,000 MiLB players with 10+ games
- **Total players:** ~16,196 unique players
- **Expected pitches:** ~75-100M total pitch records
- **Expected time:** 12-18 hours

### Your Prospects Covered
- **Total prospects:** 1,274
- **Linkable via FanGraphs ID:** 1,270 (99.7%)
- **Linkable via MLB ID (Chadwick):** 12
- **Strategy:** Collect all, link after via FanGraphs unified grades

---

## Monitor Collection Progress

### Check Database
```sql
-- Overall progress
SELECT
    season,
    COUNT(*) as total_pitches,
    COUNT(DISTINCT mlb_batter_id) as unique_batters,
    MAX(created_at) as last_update,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as pitches_last_hour
FROM milb_batter_pitches
GROUP BY season
ORDER BY season;

-- Pitcher data
SELECT
    season,
    COUNT(*) as total_pitches,
    COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers
FROM milb_pitcher_pitches
GROUP BY season
ORDER BY season;

-- Recent activity
SELECT
    COUNT(*) as pitches_last_10min,
    COUNT(DISTINCT mlb_batter_id) as players_last_10min
FROM milb_batter_pitches
WHERE created_at > NOW() - INTERVAL '10 minutes';
```

### Check Script Output
```bash
# View latest log file
cd apps/api/scripts
tail -f full_collection_*.log

# Or check specific collection
tail -f ~/.pybaseball/cache/*.log
```

### Quick Python Check
```python
cd apps/api && python -c "
import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('SQLALCHEMY_DATABASE_URI').replace('postgresql+asyncpg://', 'postgresql://')
engine = create_engine(db_url)

with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM milb_batter_pitches'))
    print(f'Total pitches collected: {result.scalar():,}')
"
```

---

## After Collection: Link to Your Prospects

Once collection completes, use these queries to access YOUR prospect data:

### Method 1: Via fangraphs_unified_grades (RECOMMENDED)

This will link your 1,270 prospects:

```sql
-- Create a view for easy access
CREATE VIEW prospect_pitch_data AS
SELECT
    p.name as prospect_name,
    p.organization,
    p.position,
    fg.year as fg_year,
    bp.*
FROM milb_batter_pitches bp
INNER JOIN fangraphs_unified_grades fg ON bp.mlb_batter_id = fg.mlb_player_id
INNER JOIN prospects p ON fg.fg_player_id = p.fg_player_id
WHERE fg.mlb_player_id IS NOT NULL;

-- Use it
SELECT
    prospect_name,
    organization,
    COUNT(*) as pitches_seen,
    AVG(start_speed) as avg_pitch_velo,
    COUNT(CASE WHEN swing THEN 1 END) as swings,
    COUNT(CASE WHEN contact THEN 1 END) as contacts,
    ROUND(COUNT(CASE WHEN contact THEN 1 END)::NUMERIC /
          NULLIF(COUNT(CASE WHEN swing THEN 1 END), 0) * 100, 1) as contact_pct
FROM prospect_pitch_data
GROUP BY prospect_name, organization
ORDER BY pitches_seen DESC;
```

### Method 2: Via prospects table (for 12 matched)

```sql
SELECT
    p.name,
    p.organization,
    COUNT(*) as pitches,
    AVG(bp.start_speed) as avg_velo
FROM milb_batter_pitches bp
INNER JOIN prospects p ON bp.mlb_batter_id::text = p.mlb_player_id
WHERE p.mlb_player_id IS NOT NULL
GROUP BY p.name, p.organization;
```

### Method 3: Via player_id_mapping

```sql
SELECT
    pm.fg_id,
    COUNT(*) as pitches
FROM milb_batter_pitches bp
INNER JOIN player_id_mapping pm ON bp.mlb_batter_id = pm.mlb_id
WHERE pm.fg_id IS NOT NULL
GROUP BY pm.fg_id;
```

---

## Populate fangraphs_unified_grades.mlb_player_id

To make linking easier, update the unified grades table with MLB IDs:

```sql
-- Add mlb_player_id column if not exists
ALTER TABLE fangraphs_unified_grades
ADD COLUMN IF NOT EXISTS mlb_player_id INTEGER;

-- Populate from milb_players (name matching)
UPDATE fangraphs_unified_grades fg
SET mlb_player_id = mp.mlb_player_id
FROM milb_players mp
WHERE fg.player_name = mp.name
AND fg.mlb_player_id IS NULL
AND mp.mlb_player_id IS NOT NULL;

-- Check coverage
SELECT
    COUNT(*) as total_fg_players,
    COUNT(mlb_player_id) as with_mlb_id,
    ROUND(COUNT(mlb_player_id)::NUMERIC / COUNT(*) * 100, 1) as coverage_pct
FROM fangraphs_unified_grades;
```

---

## Expected Timeline

### Hour 0-2: Initial Setup
- All 5 season scripts start
- Begin fetching player lists
- Start collecting first games

### Hour 2-6: Active Collection
- ~20-30% complete
- All seasons running concurrently
- Steady pitch accumulation

### Hour 6-12: Main Collection
- ~50-80% complete
- Most active period
- Database growing rapidly

### Hour 12-18: Completion
- ~80-100% complete
- Scripts finishing up
- Final games processed

### After 18 hours
- All collections should be complete
- Ready for prospect linkage
- Ready for ML feature engineering

---

## Troubleshooting

### If Collection Stops
```bash
# Check running processes
ps aux | grep python | grep collect_pitch

# Restart specific season
cd apps/api/scripts
python collect_pitch_data_2024.py

# Or restart all
python run_all_pitch_collections.py --seasons 2021 2022 2023 2024 2025
```

### If Database Connection Lost
- Scripts have automatic retry logic
- Will resume from last successful commit
- No duplicate data (UNIQUE constraints)

### If Rate Limited by MLB API
- Scripts include 0.3s delay (built-in rate limiting)
- Will slow down automatically if needed
- Increase delay in scripts if necessary

---

## Next Steps After Collection

### 1. Verify Coverage
```sql
SELECT COUNT(DISTINCT fg_player_id)
FROM prospects p
WHERE EXISTS (
    SELECT 1 FROM prospect_pitch_data ppd
    WHERE ppd.prospect_name = p.name
);
```

### 2. Create Aggregate Features
```sql
-- Per-prospect season summaries
CREATE TABLE prospect_pitch_summaries AS
SELECT
    prospect_name,
    organization,
    season,
    COUNT(*) as pitches_seen,
    AVG(start_speed) as avg_pitch_velo,
    COUNT(DISTINCT pitch_type) as pitch_types_seen,
    AVG(CASE WHEN pitch_type LIKE 'FF%' THEN start_speed END) as avg_fb_velo_faced,
    COUNT(CASE WHEN swing THEN 1 END) as total_swings,
    COUNT(CASE WHEN contact THEN 1 END) as total_contacts,
    COUNT(CASE WHEN swing_and_miss THEN 1 END) as total_whiffs,
    AVG(launch_speed) FILTER (WHERE launch_speed IS NOT NULL) as avg_exit_velo,
    AVG(launch_angle) FILTER (WHERE launch_angle IS NOT NULL) as avg_launch_angle
FROM prospect_pitch_data
GROUP BY prospect_name, organization, season;
```

### 3. Build ML Features
- Pitch recognition metrics
- Contact quality profiles
- Swing decision analytics
- Matchup analysis (vs pitch types)
- Development tracking (year-over-year)

---

## Files & Logs

### Collection Scripts Running
- collect_pitch_data_2021.py
- collect_pitch_data_2022.py
- collect_pitch_data_2023.py
- collect_pitch_data_2024.py
- collect_pitch_data_2025.py

### Log Files
- `apps/api/scripts/full_collection_YYYYMMDD_HHMMSS.log`

### Database Tables
- `milb_batter_pitches` - Batter pitch data
- `milb_pitcher_pitches` - Pitcher pitch data
- `batter_pitch_summary` - Aggregated view
- `pitcher_pitch_summary` - Aggregated view

---

## Summary

✅ **Collection RUNNING** for all 5 seasons
✅ **16,196 MiLB players** will be collected
✅ **1,270 of your prospects** will be linkable via FanGraphs
✅ **~75-100M pitches** will be captured
✅ **12-18 hours** estimated completion

The collection will run automatically. Check back in a few hours to monitor progress!
