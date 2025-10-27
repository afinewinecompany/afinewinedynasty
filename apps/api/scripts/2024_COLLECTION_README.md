# 2024 MiLB Data Collection Scripts

## Overview

These scripts collect comprehensive 2024 MiLB data for all prospects in the database, with built-in retry logic, error handling, and deduplication to avoid collecting data that already exists.

## Scripts Created

### 1. `collect_2024_batter_data_robust.py`
- Collects 2024 batter data (plate appearances and pitch-by-pitch)
- Properly filters out ALL pitcher positions (P, SP, RP, RHP, LHP, PITCHER)
- Skips prospects that already have complete 2024 data
- Uses retry logic with exponential backoff
- Processes ~729 batters needing data

### 2. `collect_2024_pitcher_data_robust.py`
- Collects 2024 pitcher data (game logs and pitch-by-pitch)
- Collects pitching stats (innings pitched, strikeouts, walks, etc.)
- Skips prospects that already have complete 2024 data
- Uses retry logic with exponential backoff
- Processes ~440 pitchers needing data

### 3. `START_2024_COLLECTIONS.bat`
- Batch file to launch both collections in parallel
- Opens separate windows for each collection
- Creates log files for monitoring

## Current 2024 Data Status

### Batters
- **With PAs**: 902/855 (105.5% - some in multiple leagues)
- **With pitch data**: 133/855 (15.6%)
- **Need collection**: 729 batters

### Pitchers
- **With game logs**: 0/440 (0.0%)
- **With pitch data**: 22/440 (5.0%)
- **Need collection**: 440 pitchers

## Features

### Deduplication
Both scripts use `ON CONFLICT ... DO NOTHING` clauses to prevent duplicate data:
- Batters: `(mlb_player_id, game_pk, season)` for PAs
- Batters: `(mlb_batter_id, game_pk, pitch_number, season)` for pitches
- Pitchers: `(mlb_player_id, game_pk, season)` for appearances
- Pitchers: `(mlb_pitcher_id, game_pk, pitch_number, season)` for pitches

### Retry Logic
- **Max retries**: 3 attempts per API call
- **Exponential backoff**: 1s, 2s, 4s delays
- **Timeout handling**: 30-second timeout per request
- **Rate limit handling**: Detects 429 status and retries

### Connection Pooling
- **Connection limit**: 10 concurrent connections
- **Per-host limit**: 5 connections per host
- Prevents overwhelming the MLB Stats API

### Progress Tracking
- Progress reports every 25 prospects
- Real-time logging to both console and log files
- Tracks successful collections, no-data cases, and failures

## Running the Collections

### Option 1: Use the Batch File (Recommended)
```bash
cd apps/api/scripts
START_2024_COLLECTIONS.bat
```

This will:
1. Start the batter collection in one window
2. Wait 5 seconds
3. Start the pitcher collection in another window
4. Create log files in `logs/` directory

### Option 2: Run Individually

**Batter Collection:**
```bash
cd apps/api/scripts
python collect_2024_batter_data_robust.py
```

**Pitcher Collection:**
```bash
cd apps/api/scripts
python collect_2024_pitcher_data_robust.py
```

### Option 3: Run in Background (Python)
```python
import subprocess

# Start batter collection
batter_proc = subprocess.Popen(
    ["python", "collect_2024_batter_data_robust.py"],
    cwd="apps/api/scripts"
)

# Start pitcher collection
pitcher_proc = subprocess.Popen(
    ["python", "collect_2024_pitcher_data_robust.py"],
    cwd="apps/api/scripts"
)
```

## Monitoring Progress

### Check Log Files
```bash
# Batter collection
tail -f apps/api/scripts/logs/2024_batter_collection.log

# Pitcher collection
tail -f apps/api/scripts/logs/2024_pitcher_collection.log
```

### Check Database Status
```sql
-- Batter data collected
SELECT
    COUNT(DISTINCT mlb_player_id) as batters_with_pas,
    COUNT(*) as total_pas
FROM milb_plate_appearances
WHERE season = 2024;

SELECT
    COUNT(DISTINCT mlb_batter_id) as batters_with_pitches,
    COUNT(*) as total_pitches
FROM milb_batter_pitches
WHERE season = 2024;

-- Pitcher data collected
SELECT
    COUNT(DISTINCT mlb_player_id) as pitchers_with_games,
    COUNT(*) as total_games
FROM milb_pitcher_appearances
WHERE season = 2024;

SELECT
    COUNT(DISTINCT mlb_pitcher_id) as pitchers_with_pitches,
    COUNT(*) as total_pitches
FROM milb_pitcher_pitches
WHERE season = 2024;
```

## Expected Results

Based on 2025 collection results:

### Batters
- **Success rate**: ~30-40% (many prospects didn't play in 2024)
- **Expected PAs**: 200,000 - 300,000
- **Expected pitches**: 400,000 - 600,000
- **Runtime**: 6-10 hours

### Pitchers
- **Success rate**: ~80-90% (high success rate for pitchers)
- **Expected games**: 2,500 - 3,500
- **Expected pitches**: 200,000 - 250,000
- **Runtime**: 4-6 hours

## Comparison to 2025 Collection

The 2025 collection achieved:
- **Batters**: 104,414 PAs, 402,764 pitches (233 prospects)
- **Pitchers**: 3,935 games, 273,476 pitches (185 pitchers)

The 2024 collection should achieve similar or slightly higher numbers since more prospects were active in 2024 (full season vs partial 2025 season).

## Troubleshooting

### Script Fails to Start
- Check Python is installed: `python --version`
- Check dependencies: `pip install aiohttp psycopg2`
- Check database connection in script

### Rate Limiting
- Scripts have built-in retry logic for 429 errors
- If persistent, increase `RETRY_DELAY` in script

### Database Connection Errors
- Verify database credentials in `DB_CONFIG`
- Check Railway database is accessible
- Ensure connection string is correct

### No Data Found
- Many prospects didn't play in 2024 (injured, promoted, etc.)
- This is expected - success rate is ~30-40% for batters, ~80-90% for pitchers

## Files Created

```
apps/api/scripts/
├── collect_2024_batter_data_robust.py
├── collect_2024_pitcher_data_robust.py
├── START_2024_COLLECTIONS.bat
├── test_2024_collection_sample.py
└── logs/
    ├── 2024_batter_collection.log
    └── 2024_pitcher_collection.log
```

## Next Steps

After collections complete:
1. Run `check_2024_status.py` to verify data collected
2. Compare 2024 vs 2025 data coverage
3. Identify any gaps or missing data
4. Consider running 2023 collection if needed
