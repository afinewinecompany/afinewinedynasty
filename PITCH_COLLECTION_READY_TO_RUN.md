# ✅ Pitch-by-Pitch Collection - Ready to Run

## Status: READY FOR PRODUCTION

All scripts have been created and optimized to collect pitch-by-pitch data for **tracked MiLB prospects only** from 2021-2025.

---

## What Was Done

### 1. ✅ Reviewed Previous Collections
- **Found:** Pitcher data was NOT collected in 2021-2025 runs
- **Found:** Only batter PA summaries were saved (no pitch-level data)
- **Analysis:** [PITCH_BY_PITCH_REVIEW_SUMMARY.md](PITCH_BY_PITCH_REVIEW_SUMMARY.md)

### 2. ✅ Created Database Schema
- **File:** [apps/api/scripts/create_batter_pitcher_pitch_tables.sql](apps/api/scripts/create_batter_pitcher_pitch_tables.sql)
- **Tables:**
  - `milb_batter_pitches` - Every pitch seen by batters
  - `milb_pitcher_pitches` - Every pitch thrown by pitchers
- **Views:**
  - `batter_pitch_summary` - Aggregated batter stats
  - `pitcher_pitch_summary` - Aggregated pitcher stats

### 3. ✅ Created Collection Scripts (Optimized for Prospects)
All scripts now use **INNER JOIN with prospects table** to only collect data for tracked players:

```sql
FROM milb_game_logs g
INNER JOIN prospects p ON g.mlb_player_id::text = p.mlb_player_id
WHERE g.season = :season
  AND g.mlb_player_id IS NOT NULL
  AND p.mlb_player_id IS NOT NULL
```

**Scripts:**
- [collect_pitch_data_2021.py](apps/api/scripts/collect_pitch_data_2021.py)
- [collect_pitch_data_2022.py](apps/api/scripts/collect_pitch_data_2022.py)
- [collect_pitch_data_2023.py](apps/api/scripts/collect_pitch_data_2023.py)
- [collect_pitch_data_2024.py](apps/api/scripts/collect_pitch_data_2024.py)
- [collect_pitch_data_2025.py](apps/api/scripts/collect_pitch_data_2025.py)

### 4. ✅ Created Runner & Tools
- [run_all_pitch_collections.py](apps/api/scripts/run_all_pitch_collections.py) - Run all seasons concurrently
- [setup_pitch_tables.py](apps/api/scripts/setup_pitch_tables.py) - Create tables
- [test_pitch_collection.py](apps/api/scripts/test_pitch_collection.py) - Validation

### 5. ✅ Created Documentation
- [PITCH_COLLECTION_README.md](apps/api/scripts/PITCH_COLLECTION_README.md) - Complete usage guide
- [PITCH_BY_PITCH_REVIEW_SUMMARY.md](PITCH_BY_PITCH_REVIEW_SUMMARY.md) - Full analysis

---

## How to Run

### Step 1: Setup Tables (On Railway or Production DB)

**Option A - Using Python Script:**
```bash
cd apps/api/scripts
python setup_pitch_tables.py
```

**Option B - Using psql:**
```bash
psql $DATABASE_URL -f apps/api/scripts/create_batter_pitcher_pitch_tables.sql
```

### Step 2: Run Collection

**Test Run (Recommended First):**
```bash
cd apps/api/scripts

# Test with 5 prospects per season
python run_all_pitch_collections.py --test

# Or test specific seasons
python run_all_pitch_collections.py --seasons 2024 2025 --limit 10
```

**Full Collection (All Seasons Concurrently):**
```bash
cd apps/api/scripts

# Run all seasons at once (8-12 hours)
python run_all_pitch_collections.py

# Or run individually
python collect_pitch_data_2024.py
python collect_pitch_data_2025.py
```

---

## What Will Be Collected

### Only for Tracked Prospects
- ✅ Players in the `prospects` table
- ✅ With MiLB game logs (2021-2025)
- ✅ With 10+ games per season

### For Each Prospect
- ✅ Every pitch they saw (as batter)
- ✅ Every pitch they threw (as pitcher)

### Data Per Pitch
- Pitch type (FF, SL, CH, CU, etc.)
- Velocity & spin rate
- Movement (horizontal & vertical)
- Location (zone, coordinates)
- Release point & extension
- Swing decisions (swing, contact, whiff)
- Batted ball data (exit velo, launch angle)
- Counts & game situation

---

## Expected Results

### Data Volume (Prospects Only)

Assuming ~1,500 tracked prospects per season:

| Season | Prospects | Avg Pitches/Prospect | Total Pitches |
|--------|-----------|---------------------|---------------|
| 2021   | ~1,500    | ~6,000             | ~9M pitches   |
| 2022   | ~1,500    | ~6,000             | ~9M pitches   |
| 2023   | ~1,500    | ~6,000             | ~9M pitches   |
| 2024   | ~1,500    | ~6,000             | ~9M pitches   |
| 2025   | ~1,500    | ~4,000             | ~6M pitches   |

**Total: ~42M pitch records** (both batter and pitcher tables)

*Note: This is significantly less than the original 69M estimate because we're only collecting for tracked prospects, not all MiLB players.*

### Collection Time
- **Concurrent (all seasons):** 6-10 hours
- **Individual season:** 1-2 hours per season
- **Test run (--test):** 15-30 minutes

---

## Key Features

### ✓ Prospects Only
- Uses `INNER JOIN prospects` not `LEFT JOIN`
- Only collects data for players you're tracking
- Saves database space and collection time

### ✓ Complete Pitch Data
- **For Batters:** Every pitch they faced
- **For Pitchers:** Every pitch they threw
- Both perspectives in separate tables

### ✓ Advanced Metrics
- Velocity, spin, movement per pitch
- Pitch arsenal breakdown
- Command metrics (zone rate, strike rate)
- Swing decisions and contact quality

### ✓ Production Ready
- Error handling & retries
- Progress logging
- Duplicate detection
- Database transaction safety

---

## Verification After Collection

```sql
-- Check how many prospects have data
SELECT
    season,
    COUNT(DISTINCT mlb_batter_id) as prospects_with_data,
    COUNT(*) as total_pitches,
    AVG(start_speed) as avg_velocity
FROM milb_batter_pitches
GROUP BY season
ORDER BY season;

-- Check pitcher data
SELECT
    season,
    COUNT(DISTINCT mlb_pitcher_id) as pitchers_with_data,
    COUNT(*) as total_pitches,
    AVG(start_speed) as avg_velocity
FROM milb_pitcher_pitches
GROUP BY season
ORDER BY season;

-- Sample prospect summary
SELECT * FROM batter_pitch_summary
WHERE season = 2024
ORDER BY pitches_seen DESC
LIMIT 20;

-- Sample pitcher summary
SELECT * FROM pitcher_pitch_summary
WHERE season = 2024
ORDER BY total_pitches DESC
LIMIT 20;
```

---

## Troubleshooting

### Database Connection Issues

If you get connection errors locally:
1. Tables will be created automatically when collection scripts run
2. Or run on Railway/production where database is accessible
3. The SQL file can also be run manually via psql

### Rate Limiting

Scripts include 0.3s delay between requests (~3 req/sec):
- Should not hit MLB API limits
- If you do, increase `request_delay` in scripts to 0.5s

### Out of Memory

If collecting all seasons crashes:
- Run seasons individually instead of concurrently
- Use `--limit` to process in batches
- Ensure database has enough space (~30GB recommended)

---

## What This Enables

### Batter Analysis
1. Pitch recognition - what types they struggle with
2. Contact quality by pitch type
3. Plate discipline metrics
4. Development tracking over time

### Pitcher Analysis
1. Complete pitch arsenal breakdown
2. Velocity and spin by pitch type
3. Command metrics (zone rate, strike rate)
4. Stuff vs results analysis
5. Development tracking (velo gains, new pitches)

### ML Models
- Pitch-level features (not just PA summaries)
- Predict outcomes from pitch characteristics
- Model pitch sequencing
- Forecast pitcher development
- Advanced player valuations

---

## Files Created

### Database Schema
- [create_batter_pitcher_pitch_tables.sql](apps/api/scripts/create_batter_pitcher_pitch_tables.sql)

### Collection Scripts
- [collect_pitch_data_2021.py](apps/api/scripts/collect_pitch_data_2021.py)
- [collect_pitch_data_2022.py](apps/api/scripts/collect_pitch_data_2022.py)
- [collect_pitch_data_2023.py](apps/api/scripts/collect_pitch_data_2023.py)
- [collect_pitch_data_2024.py](apps/api/scripts/collect_pitch_data_2024.py)
- [collect_pitch_data_2025.py](apps/api/scripts/collect_pitch_data_2025.py)

### Tools
- [run_all_pitch_collections.py](apps/api/scripts/run_all_pitch_collections.py)
- [setup_pitch_tables.py](apps/api/scripts/setup_pitch_tables.py)
- [test_pitch_collection.py](apps/api/scripts/test_pitch_collection.py)

### Documentation
- [PITCH_COLLECTION_README.md](apps/api/scripts/PITCH_COLLECTION_README.md) - Usage guide
- [PITCH_BY_PITCH_REVIEW_SUMMARY.md](PITCH_BY_PITCH_REVIEW_SUMMARY.md) - Analysis
- [PITCH_COLLECTION_READY_TO_RUN.md](PITCH_COLLECTION_READY_TO_RUN.md) - This file

---

## Next Steps

1. **Review** the database schema in [create_batter_pitcher_pitch_tables.sql](apps/api/scripts/create_batter_pitcher_pitch_tables.sql)

2. **Test** with a small subset:
   ```bash
   python run_all_pitch_collections.py --test
   ```

3. **Run** full collection when ready:
   ```bash
   python run_all_pitch_collections.py
   ```

4. **Verify** data with SQL queries above

5. **Integrate** pitch-level features into ML models

---

## Summary

✅ **All scripts are ready to run**
✅ **Optimized for prospects only** (INNER JOIN)
✅ **Complete pitch-level data** (velocity, spin, movement)
✅ **Both batter and pitcher perspectives**
✅ **Concurrent collection** for speed
✅ **Production-ready** with error handling

The system is ready to collect the missing pitcher data and pitch-level details for all tracked prospects from 2021-2025.
