# MILB Data Export Tools

This document describes the available scraped MILB data and tools to export it to CSV files.

## Available Data Tables

### 1. prospect_stats (24 columns)
**Season-level aggregated statistics**

Location: `apps/api/app/db/models.py`

**Columns:**
- `id`, `prospect_id`, `date_recorded`, `season`
- **Batting:** `games_played`, `at_bats`, `hits`, `home_runs`, `rbi`, `stolen_bases`, `walks`, `strikeouts`
- **Rate Stats:** `batting_avg`, `on_base_pct`, `slugging_pct`, `woba`, `wrc_plus`
- **Pitching:** `innings_pitched`, `earned_runs`, `era`, `whip`, `strikeouts_per_nine`, `walks_per_nine`
- **Metadata:** `created_at`, `updated_at`

---

### 2. milb_game_logs (99 columns)
**Complete game-level statistics from MLB Stats API**

Location: `apps/api/alembic/versions/017_add_comprehensive_milb_game_logs.py`

**Key Column Categories:**
- **Identifiers:** `id`, `prospect_id`, `mlb_player_id`, `season`, `game_pk`, `game_date`, `game_type`
- **Context:** `team_id`, `opponent_id`, `is_home`
- **Hitting Stats (36 fields):** Basic counting stats, plate discipline, baserunning, outs, rate stats
- **Pitching Stats (63 fields):** Games/innings, results allowed, outs recorded, rate stats
- **Metadata:** `data_source`, `created_at`, `updated_at`

**Full Schema Details:**
```
Core: id, prospect_id, mlb_player_id, season, game_pk, game_date, game_type, team_id, opponent_id, is_home

Hitting: games_played, at_bats, plate_appearances, runs, hits, doubles, triples, home_runs,
         rbi, total_bases, walks, intentional_walks, strikeouts, hit_by_pitch, stolen_bases,
         caught_stealing, fly_outs, ground_outs, air_outs, ground_into_double_play,
         ground_into_triple_play, sac_bunts, sac_flies, left_on_base, number_of_pitches,
         catchers_interference, batting_avg, obp, slg, ops, babip, stolen_base_percentage,
         ground_outs_to_airouts, at_bats_per_home_run

Pitching: games_started, games_pitched, complete_games, shutouts, games_finished, wins,
          losses, saves, save_opportunities, holds, blown_saves, innings_pitched, outs,
          batters_faced, number_of_pitches_pitched, strikes, hits_allowed, runs_allowed,
          earned_runs, home_runs_allowed, walks_allowed, intentional_walks_allowed,
          strikeouts_pitched, hit_batsmen, stolen_bases_allowed, caught_stealing_allowed,
          balks, wild_pitches, pickoffs, inherited_runners, inherited_runners_scored,
          fly_outs_pitched, ground_outs_pitched, air_outs_pitched, ground_into_double_play_pitched,
          total_bases_allowed, sac_bunts_allowed, sac_flies_allowed, catchers_interference_pitched,
          era, whip, avg_against, obp_against, slg_against, ops_against, win_percentage,
          strike_percentage, pitches_per_inning, strikeout_walk_ratio, strikeouts_per_9inn,
          walks_per_9inn, hits_per_9inn, runs_scored_per_9, home_runs_per_9,
          stolen_base_percentage_against, ground_outs_to_airouts_pitched
```

---

### 3. milb_batter_pitches (48 columns)
**Individual pitch-level data for batters**

Location: `apps/api/scripts/run_complete_mlb_collections.py`

**Key Column Categories:**
- **Context:** `mlb_batter_id`, `mlb_pitcher_id`, `game_pk`, `game_date`, `season`, `level`
- **At-Bat:** `at_bat_index`, `pitch_number`, `inning`, `half_inning`
- **Pitch Type:** `pitch_type`, `pitch_type_description`, `start_speed`, `end_speed`
- **Movement:** `pfx_x`, `pfx_z` (horizontal/vertical break)
- **Release:** `release_pos_x/y/z`, `release_extension`
- **Spin:** `spin_rate`, `spin_direction`
- **Location:** `plate_x`, `plate_z`, `zone`
- **Result:** `pitch_call`, `pitch_result`, `is_strike`, `balls`, `strikes`, `outs`
- **Swing:** `swing`, `contact`, `swing_and_miss`, `foul`
- **PA Result:** `is_final_pitch`, `pa_result`, `pa_result_description`
- **Batted Ball:** `launch_speed`, `launch_angle`, `total_distance`, `trajectory`, `hardness`, `hit_location`, `coord_x`, `coord_y`

**Full Schema:**
```sql
id, mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season, level,
at_bat_index, pitch_number, inning, half_inning,
pitch_type, pitch_type_description, start_speed, end_speed,
pfx_x, pfx_z, release_pos_x, release_pos_y, release_pos_z, release_extension,
spin_rate, spin_direction,
plate_x, plate_z, zone,
pitch_call, pitch_result, is_strike, balls, strikes, outs,
swing, contact, swing_and_miss, foul,
is_final_pitch, pa_result, pa_result_description,
launch_speed, launch_angle, total_distance, trajectory, hardness, hit_location, coord_x, coord_y,
created_at
```

**Unique Constraint:** `(mlb_batter_id, game_pk, at_bat_index, pitch_number)`

**Indexes:**
- `idx_batter_pitches_player` (mlb_batter_id)
- `idx_batter_pitches_season` (season)
- `idx_batter_pitches_game` (game_pk)

---

### 4. milb_pitcher_pitches (48 columns)
**Individual pitch-level data for pitchers**

Location: `apps/api/scripts/run_complete_mlb_collections.py`

**Schema:** Identical to `milb_batter_pitches` with `mlb_pitcher_id` as the primary player identifier instead of `mlb_batter_id`.

**Unique Constraint:** `(mlb_pitcher_id, game_pk, at_bat_index, pitch_number)`

**Indexes:**
- `idx_pitcher_pitches_player` (mlb_pitcher_id)
- `idx_pitcher_pitches_season` (season)
- `idx_pitcher_pitches_game` (game_pk)

---

## Export Scripts

Two export scripts have been created to handle different connection scenarios:

### 1. Async Export Script (Primary)
**File:** [apps/api/scripts/export_scraped_data_to_csv.py](apps/api/scripts/export_scraped_data_to_csv.py)

**Features:**
- Uses async SQLAlchemy for better performance
- Loads entire tables into memory (fast but memory-intensive)
- Best for smaller datasets or powerful machines

**Usage:**
```bash
# Using environment variables
python apps/api/scripts/export_scraped_data_to_csv.py

# With explicit database URL
python apps/api/scripts/export_scraped_data_to_csv.py \
  --database-url "postgresql+asyncpg://user:pass@host:port/dbname"

# With row limit (for testing)
python apps/api/scripts/export_scraped_data_to_csv.py \
  --database-url "postgresql+asyncpg://user:pass@host:port/dbname" \
  --limit 1000
```

---

### 2. Synchronous Export Script (Recommended for Large Datasets)
**File:** [apps/api/scripts/export_scraped_data_to_csv_sync.py](apps/api/scripts/export_scraped_data_to_csv_sync.py)

**Features:**
- Uses psycopg2 with server-side cursors
- Processes data in batches (10,000 rows at a time)
- Memory-efficient for large tables
- More stable network connection handling
- Progress indicators for long exports

**Usage:**
```bash
# Basic usage (database URL required)
python apps/api/scripts/export_scraped_data_to_csv_sync.py \
  --database-url "postgresql://user:pass@host:port/dbname"

# With row limit (for testing)
python apps/api/scripts/export_scraped_data_to_csv_sync.py \
  --database-url "postgresql://user:pass@host:port/dbname" \
  --limit 1000
```

**Example with Railway Database:**
```bash
python apps/api/scripts/export_scraped_data_to_csv_sync.py \
  --database-url "postgresql://postgres:PASSWORD@autorack.proxy.rlwy.net:24426/railway"
```

---

## Output

Both scripts create a `data_exports/` directory in the project root containing:

```
data_exports/
├── prospect_stats.csv
├── milb_game_logs.csv
├── milb_batter_pitches.csv
└── milb_pitcher_pitches.csv
```

---

## Expected Data Volumes

Based on the schema and typical MILB data collection:

| Table | Estimated Rows | Estimated Size | Notes |
|-------|---------------|----------------|-------|
| prospect_stats | 1K - 10K | 1-10 MB | One row per prospect per season |
| milb_game_logs | 10K - 100K | 10-100 MB | One row per player per game |
| milb_batter_pitches | 1M - 10M+ | 100 MB - 1 GB+ | One row per pitch seen |
| milb_pitcher_pitches | 1M - 10M+ | 100 MB - 1 GB+ | One row per pitch thrown |

**Note:** Pitch-level tables can be very large depending on collection scope.

---

## Troubleshooting

### Connection Issues

If you encounter connection errors:

1. **Verify Database Credentials:**
   ```bash
   # Test connection with psql
   psql "postgresql://user:pass@host:port/dbname"
   ```

2. **Check Network/Firewall:**
   - Ensure Railway database is not sleeping
   - Check if your IP is whitelisted (if required)
   - Verify port 24426 is accessible

3. **Use Synchronous Script:**
   - The sync script ([export_scraped_data_to_csv_sync.py](apps/api/scripts/export_scraped_data_to_csv_sync.py)) has better network stability

### Memory Issues

If the async script runs out of memory:

1. **Use the synchronous script** (batches data automatically)
2. **Or add --limit flag** to test with smaller datasets first
3. **Process one table at a time** by modifying the scripts `tables` list

### Empty Tables

If tables return no data:

1. Verify data collection has run successfully
2. Check migration status: `alembic current`
3. Query database directly to confirm data exists

---

## Data Schema Documentation

For complete schema details, see:
- **ORM Models:** [apps/api/app/db/models.py](apps/api/app/db/models.py)
- **Migrations:** [apps/api/alembic/versions/](apps/api/alembic/versions/)
- **Collection Scripts:** [apps/api/scripts/run_complete_mlb_collections.py](apps/api/scripts/run_complete_mlb_collections.py)

---

## Next Steps

Once exports complete successfully:

1. **Verify Data Integrity:**
   - Check row counts match database
   - Spot-check random rows for accuracy
   - Verify CSV encoding (UTF-8)

2. **Analyze Data:**
   - Use pandas, R, or Excel for analysis
   - Join tables using:
     - `prospect_id` (prospect_stats → milb_game_logs)
     - `mlb_player_id` (game_logs → pitches)
     - `game_pk` (game context)

3. **Example Analysis Queries:**
   ```python
   import pandas as pd

   # Load data
   game_logs = pd.read_csv('data_exports/milb_game_logs.csv')
   pitches = pd.read_csv('data_exports/milb_batter_pitches.csv')

   # Join pitch data with game context
   merged = pitches.merge(
       game_logs[['game_pk', 'mlb_player_id', 'season', 'level']],
       left_on=['game_pk', 'mlb_batter_id'],
       right_on=['game_pk', 'mlb_player_id']
   )

   # Analyze pitch types by level
   pitch_analysis = merged.groupby(['level', 'pitch_type']).size()
   ```

---

## Contact & Support

For issues or questions:
- Check this README first
- Review script output for specific error messages
- Verify database connectivity independently
- Ensure sufficient disk space for exports

---

**Last Updated:** 2025-11-06
