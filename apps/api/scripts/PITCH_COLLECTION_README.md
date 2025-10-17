# Pitch-by-Pitch Data Collection for 2021-2025

## Overview

This collection system gathers **detailed pitch-level data** for both **batters** and **pitchers** from the MLB Stats API for all MiLB players from 2021-2025.

### What Data is Collected?

#### For Batters (`milb_batter_pitches` table):
- Every pitch faced by each batter
- Pitch type, velocity, spin rate, movement
- Pitch location and swing decisions
- Contact quality and batted ball metrics
- Plate appearance outcomes

#### For Pitchers (`milb_pitcher_pitches` table):
- Every pitch thrown by each pitcher
- Pitch arsenal (fastball, slider, changeup, curve, etc.)
- Velocity, spin, and movement for each pitch
- Command (zone rate, strike rate)
- Batted ball data allowed
- Plate appearance outcomes

---

## Database Schema

### Setup Tables

Run this SQL script first to create the tables:

```bash
psql -d your_database -f create_batter_pitcher_pitch_tables.sql
```

This creates:
- `milb_batter_pitches` - Pitch-level data from batter perspective
- `milb_pitcher_pitches` - Pitch-level data from pitcher perspective
- `batter_pitch_summary` - Aggregated view for batters
- `pitcher_pitch_summary` - Aggregated view for pitchers

### Key Fields

**Pitch Identification:**
- `pitch_type` - FF (4-seam), SL (slider), CH (changeup), CU (curve), etc.
- `start_speed` - Release velocity (mph)
- `spin_rate` - Spin rate (rpm)
- `pfx_x`, `pfx_z` - Horizontal and vertical movement

**Results:**
- `is_strike` - Strike or ball
- `swing`, `contact`, `swing_and_miss` - Swing decisions
- `launch_speed`, `launch_angle` - Batted ball metrics

---

## Collection Scripts

### Individual Season Scripts

Run each season independently:

```bash
# Full collection for 2021
python collect_pitch_data_2021.py

# Test with 100 players
python collect_pitch_data_2021.py --limit 100

# Available scripts:
# - collect_pitch_data_2021.py
# - collect_pitch_data_2022.py
# - collect_pitch_data_2023.py
# - collect_pitch_data_2024.py
# - collect_pitch_data_2025.py
```

### Concurrent Collection (RECOMMENDED)

Run all seasons simultaneously for faster collection:

```bash
# Test mode (5 players per season)
python run_all_pitch_collections.py --test

# Full collection (all seasons at once)
python run_all_pitch_collections.py

# Custom limit per season
python run_all_pitch_collections.py --limit 50

# Specific seasons only
python run_all_pitch_collections.py --seasons 2024 2025
```

**Advantages of concurrent collection:**
- 5x faster (all seasons run in parallel)
- Better use of API rate limits
- Collect all historical data in one run

---

## Expected Data Volume

### Per Season Estimates:

| Season | Players | Games/Player | Pitches/Game | Total Pitches |
|--------|---------|--------------|--------------|---------------|
| 2021   | ~2,000  | 50          | 150          | ~15M pitches  |
| 2022   | ~2,000  | 50          | 150          | ~15M pitches  |
| 2023   | ~2,000  | 50          | 150          | ~15M pitches  |
| 2024   | ~2,000  | 50          | 150          | ~15M pitches  |
| 2025   | ~2,000  | 30          | 150          | ~9M pitches   |

**Total Expected:** ~69 million pitch records (both batter and pitcher tables)

### Collection Time:

- Single season: 4-8 hours
- All seasons concurrent: 8-12 hours
- With `--limit 100`: 30-60 minutes (testing)

---

## API Rate Limiting

The scripts include built-in rate limiting:
- 0.3 second delay between requests (~3 requests/second)
- Respects MLB Stats API fair use
- Automatic retries on errors

**Note:** MLB Stats API is free and publicly available but should be used responsibly.

---

## Monitoring Progress

Each script logs progress:

```
[2021] - INFO - Found 1,847 players for 2021
[1/1847] John Doe (Los Angeles Dodgers)
  Processing John Doe (ID: 123456)
    Found 52 games
      Progress: 20/52 games
    Collected 2,847 pitches

Progress: 100/1847 players
Pitches collected: 1,245,823
Games processed: 5,234
Errors: 12
```

---

## What Makes This Different from Previous Collections?

### Previous Collections:
- ✗ Only collected **plate appearance** summaries
- ✗ No pitch-level data
- ✗ No pitcher data at all
- ✗ Limited Statcast metrics

### New Collections:
- ✓ **Every individual pitch** recorded
- ✓ **Both batter and pitcher** perspectives
- ✓ Complete pitch arsenal and usage data
- ✓ Detailed Statcast metrics (velocity, spin, movement)
- ✓ Pitch sequencing and results

---

## Use Cases

### For Batters:
1. **Pitch Recognition:** What pitch types does a batter see most?
2. **Swing Decisions:** Whiff rate, chase rate, contact rate by pitch type
3. **Batted Ball Quality:** Exit velocity, launch angle by pitch type
4. **Pitch Matchups:** Performance vs fastballs vs breaking balls

### For Pitchers:
1. **Pitch Arsenal:** Complete repertoire with usage rates
2. **Stuff Metrics:** Velocity, spin, movement by pitch type
3. **Command:** Strike rate, zone rate, location consistency
4. **Results:** Whiff rate, hard contact rate, outcomes by pitch
5. **Pitch Development:** Track velocity/spin changes over time

### For ML Models:
- Train on pitch-level features (not just game summaries)
- Predict outcomes based on pitch characteristics
- Model pitch sequencing strategies
- Forecast pitcher development (stuff metrics)

---

## Troubleshooting

### Database Connection Errors

```bash
# Check your .env file has:
SQLALCHEMY_DATABASE_URI=postgresql+asyncpg://user:pass@host:port/db
```

### Missing Tables

```bash
# Run schema creation first:
psql -d your_database -f create_batter_pitcher_pitch_tables.sql
```

### API Errors (429 - Too Many Requests)

The scripts include rate limiting, but if you hit limits:
- Increase `request_delay` in the script (default: 0.3s → try 0.5s)
- Run fewer seasons concurrently
- Use `--limit` to process in smaller batches

### Memory Issues

If collecting all seasons crashes due to memory:
- Run seasons individually instead of concurrently
- Process in batches with `--limit`
- Ensure database has enough disk space (~50GB recommended)

---

## Verification Queries

After collection, verify your data:

```sql
-- Check total pitches collected
SELECT
    season,
    COUNT(*) as total_pitches,
    COUNT(DISTINCT mlb_batter_id) as unique_batters
FROM milb_batter_pitches
GROUP BY season
ORDER BY season;

-- Check pitcher data
SELECT
    season,
    COUNT(*) as total_pitches,
    COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers
FROM milb_pitcher_pitches
GROUP BY season
ORDER BY season;

-- Sample batter summary
SELECT * FROM batter_pitch_summary
WHERE season = 2024
ORDER BY pitches_seen DESC
LIMIT 10;

-- Sample pitcher summary
SELECT * FROM pitcher_pitch_summary
WHERE season = 2024
ORDER BY total_pitches DESC
LIMIT 10;
```

---

## Next Steps

1. **Create Tables:** Run `create_batter_pitcher_pitch_tables.sql`
2. **Test Collection:** `python run_all_pitch_collections.py --test`
3. **Full Collection:** `python run_all_pitch_collections.py`
4. **Verify Data:** Run verification queries
5. **Build Features:** Use pitch-level data in ML models

---

## Questions?

This collection fills the gap identified in the original review:
- ✓ Pitcher PBP data now available
- ✓ Pitch-level granularity (not just PA summaries)
- ✓ Complete 2021-2025 coverage
- ✓ Concurrent collection for speed

The data collected here provides the foundation for advanced pitcher analysis and ML modeling.
